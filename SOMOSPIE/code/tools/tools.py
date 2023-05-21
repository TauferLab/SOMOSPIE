# Contributors: Camila Roa (@CamilaR20), Eric Vaughan (@VaughanEric), Andrew Mueller (@), Sam Baumann (@sam-baumann), David Huang (dhuang0212), Ben Klein (robobenklein)
import os
from pathlib import Path
import glob
import shutil
import subprocess
from osgeo import gdal, ogr  # Install in a conda env: https://anaconda.org/conda-forge/gdal
import numpy as np
import pandas as pd
import math
import multiprocessing
import concurrent.futures

# In Ubuntu: sudo apt-get install grass grass-doc
# pip install grass-session
from grass_session import Session
import grass.script as gscript
import tempfile

# Increased the size of GDAL’s input-output buffer cache to reduce the number of look-up operations
gdal.SetConfigOption("GDAL_CACHEMAX", "512")

def bash(argv):
    arg_seq = [str(arg) for arg in argv]
    proc = subprocess.Popen(arg_seq)#, shell=True)
    proc.wait() #... unless intentionally asynchronous
       

def download_dem(file, folder):
    with open(file, 'r', encoding='utf8') as dsvfile:
        lines = dsvfile.readlines()
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=20) as executor:
        for line in lines:
            commands = ['wget', '-q', '-P', folder, line.rstrip()]
            executor.submit(bash, commands)


def merge_tiles(input_files, output_file):
    # input_files: list of .tif files to merge
    vrt = gdal.BuildVRT("merged.vrt", input_files)
    translate_options = gdal.TranslateOptions(creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES', 'NUM_THREADS=ALL_CPUS'],
                                              callback=gdal.TermProgress_nocb)
    gdal.Translate(output_file, vrt, options=translate_options)
    vrt = None  # closes file

    # Loads all tiles into memory to merge, vrt better for large rasters
    # cmd = ['gdal_merge.py', '-co', 'COMPRESS=LZW', '-co', 'TILED=YES', '-o', './merged.tif']
    # cmd = cmd + files
    # bash(cmd)


def reproject(input_file, output_file, projection):
    # Projection can be EPSG:4326, .... or the path to a wkt file
    warp_options = gdal.WarpOptions(dstSRS=projection, creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES', 'NUM_THREADS=ALL_CPUS'],
                                    callback=gdal.TermProgress_nocb, multithread=True, warpOptions=['NUM_THREADS=ALL_CPUS'])
    warp = gdal.Warp(output_file, input_file, options=warp_options)
    warp = None  # Closes the files


def change_raster_format(input_file, output_file, raster_format):
    # Supported formats: https://gdal.org/drivers/raster/index.html
    # SAGA, GTiff
    if raster_format == 'GTiff':
        translate_options = gdal.TranslateOptions(format=raster_format, creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES'],
                                                callback=gdal.TermProgress_nocb)
    elif raster_format == 'NC4C':
        translate_options = gdal.TranslateOptions(format=raster_format, creationOptions=['COMPRESS=DEFLATE'],
                                                callback=gdal.TermProgress_nocb)
    else:
        translate_options = gdal.TranslateOptions(format=raster_format,
                                                callback=gdal.TermProgress_nocb)
    
    gdal.Translate(output_file, input_file, options=translate_options)



def compute_params_saga(file_prefix):
    # Compute 15 terrain parameters with saga inside tmux session
    # tmux new-session -d -s "myTempSession" bash ./terrestrial_parameters.sh ./mosaic/TN_WGS84_30m_
    command = ['tmux', 'new-session', '-d', '-s', 'terrainParamsSession', 'bash ./terrestrial_parameters.sh ' + file_prefix]
    # command = ['bash', './terrestrial_parameters.sh', name_file]
    bash(command)
    
    
def build_stack(input_files, output_file):
    # input_files: list of .tif files to stack
    vrt_options = gdal.BuildVRTOptions(separate=True)
    vrt = gdal.BuildVRT("stack.vrt", input_files, options=vrt_options)
    translate_options = gdal.TranslateOptions(creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES'],
                                              callback=gdal.TermProgress_nocb)
    gdal.Translate(output_file, vrt, options=translate_options)
    vrt = None  # closes file


def crop_region(input_file, shp_file, output_file):
    warp_options = gdal.WarpOptions(cutlineDSName=shp_file, cropToCutline=True, creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES'],
                                    callback=gdal.TermProgress_nocb)
    warp = gdal.Warp(output_file, input_file, options=warp_options)
    warp = None


