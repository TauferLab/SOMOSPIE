# Remove this if calling from Jupyter Notebook
#from matplotlib import use as mpluse
#mpluse('Agg')
# The above didn't work, but this does: (https://stackoverflow.com/a/37605654)
# $ echo "backend: Agg" > ~/.config/matplotlib/matplotlibrc

import pathlib
from os import listdir
from utils import *
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

def visualize(IN, OUT, ORIGEN, reg_type, reg,  pl, hi):
    
    # Finding the intersection of the range of the different methods for each region
    # for the different models
    Region = f"{reg_type} {reg}"
    minimum = 0
    maximum = 1

    for in_file in (file for file in listdir(IN.joinpath(SUB_PRED)) if file.endswith(".csv")):
        model = pathlib.Path(in_file).stem
        
        in_dir = IN.joinpath(SUB_PRED)
        i = in_dir.joinpath(in_file)
        print(i)
        df = pd.read_csv(i, header=None)
        if df[2].min() > minimum:
            minimum = df[2].min()
        
        if df[2].max() < maximum:
            maximum = df[2].max()
     
    ORIGFILE = append_to_folder(ORIGEN, ".csv")
    df1 = pd.read_csv(ORIGFILE, header=None)
    #ORIGFILEOUT = append_to_folder(ORIGEN, ".png")
    #splot.soil_map(df1, out=ORIGFILEOUT, vmin=minimum, vmax=maximum)
    
    for in_file in (file for file in listdir(IN.joinpath(SUB_PRED)) if file.endswith(".csv")):
        model = pathlib.Path(in_file).stem
        
        #Plot predictions
        in_dir = IN.joinpath(SUB_PRED)
        i = in_dir.joinpath(in_file)
        print(i)
        df = pd.read_csv(i, header=None)
        
        out_dir = OUT.joinpath(SUB_PRED)
        if not out_dir.is_dir():
            out_dir.mkdir(parents=True)
        out_file = out_dir.joinpath(model)
        out_file_origen = out_dir.joinpath("origen")
        log_file = out_file.with_suffix(".log")
        with open(log_file, "a") as log:

            if pl:
                o   = append_to_folder(out_file, "-plot.png")
                oo  = append_to_folder(out_file_origen, ".png")
                ooo = append_to_folder(out_file, ".svg")
                log.write(f"Plotting {i} to {o}\n")
                splot.soil_map(df, out=o, vmin=minimum, vmax=maximum, title=f"Prediction for {Region}. Model: {model}")
                splot.soil_map(df1, out=oo, vmin=minimum, vmax=maximum, title=f"Observation Data for {Region}.", size=20)
                splot.soil_map(df, out=ooo, vmin=minimum, vmax=maximum, title=f"Observation Data for {Region}.", size=20)
            if hi:
                o = append_to_folder(out_file, "-hist.png")
                log.write(f"Histogramming {i} to {o}\n")
                splot.histogram(df, out=o, title="Histogram of Soil Moisture")
   