#!/usr/bin/env python3

import argparse
import os
import glob
from osgeo import gdal # Install in a conda env: https://anaconda.org/conda-forge/gdal


def get_parser():
    parser = argparse.ArgumentParser(description='Arguments and data files to merge multiple tiles into a mosaic.')
    parser.add_argument('-i', "--infiles", help='Path to input tiles.', nargs='+')
    parser.add_argument('-o', "--outfile", help='Mosaic built from input tiles.')
    return parser

#Translate from namespaces to Python variables 
def from_args_to_vars (args):	
    input_files = args.infiles
    output_file = args.outfile
    return input_files, output_file


def merge_tiles(input_files, output_file):
    # input_files: list of .tif files to merge
    vrt = gdal.BuildVRT('merged.vrt', input_files)
    translate_options = gdal.TranslateOptions(creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES', 'NUM_THREADS=ALL_CPUS'], callback=gdal.TermProgress_nocb)
    gdal.Translate(output_file, vrt, options=translate_options)
    vrt = None  # closes file
    os.remove('merged.vrt')


if __name__ == "__main__":
    parser=get_parser()
    args = parser.parse_args()
    input_files, output_file = from_args_to_vars(args)
    merge_tiles(input_files, output_file)