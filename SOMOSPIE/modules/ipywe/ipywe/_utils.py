# coding: utf-8

import ipywidgets as ipyw
from IPython.display import display, HTML, clear_output

def js_alert(m):
    js = "<script>alert('%s');</script>" % m
    display(HTML(js))
    return

layout_reserved_keys = ['keys', 'comm']
def cloneLayout(l):
    c = ipyw.Layout()
    for k in l.trait_names():
        if k.startswith('_'): continue
        if k in layout_reserved_keys: continue
        v = getattr(l, k)
        setattr(c, k, v)
    return c

def updateLayout(this, other):
    'update "this" layout with all non-trivial values of "other" layout'
    for n in other.trait_names():
        if n.startswith('_'): continue
        if n in layout_reserved_keys: continue
        v = getattr(other, n)
        if v is None: continue
        setattr(this, n, v)
    return this

def close(w):
    "recursively close a widget"
    recursive_op(w, lambda x: x.close())
    return

def disable(w):
    "recursively disable a widget"
    def _(w):
        w.disabled = True
    recursive_op(w, _)
    return

def enable(w):
    "recursively enable a widget"
    def _(w):
        w.disabled = False
    recursive_op(w, _)
    return

def recursive_op(w, single_op):
    if hasattr(w, 'children'):
        for c in w.children:
            recursive_op(c, single_op)
            continue
    single_op(w)
    return

