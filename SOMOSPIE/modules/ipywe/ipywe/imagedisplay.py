#Allows for Python 3-style division in Python 2.7
from __future__ import division

import ipywidgets as ipyw
from . import base
from traitlets import Unicode, Float, Integer, HasTraits, observe
import numpy as np
import sys


@ipyw.register('ipywe.ImageDisplay')
class ImageDisplay(base.DOMWidget):

    _view_name = Unicode("ImgDisplayView").tag(sync=True)
    _model_name = Unicode("ImgDisplayModel").tag(sync=True)

    _b64value = Unicode().tag(sync=True)
    _format = Unicode("png").tag(sync=True)
    _offXtop = Float().tag(sync=True)
    _offXbottom = Float().tag(sync=True)
    _offYtop = Float().tag(sync=True)
    _offYbottom = Float().tag(sync=True)
    _zoom_click = Integer(0).tag(sync=True)
    _reset_click = Integer(0).tag(sync=True)
    _xcoord_absolute = Integer(0).tag(sync=True)
    _ycoord_absolute = Integer(0).tag(sync=True)
    _nrows_currimg = Integer().tag(sync=True)
    _ncols_currimg = Integer().tag(sync=True)
    _extrarows = Integer(0).tag(sync=True)
    _extracols = Integer(0).tag(sync=True)
    _xcoord_max_roi = Integer().tag(sync=True)
    _ycoord_max_roi = Integer().tag(sync=True)

    height = Integer().tag(sync=True)
    width = Integer().tag(sync=True)

    
    def __init__(self, image, width, height, init_roi=None):
        self.width = width
        self.height = height
        self.curr_img = image
        self.arr = self.curr_img.data.copy().astype("float")
        self._img_min, self._img_max = int(np.min(self.arr)), int(np.max(self.arr))
        self._nrows, self._ncols = self.arr.shape
        self._nrows_currimg, self._ncols_currimg = self.arr.shape
        self._ycoord_max_roi, self._xcoord_max_roi = self.arr.shape
        self.curr_img_data = self.arr.copy()
        self.xbuff = 0
        self.ybuff = 0
        if init_roi != None:
            assert (type(init_roi) is list or type(init_roi) is tuple)
            self._offXtop = init_roi[0]*1./self._ncols_currimg * self.width
            self._offXbottom = init_roi[1]*1./self._ncols_currimg * self.width
            self._offYtop = init_roi[2]*1./self._nrows_currimg * self.height
            self._offYbottom = init_roi[3]*1./self._nrows_currimg * self.height
        self._b64value = self.createImg()
        super(ImageDisplay, self).__init__()
        return

    def createImg(self):
        if self._img_min >= self._img_max:
            self._img_max = self._img_min + abs(self._img_max - self._img_min) * 1e-5
        img = ((self.curr_img_data-self._img_min)/(self._img_max-self._img_min)*(2**8-1)).astype('uint8')
        size = np.max(img.shape)
        view_size = np.max((self.width, self.height))
        if size > view_size:
            downsample_ratio = 1.*view_size/size
            import scipy.misc
            img = scipy.misc.imresize(img, downsample_ratio)
        else:
            upsample_ratio = 1.*view_size/size
            import scipy.misc
            img = scipy.misc.imresize(img, upsample_ratio)
        """Chooses the correct string IO method based on 
               which version of Python is being used.
           Once Python 2.7 support ends, this can be replaced
               with just the content of the else statement."""
        if sys.version_info < (3, 0):
            from cStringIO import StringIO
            f = StringIO()
        else:
            from io import BytesIO
            f = BytesIO()
        import PIL.Image, base64
        PIL.Image.fromarray(img).save(f, self._format)
        imgb64v = base64.b64encode(f.getvalue())
        return imgb64v

    @observe("_zoom_click")
    def zoomImg(self, change):
        self.arr = self.curr_img.data.copy()
        left = int(self._offXtop/self.width * self._ncols_currimg)
        right = int(self._offXbottom/self.width*self._ncols_currimg)
        top = int(self._offYtop/self.height*self._nrows_currimg)
        bottom = int(self._offYbottom/self.height*self._nrows_currimg)
        select_width = right - left
        select_height = bottom - top
        self._xcoord_absolute += (left - self.xbuff)
        self._ycoord_absolute += (top - self.ybuff)
        if select_width == 0:
            select_width = 1
        if select_height == 0:
            select_height = 1
        self.arr = self.arr[self._ycoord_absolute:(self._ycoord_absolute + select_height),
                            self._xcoord_absolute:(self._xcoord_absolute + select_width)]
        self._nrows, self._ncols = self.arr.shape
        self.curr_img_data = self.arr.copy()
        if self._ncols > self._nrows:
            diff = self._ncols - self._nrows
            if diff % 2 == 0:
                addtop = diff // 2
                addbottom = diff // 2
            else:
                addtop = diff // 2 + 1
                addbottom = diff // 2
            self.xbuff = 0
            self.ybuff = addtop
            self._nrows_currimg = self._ncols
            self._ncols_currimg = self._ncols
            self._extrarows = diff
            self._extracols = 0
            extrarows_top = np.full((addtop, self._ncols), 1)
            extrarows_bottom = np.full((addbottom, self._ncols), 1)
            self.curr_img_data = np.vstack((extrarows_top, self.curr_img_data, extrarows_bottom))
        else:
            diff = self._nrows - self._ncols
            if diff % 2 == 0:
                addleft = diff // 2
                addright = diff // 2
            else:
                addleft = diff // 2 + 1
                addright = diff // 2
            self.xbuff = addleft
            self.ybuff = 0
            self._nrows_currimg = self._nrows
            self._ncols_currimg = self._nrows
            self._extrarows = 0
            self._extracols = diff
            extrarows_left = np.full((self._nrows, addleft), 1)
            extrarows_right = np.full((self._nrows, addright), 1)
            self.curr_img_data = np.hstack((extrarows_left, self.curr_img_data, extrarows_right))
        self._xcoord_max_roi = self._xcoord_absolute + self._ncols_currimg - self._extracols
        self._ycoord_max_roi = self._ycoord_absolute + self._nrows_currimg - self._extrarows
        self._b64value = self.createImg()
        return

    @observe("_reset_click")
    def resetImg(self, change):
        self.arr = self.curr_img.data.copy()
        self._nrows, self._ncols = self.arr.shape
        self._nrows_currimg, self._ncols_currimg = self.arr.shape
        self._ycoord_max_roi, self._xcoord_max_roi = self.arr.shape
        self.xbuff = 0
        self.ybuff = 0
        self._xcoord_absolute = 0
        self._ycoord_absolute = 0
        self._extrarows = 0
        self._extracols = 0
        self.curr_img_data = self.arr.copy()
        self._b64value = self.createImg()
        return
