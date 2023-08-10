#!/usr/bin/env python3

import argparse
import os
import glob
from osgeo import gdal # Install in a conda env: https://anaconda.org/conda-forge/gdal
import subprocess
import numpy as np


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

def bash(argv):
    arg_seq = [str(arg) for arg in argv]
    proc = subprocess.Popen(arg_seq, stdout=subprocess.PIPE, stderr=subprocess.PIPE)#, shell=True)
    proc.wait() #... unless intentionally asynchronous
    stdout, stderr = proc.communicate()

    # Error catching: https://stackoverflow.com/questions/5826427/can-a-python-script-execute-a-function-inside-a-bash-script
    if proc.returncode != 0:
        raise RuntimeError("'%s' failed, error code: '%s', stdout: '%s', stderr: '%s'" % (
            ' '.join(arg_seq), proc.returncode, stdout.rstrip(), stderr.rstrip()))


def merge_avg(input_files, output_file):
    vrt = gdal.BuildVRT('merged.vrt', input_files)
    vrt = None  # closes file

    with open('merged.vrt', 'r') as f:
        contents = f.read()

    if '<NoDataValue>' in contents:
        nodata_value = contents[contents.index('<NoDataValue>') + len('<NoDataValue>'): contents.index('</NoDataValue>')]# To add averaging function
    else:
        nodata_value = 0

    code = '''band="1" subClass="VRTDerivedRasterBand">
  <PixelFunctionType>average</PixelFunctionType>
  <PixelFunctionLanguage>Python</PixelFunctionLanguage>
  <PixelFunctionCode><![CDATA[
import numpy as np

def average(in_ar, out_ar, xoff, yoff, xsize, ysize, raster_xsize,raster_ysize, buf_radius, gt, **kwargs):
    data = np.ma.array(in_ar, mask=np.equal(in_ar, {}))
    np.mean(data, axis=0, out=out_ar, dtype="float32")
    mask = np.all(data.mask,axis = 0)
    out_ar[mask] = {}
]]>
  </PixelFunctionCode>'''.format(nodata_value, nodata_value)

    sub1, sub2 = contents.split('band="1">', 1)
    contents = sub1 + code + sub2

    with open('merged.vrt', 'w') as f:
        f.write(contents)

    cmd = ['gdal_translate', '-co', 'COMPRESS=LZW', '-co', 'TILED=YES', '-co', 'BIGTIFF=YES', '--config', 'GDAL_VRT_ENABLE_PYTHON', 'YES', 'merged.vrt', output_file]
    bash(cmd)
    os.remove('merged.vrt')


def reproject(input_file, output_file, projection):
    # Projection can be EPSG:4326, .... or the path to a wkt file
    warp_options = gdal.WarpOptions(dstSRS=projection, creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES', 'NUM_THREADS=ALL_CPUS'], multithread=True, warpOptions=['NUM_THREADS=ALL_CPUS'], dstNodata=np.nan, callback=gdal.TermProgress_nocb)
    warp = gdal.Warp(output_file, input_file, options=warp_options)
    warp = None  # Closes the files


if __name__ == "__main__":	
    parser=get_parser()
    args = parser.parse_args()
    input_files, output_file = from_args_to_vars(args)

    for input_file in input_files:
        print("Tile (", input_file, ")", "Size is :", os.path.getsize(input_file), " bytes")

    merge_avg(input_files, output_file)
    reproject(output_file, output_file, 'EPSG:4326')
