#!/bin/bash
#This script runs the code necessary to update the development install after changes have been made to Javascript code. This file must be run to see the changes in a test Jupyter notebook.

pip install -e . && \
  jupyter nbextension enable --py --sys-prefix widgetsnbextension && \
  jupyter nbextension install --py --symlink --sys-prefix ipywe && \
  jupyter nbextension enable --py --sys-prefix ipywe
