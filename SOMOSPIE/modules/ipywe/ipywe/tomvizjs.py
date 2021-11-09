#Allows Python 3-style division in Python 2.7
from __future__ import division

import ipywidgets as ipyw
from . import base
from traitlets import Unicode, Integer, Float, Tuple, HasTraits, observe
import numpy as np
import sys


@ipyw.register('ipywe.TomvizJs')
class TomvizJs(base.DOMWidget):

    _view_name = Unicode("TomvizJsView").tag(sync=True)
    _model_name = Unicode("TomvizJsModel").tag(sync=True)

    url = Unicode("").tag(sync=True)

    def __init__(self, url=None):
        super(TomvizJs, self).__init__()
        self.url =  url
