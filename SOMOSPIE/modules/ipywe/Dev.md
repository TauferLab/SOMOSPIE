## New widget

To develop a new widget, add a py module to ipywe/ and a js module to js/src/, and add a line to js/src/loadwidgets.js.

Run

    $ python setup.py build

to check for errors (especially in js code).

## Dev installation

For a development installation (requires npm),

    $ git clone https://github.com/scikit-beam/ipywe.git
    $ cd ipywe
    $ pip install -e .
    $ jupyter nbextension install --py --symlink --sys-prefix ipywe
    $ jupyter nbextension enable --py --sys-prefix ipywe

## Updating JavaScript Code in a Dev Install

After making a change to a widget's Javascript code (must be in the ipywe directory),

    $ chmod -x dev_js_update.sh
    $ ./dev_js_update.sh

Note that the Jupyter server must be restarted after running these commands.


## at conda-forge

* [feedstock](https://github.com/conda-forge/ipywe-feedstock)
