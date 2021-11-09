#Allows Python 3-style division in Python 2.7
from __future__ import division

import ipywidgets as ipyw
from . import base
from traitlets import Unicode, Integer, Float, Tuple, HasTraits, observe
import numpy as np
import sys


@ipyw.register('ipywe.ImageSlider')
class ImageSlider(base.DOMWidget):
    """The backend python class for the custom ImageSlider widget.

    This class declares and initializes all of the data that is synced
        between the front- and back-ends of the widget code.
        It also provides the majority of the calculation-based code
        that runs the ImageSlider widget."""

    _view_name = Unicode("ImgSliderView").tag(sync=True)
    _model_name = Unicode("ImgSliderModel").tag(sync=True)

    # public attrs
    height = Integer().tag(sync=True)
    width = Integer().tag(sync=True)

    # index of current image in display
    _img_index = Integer(0).tag(sync=True)
    _N_images = Integer().tag(sync=True)

    _b64value = Unicode().tag(sync=True)
    _err = Unicode().tag(sync=True)
    _format = Unicode("png").tag(sync=True)
    _series_min = Float().tag(sync=True)
    _series_max = Float().tag(sync=True)
    _img_min = Float().tag(sync=True)
    _img_max = Float().tag(sync=True)
    _nrows = Integer().tag(sync=True)
    _ncols = Integer().tag(sync=True)
    _offsetX = Integer().tag(sync=True)
    _offsetY = Integer().tag(sync=True)
    _pix_val = Float().tag(sync=True)


    # These variables were added to support zoom functionality
    _ROI = Tuple((0,0,0,0), sync=True) # Xtop, Ytop, Xbottom, Ybottom
    _extrarows = Integer(0).tag(sync=True)
    _extracols = Integer(0).tag(sync=True)
    _nrows_currimg = Integer().tag(sync=True)
    _ncols_currimg = Integer().tag(sync=True)
    _xcoord_absolute = Integer(0).tag(sync=True)
    _ycoord_absolute = Integer(0).tag(sync=True)
    _vslide_reset = Integer(0).tag(sync=True)
    _xcoord_max_roi = Integer().tag(sync=True)
    _ycoord_max_roi = Integer().tag(sync=True)

    def __init__(self, image_series, width, height):
        """Constructor method for setting the necessary member variables
           that are synced between the front- and back-ends.

        Creates the following non-synced member variables:

            *image_series: the list containing the original series of image objects
                 passed by the image_series parameter.
                 This variable is not changed in the code to preserve the original data.
            *current_img: the image object or corresponding numpy array of data
                 that is currently being displayed
            *arr: a numpy array containing the data for the current image
                 that does not contain buffer rows/columns
            *curr_img_data: a numpy array containing the data for the current image,
                 including buffer rows/columns
            *xbuff and ybuff: the number of buffer rows in the previously displayed image

        Parameters:

            *image_series: a list of ImageFile objects (see
                 https://github.com/ornlneutronimaging/iMars3D/blob/master/python/imars3d/ImageFile.py
                 for more details).
                 This list is used to give the widget access
                 to the images that are to be viewed.
            *width: an integer that is used to set the width of the image and UI elements.
            *height: an integer that is used to set the height of the image and UI elements."""

        super(ImageSlider, self).__init__()
        assert len(image_series), "Image series cannot be empty"
        self.image_series = list(image_series)
        self.width = width
        self.height = height
        self._N_images = len(self.image_series)
        self.current_img = self.image_series[self._img_index]
        # image data array. need it to obtain the value at mouse p
        self.arr = self.current_img.data.copy().astype("float") 
        # image data in the <img> tag. this may contains buffers at zoom, or may be altered due to 
        # intensity range limit
        self.curr_img_data = self.arr.copy() 
        self._nrows, self._ncols = self.arr.shape
        self._nrows_currimg, self._ncols_currimg = self.arr.shape
        self._ycoord_max_roi, self._xcoord_max_roi = self.arr.shape
        self.ybuff = 0
        self.xbuff = 0
        self._zoom = False
        self.get_series_minmax()
        self.update_image_div_data(None)
        return

    def get_series_minmax(self, sample_size=10):
        """Determines the absolute minimum and maximum image values of either
               all the images in self.image_series or of
               'sample_size' random images from self.image_series

        Parameters:
            *sample_size: the maximum number of images to use
                 in determining _img_min and _img_max.
                 By default, its value is 10."""

        img_series = list(self.image_series)
        N = len(img_series)
        if N < sample_size:
            data = [img.data for img in img_series]
        else:
            indexes = np.random.choice(N, sample_size, replace=False)
            data = [img_series[i].data for i in indexes]
        self._series_min = self._img_min = float(np.min(data))
        self._series_max = self._img_max = float(np.max(data))
        return

    #This function is called when the values of _offsetX and/or _offsetY change
    @observe("_offsetX", "_offsetY")
    def get_val(self, change):
        """Tries to calculate the value of the image at the mouse position
               and store the result in the member variable _pix_val

        If an error occurs, this method calls the handle_error method
            and stores the result in the member variable _err."""

        try:
            col = int(self._offsetX/self.width * self._ncols_currimg)
            row = int(self._offsetY/self.height * self._nrows_currimg)
            if self._extrarows != 0:
                row = row - self.ybuff
            if self._extracols != 0:
                col = col - self.xbuff
            if col >= self.arr.shape[1]:
                col = self.arr.shape[1]-1
            if row >= self.arr.shape[0]:
                row = self.arr.shape[0]-1
            self._pix_val = float(self.arr[row, col])
            self._err = ""
        except Exception:
            self._pix_val = float(np.nan)
            self._err = self.handle_error()
            return

    def getimg_bytes(self):
        """Encodes the data for the currently viewed image into Base64.

        If _img_min and/or _img_max have been changed from their initial values,
            this function will also change the image data to account for
            this change before encoding the data into Base64."""
        # force the intensity range limitation to be positive
        if self._img_min >= self._img_max:
            self._img_max = self._img_min + (self._series_max - self._series_min) * 1e-5
        # apply intensity range
        self.curr_img_data[self.curr_img_data < self._img_min] = self._img_min
        self.curr_img_data[self.curr_img_data > self._img_max] = self._img_max
        img = ((self.curr_img_data-self._img_min)/(self._img_max-self._img_min)*(2**8-1)).astype('uint8')
        size = np.max(img.shape)
        view_size = np.max((self.width, self.height))
        # resample if necessary
        resample_ratio = view_size/size
        if resample_ratio != 1.:
            import scipy.misc
            img = scipy.misc.imresize(img, resample_ratio)
        """Allows the correct string IO module to be used
               based on the version of Python.
           Once support for Python 2.7 ends, this if-else statement
               can be replaced by just the contents of the else statement."""
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

    def handle_error(self):
        """Creates and returns a custom error message if an error occurs in the get_val method."""

        cla, exc, tb = sys.exc_info()
        ex_name = cla.__name__
        try:
            ex_args = exc.__dict__["args"]
        except KeyError:
            ex_args = ("No args",)
        ex_mess = str(ex_name)
        for arg in ex_args:
            ex_mess = ex_mess + str(arg)
        return(ex_mess)

    #This function is called when _img_index
    @observe("_img_index")
    def update_image_index(self, change):
        """
        change the current_img member variable to the new desired image
        and then update the image div
        """
        self.current_img = self.image_series[self._img_index]
        self.update_image_div_data(change)
        return

    @observe("_img_min", "_img_max")
    def update_image_div_data(self, change):
        """update the image div data

        This function is called whenever the image div needs to be updated.
        It could be triggered directly by changes to _img_min and _img_max, but also
        by function calls from handlers of other events such as image-index-change,
        and ROI-change.

        If the zoom is activated (see flag _zoom)
            this function will call the update_image_div_data_with_zoom function to zoom into
            the image and obtain the Base64 encoding.

        Otherwise, this function calls the getimg_bytes method
            to obtain the new Base64 encoding (of either the new or old image)
            and stores this encoding in _b64value."""

        self.arr = self.current_img.data.copy().astype("float")
        self.curr_img_data = self.arr.copy()
        if self._zoom:
            self.update_image_div_data_with_zoom()
            return
        self._nrows, self._ncols = self.arr.shape
        self._ycoord_max_roi, self._xcoord_max_roi = self.arr.shape
        self._nrows_currimg, self._ncols_currimg = self.arr.shape
        self._b64value = self.getimg_bytes()
        return

    #This function is called when _ROI changes.
    @observe("_ROI")
    def zoom_image(self, change):
        """Sets all values necessary for zooming into a Region of Interest
        and then calls the update_image_div_data function."""
        Xtop, Ytop, Xbottom, Ybottom = self._ROI
        if Xtop < 0: # invalid ROI means reset
            self._zoom = False
            return self.reset_image()
        self._zoom = True
        self.left = int(Xtop/self.width * self._ncols_currimg)
        self.right = int(Xbottom/self.width*self._ncols_currimg)
        self.top = int(Ytop/self.height*self._nrows_currimg)
        self.bottom = int(Ybottom/self.height*self._nrows_currimg)
        self._xcoord_absolute += (self.left - self.xbuff)
        self._ycoord_absolute += (self.top - self.ybuff)
        self.update_image_div_data(change)
        return

    def reset_image(self):
        """Resets all variables that are involved in zooming to their default values.

        After resetting, the update_image_div_data function is called."""
        self._extrarows = 0
        self._extracols = 0
        self.xbuff = 0
        self.ybuff = 0
        self._xcoord_absolute = 0
        self._ycoord_absolute = 0
        self.get_series_minmax()
        self._vslide_reset += 1
        self.update_image_div_data(None)
        return

    def update_image_div_data_with_zoom(self):
        """The function that controlls zooming on a single image.

        It splices the image data based on the left, right, bottom,
            and top variables calculated in the zoom_image function.

        The function then copies the data in ROI and adds
            buffer rows/columns to the copy to insure the data
            used to create the image is a square numpy array.

        Then, the number of extra rows and/or columns is calculated.

        Finally, the zoomed image data is converted to
            a displayable image by calling the getimg_bytes function."""

        select_width = self.right - self.left
        select_height = self.bottom - self.top
        if select_width == 0: select_width = 1
        if select_height == 0: select_height = 1
        self.arr = self.arr[self._ycoord_absolute:(self._ycoord_absolute + select_height),
                            self._xcoord_absolute:(self._xcoord_absolute + select_width)]
        self._nrows, self._ncols = self.arr.shape
        self.curr_img_data = self.arr.copy()
        # calculate paddings
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
        self._b64value = self.getimg_bytes()
        return

