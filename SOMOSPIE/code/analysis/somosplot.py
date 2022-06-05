#!/usr/bin/env python3

# Danny Rorabaugh, 2018 Dec

import argparse, pathlib, re, string 
import pandas as pd 
import matplotlib as mpl
import numpy as np
import argument_validators as av
from matplotlib import pyplot as plt
from os import fspath
from math import ceil

# Remove this if calling from Jupyter Notebook
#from matplotlib import use as mpluse
#mpl.use('Agg')

# If the above doesn't work, try: (https://stackoverflow.com/a/37605654)
# echo "backend: Agg" > ~/.config/matplotlib/matplotlibrc
plt.switch_backend('agg')

def validate_args(args):
    val_args = {}

    # Validate file paths.
    val_args["input_file"] = av.validate_input_file(args.input_file)
    val_args["output_file"] = av.validate_output_file(args.output_file)

    # Does the input file have column headers or not?
    val_args["header"] = av.str_to_bool(args.header)

    if args.title:    
        val_args["title"] = str(args.title)
    if args.size:
        val_args["size"] = float(args.size)
    if args.min:
        val_args["min"] = float(args.min)
    if args.max:
        val_args["max"] = float(args.max)
    
    val_args["type"] = args.type
    val_args["dependent"] = args.dependent

    return val_args 


# General heatmap function. 
def heatmap(df, horizontal=0, vertical=1, value=2, vmin=None, vmax=None, size=1, title="Heatmap", out="", cmap=None):
    df.plot.scatter(x=horizontal, y=vertical, s=size, c=value, cmap=cmap, title=title, vmin=vmin, vmax=vmax)
    if out:
        print(f"Saving image to {out}")
        plt.savefig(fspath(out))
    else:
        plt.show()
    plt.close()


# For if a dataframe has three columns--1st lon, 2nd lat, 3rd soil moisture
def soil_map(df, title="Soil Moisture Heatmap", out="", cmap=plt.cm.get_cmap('RdBu'), legend="Soil Moisture", size=.05, vmin=None, vmax=None, value=2):
    if df.shape[1]<3:
        raise ValueError("The dataframe doesn't have enough columns.")
    elif df.shape[1]>3:
        #print("The dataframe has too many columns, so we're dropping all but the first three.")
        df = df[df.columns[:3]]
    df.columns=["Longitude", "Latitude", legend]
    heatmap(df, title=title, out=out, cmap=cmap, size=size, vmin=vmin, vmax=vmax, value=value)


# Rounds value to one of a specified "scale", or to integers if no scale given.
# Rounds up/nearest/down if direction >/==/< 0.
def round_number_to(datum, scale=[], direction=0):
    if scale:
        if datum in scale:
            return datum
        elif (datum<scale[0]):
            if direction<0:
                raise ValueError(f"Cannot round down! {datum} is below the bottom of the scale.")
            else:
                return scale[0]
        elif (datum>scale[-1]):
            if direction>0:
                raise ValueError(f"Cannot round up! {datum} is above the top of the scale.")
            else:
                return scale[-1]
        elif len(scale)==1:
            return scale[0]
        else:
            i = 1
            while datum>scale[i]:
                i += 1
            if direction<0:
                return scale[i-1]
            elif direction>0:
                return scale[i]
            else:
                if (scale[i-1] + scale[i])<(datum + datum):
                    return scale[i-1]
                else:
                    return scale[i]
    else:
        if direction<0:
            return int(datum)
        elif direction==0:
            return round(datum)
        else:
            return ceil(datum)


# Rounds every value of a list to one of a specified "scale", or to integers if no scale given.
def round_list_to(data, scale=[], direction=0):
    return [rount_number_to(datum, scale=scale, direction=direction) for datum in data]


# Heatmap with discrete values.
# Currently assumes bounds=[].
# TODO: Implement bounds.
def discrete_map(df, horizontal=0, vertical=1, value=2, title="Discrete Heatmap", out="", legend="", size=.3, bounds=[]):
    #df[df.columns[value]] = df[df.columns[value]].apply(lambda x: round_number_to(x, scale=bounds))
    
    if not bounds:
        values = df[df.columns[value]]
        bounds = range(int(values.min()), ceil(values.max()) + 1)
    #print(bounds)
        
    n = len(bounds)    
    base = plt.cm.gnuplot
    color_list = base(np.linspace(0, 1, n))
    cmap = base.from_list(f"cmap{n}", color_list, n)
    heatmap(df, horizontal=horizontal, vertical=vertical, value=value, vmin=bounds[0]-.5, vmax=bounds[-1]+.5, title=title, out=out, cmap=cmap)


