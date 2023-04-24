from osgeo import gdal
import glob
from pathlib import Path
import os
from matplotlib import pyplot as plt
import pandas as pd
import numpy as np
import geopandas


def csv2tif(input_file, output_file):
    xyz_path = os.path.join(os.path.dirname(output_file), 'df.xyz')
    df = pd.read_csv(input_file)
    df.sort_values(by=["y", "x"], ascending=[False, True], inplace=True)
    df.to_csv(xyz_path, index=False, header=None, sep=" ")
    
    translate_options = gdal.TranslateOptions(format='GTiff', creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES'], callback=gdal.TermProgress_nocb)
    tif = gdal.Translate(output_file, xyz_path, options=translate_options)
    tif = None
    os.remove(xyz_path)
    
    
def rasterize(input_file, output_file, xres, yres):
    # When there is not a regular grid (has missing values)
    vrt_file = output_file[:-4] + '.vrt'
    if os.path.exists(vrt_file):
        os.remove(vrt_file)
        
    f = open(vrt_file, 'w')
    f.write('<OGRVRTDataSource>\n \
    <OGRVRTLayer name="{}">\n \
        <SrcDataSource>{}</SrcDataSource>\n \
        <GeometryType>wkbPoint</GeometryType>\n \
        <GeometryField encoding="PointFromColumns" x="x" y="y" z="sm"/>\n \
    </OGRVRTLayer>\n \
</OGRVRTDataSource>'.format(os.path.basename(output_file[:-4]), input_file)) # https://gdal.org/programs/gdal_grid.html#gdal-grid
    f.close()
    
    rasterize_options = gdal.RasterizeOptions(xRes=xres, yRes=yres, attribute='sm', noData=np.nan, outputType=gdal.GDT_Float32, creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES'], callback=gdal.TermProgress_nocb)
    r = gdal.Rasterize(output_file, vrt_file, options=rasterize_options)
    r = None
    
    #grid_options = gdal.GridOptions(width=w, height=h, creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES'], callback=gdal.TermProgress_nocb)
    #g = gdal.Grid(output_file, vrt_file, options=grid_options)
    #g = None
    
    
def merge_tiles(input_files, output_file):
    # input_files: list of .tif files to merge
    vrt = gdal.BuildVRT(output_file, input_files)
    vrt = None  # closes file
    

def resample_mosaic(input_file, output_file, width=7680):
    ds = gdal.Open(input_file, 0)
    band = ds.GetRasterBand(1)

    w = ds.RasterXSize
    h = ds.RasterYSize
    
    height = int(h * width / float(w))
    
    warp_options = gdal.WarpOptions(format='GTiff', creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES'], resampleAlg='average', width=width, height= height, callback=gdal.TermProgress_nocb)
    warp = gdal.Warp(output_file, input_file, options=warp_options)
    warp = None  # Closes the files
    
    
def plot_tif(tif_path, png_path, sm_min, sm_max, shp_file=None):
    ds = gdal.Open(tif_path, 0)
    xmin, xres, _, ymax, _, yres = ds.GetGeoTransform()
    band = ds.GetRasterBand(1)
    data = band.ReadAsArray()
    data = np.ma.array(data, mask=np.equal(data, band.GetNoDataValue()))

    extent = [xmin, xmin + xres * data.shape[1], ymax + yres * data.shape[0], ymax]

    fig, ax = plt.subplots()
    sm = ax.imshow(data, cmap='RdBu', extent=extent, vmin=sm_min, vmax=sm_max)
    fig.colorbar(sm, fraction=0.046*data.shape[0]/data.shape[1] , pad=0.04)

    # To overlay polygons on top of plot, for example a map outline
    if shp_file is not None:
        overlay = geopandas.read_file(shp_file)
        overlay.boundary.plot(color='k', linewidth=0.8, ax=ax)

    fig.savefig(png_path, bbox_inches='tight', dpi=150, pad_inches=0)
    
    
if __name__ == '__main__':
    csv_folder = '/home/exouser/predictions'
    tiles_folder = './tiles'
    output_file = './oklahoma_10m.png'

    Path(tiles_folder).mkdir(parents=True, exist_ok=True)

    mosaic_vrt = os.path.join(tiles_folder, 'mosaic.vrt')
    mosaic_tif = os.path.join(tiles_folder, 'sm.tif')
    
    csv_files = sorted(glob.glob(os.path.join(csv_folder, '*.csv')))
    # csv_files = csv_files[74:]
    
    # CSV to tiff
    print('Converting csv files to tif...')
    for csv_file in csv_files:
        tif_path = os.path.join(tiles_folder, os.path.basename(csv_file)[:-4] + '.tif')
        print(os.path.basename(csv_file))
        try:
            csv2tif(csv_file, tif_path)
        except:
            ds = gdal.Open(os.path.join(tiles_folder, os.path.basename(csv_files[0])[:-4] + '.tif'))
            gt = ds.GetGeoTransform()
            rasterize(csv_file, tif_path, gt[1], gt[5])
    
    # Build Mosaic
    print('Building mosaic...')
    tif_files = sorted(glob.glob(os.path.join(tiles_folder, '*.tif')))
    merge_tiles(tif_files, mosaic_vrt)
    
    # Resample Mosaic
    print("Resampling mosaic...")
    resample_mosaic(mosaic_vrt, mosaic_tif)
    
    
    print("Ploting resampled mosaic...")
    sm_max = 0.382
    sm_min = 0.143
    
    plot_tif(mosaic_tif, output_file, sm_min, sm_max)
