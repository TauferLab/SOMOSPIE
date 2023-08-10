#!/usr/bin/env python3

import argparse
import os
import numpy as np
from osgeo import gdal # Install in a conda env: https://anaconda.org/conda-forge/gdal


def get_parser():
    parser = argparse.ArgumentParser(description='Arguments and data files for executing Nearest Neighbors Regression.')
    parser.add_argument('-i', "--infile", help='Input file (DEM).')
    parser.add_argument('-o', "--outfile", help='Output file (reprojected DEM).')
    parser.add_argument('-p', "--projection", help='Projection, can be an EPSG identifier such as EPSG:4326 or the path to a wkt file')
    parser.add_argument('-n', "--nodata", help='If y, nodata value will be set to np.nan.', default='n')
    return parser 

#Translate from namespaces to Python variables 
def from_args_to_vars (args):	
    input_file = args.infile
    output_file = args.outfile
    projection = args.projection
    nodata = args.nodata
    return input_file, output_file, projection, nodata


def reproject(input_file, output_file, projection, nodata='n'):
    # Projection can be EPSG:4326, .... or the path to a wkt file
    if nodata == 'y':
        warp_options = gdal.WarpOptions(dstSRS=projection, dstNodata=np.nan, creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES', 'NUM_THREADS=ALL_CPUS'], multithread=True, warpOptions=['NUM_THREADS=ALL_CPUS'], callback=gdal.TermProgress_nocb)
    else:
        warp_options = gdal.WarpOptions(dstSRS=projection, creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES', 'NUM_THREADS=ALL_CPUS'], callback=gdal.TermProgress_nocb, multithread=True, warpOptions=['NUM_THREADS=ALL_CPUS'])
    warp = gdal.Warp(output_file, input_file, options=warp_options)
    warp = None  # Closes the files


if __name__ == "__main__":	
    parser=get_parser()
    args = parser.parse_args()
    input_file, output_file, projection, nodata = from_args_to_vars(args)
    reproject(input_file, output_file, projection, nodata)