#Takes a dictionary of items in form {key: list, key: list} and a list or tuple of widgets.
#Returns an Accordion widget with form:
# "key"
# "listentry[i]", widget1, widget2 . . .
# "listentry[i+1]", widget1, widget2 . . .
def dlist(items, widgs):
    import ipywidgets as widgets
    from collections import OrderedDict
    import os

    keys = items.keys()
    rdict = items
    typeboxes = {}
    regboxes = widgets.Accordion()
    for step, i in enumerate(keys):
        typeboxes[i] = widgets.VBox()
        for j in rdict[i]:
            boxpop = [widgets.Label(str(j))] + [widg() for widg in widgs]
            typeboxes[i].children += (widgets.HBox(boxpop),)
        regboxes.children += (typeboxes[i],)
        regboxes.set_title(step, i)
    return regboxes
