#!/usr/bin/env python3

## Script KKNN 
## PREPARED BY PAULA OLAYA (UTK) TO MICHELA TAUFER, 2021
## Modified by Leobardo Valera, 2021

## Commandline example: 
## ./2c-rf.py -t ../data/2012/t-postproc/6.2.csv -e ../data/2012/e-postproc/6.2.csv -o ../data/2012/example.csv 

import numpy as np
import pandas as pd
import argparse
import pickle
from sklearn.ensemble import RandomForestRegressor
from sklearn.datasets import make_regression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import RandomizedSearchCV
from sklearn.metrics import mean_squared_error

def get_parser():
    #Input arguments to execute the k-Nearest Neighbors Regression 
    parser = argparse.ArgumentParser(description='Arguments and data files for executing Random forest.')
    parser.add_argument('-t', "--trainingdata", help='Training data')
    parser.add_argument('-e', "--evaluationdata", help='Evaluation data')
    parser.add_argument('-o', "--outputdata", help='Predictions')
    parser.add_argument('-l', "--log", help='Log file')
    parser.add_argument('-maxtree', "--maxtree", help='Maximum number of trees to try for finding optimal model', default=2000)
    parser.add_argument('-seed', "--seed", help='Seed for reproducibility purposed in random research grid', default=3)
    return parser

#Translate from namespaces to Python variables 
def from_args_to_vars (args):	
    print("Reading training data from", args.trainingdata)
    training_data = pd.read_csv(args.trainingdata)
    col = list(training_data.columns)
    col[2] = 'z'
    training_data.columns = col
    #print(training_data)
    #print(maxtree)
    seed = int(args.seed)
    maxtree = int(args.maxtree)
    #print(seed)
    print("Reading evaluation data from", args.evaluationdata)
    evaluation_data = pd.read_csv(args.evaluationdata)
    #print(evaluation_data)

    output_data = args.outputdata 

    return training_data, evaluation_data, output_data, maxtree, seed


def split_and_preprocess_trainingdata (training_data):
    x_train, x_test, y_train, y_test = train_test_split(training_data.loc[:,training_data.columns != 'z'], training_data.loc[:,'z'], test_size=0.1)
    #print(x_train,"\n",y_train,"TEST\n",x_test,y_test)
    ss = StandardScaler()
    x_train = ss.fit_transform(x_train)
    x_test = ss.transform(x_test)
    
    return x_train, y_train, x_test, y_test, ss

def random_parameter_search(rf, x_train, y_train, maxtree, seed):
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
    params = {'n_estimators': n_estimators,
                   'max_features': ['sqrt'],
                   'max_depth': [20,50,70],
                   'bootstrap': [True],
                   'n_jobs':[-1]}
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


def train_rf(x_train, y_train, maxtree, seed):
    # Define initial model
    rf = RandomForestRegressor()
    # Random parameter search for rf
    #maxtree = 2000
    #seed    = 3
    best_rf = random_parameter_search(rf, x_train, y_train, maxtree, seed)
    
    return best_rf

def validate_rf(rf, x_test, y_test):
    # Predict on x_test
    y_test_predicted = rf.predict(x_test)
    # Measure the rmse
    rmse = np.sqrt(mean_squared_error(y_test, y_test_predicted))
    # Print error	
    #print("Predictions of soil moisture:", y_test_predicted)
    #print("Original values of soil moisture:", y_test)
    print("The rmse for the validation is:", rmse)

def preprocess_evaluationdata (evaluation_data,ss):
    # Load ss model
    x_predict = ss.transform(evaluation_data)
    #print(x_predict)
    
    return(x_predict)

def predict_rf(x_predict, evaluation_data, output_data, rf):
    # Predict on evaluation data
    y_predict = rf.predict(x_predict)
    # Create dataframe with long, lat, soil moisture
    out_df = pd.DataFrame(data={'x':evaluation_data['x'].round(decimals=9), 'y':evaluation_data['y'].round(decimals=9), 'sm':y_predict})
    out_df = out_df.reindex(['x','y','sm'], axis=1)
    # Print to file predictions 
    out_df.to_csv(output_data, index=False, header=False)

if __name__ == "__main__":
    parser=get_parser()
    args = parser.parse_args()
    training_data, evaluation_data, output_data, maxtree, seed = from_args_to_vars(args)
    x_train, y_train, x_test, y_test, ss = split_and_preprocess_trainingdata (training_data)
    rf = train_rf(x_train, y_train, maxtree, seed)
    validate_rf(rf, x_test, y_test)
    x_predict = preprocess_evaluationdata (evaluation_data, ss)
    predict_rf(x_predict, evaluation_data, output_data, rf)
