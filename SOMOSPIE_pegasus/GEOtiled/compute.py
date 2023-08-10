#!/usr/bin/env python3

import argparse
import os
import numpy as np
from osgeo import gdal # Install in a conda env: https://anaconda.org/conda-forge/gdal


def get_parser():
    parser = argparse.ArgumentParser(description='Arguments and data files for computing terrain parameters.')
    parser.add_argument('-i', "--infile", help='Input file (DEM tile).')
    parser.add_argument('-o', "--outfile", help='Output files (aspect, hillshading, slope).', nargs='+')
    return parser 

#Translate from namespaces to Python variables 
def from_args_to_vars (args):	
    input_file = args.infile
    aspect_file, hillshading_file, slope_file = args.outfile
    return input_file, aspect_file, hillshading_file, slope_file


def compute_geotiled(input_file, aspect_file, hillshading_file, slope_file):
    # Slope
    dem_options = gdal.DEMProcessingOptions(format='GTiff', creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES'])
    gdal.DEMProcessing(slope_file, input_file, processing='slope', options=dem_options)
    # Aspect
    dem_options = gdal.DEMProcessingOptions(zeroForFlat=True, format='GTiff', creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES'])
    gdal.DEMProcessing(aspect_file, input_file, processing='aspect', options=dem_options)
    # Hillshading
    dem_options = gdal.DEMProcessingOptions(format='GTiff', creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES'])
    gdal.DEMProcessing('hill.tif', input_file, processing='hillshade', options=dem_options)

    # Change datatype of hillshading to the same as the other parameters and nodata value
    translate_options = gdal.TranslateOptions(creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES', 'NUM_THREADS=ALL_CPUS'], outputType=gdal.GDT_Float32, callback=gdal.TermProgress_nocb)
    gdal.Translate(hillshading_file, 'hill.tif', options=translate_options)
    os.remove('hill.tif')

if __name__ == "__main__":	
    parser = get_parser()
    args = parser.parse_args()
    input_file, aspect_file, hillshading_file, slope_file = from_args_to_vars(args)
    print("Tile (", input_file, ")", "Size is :", os.path.getsize(input_file), " bytes") # For debugging
    compute_geotiled(input_file, aspect_file, hillshading_file, slope_file)