#!/usr/bin/env python3

import numpy as np
import pandas as pd
import argparse
import pickle
from osgeo import gdal
from sklearn.neighbors import KNeighborsRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import RandomizedSearchCV
from sklearn.metrics import mean_squared_error


def get_parser():
    parser = argparse.ArgumentParser(description='Arguments and data files for executing Nearest Neighbors Regression or Random Forest.')
    parser.add_argument('-i', "--infile", help='Training GeoTIF file.')
    parser.add_argument('-o', "--outfile", help='Path where the model will be saved')
    parser.add_argument('-s', "--scfile", help='Path where the scaler will be saved')
    parser.add_argument('-m', "--model", help='Model to train (knn or rf)', default='knn')
    parser.add_argument('-k', "--maxK", help='Maximum k to try for finding optimal model (KNN)', default=20)
    parser.add_argument('-t', "--maxtree", help='Maximum number of trees to try for finding optimal model (RF)', default=2000)
    parser.add_argument('-e', "--seed", help='Seed for reproducibility purposed in random research grid', default=3)
    return parser 

#Translate from namespaces to Python variables 
def from_args_to_vars (args):	
    train_file = args.infile
    model_file = args.outfile
    scaler_file = args.scfile
    model = args.model
    maxK = int(args.maxK)
    maxtree = int(args.maxtree)
    seed = int(args.seed)
    return train_file, model_file, scaler_file, model, maxK, maxtree, seed


def tif2df(raster_file):
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

    band_names = get_band_names(raster_file)

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
    # df.to_csv(output_file, index=None)
    return df


def get_band_names(raster):
    ds = gdal.Open(raster, 0)
    names = []
    for band in range(ds.RasterCount):
        b = ds.GetRasterBand(band + 1)
        names.append(b.GetDescription())
    ds = None
    return names


def load_ds(train_file, scaler_file):
    train_data = tif2df(train_file)
    print(train_data.shape)

    x_train, x_val, y_train, y_val = train_test_split(train_data.loc[:,train_data.columns != 'z'], train_data.loc[:,'z'], test_size=0.1)

    ss = StandardScaler()
    x_train = ss.fit_transform(x_train)
    x_val = ss.transform(x_val)
    pickle.dump(ss, open(scaler_file, 'wb'))
    return x_train, x_val, y_train, y_val


def gaussian(dist, sigma = 4):
    # Input a distance and return its weight using the gaussian kernel 
    weight = np.exp(-dist**2/(2*sigma**2))
    return weight


def random_parameter_search_knn(model, x_train, y_train, maxK, seed):
    # Dictionary with all the hyperparameter options for the knn model: n_neighbors, weights, metric
    params = {'n_neighbors': list(range(2,maxK)),
    	  'weights': ['uniform','distance', gaussian],
    	  'metric': ['euclidean','minkowski']
             }
    # Random search based on the grid of params and n_iter controls number of random combinations it will try
    # n_jobs=-1 means using all processors
    # random_state sets the seed for manner of reproducibility 
    params_search = RandomizedSearchCV(model, params, verbose=1, cv=10, n_iter=50, random_state=seed, n_jobs=-1)
    params_search.fit(x_train,y_train)
    # Check the results from the parameter search  
    print(params_search.best_score_)
    print(params_search.best_params_)
    print(params_search.best_estimator_)
    return params_search.best_params_


def train_knn(x_train, y_train, maxK, seed, model_file):
    # Define initial model
    knn = KNeighborsRegressor()
    # Random parameter search of n_neighbors, weigths and metric
    best_params = random_parameter_search_knn(knn, x_train, y_train, maxK, seed)
    # Based on selection build the new regressor
    knn = KNeighborsRegressor(n_neighbors=best_params['n_neighbors'], weights=best_params['weights'], metric=best_params['metric'], n_jobs=-1)
    # Fit the new model to data
    knn.fit(x_train, y_train)
    # Save model
    pickle.dump(knn, open(model_file, 'wb'))
    
    return knn


def random_parameter_search_rf(rf, x_train, y_train, maxtree, seed):
    # Number of trees in random forest
    n_estimators = [int(x) for x in np.linspace(start = 300, stop = maxtree, num = 100)]
    # Number of features to consider at every split
    max_features = ['auto', 'sqrt']
    # Maximum number of levels in tree
    max_depth = [int(x) for x in np.linspace(10, 110, num = 11)]
    max_depth.append(None)
    # Minimum number of samples required to split a node
    min_samples_split = [2, 5, 10]
    # Minimum number of samples required at each leaf node
    min_samples_leaf = [1, 2, 4]
    # Method of selecting samples for training each tree
    bootstrap = [True, False]# Create the random grid
    params = {'n_estimators': n_estimators, 'max_features': ['sqrt'], 'max_depth': [20,50,70], 'bootstrap': [True], 'n_jobs':[-1]}
    # Random search based on the grid of params and n_iter controls number of random combinations it will try
    # n_jobs=-1 means using all processors
    # random_state sets the seed for manner of reproducibility 
    params_search = RandomizedSearchCV(rf, params, verbose=1, cv=10, n_iter=10, random_state=seed, n_jobs=-1)
    params_search.fit(x_train,y_train)
    # Check the results from the parameter search  
    print(params_search.best_score_)
    print(params_search.best_params_)
    print(params_search.best_estimator_)
    return params_search.best_estimator_


def train_rf(x_train, y_train, maxtree, seed, model_file):
    # Define initial model
    rf = RandomForestRegressor()
    # Random parameter search for rf
    #maxtree = 2000
    #seed    = 3
    best_rf = random_parameter_search_rf(rf, x_train, y_train, maxtree, seed)
    pickle.dump(best_rf, open(model_file, 'wb'))
    
    return best_rf


def validate_model(model, x_val, y_val):
    # Predict on x_test
    y_predicted = model.predict(x_val)
    # Measure the rmse
    rmse = np.sqrt(mean_squared_error(y_val, y_predicted))
    # Print error	
    print("The rmse for the validation is:", rmse)


if __name__ == "__main__":	
    parser = get_parser()
    args = parser.parse_args()
    train_file, model_file, scaler_file, model, maxK, maxtree, seed = from_args_to_vars(args)
    
    x_train, x_val, y_train, y_val = load_ds(train_file, scaler_file)

    if model == 'knn':
        model = train_knn(x_train, y_train, maxK, seed, model_file)
    elif model == 'rf':
        model = train_rf(x_train, y_train, maxtree, seed, model_file)

    validate_model(model, x_val, y_val)
