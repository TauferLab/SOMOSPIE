def dlist():
    import ipywidgets as widgets
    from collections import OrderedDict
    import os

    regionlist = ["NEON", "CEC", "BOX", "STATE"]
    rdict = { "NEON": [1, 2, 3], "CEC": [1, 2, 3], "BOX": [1, 2, 3], "STATE": [1, 2, 3]}
    typeboxes = {}
    regboxes = widgets.Accordion()
    for step, i in enumerate(regionlist):
        typeboxes[i] = widgets.VBox()
        for j in rdict[i]:
            boxpop = (widgets.Label(str(j)), widgets.Checkbox())
            typeboxes[i].children += (widgets.HBox(boxpop),)
        regboxes.children += (typeboxes[i],)

    return regboxes

    


