import numpy as np
import pandas as pd
import argparse
import pickle
from sklearn.neighbors import KNeighborsRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error


#Input arguments to execute the k-Nearest Neighbors Regression 
parser = argparse.ArgumentParser(description='Arguments and data files for executing Nearest Neighbors Regression.')
parser.add_argument('-m', "--pathtomodel", help='Directory where the knn model will be saved')
parser.add_argument('-e', "--evaluationdata", help='Evaluation data')
parser.add_argument('-o', "--outputdata", help='Predictions')
args = parser.parse_args()

#Translate from namespaces to Python variables 
def from_args_to_vars (args):	
	print("Reading evaluation data from", args.evaluationdata)
	evaluation_data = pd.read_csv(args.evaluationdata)
	print(evaluation_data)
	pathtomodel = args.pathtomodel
	output_data = args.outputdata
	return evaluation_data, pathtomodel, output_data

def preprocess_evaluationdata (evaluation_data, pathtomodel):
	# Load ss model
	ss = pickle.load(open(pathtomodel+'scaler.pkl', 'rb'))
	x_predict = ss.transform(evaluation_data)
	print(x_predict)
	
	return(x_predict)

def predict_knn(x_predict, evaluation_data, output_data, pathtomodel):
	# Load knn regressor
	knn = pickle.load(open(pathtomodel+'model.pkl', 'rb'))
	# Predict on evaluation data
	y_predict = knn.predict(x_predict)
	# Create dataframe with long, lat, soil moisture
	out_df = pd.DataFrame(data={'x':evaluation_data['x'].round(decimals=9), 'y':evaluation_data['y'].round(decimals=9), 'sm':y_predict})
	# Print to file predictions 
	out_df.to_csv(output_data, index=False)
	
if __name__ == "__main__":	
	evaluation_data, pathtomodel, output_data = from_args_to_vars(args)
	x_predict = preprocess_evaluationdata (evaluation_data, pathtomodel)
	predict_knn(x_predict, evaluation_data, output_data, pathtomodel)





