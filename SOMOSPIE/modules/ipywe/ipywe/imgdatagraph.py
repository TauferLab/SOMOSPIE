#Allows Python 3-style division in Python 2.7
from __future__ import division

import numpy as np
import ipywidgets as ipyw
from . import base
import sys
from traitlets import Unicode, Integer, Float, HasTraits, observe
import matplotlib.pyplot as plt


@ipyw.register('ipywe.ImageDataGraph')
class ImageDataGraph(base.DOMWidget):
    """The backend python class for the custom ImageDataGraph widget.

    This class declares and initializes all of the data that is synced
        between the front- and back-ends of the widget code.
    It also provides the majority of the mathematical calculations that run this widget."""

    _view_name = Unicode("ImgDataGraphView").tag(sync=True)
    _model_name = Unicode("ImgDataGraphModel").tag(sync=True)

    _b64value = Unicode().tag(sync=True)
    _graphb64 = Unicode().tag(sync=True)
    _format = Unicode().tag(sync=True)
    _nrows = Integer().tag(sync=True)
    _ncols = Integer().tag(sync=True)
    _offsetX1 = Float().tag(sync=True)
    _offsetY1 = Float().tag(sync=True)
    _offsetX2 = Float().tag(sync=True)
    _offsetY2 = Float().tag(sync=True)
    _img_min = Float().tag(sync=True)
    _img_max = Float().tag(sync=True)
    _graph_click = Integer(0).tag(sync=True)
    _linepix_width = Float(1.0).tag(sync=True)
    _num_bins = Integer(1).tag(sync=True)

    width = Integer().tag(sync=True)
    height = Integer().tag(sync=True)

    def __init__(self, image, width, height, uformat="png"):
        """Constructor method for setting the necessary
               member variables (including synced ones).
               This function also calls the getimg_bytes() method
               to create provide the image data to create the widget.

        Parameters:

        * image: an ImageFile object (see
              https://github.com/ornlneutronimaging/iMars3D/blob/master/python/imars3d/ImageFile.py
              for more details) that stores the data
              for the image to be used in this widget.
        * width: an integer that is used to set the width of the image and UI elements.
        * height: an integer that is used to set the height of the image and UI elements.
        * uformat: a string indicating the type of image
              that the displayed image and graph will be.
              By default, this is set to "png"."""

        self.img = image
        self.img_data = image.data.copy()
        self.width = width
        self.height = height
        self._format = uformat
        self._nrows, self._ncols = self.img_data.shape
        self._img_min, self._img_max = int(np.min(self.img_data)), int(np.max(self.img_data))
        self._b64value = self.getimg_bytes()
        super(ImageDataGraph, self).__init__()
        return

    def getimg_bytes(self):
        """Encodes the image's data into Base64."""

        img = ((self.img_data-self._img_min)/(self._img_max-self._img_min)*(2**8-1)).astype("uint8")
        size = np.max(img.shape)
        view_size = np.max((self.width, self.height))
        if size > view_size:
            downsample_ratio = view_size/size
            import scipy.misc
            img = scipy.misc.imresize(img, downsample_ratio)
        else:
            upsample_ratio = view_size/size
            import scipy.misc
            img = scipy.misc.imresize(img, upsample_ratio)
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

    #This function is called when the value of _graph_click changes
    @observe("_graph_click")
    def graph_data(self, change):
        """Determines whether the graph calculations should
               include width or not and calls the appropriate function."""

        if self._linepix_width == 1:
            self._graphb64 = self.nowidth_graph()
        else:
            self._graphb64 = self.width_graph()
        return

    def nowidth_graph(self):
        """Collects the data for a line with no width.
               Then, creates a matplotlib graph of the data,
               and encodes the graph into Base64 for the JavaScript code to display."""

        p1x_abs = self._offsetX1/self.width * self._ncols
        p1y_abs = self._offsetY1/self.height * self._nrows
        p2x_abs = self._offsetX2/self.width * self._ncols
        p2y_abs = self._offsetY2/self.height * self._nrows
        if p1x_abs > p2x_abs:
            tempx = p2x_abs
            tempy = p2y_abs
            p2x_abs = p1x_abs
            p2y_abs = p1y_abs
            p1x_abs = tempx
            p1y_abs = tempy
        xcoords = []
        ycoords = []
        dists = []
        vals = []
        curr_x_abs = p1x_abs
        curr_y_abs = p1y_abs
        curr_x = int(curr_x_abs)
        curr_y = int(curr_y_abs)
        xcoords.append(curr_x)
        ycoords.append(curr_y)
        vals.append(self.img_data[curr_y, curr_x])
        if p2y_abs == p1y_abs and p2x_abs != p1x_abs:
            while curr_x_abs < p2x_abs:
                curr_x_abs += 1
                curr_x = int(curr_x_abs)
                curr_y = int(curr_y_abs)
                xcoords.append(curr_x)
                ycoords.append(curr_y)
                vals.append(self.img_data[curr_y, curr_x])
        elif p2x_abs == p1x_abs and p2y_abs != p1y_abs:
            while curr_y_abs < p2y_abs:
                curr_y_abs += 1
                curr_x = int(curr_x_abs)
                curr_y = int(curr_y_abs)
                xcoords.append(curr_x)
                ycoords.append(curr_y)
                vals.append(self.img_data[curr_y, curr_x])
        else:
            while curr_x_abs < p2x_abs:
                slope = (p2y_abs - p1y_abs) / (p2x_abs - p1x_abs)
                curr_x_abs += 1
                curr_y_abs += slope
                curr_x = int(curr_x_abs)
                curr_y = int(curr_y_abs)
                if curr_x_abs < p2x_abs:
                    xcoords.append(curr_x)
                    ycoords.append(curr_y)
                    vals.append(self.img_data[curr_y, curr_x])
        curr_x = int(p2x_abs)
        curr_y = int(p2y_abs)
        xcoords.append(curr_x)
        ycoords.append(curr_y)
        vals.append(self.img_data[curr_x, curr_y])
        for x, y in np.nditer([xcoords, ycoords]):
            dist = np.sqrt(((x - xcoords[0])**2 + (y - ycoords[0])**2))
            dists.append(dist)
        plt.plot(dists, vals)
        plt.xlim(np.min(dists) * 0.75, np.max(dists))
        plt.ylim(np.min(vals) * 0.75, np.max(vals) * 1.25)
        plt.xlabel("Distance from Initial Point")
        plt.ylabel("Value")
        graph = plt.gcf()
        if sys.version_info < (3, 0):
            from StringIO import StringIO
            graphdata = StringIO()
        else:
            from io import BytesIO
            graphdata = BytesIO()
        graph.savefig(graphdata, format=self._format)
        graphdata.seek(0)
        import base64
        gb64v = base64.b64encode(graphdata.read())
        plt.clf()
        return gb64v

    def width_graph(self):
        """Creates the graph for a line with width.
               First, it calculates the endpoints of the drawn line.
               Then, depending on whether the line is horizontal,
               vertical, or diagonal, it calls the corresponding function
               to get the data needed for graphing. Finally, it creates
               the matplotlib graph and encodes it into Base64."""

        p1x_abs = self._offsetX1/self.width * self._ncols
        p1y_abs = self._offsetY1/self.height * self._nrows
        p2x_abs = self._offsetX2/self.width * self._ncols
        p2y_abs = self._offsetY2/self.height * self._nrows
        dists = []
        vals = []
        if p1y_abs == p2y_abs and p1x_abs != p2x_abs:
            dists, vals, bar_width = self.get_data_horizontal(p1x_abs, p1y_abs, p2x_abs)
        elif p1y_abs != p2y_abs and p1x_abs == p2x_abs:
            dists, vals, bar_width = self.get_data_vertical(p1x_abs, p1y_abs, p2y_abs)
        else:
            dists, vals, bar_width = self.get_data_diagonal(p1x_abs, p1y_abs, p2x_abs, p2y_abs)
        plt.bar(dists, vals, width=bar_width)
        plt.xlabel("Distance from Initial Point")
        plt.ylabel("Value")
        graph = plt.gcf()
        if sys.version_info < (3, 0):
            from StringIO import StringIO
            graphdata = StringIO()
        else:
            from io import BytesIO
            graphdata = BytesIO()
        graph.savefig(graphdata, format=self._format)
        graphdata.seek(0)
        import base64
        gb64v = base64.b64encode(graphdata.read())
        plt.clf()
        return gb64v

    def get_data_horizontal(self, x_init, y_init, x_fin):
        """Calculates the graphing data for a horizontal line with width.

        Parameters:

        * x_init: a float containing the exact mathematical
              x coordinate of the first point of the line.
        * y_init: a float containing the exact mathematical
              y coordinate of the first point of the line.
        * x_fin: a float containing the exact mathematical
              x coordinate of the last point of the line."""

        vals = []
        x0 = x_init
        x1 = x_fin
        if x0 > x1:
            tempx = x1
            x1 = x0
            x0 = tempx
        wid = self._linepix_width//self.height * self._nrows
        top = y_init - wid//2
        if int(top) < 0:
            top = 0
        bottom = y_init + wid//2 + 1
        if int(bottom) > self._nrows - 1:
            bottom = self._nrows - 1
        max_dist = np.sqrt((x1 - x0)**2)
        bin_step = max_dist / self._num_bins
        bins = [0]
        curr_bin_max = 0
        for i in range(self._num_bins):
            curr_bin_max += bin_step
            bins.append(curr_bin_max)
        intensities = np.zeros(len(bins))
        num_binvals = np.zeros(len(bins))
        Y, X = np.mgrid[top:bottom, x0:(x1+1)]
        for x, y in np.nditer([X, Y]):
            for b in bins:
                ind = bins.index(b)
                if ind < len(bins) - 1:
                    if x >= b + x0 and x < bins[ind+1] + x0:
                        intensities[ind] = intensities[ind] + self.img_data[int(y), int(x)]
                        num_binvals[ind] = num_binvals[ind] + 1
                        break
        for val, num in np.nditer([intensities, num_binvals]):
            if num == 0:
                vals.append(0)
            else:
                vals.append(val/num)
        return bins, vals, bin_step

    def get_data_vertical(self, x_init, y_init, y_fin):
        """Calculates the graphing data for a vertical line with width.

        Parameters:

        * x_init: a float containing the exact mathematical
              x coordinate of the first point of the line.
        * y_init: a float containing the exact mathematical
              y coordinate of the first point of the line.
        * y_fin: a float containing the exact mathematical
              y coordinate of the last point of the line."""

        vals = []
        y0 = y_init
        y1 = y_fin
        if y0 > y1:
            tempy = y1
            y1 = y0
            y0 = tempy
        wid = self._linepix_width//self.width * self._ncols
        left = x_init - wid//2
        if int(left) < 0:
            left = 0
        right = x_init + wid//2 + 1
        if int(right) > self._ncols - 1:
            right = self._ncols - 1
        max_dist = np.sqrt((y1 - y0)**2)
        bin_step = max_dist / self._num_bins
        bins = [0]
        curr_bin_max = 0
        for i in range(self._num_bins):
            curr_bin_max += bin_step
            bins.append(curr_bin_max)
        intensities = np.zeros(len(bins))
        num_binvals = np.zeros(len(bins))
        Y, X = np.mgrid[y0:(y1+1), left:right]
        for x, y in np.nditer([X, Y]):
            for b in bins:
                ind = bins.index(b)
                if ind < len(bins) - 1:
                    if y >= b + y0 and y < bins[ind+1] + y0:
                        intensities[ind] = intensities[ind] + self.img_data[int(y), int(x)]
                        num_binvals[ind] = num_binvals[ind] + 1
                        break
        for val, num in np.nditer([intensities, num_binvals]):
            if num == 0:
                vals.append(0)
            else:
                vals.append(val/num)
        return bins, vals, bin_step

    def get_data_diagonal(self, x_init, y_init, x_fin, y_fin):
        """Calculates the graphing data for a vertical line with width.

        Parameters:

        * x_init: a float containing the exact mathematical
              x coordinate of the first point of the line.
        * y_init: a float containing the exact mathematical
              y coordinate of the first point of the line.
        * x_fin: a float containing the exact mathematical
              x coordinate of the last point of the line.
        * y_fin: a float containing the exact mathematical
              y coordinate of the last point of the line."""

        bins = []
        vals = []
        x0 = x_init
        x1 = x_fin
        y0 = y_init
        y1 = y_fin
        if x0 > x1:
            tempx = x1
            tempy = y1
            x1 = x0
            y1 = y0
            x0 = tempx
            y0 = tempy
        slope = (y1 - y0) / (x1 - x0)
        angle = np.arctan(slope)
        wid_x = abs((self._linepix_width * np.cos(angle))/self.width * self._ncols)
        wid_y = abs((self._linepix_width * np.sin(angle))/self.height * self._nrows)
        wid = np.sqrt((wid_x)**2 + (wid_y)**2)
        left = x0 - (wid_x // 2)
        right = x1 + (wid_x // 2) + 1
        if slope > 0:
            bottom = y0 - (wid_y // 2)
            top = y1 + (wid_y // 2) + 1
        else:
            bottom = y1 - (wid_y // 2)
            top = y0 + (wid_y // 2)
        if int(bottom) < 0:
            bottom = 0
        if int(top) > self._nrows - 1:
            top = self._nrows - 1
        if int(left) < 0:
            left = 0
        if int(right) > self._ncols - 1:
            right = self._ncols - 1
        Y, X = np.mgrid[bottom:top, left:right]
        h_x = X - x0
        h_y = Y - y0
        norm_x = (y0 - y1) / np.sqrt((y0 - y1)**2 + (x1 - x0)**2)
        norm_y = (x1 - x0) / np.sqrt((y0 - y1)**2 + (x1 - x0)**2)
        e_x = (x1 - x0) / np.sqrt((x1 - x0)**2 + (y1 - y0)**2)
        e_y = (y1 - y0) / np.sqrt((x1 - x0)**2 + (y1 - y0)**2)
        dist = h_x*norm_x + h_y*norm_y
        pos = h_x*e_x + h_y*e_y
        max_dist = np.sqrt((x1 - x0)**2 + (y1 - y0)**2)
        bin_step = max_dist / self._num_bins
        curr_bin_max = 0
        bin_borders = [0]
        for i in range(self._num_bins):
            curr_bin_max += bin_step
            bin_borders.append(curr_bin_max)
        intensities = np.zeros(len(bin_borders))
        num_binvals = np.zeros(len(bin_borders))
        for x, y, d, p in np.nditer([X, Y, dist, pos]):
            if d <= wid / 2:
                if p < 0 or p > max_dist:
                    continue
                else:
                    for b in bin_borders:
                        ind = bin_borders.index(b)
                        if ind < len(bin_borders) - 1:
                            if p >= b and p < bin_borders[ind + 1]:
                                intensities[ind] = intensities[ind] + self.img_data[int(y), int(x)]
                                num_binvals[ind] = num_binvals[ind] + 1
                                break
        for i, n in np.nditer([intensities, num_binvals]):
            ind = np.where(intensities == i)
            if n == 0:
                vals.append(0)
            else:
                vals.append(i/n)
        bins = bin_borders
        return bins, vals, bin_step
