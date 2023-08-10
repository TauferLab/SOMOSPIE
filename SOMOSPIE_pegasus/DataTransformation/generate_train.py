#!/usr/bin/env python3

import argparse
from osgeo import gdal # Install in a conda env: https://anaconda.org/conda-forge/gdal
import os
import zipfile
from pathlib import Path
import glob
import shutil


def get_parser():
    parser = argparse.ArgumentParser(description='Arguments and data files to generate GeoTIF training file for model.')
    parser.add_argument('-i', "--infile", help='Satellite soil moisture GeoTIF file.')
    parser.add_argument('-f', "--paramfiles", help='Terrain parameters GeoTIF files.', nargs='+')
    parser.add_argument('-p', "--params", help='Terrain parameter identifiers for csv file headers.', nargs='+')
    parser.add_argument('-s', "--shpfile", help='Shp file to crop into region, in zip.')
    parser.add_argument('-o', "--outfile", help='Training file in tif format.')
    return parser


#Translate from namespaces to Python variables 
def from_args_to_vars (args):	
    satellite_file = args.infile
    parameter_files = args.paramfiles
    parameter_names = args.params
    shp_file = args.shpfile
    output_file = args.outfile
    return satellite_file, parameter_files, parameter_names, shp_file, output_file


def build_stack(input_files, output_file):
    # input_files: list of .tif files to stack

    # Get target resolution from satellite file
    ds = gdal.Open(input_files[0], 0)
    xmin, xres, _, ymax, _, yres = ds.GetGeoTransform()

    vrt_file = 'stack.vrt'
    vrt_options = gdal.BuildVRTOptions(separate=True)
    vrt = gdal.BuildVRT(vrt_file, input_files, options=vrt_options)
    translate_options = gdal.TranslateOptions(creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES'], xRes=xres , yRes=yres,
                                              callback=gdal.TermProgress_nocb)
    gdal.Translate(output_file, vrt, options=translate_options)
    vrt = None  # closes file
    os.remove('stack.vrt')


def set_band_names(raster, band_names):
    ds = gdal.Open(raster, 0)
    for i, name in enumerate(band_names):
        b = ds.GetRasterBand(i + 1)
        b.SetDescription(name)
    ds = None


def get_band_names(raster):
    ds = gdal.Open(raster, 0)
    names = []
    for band in range(ds.RasterCount):
        b = ds.GetRasterBand(band + 1)
        names.append(b.GetDescription())
    ds = None
    return names


def get_shp(zip_file):
    Path('shp_file').mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
        zip_ref.extractall('./shp_file')

    shp_file = glob.glob('./shp_file/*.shp')[0]
    return shp_file


def crop_region(input_file, shp_file, output_file):
    warp_options = gdal.WarpOptions(cutlineDSName=shp_file, cropToCutline=True, creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES'],
                                    callback=gdal.TermProgress_nocb)
    warp = gdal.Warp(output_file, input_file, options=warp_options)
    warp = None


if __name__ == "__main__":	
    parser = get_parser()
    args = parser.parse_args()
    satellite_file, parameter_files, parameter_names, shp_file, output_file = from_args_to_vars(args)

    parameter_files.insert(0, satellite_file)
    parameter_names.insert(0, 'z')

    build_stack(parameter_files, output_file)
    shp_file = get_shp(shp_file)
    crop_region(output_file, shp_file, output_file)
    
    set_band_names(output_file, parameter_names)
    print(get_band_names(output_file))
    