# Argument dep_var give the column number for the dependent variable.
# Values of the dependent variable range from dep_min to dep_max.
def histogram(df, dep_var=2, dep_min=0, dep_max=1, title="Histogram", out="", xlabel="Values", ylabel="Frequency", bins=100):
    if df.shape[1]<dep_var:
        raise ValueError("The dataframe doesn't have enough columns.")
    values = df[df.columns[dep_var]].tolist()
    plt.hist(values, range=(dep_min, dep_max), bins=bins)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    if out:
        plt.savefig(fspath(out))
    else:
        plt.show()
    plt.close()


if __name__ == "__main__":
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file", 
                        help="The input file should be a csv or tsv.")
    parser.add_argument("-c", "--header",
                        help="Binary value to indicate whether the input_file has a header row.",
                        default="true")
    parser.add_argument("-o", "--output_file",
                        help="Path where to save a plot of the input. If not specified, a plot will be displayed but not saved.")
    parser.add_argument("-s", "--size",
                        help="Point size for heatmap. 0.3 is default.",
                        default=".3")
    parser.add_argument("-d", "--dependent",
                        help="Column index of dependent variable; default=2",
                        type=int, default=2)
    parser.add_argument("-p", "--type",
                        help="Type of plot: soil, heat, discr, or hist.",
                        choices=["soil", "heat", "discr", "hist", "min", "sat"])
    parser.add_argument("-t", "--title",
                        help="Plot title.")
    parser.add_argument("-m", "--min",
                        #type=float,
                        help="Dependent variable minimum.")
    parser.add_argument("-M", "--max",
                        #type=float,
                        help="Dependent variable maximum.")
    parser.add_argument("-x", "--xlabel",
                        help="Label for x-axis. Default depends on plot type.")
    parser.add_argument("-y", "--ylabel",
                        help="Label for y-axis. Default depends on plot type.")

    args = parser.parse_args()
    # Check that arguments are sane.
    vargs = validate_args(args)
    
    print(vargs)

    # Read a delimited file (e.g., .csv) into a dataframe.
    # The regular expression below only matches a single-comma or single-tab
    # delimiter right now, but you can change it to whatever you need later.
    delimiter_regex = "[,\t]"
    if vargs["header"]:
        head = 0
    else:
        head = None
    dataframe = pd.read_csv(vargs["input_file"], delimiter=delimiter_regex, header=head, engine='python')

    # Make sure column headers are alphanumeric.
    dataframe = dataframe.rename(columns=av.alphanumeric)
  
    # TODO: Find clean way to use function-specific default arguments when argment not specified; possibly with subparsers? 
    if (vargs["type"]=="soil"):
        soil_map(dataframe, out=vargs["output_file"], size=vargs["size"], vmin=vargs["min"], vmax=vargs["max"], value=vargs["dependent"])
    elif (vargs["type"]=="sat"):
        soil_map(dataframe, out=vargs["output_file"], size=10, vmin=vargs["min"], vmax=vargs["max"], value=vargs["dependent"], cmap=plt.cm.get_cmap('hsv'))
    elif (vargs["type"]=="discr"):
        discrete_map(dataframe, out=vargs["output_file"], size=vargs["size"], value=vargs["dependent"])
    elif (vargs["type"]=="gist_rainbow"):
        histogram(dataframe, out=vargs["output_file"])
    elif (vargs["type"]=="heat"):
        print("Select one of ['soil', 'discr'] for a specific type of heatmap.") 
    elif (vargs["type"]=="min"):
        df_min = dataframe[dataframe.columns[vargs["dependent"]:]].min(axis=1)
        dataframe = dataframe[dataframe.columns[:2]]
        dataframe["min"] = df_min
        soil_map(dataframe, out=vargs["output_file"], size=vargs["size"], title="Minimum Cumulative SSE", cmap=plt.cm.get_cmap('cool'))
    