def get_projection(input_file, output_file):
    cmd = ['gdalsrsinfo', '-o', 'wkt', input_file, '>', output_file]
    bash(cmd)


def crop_coord(input_file, output_file, upper_left, lower_right):
    # upper_left = (x, y), lower_right = (x, y)
    # Coordinates must be in the same projection as the raster
    window = upper_left + lower_right
    translate_options = gdal.TranslateOptions(projWin=window, creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES'],
                                              callback=gdal.TermProgress_nocb)
    gdal.Translate(output_file, input_file, options=translate_options)


def crop_pixels(input_file, output_file, window):
    # Window to crop by [left_x, top_y, width, height]
    translate_options = gdal.TranslateOptions(srcWin=window,
                                              creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES'],
                                              callback=gdal.TermProgress_nocb)
    gdal.Translate(output_file, input_file, options=translate_options)


def get_extent(shp_file):
    ds = ogr.Open(shp_file)
    layer = ds.GetLayer()
    ext = layer.GetExtent()
    upper_left = (ext[0], ext[3])
    lower_right = (ext[1], ext[2])

    return upper_left, lower_right


def compute_geotiled(input_file):
    out_folder = os.path.dirname(os.path.dirname(input_file))
    out_file = os.path.join(out_folder,'slope_tiles', os.path.basename(input_file))
    # Slope
    dem_options = gdal.DEMProcessingOptions(format='GTiff', creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES'])
    gdal.DEMProcessing(out_file, input_file, processing='slope', options=dem_options)
    # Aspect
    out_file = os.path.join(out_folder,'aspect_tiles', os.path.basename(input_file))
    dem_options = gdal.DEMProcessingOptions(zeroForFlat=True, format='GTiff', creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES'])
    gdal.DEMProcessing(out_file, input_file, processing='aspect', options=dem_options)
    # Hillshading
    out_file = os.path.join(out_folder,'hillshading_tiles', os.path.basename(input_file))
    dem_options = gdal.DEMProcessingOptions(format='GTiff', creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES'])
    gdal.DEMProcessing(out_file, input_file, processing='hillshade', options=dem_options)


def compute_params(input_prefix, parameters):
    # Slope
    if 'slope' in parameters:
        dem_options = gdal.DEMProcessingOptions(format='GTiff', creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES'], callback=gdal.TermProgress_nocb)
        gdal.DEMProcessing(input_prefix + 'slope.tif', input_prefix + 'elevation.tif', processing='slope', options=dem_options)
    # Aspect
    if 'aspect' in parameters:
        dem_options = gdal.DEMProcessingOptions(zeroForFlat=True, format='GTiff', creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES'], callback=gdal.TermProgress_nocb)
        gdal.DEMProcessing(input_prefix + 'aspect.tif', input_prefix + 'elevation.tif', processing='aspect', options=dem_options)
    # Hillshading
    if 'hillshading' in parameters:
        dem_options = gdal.DEMProcessingOptions(format='GTiff', creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES'], callback=gdal.TermProgress_nocb)
        gdal.DEMProcessing(input_prefix + 'hillshading.tif', input_prefix + 'elevation.tif', processing='hillshade', options=dem_options)

    # Other parameters with GRASS GIS
    if any(param in parameters for param in ['twi', 'plan_curvature', 'profile_curvature']):
        # define where to process the data in the temporary grass-session
        tmpdir = tempfile.TemporaryDirectory()

        s = Session()
        s.open(gisdb=tmpdir.name, location='PERMANENT', create_opts=input_prefix + 'elevation.tif')
        creation_options = 'BIGTIFF=YES,COMPRESS=LZW,TILED=YES' # For GeoTIFF files

        # Load raster into GRASS without loading it into memory (else use r.import or r.in.gdal)
        gscript.run_command('r.external', input=input_prefix + 'elevation.tif', output='elevation', overwrite=True)
        # Set output folder for computed parameters
        gscript.run_command('r.external.out', directory=os.path.dirname(input_prefix), format="GTiff", option=creation_options)

        if 'twi' in parameters:
            gscript.run_command('r.topidx', input='elevation', output='twi.tif', overwrite=True)

        if 'plan_curvature' in parameters:
            gscript.run_command('r.slope.aspect', elevation='elevation', tcurvature='plan_curvature.tif', overwrite=True)

        if 'profile_curvature' in parameters:
            gscript.run_command('r.slope.aspect', elevation='elevation', pcurvature='profile_curvature.tif', overwrite=True)

        if 'convergence_index' in parameters:
            gscript.run_command('r.convergence', input='elevation', output='convergence_index.tif', overwrite=True)

        if 'valley_depth' in parameters:
            gscript.run_command('r.valley.bottom', input='elevation', mrvbf='valley_depth.tif', overwrite=True)

        if 'ls_factor' in parameters:
            gscript.run_command('r.watershed', input='elevation', length_slope='ls_factor.tif', overwrite=True)


        tmpdir.cleanup()
        s.close()
        
        # Slope and aspect with GRASS GIS (uses underlying GDAL implementation)
        #vgscript.run_command('r.slope.aspect', elevation='elevation', aspect='aspect.tif', slope='slope.tif', overwrite=True)

def compute_params_concurrently(input_prefix, parameters):
    with concurrent.futures.ProcessPoolExecutor(max_workers=20) as executor:
        for param in parameters:
            executor.submit(compute_params, input_prefix, param)


def extract_raster(csv_file, raster_file, band_names):
    # Extract values from raster corresponding to
    df = pd.read_csv(csv_file)

    ds = gdal.Open(raster_file, 0)
    gt = ds.GetGeoTransform()

    n_bands = ds.RasterCount
    bands = np.zeros((df.shape[0], n_bands))

    for i in range(df.shape[0]):
        px = int((df['x'][i] - gt[0]) / gt[1])
        py = int((df['y'][i] - gt[3]) / gt[5])

        for j in range(n_bands):
            band = ds.GetRasterBand(j + 1)
            val = band.ReadAsArray(px, py, 1, 1)
            bands[i, j] = val[0]
    ds = None

    for j in range(n_bands):
        df[band_names[j]] = bands[:, j]

    df.to_csv(csv_file, index=None)


def tif2csv(raster_file, band_names=['elevation'], output_file='params.csv'):
    ds = gdal.Open(raster_file, 0)
    xmin, res, _, ymax, _, _ = ds.GetGeoTransform()
    xsize = ds.RasterXSize
    ysize = ds.RasterYSize
    xstart = xmin + res / 2
    ystart = ymax - res / 2

    x = np.arange(xstart, xstart + xsize * res, res)
    y = np.arange(ystart, ystart - ysize * res, -res)
    x = np.tile(x[:xsize], ysize)
    y = np.repeat(y[:ysize], xsize)

    n_bands = ds.RasterCount
    bands = np.zeros((x.shape[0], n_bands))
    for k in range(1, n_bands + 1):
        band = ds.GetRasterBand(k)
        data = band.ReadAsArray()
        data = np.ma.array(data, mask=np.equal(data, band.GetNoDataValue()))
        data = data.filled(np.nan)
        bands[:, k-1] = data.flatten()

    column_names = ['x', 'y'] + band_names
    stack = np.column_stack((x, y, bands))
    df = pd.DataFrame(stack, columns=column_names)
    df.dropna(inplace=True)
    df.to_csv(output_file, index=None)


def shp2csv(input_file, output_file):
    cmd = ['ogr2ogr', '-f', 'CSV', output_file, input_file, '-lco', 'GEOMETRY=AS_XY']
    bash(cmd)


def crop_into_tiles(mosaic, out_folder, n_tiles):
    n_tiles = math.sqrt(n_tiles)

    ds = gdal.Open(mosaic, 0)
    cols = ds.RasterXSize
    rows = ds.RasterYSize
    x_win_size = int(math.ceil(cols / n_tiles))
    y_win_size = int(math.ceil(rows / n_tiles))

    buffer = 10 # 10 pixels
    tile_count = 0

    for i in range(0, rows, y_win_size):
        if i + y_win_size < rows:
            nrows = y_win_size
        else:
            nrows = rows - i

        for j in range(0, cols, x_win_size):
            if j + x_win_size < cols:
                ncols = x_win_size
            else:
                ncols = cols - j

            tile_file = out_folder + '/tile_' + '{0:04d}'.format(tile_count) + '.tif'
            win = [j, i, ncols, nrows]

            # Upper left corner
            win[0] = max(0, win[0] - buffer)
            win[1] = max(0, win[1] - buffer)

            w = win[2] + 2*buffer
            win[2] = w if win[0] + w < cols else cols - win[0]

            h = win[3] + 2*buffer
            win[3] = h if win[1] + h < cols else cols - win[1]

            crop_pixels(mosaic, tile_file, win)
            tile_count += 1


def build_mosaic(input_files, output_file):
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