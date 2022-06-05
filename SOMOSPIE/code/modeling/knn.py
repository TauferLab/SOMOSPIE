#!/usr/bin/env python3

## Script KKNN 
## PREPARED BY PAULA OLAYA (UTK) TO MICHELA TAUFER, 2021
## Modified by Leobardo Valera, 2021

## Commandline example: 
## ./2b-kknn.py -t ../data/2012/t-postproc/6.2.csv -e ../data/2012/e-postproc/6.2.csv -o ../data/2012/example.csv -k 20

import numpy as np
import pandas as pd
import argparse
import pickle
from sklearn.neighbors import KNeighborsRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import RandomizedSearchCV
from sklearn.metrics import mean_squared_error


#Input arguments to execute the k-Nearest Neighbors Regression 
def get_parser():
    parser = argparse.ArgumentParser(description='Arguments and data files for executing Nearest Neighbors Regression.')
    parser.add_argument('-t', "--trainingdata", help='Training data')
    #parser.add_argument('-m', "--pathtomodel", help='Directory where the knn model will be saved')
    parser.add_argument('-k', "--maxK", help='Mamximum k to try for finding optimal model', default=20)
    parser.add_argument('-seed', "--seed", help='Seed for reproducibility purposed in random research grid', default=3)
    parser.add_argument('-e', "--evaluationdata", help='Evaluation data')
    parser.add_argument('-o', "--outputdata", help='Predictions')
    parser.add_argument('-l', "--log", help='Log file')
    parser.add_argument("-f", "--fff", help="a dummy argument to fool ipython", default="1")
    return parser 

#Translate from namespaces to Python variables 
def from_args_to_vars (args):	
    print("Reading training data from", args.trainingdata)
    training_data = pd.read_csv(args.trainingdata)
    col = list(training_data.columns)
    col[2] = 'z'
    training_data.columns = col
    #print(training_data)
    maxK = int(args.maxK)
    seed = int(args.seed)
    #pathtomodel = args.pathtomodel
    print("Reading evaluation data from", args.evaluationdata)
    evaluation_data = pd.read_csv(args.evaluationdata)
    output_data = args.outputdata
    # return training_data, pathtomodel, maxK, seed
    #return training_data, pathtomodel, maxK, seed, evaluation_data, output_data
    return training_data, maxK, seed, evaluation_data, output_data

def split_and_preprocess_trainingdata (training_data):
    x_train, x_test, y_train, y_test = train_test_split(training_data.loc[:,training_data.columns != 'z'], training_data.loc[:,'z'], test_size=0.1)
    #print(x_train,"\n",y_train,"TEST\n",x_test,y_test)
    ss = StandardScaler()
    x_train = ss.fit_transform(x_train)
    x_test = ss.transform(x_test)
    #print("SCALED")
    #print(x_train,"\n",y_train,"TEST\n",x_test,y_test)
    
    # Save scaler model so it can be reused for predicting
    #pickle.dump(ss, open(pathtomodel+'scaler.pkl', 'wb'))
    return(x_train, y_train, x_test, y_test, ss)

def random_parameter_search(knn, x_train, y_train, maxK, seed):
    # Dictionary with all the hyperparameter options for the knn model: n_neighbors, weights, metric
    params = {'n_neighbors': list(range(2,maxK)),
    	  'weights': ['uniform','distance', gaussian],
    	  'metric': ['euclidean','minkowski']
             }
    # Random search based on the grid of params and n_iter controls number of random combinations it will try
    # n_jobs=-1 means using all processors
    # random_state sets the seed for manner of reproducibility 
    params_search = RandomizedSearchCV(knn, params, verbose=1, cv=10, n_iter=50, random_state=seed, n_jobs=-1)
    params_search.fit(x_train,y_train)
    # Check the results from the parameter search  
    print(params_search.best_score_)
    print(params_search.best_params_)
    print(params_search.best_estimator_)
    return params_search.best_params_

def gaussian(dist, sigma = 4):
    # Input a distance and return its weight using the gaussian kernel 
    weight = np.exp(-dist**2/(2*sigma**2))
    return weight

def train_knn(x_train, y_train, maxK, seed, scalermodel):
    # Define initial model
    knn = KNeighborsRegressor()
    # Random parameter search of n_neighbors, weigths and metric
    best_params = random_parameter_search(knn, x_train, y_train, maxK, seed)
    # Based on selection build the new regressor
    knn = KNeighborsRegressor(n_neighbors=best_params['n_neighbors'], weights=best_params['weights'],
    				metric=best_params['metric'], n_jobs=-1)
    # Fit the new model to data
    knn.fit(x_train, y_train)
    # Save model
    #pickle.dump(knn, open(pathtomodel+'model.pkl', 'wb'))
    
    return knn

def validate_knn(knn, x_test, y_test):
    # Predict on x_test
    y_test_predicted = knn.predict(x_test)
    # Measure the rmse
    rmse = np.sqrt(mean_squared_error(y_test, y_test_predicted))
    # Print error	
    #print("Predictions of soil moisture:", y_test_predicted)
    #print("Original values of soil moisture:", y_test)
    print("The rmse for the validation is:", rmse)

def preprocess_evaluationdata (evaluation_data, ss):
    # Load ss model
    #ss = pickle.load(open(pathtomodel+'scaler.pkl', 'rb'))
    x_predict = ss.transform(evaluation_data)
    #print(x_predict)
    
    return(x_predict)

def predict_knn(x_predict, evaluation_data, output_data, knn):
    # Load knn regressor
    #knn = pickle.load(open(pathtomodel+'model.pkl', 'rb'))
    # Predict on evaluation data
    y_predict = knn.predict(x_predict)
    # Create dataframe with long, lat, soil moisture
    out_df = pd.DataFrame(data={'x':evaluation_data['x'].round(decimals=9), 'y':evaluation_data['y'].round(decimals=9), 'sm':y_predict})
    out_df = out_df.reindex(['x','y','sm'], axis=1)
    #Print to file predictions 
    out_df.to_csv(output_data, index=False, header=False)


if __name__ == "__main__":	
    parser=get_parser()
    args = parser.parse_args()
    training_data, maxK, seed, evaluation_data, output_data = from_args_to_vars(args)
    x_train, y_train, x_test, y_test, ss = split_and_preprocess_trainingdata (training_data)
    knn = train_knn(x_train, y_train, maxK, seed, ss)
    validate_knn(knn, x_test, y_test)
    x_predict = preprocess_evaluationdata (evaluation_data, ss)
    predict_knn(x_predict, evaluation_data, output_data, knn)
