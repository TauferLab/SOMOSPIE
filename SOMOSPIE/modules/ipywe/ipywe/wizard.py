# coding: utf-8


import traitlets
import ipywidgets as ipyw
from IPython.display import display, HTML, clear_output
from ._utils import js_alert


class Context:
    pass


class Step(traitlets.HasTraits):

    layout = ipyw.Layout(border="1px lightgray solid",
                         margin='5px', padding='15px')
    button_layout = ipyw.Layout(margin='10px 5px 5px 5px')

    def __init__(self, context, previous_step=None):
        super(Step, self).__init__()
        self.context = context
        self.previous_step = previous_step
        self.next_step = None
        self.panel = None
        self._ondisplay = False
        return

    def createPanel(self):
        body = self.createBody()
        navigation = self.createNavigation()
        panel = ipyw.VBox(children=[body, navigation])
        return panel

    def createBody(self):
        raise NotImplementedError

    def createNavigation(self):
        previous_step = self.previous_step
        buttons = []
        if previous_step:
            PREVIOUS = ipyw.Button(description='PREVIOUS')
            PREVIOUS.on_click(self.handle_previous_button_click)
            buttons.append(PREVIOUS)
        #
        NEXT = ipyw.Button(description='NEXT')
        NEXT.on_click(self.handle_next_button_click)
        buttons.append(NEXT)
        return ipyw.HBox(children=buttons)

    def show(self):
        if self.panel is None:
            self.panel = self.createPanel()
        if not self._ondisplay:
            display(self.panel)
            self._ondisplay = True
        self.panel.layout.display = 'block'

    def remove(self):
        self.panel.layout.display = 'none'

    def handle_next_button_click(self, s):
        if not self.validate():
            return
        self.remove()
        self.nextStep()

    def handle_previous_button_click(self, s):
        self.remove()
        self.previousStep()

    def previousStep(self):
        step = self.previous_step
        step.show()

    def validate(self):
        raise NotImplementedError

    def nextStep(self):
        if self.next_step is None:
            self.next_step = next_step = self.createNextStep()
        else:
            next_step = self.next_step
        # no next step. done
        if next_step is None: return
        # has next step. make sure it knows about this step
        next_step.previous_step = self
        next_step.show()
        return

    def createNextStep(self):
        raise NotImplementedError


