import ipywidgets
from traitlets import Unicode

from ._version import __frontend_version__

class DOMWidget(ipywidgets.DOMWidget):

    _view_module = Unicode('ipywe').tag(sync=True)
    _model_module = Unicode('ipywe').tag(sync=True)
    _view_module_version = Unicode(__frontend_version__).tag(sync=True)
    _model_module_version = Unicode(__frontend_version__).tag(sync=True)
