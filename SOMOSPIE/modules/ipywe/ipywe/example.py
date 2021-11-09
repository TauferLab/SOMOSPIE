import ipywidgets as widgets
from traitlets import Unicode

# devel = 1
devel = 0


@widgets.register('hello.Hello')
class HelloWorld(widgets.DOMWidget):
    """"""
    _view_name = Unicode('HelloView').tag(sync=True)
    _model_name = Unicode('HelloModel').tag(sync=True)
    if devel:
        _view_module = Unicode('example').tag(sync=True)
        _model_module = Unicode('example').tag(sync=True)
    else:
        _view_module = Unicode('ipywe').tag(sync=True)
        _model_module = Unicode('ipywe').tag(sync=True)
    _view_module_version = Unicode('^0.1.0').tag(sync=True)
    _model_module_version = Unicode('^0.1.0').tag(sync=True)
    value = Unicode('Hello World!').tag(sync=True)


if devel:
    from IPython.display import display, HTML

    def get_js():
        import os
        js = open(os.path.join(os.path.dirname(__file__),
                               "..", "js", "src", "example.js")).read()
        return js.decode("UTF-8")

    def run_js():
        js = get_js()
        display(HTML("<script>"+js+"</script>"))
        return
    run_js()
