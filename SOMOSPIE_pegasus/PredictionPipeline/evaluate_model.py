#!/usr/bin/env python3

import argparse
import pickle
import numpy as np
import os
from osgeo import gdal


def get_parser():
    parser = argparse.ArgumentParser(description='Arguments and data files for executing Nearest Neighbors Regression.')
    parser.add_argument('-i', "--infile", help='Evaluation data')
    parser.add_argument('-o', "--outfile", help='File where predictions will be saved')
    parser.add_argument('-s', "--scfile", help='File with scaler')
    parser.add_argument('-m', "--modelfile", help='file with model', default='knn')
    return parser 

#Translate from namespaces to Python variables 
def from_args_to_vars (args):	
    evaluation_file = args.infile
    out_file = args.outfile
    scaler_file = args.scfile
    model_file = args.modelfile
    return evaluation_file, model_file, scaler_file, out_file


def get_band_names(raster):
    ds = gdal.Open(raster, 0)
    names = []
    for band in range(ds.RasterCount):
        b = ds.GetRasterBand(band + 1)
        names.append(b.GetDescription())
    ds = None
    return names


def tif2arr(raster_file):
    ds = gdal.Open(raster_file, 0)
    xmin, res, _, ymax, _, _ = ds.GetGeoTransform()
    xsize = ds.RasterXSize
    ysize = ds.RasterYSize
    xstart = xmin + res / 2
    ystart = ymax - res / 2

    x = np.arange(xstart, xstart + xsize * res, res, dtype=np.single)
    y = np.arange(ystart, ystart - ysize * res, -res,dtype=np.single)
    x = np.tile(x[:xsize], ysize)
    y = np.repeat(y[:ysize], xsize)

    n_bands = ds.RasterCount
    data = np.zeros((x.shape[0], n_bands), dtype=np.single)
    for k in range(1, n_bands + 1):
        band = ds.GetRasterBand(k)
        data[:, k-1] = band.ReadAsArray().flatten().astype(np.single)
        
    data = np.column_stack((x, y, data))
    del x, y
    data = data[~np.isnan(data).any(axis=1)]
    return data


def load_ds(evaluation_file, scaler_file):
    evaluation_data = tif2arr(evaluation_file) 
    ss = pickle.load(open(scaler_file, 'rb'))
    x_predict = ss.transform(evaluation_data)
    evaluation_data = evaluation_data[:,0:2]
    return x_predict, evaluation_data


def predict(x_predict, evaluation_data, out_file, model_file):
    model = pickle.load(open(model_file, 'rb'))
    # Predict on evaluation data
    y_predict = model.predict(x_predict)
    
    evaluation_data = np.column_stack((evaluation_data, y_predict))
    np.savetxt(out_file, evaluation_data, fmt='%.7f', header='x,y,z', delimiter=',', comments='')


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
        <GeometryField encoding="PointFromColumns" x="x" y="y" z="z"/>\n \
    </OGRVRTLayer>\n \
</OGRVRTDataSource>'.format('predictions', input_file)) # https://gdal.org/programs/gdal_grid.html#gdal-grid
    f.close()
    
    rasterize_options = gdal.RasterizeOptions(xRes=xres, yRes=yres, attribute='z', noData=np.nan, outputType=gdal.GDT_Float32, creationOptions=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=YES'], callback=gdal.TermProgress_nocb)
    r = gdal.Rasterize(output_file, vrt_file, options=rasterize_options)
    r = None
    os.remove(vrt_file)


if __name__ == "__main__":
    parser = get_parser()
    args = parser.parse_args()
    evaluation_file, model_file, scaler_file, out_file = from_args_to_vars(args)

    print("Loading dataset...")
    x_predict, evaluation_data = load_ds(evaluation_file, scaler_file)

    band_names = get_band_names(evaluation_file)
    print("Band names: ", band_names)

    print("Running model to get predictions...")
    predict(x_predict, evaluation_data, './predictions.csv', model_file)

    ds = gdal.Open(evaluation_file)
    gt = ds.GetGeoTransform()
    print("Running rasterize...")
    rasterize('./predictions.csv', out_file, gt[1], gt[5])

    os.remove('./predictions.csv')

