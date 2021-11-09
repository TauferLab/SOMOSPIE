#!/usr/bin/env python3

# Danny Rorabaugh, 2018 Dec

import argparse
import numpy as np
import pandas as pd
import skgstat as skg
from os import path, listdir
from time import time
t0 = time()

def mean(df):
    return df.mean()

def std(df):
    return df.std()

def mx(df):
    return df.max()

def mn(df):
    return df.min()

def rng(df):
    return df.max() - df.min()

def qnt25(df):
    return df.quantile(.25)

def qnt75(df):
    return df.quantile(.75)

def count(df):
    return df.dropna().shape[0]

def corr(df):
    if df.columns[0]==df.columns[1]:
        return 1
    else:
        return df[df.columns[0]].corr(df[df.columns[1]])

def variogram_range(df):
    if df.columns[0]==df.columns[1]:
        return 0
    df = df.dropna()
    if (len(set(df.columns[0]))<2):
        return np.nan
    coordinates = df[df.columns[:-1]]
    values = df[df.columns[-1]]
    try:
        V = skg.Variogram(coordinates=coordinates, values=values)
    except:
        return np.nan
    return V.describe()["effective_range"]

def variogram_sill(df):
    if df.columns[0]==df.columns[1]:
        return np.nan
    df = df.dropna()
    if (len(set(df.columns[0]))<2):
        return np.nan
    coordinates = df[df.columns[:-1]]
    values = df[df.columns[-1]]
    try:
        V = skg.Variogram(coordinates=coordinates, values=values)
    except:
        return np.nan
    return V.describe()["sill"]

def variogram_nugget(df):
    if df.columns[0]==df.columns[1]:
        return np.nan
    df = df.dropna()
    if (len(set(df.columns[0]))<2):
        return np.nan
    coordinates = df[df.columns[:-1]]
    values = df[df.columns[-1]]
    try:
        V = skg.Variogram(coordinates=coordinates, values=values)
    except:
        return np.nan
    return V.describe()["nugget"]

def compute_stats(in_file, out_file, stat_dicts):
    df = pd.read_csv(in_file)
    cols = df.shape[1]
    print(f"Input file {in_file} has {cols} data columns.")
    
    with open(out_file+"stats", "w") as stat_out:
        with open(out_file+"stats.keys", "w") as keys_out:
            
            for stat in stat_dicts[0]:
                keys_out.write(f"{stat}()\n")
                stat_out.write(str(list(stat_dicts[0][stat](df))).strip("[]")+"\n")
            
            for stat in stat_dicts[1]:
                keys_out.write(f"{stat}()\n")
                stat_out.write(",".join([str(stat_dicts[1][stat](df[df.columns[i]])) for i in range(cols)])+"\n")
                
            for stat in stat_dicts[2]:
                for i in range(cols):
                    keys_out.write(f"{stat}({df.columns[i]})\n")
                    stat_out.write(",".join([str(stat_dicts[2][stat](df[[df.columns[i],df.columns[j]]])) for j in range(cols)])+"\n")
                    
            for stat in stat_dicts[3]:
                keys_out.write(f"{stat}(x,y)\n")
                stat_out.write("nan,nan," + ",".join([str(stat_dicts[3][stat](df[[df.columns[0], df.columns[1], df.columns[i]]])) for i in range(2,cols)])+"\n")
    

if __name__ == "__main__":
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("input_path", 
                        help="The input file or directory of input files.")
    parser.add_argument("-e", "--extension",
                        help="Expected file extension",
                        default="csv")
    args = parser.parse_args()

    # Check that arguments are sane
    if not path.exists(args.input_path):
        print(f"Warning! The file/folder {args.input_path} does not exist.")
    
    if path.isfile(args.input_path):
        files = [args.input_path]
    elif path.isdir(args.input_path):
        files = [file for file in listdir(args.input_path) if file.endswith(args.extension)]
        
    stat_func_dicts = [{},{},{},{}]
    # Functions that act on the entire dataframe, each column independently
    stat_func_dicts[0] = {"mean":mean, "std":std, "min":mn, "max":mx, "range":rng, "quantile25":qnt25, "quantile75":qnt75}
    # Functions performed on a 1-column dataframe
    stat_func_dicts[1] = {"count":count}
    # Functions performed on a 2-column dataframe, with the first column the dependent variable when applicable
    stat_func_dicts[2] = {"count":count, "corr":corr}#, "variogram_range":variogram_range, "variogram_sill":variogram_sill}#, "variogram_nugget":variogram_nugget}
    # Functions performed on a 3-column dataframe, with the first two cols x (longitude) and y (latitude)
    #stat_func_dicts[3] = {"variogram_range":variogram_range, "variogram_sill":variogram_sill, "variogram_nugget":variogram_nugget}
        
    for file in files:
        out_path = file[:-len(args.extension)]
        compute_stats(file, out_path, stat_func_dicts)

t1 = time()    
print(f"Computed statistics for {len(files)} file(s) in {t1-t0} seconds.")