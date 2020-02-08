# Remove this if calling from Jupyter Notebook
#from matplotlib import use as mpluse
#mpluse('Agg')
# The above didn't work, but this does: (https://stackoverflow.com/a/37605654)
# $ echo "backend: Agg" > ~/.config/matplotlib/matplotlibrc

import pathlib
from os import listdir
from __utils import *
import pandas as pd
import somosplot as splot
from matplotlib import pyplot as plt
plt.switch_backend('agg')

# This is a wrapper script for visualization of predictions.
#
#        Given a selected regional folder with a model subfolder, can...
#        ... generate heatmap and histogram .png files for every model
#
#      Arguments:
#        IN     a folder with csv files
#        OUT    a folder location for output
#        pl     boolean argument: 1 for plots, 0 for not
#        hi     boolean argument: 1 for histograms, 0 for not

def visualize(IN, OUT, pl, hi):
    
    for in_file in (file for file in listdir(IN.joinpath(SUB_PRED)) if file.endswith(".csv")):
        model = pathlib.Path(in_file).stem
        #print(model)
        
        #Plot predictions
        in_dir = IN.joinpath(SUB_PRED)
        i = in_dir.joinpath(in_file)
        print(i)
        df = pd.read_csv(i, header=None)

        out_dir = OUT.joinpath(SUB_PRED)
        if not out_dir.is_dir():
            out_dir.mkdir(parents=True)
        out_file = out_dir.joinpath(model)
        log_file = out_file.with_suffix(".log")
        with open(log_file, "a") as log:

            if pl:
                o = append_to_folder(out_file, "-plot.png")
                log.write(f"Plotting {i} to {o}\n")
                splot.soil_map(df, out=o)
            if hi:
                o = append_to_folder(out_file, "-hist.png")
                log.write(f"Histogramming {i} to {o}\n")
                splot.histogram(df, out=o, title="Histogram of Soil Moisture")
