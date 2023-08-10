#!/usr/bin/env python3

import argparse
import os
from osgeo import gdal # Install in a conda env: https://anaconda.org/conda-forge/gdal
import numpy as np
import math


def get_parser():
    parser = argparse.ArgumentParser(description='Arguments and data files to generate GeoTIF evaluation file for model.')
    parser.add_argument('-i', "--infiles", help='Terrain parameters GeoTIF files.', nargs='+')
    parser.add_argument('-p', "--params", help='Terrain parameter identifiers (names).', nargs='+')
    parser.add_argument('-n', "--ntiles", help='Number of tiles (Must be a square number), if it is 0 it means tiling is not being used.', default=0)
    parser.add_argument('-x', "--xnum", help='Number of the tile in the x dimension.', default=0)
    parser.add_argument('-y', "--ynum", help='Number of the tile in the y dimension.', default=0)
    parser.add_argument('-s', "--shpfile", help='Shp file to crop into region.')
    parser.add_argument('-o', "--outfile", help='Evaluation file in csv format.')
    return parser


#Translate from namespaces to Python variables 
def from_args_to_vars (args):	
    parameter_files = args.infiles
    parameter_names = args.params
    n_tiles = int(args.ntiles)
    idx_x = int(args.xnum)
    idx_y = int(args.ynum)
    shp_file = args.shpfile
    output_file = args.outfile
    return parameter_files, parameter_names, n_tiles, idx_x, idx_y, shp_file, output_file


def build_stack(input_files):
    # input_files: list of .tif files to stack
    vrt_file = 'stack.vrt'
    vrt_options = gdal.BuildVRTOptions(separate=True)
    vrt = gdal.BuildVRT(vrt_file, input_files, options=vrt_options)
    # translate_options = gdal.TranslateOptions(creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES'],
    #                                           callback=gdal.TermProgress_nocb)
    # gdal.Translate(output_file, vrt_file, options=translate_options)
    vrt = None  # closes file
    return vrt_file


def crop_tile(raster, out_file, n_tiles, idx_x, idx_y):
    # idx_x number of the tile in the x dimension
    ds = gdal.Open(raster, 0)
    cols = ds.RasterXSize
    rows = ds.RasterYSize
    x_win_size = int(math.ceil(cols / n_tiles))
    y_win_size = int(math.ceil(rows / n_tiles))
    
    idx_x = range(0, cols, x_win_size)[idx_x]
    idx_y = range(0, rows, y_win_size)[idx_y]

    if idx_y + y_win_size < rows:
        nrows = y_win_size
    else:
        nrows = rows - idx_y

    if idx_x + x_win_size < cols:
        ncols = x_win_size
    else:
        ncols = cols - idx_x

    translate_options = gdal.TranslateOptions(srcWin=[idx_x, idx_y, ncols, nrows], creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES'], callback=gdal.TermProgress_nocb)
    gdal.Translate(out_file, raster, options=translate_options)


def write_stack(vrt_file, out_file):
    translate_options = gdal.TranslateOptions(creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES'], callback=gdal.TermProgress_nocb)
    gdal.Translate(out_file, vrt_file, options=translate_options)


def set_band_names(raster, band_names):
    ds = gdal.Open(raster, 0)
    print(ds.RasterCount)
    for i, name in enumerate(band_names):
        b = ds.GetRasterBand(i + 1)
        b.SetDescription(name)
    del ds


def get_band_names(raster):
    ds = gdal.Open(raster, 0)
    names = []
    for band in range(ds.RasterCount):
        b = ds.GetRasterBand(band + 1)
        names.append(b.GetDescription())
    ds = None
    return names


def crop_region(input_file, shp_file, output_file):
    warp_options = gdal.WarpOptions(cutlineDSName=shp_file, cropToCutline=True, creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES'], callback=gdal.TermProgress_nocb)
    warp = gdal.Warp(output_file, input_file, options=warp_options)
    warp = None

    
if __name__ == "__main__":	
    parser = get_parser()
    args = parser.parse_args()
    parameter_files, parameter_names, n_tiles, idx_x, idx_y, shp_file, output_file = from_args_to_vars(args)

    for f in parameter_files:
        crop_region(f, shp_file, f)

    vrt_file = build_stack(parameter_files)
    if n_tiles == 0:
        write_stack(vrt_file, output_file)
    else:
        crop_tile(vrt_file, output_file, n_tiles, idx_x, idx_y)

    set_band_names(output_file, parameter_names)
    os.remove('stack.vrt')
    print("Band names:")
    print(get_band_names(output_file))
        

