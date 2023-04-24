from osgeo import gdal
import numpy as np
import pandas as pd
import math
from pathlib import Path
import tools


def tif2csv(ds, j, i, ncols, nrows, band_names=['elevation'], output_file='params.csv'):
    xmin, res, _, ymax, _, _ = ds.GetGeoTransform()
    xstart = xmin + res / 2
    ystart = ymax - res / 2

    x = np.arange(xstart + j*res, xstart + (j + ncols) * res, res)
    y = np.arange(ystart - i*res, ystart - (i + nrows) * res, -res)
    x = np.tile(x[:ncols], nrows)
    y = np.repeat(y[:nrows], ncols)

    n_bands = ds.RasterCount
    bands = np.zeros((x.shape[0], n_bands))
    for k in range(1, n_bands + 1):
        band = ds.GetRasterBand(k)
        data = band.ReadAsArray(j, i, ncols, nrows)
        data = data.astype(np.float32)
        data = np.ma.array(data, mask=np.equal(data, band.GetNoDataValue()))
        data = data.filled(np.nan)
        bands[:, k-1] = data.flatten()

    column_names = ['x', 'y'] + band_names
    stack = np.column_stack((x, y, bands))
    df = pd.DataFrame(stack, columns=column_names)
    df.dropna(inplace=True)
    if not df.empty:
        df.to_csv(output_file, index=None)


if __name__ == '__main__':
    # Arguments
    prefix = '/media/volume/sdb/terrain_parameters/CONUS_WGS84_10m_'
    parameters = ['aspect', 'elevation', 'hillshading', 'slope']
    n_tiles = 52 # 52x52

    csv_folder = '/media/volume/sdb/terrain_parameters/csv_files'
    csv_prefix = '/CONUS_WGS84_10m_'

    # Start computation
    files_stack = [prefix + param + '.tif' for param in parameters]
    raster_path = './stack.vrt'
    Path(csv_folder).mkdir(parents=True, exist_ok=True)

    print('Buiding stack...')
    tools.build_stack(files_stack, '')

    ds = gdal.Open(raster_path, 0)
    cols = ds.RasterXSize
    rows = ds.RasterYSize

    x_win_size = int(math.ceil(cols / n_tiles))
    y_win_size = int(math.ceil(rows / n_tiles))
    print('Window Size: ', x_win_size, y_win_size)

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

            tile_count += 1
            csv_file = csv_folder + csv_prefix + '{0:04d}'.format(tile_count) + '.csv'
            print('Converting tile {} to csv...'.format(tile_count))
            tif2csv(ds, j, i, ncols, nrows, band_names=parameters, output_file=csv_file)

    ds = None

