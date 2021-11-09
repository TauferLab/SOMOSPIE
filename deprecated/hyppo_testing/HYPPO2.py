#!/usr/bin/env python3

# Code by Travis Johnston, 2017.
# Modified by Danny Rorabaugh, 2018.


import argparse, itertools, csv, random
import numpy as np
from scipy.special import comb # Use comb(n, r, exact=True) to return int instead of float.
from functools import reduce


### This function expects a list of coefficients for the polynomial in order: 
### This function expects the degree of the polynomial (integer).
### This function expects a point (list of floats) of where to evaluate the polynomial.
### This function returns the value of the polynomial evaluated at the point provided.
def evaluate_polynomial(coefficients, degree, point):
    if degree == 0:
        return coefficients[0]
    
    monomials = [ reduce(lambda a, b: a*b, x) for x in itertools.combinations_with_replacement([1.0] + point, degree) ]
    return sum( [ a[0]*a[1] for a in zip(coefficients, monomials) ] )


### independent_variable_points is a list of settings for the independent variables that were observed.
### dependent_variable_values is a list of observed values of the dependent variable.
### It is important that for each i the result of independent_variable_points[i] is stored as dependent_variable_values[i].
### degree is the degree of the polynomial to build.
### This function returns the list of coefficients of the best fit polynomial surface of degree "degree".
def determine_coefficients(independent_variable_points, dependent_variable_values, degree):
    X = []
    if degree > 0:
        for iv in independent_variable_points:
            X.append( [ reduce(lambda a, b: a*b, x) for x in itertools.combinations_with_replacement([1.0] + iv, degree) ] )
    else:
        X = [ [1] for iv in independent_variable_points ]
    X = np.array(X)
    Xt = np.transpose(X)
    Z = np.array(dependent_variable_values)
    coef = np.linalg.solve( np.dot(Xt, X), np.dot(Xt, Z) )
    return list( coef )


### data_points is a list of the observed independent variable settings.
### specific_points is one chosen setting of the independent variables.
### k is the number of nearest neighbors to find.
### scale indicates how the coordinates can/should be re-scaled before the distance metric is computed.
### For example, if the points are of the form (x, y) and x's are measured in 1's and y's are measured by 100's.
### Then, it may be desirable to multiply the x-values by 100 to bring them onto the same scale as the y-values.
### To do this, set scale=[100, 1]. The default for CONUS is [1, 2],
### since each degree latitude (y step) is about twice as long as each degree longitude (x step).
### This function returns a list of indices (in data_points) of the k nearest neighbors.
### If specific_point is among the data sampled in data points (distance < error) it is excluded from the neighbors.
def indices_of_kNN(data_points, specific_point, k, scale=[1, 2], error=.0001):
    
    scale = np.array(scale)
    scaled_data = [ np.array(x[:2])*scale for x in data_points ]
    specific_point = np.array(specific_point[:2])*scale

    distances = [ sum( (x - specific_point)**2 ) for x in scaled_data ]
    indices = np.argsort( distances, kind='mergesort' )[:k+1]

    if distances[indices[0]] < error:
        return indices[1:]
    else:
        return indices[:k]


### Variant of above for higher dimensional space.
### Pre-scaled data assumed.
def indices_of_kNN_ndim(data_points, specific_point, k):
    if len(data_points)==0:
        print("Error: data_points empty!")
        return False
    if len(data_points[0])!=len(specific_point):
        print("Error: specific_point not same dim as elements of data_points!")
        return False

    distances = [ sum( (x - specific_point)**2 ) for x in data_points ]
    indices = np.argsort( distances, kind='mergesort' )[:k]
    return indices


### Find the standard deviation of all columns of df
def compute_scale(df):
    return [col.std(ddof=0) for col in df.columns]


### independent_data_points is a list of the observed independent variables to build models from.
### dependent_data_points is a list of the observed dependent variables (in the same order).
### k is the number of folds or partitions to divide the data into.
### num_random_partitions is the number of times the data is randomly partitioned (for averaging over many runs).
### D is an explicit cap on degree.
def kfold_crossvalidation(independent_data_points, dependent_data_points, k, num_random_partitions, D=10):
    
    n = len(independent_data_points)                ### Number of data points.
    dim = len(independent_data_points[0])           ### Dimension of the data.
    size_of_smallest_learning_set = (n*k - n)//k    ### Used to constrain degree of polynomial.
    degree_cap = 0

    # The following guarantees that there is enough data to determine the coefficients uniquely.
    while ( comb(degree_cap + dim, dim, exact=True) < size_of_smallest_learning_set ) and ( degree_cap < D ):
        degree_cap += 1

    fold_sizes = [n//k]   ### Integer division rounds down.
    first_index = [0]     ### Index of first element of the fold in the indices list (below).
    for i in range(1, k):
        fold_sizes.append( (n - sum(fold_sizes))//(k - i) )
        first_index.append( first_index[i - 1] + fold_sizes[i - 1] )
    first_index.append(n)

    ### A list of 0's of same length as possible degrees.
    Total_SSE = [0]*degree_cap
    
    for iteration in range(num_random_partitions):

        ### Randomly partition the data into k sets as equally sized as possible.
        indices = list(range(n))
        ### Get a new random shuffling of the indices.
        random.shuffle(indices)
        Folds = [ indices[first_index[fold]:first_index[fold + 1]] for fold in range(k) ]
        
        for d in range(degree_cap):

            ### Build k models of degree d (each model reserves one set as testing set).
            for testing_fold in range(k):
                testing_independent_data = [ independent_data_points[i] for i in Folds[testing_fold] ]
                testing_dependent_data = [ dependent_data_points[i] for i in Folds[testing_fold] ]
                
                model_independent_data = []
                model_dependent_data = []
                for fold in range(k):
                    if fold != testing_fold:
                        model_independent_data += [ independent_data_points[i] for i in Folds[fold] ]
                        model_dependent_data += [ dependent_data_points[i] for i in Folds[fold] ]
                
                ### Get the polynomial built from the model data of degree d.
                try:
                    coefficients = determine_coefficients( model_independent_data, model_dependent_data, d )
                
                    ### Predict the testing points and add the error to the Total_SSE[d].
                    for x, z in zip(testing_independent_data, testing_dependent_data):
                        ### The square of the difference between polynomial prediction and observed value (z) at x.
                        Total_SSE[d] += (evaluate_polynomial(coefficients, d, x) - z)**2    
                    #print(f"d: {d}; Total_SSA[d]: {Total_SSE[d]}; \ncoefficients: {coefficients}\n")

                except:
                    Total_SSE[d] += 99999999999        ### Basically, this d was too big.

    ### Return index of minimum Total_SSE.
    ### Note: Total_SSE[i] corresponds to polynomial of degree i.
    winning_degree = Total_SSE.index(min(Total_SSE))
    #print(f"n: {n}; dim: {dim}; degree_cap: {degree_cap}; winning_degree: {winning_degree}; \nTotal_SSE: {Total_SSE}\n")
    
    return winning_degree


### Ideal for small sample sizes
def leave_one_out_crossvalidation(independent_data_points, dependent_data_points):
    return kfold_crossvalidation(independent_data_points, dependent_data_points, len(independent_data_points), 1)


def model_at_point(x, Independent_Data, Dependent_Data, K, model="HYPPO", spatialVars=2): 

            ### Find Nearest neighbors
            if spatialVars==2:
                indices_of_nearest_neighbors = indices_of_kNN(Independent_Data, x, K)
            else:
                indices_of_nearest_neighbors = indices_of_kNN_ndim(Independent_Data, x, K)

            ### Select the data associated with the nearest neighbors for use with modeling
            selected_independent_data = [ Independent_Data[i] for i in indices_of_nearest_neighbors ]
            selected_dependent_data = [ Dependent_Data[i] for i in indices_of_nearest_neighbors ]

            ### Determine the best polynomial degree
            if model == "KNN":
                ### Setting the degree to 0 forces us to just average the nearest neighbors.
                ### This is exactly kNN (a degree 0 polynomial).
                degree = 0
        
            elif model == "SBM":
                degree = kfold_crossvalidation(selected_independent_data, selected_dependent_data, 10, 10)
            
            elif model=="HYPPO":
                degree = leave_one_out_crossvalidation(selected_independent_data, selected_dependent_data)

            else:
                raise ValueError(f"\"{model}\" is not a valid model.")

            ### Compute the coefficients of the "best" polynomial of degree degree.
            coefficients = determine_coefficients(selected_independent_data, selected_dependent_data, degree)

            ### Using the surface, predict the value of the point.
            z = evaluate_polynomial(coefficients, degree, x)
            
            #if degree > 0:
            #    print(f"x: {x}; \nindices_of_nearest_neighbors: {indices_of_nearest_neighbors}; \ndegree: {degree}; coefficients: {coefficients}; \nz: {z}\n")
            return (z,degree)


### input1 and input2 are arrays or ndarrays.
### Columns index 0 and 1 of input1 and input2 are the x/y-coordinates.
### input1 should have 1 more column than input2, the column with the dependent variable.
### depIndex is the index of the dependent variable column in input1.
### model is one of ["HYPPO", "KNN", "SBM"].
### Implementations of HYPPO and SBM are not well-suited for high dimensional data.
### k is the number of nearest neighbors for HYPPO or KNN (is overridden for SBM).
def main(input1, input2, depIndex=2, model="HYPPO", k=6, spatialVars=2):

    Independent_Data = []
    Dependent_Data = []
    for line in input1:
        numbers = list(line)
        Dependent_Data.append(numbers.pop(depIndex))
        Independent_Data.append(np.array(numbers))
   
    scale = np.std(Independent_Data, axis=0)
    print(scale)

    print(f"Dependent_Data is an array of length {len(Dependent_Data)} with first elements:\n{Dependent_Data[:5]}\n")
    print(f"Independent_Data is a length-{len(Independent_Data)} array of arrays with first element:\n{Independent_Data[0]}\n")    
    
    if spatialVars>2:
        Independent_Data = [row/scale for row in Independent_Data]
        print(f"Independent_Data is a now an array of arrays with first element:\n{Independent_Data[0]}\n")    
 
    # Set K, the number of nearest neighbors to use when building the model.
    if model == "SBM":
        K = len(Dependent_Data) - 1
    else:
        K = k
    print(f"Each local model will be generated with {K} nearest neighbors.\n")

    output = []
    for x in input2:
        a = x[0]
        b = x[1]
        if spatialVars>2:
            x = np.array(x)/scale

        #print(f"x: {x}; K: {K}; model: {model}")
        (z,d) = model_at_point(x, Independent_Data, Dependent_Data, K, model, spatialVars) 
        
        output.append([a, b, z, d])
    
    return output


if __name__ == "__main__":    
    parser = argparse.ArgumentParser()
    parser.add_argument( "fileName", 
                         help="The path to the csv file containing the training data.")
    parser.add_argument( "-m", "--model", 
                         help="The type of model to build.",
                         choices=["HYPPO", "KNN", "SBM"], default="HYPPO")
    parser.add_argument( "-k", "--k", 
                         help="The number of nearest neighbors to use for either the KNN or HYPPO model.",
                         type=int, default=6)
    parser.add_argument( "-e", "--eval", 
                         help="Name of file where the evaluation points are stored.")
    parser.add_argument( "-o", "--out",
                         help="Name of file where prediction is to be stored.")
    parser.add_argument( "-i", "--depIndex", 
                         help="Index of column in fileName with dependent variable to be tested for building a model.",
                         type=int, default=2)
    parser.add_argument( "-r", "--headerRows", 
                         help="Number of rows to ignore, being header row(s).", 
                         type=int, default=1)
    parser.add_argument( "-d", "--delimiter",
                         help="Delimiter of fileName and eval.",
                         default=",")
    parser.add_argument( "-v", "--variables",
                         help="Number of independent variables for nearest neighbor selection; if unspecified, will use only first two columns in the file.",
                         type=int, default=2)
    args=parser.parse_args()

    ### args.fileName contains the data from which to build the model.
    ### It is expected that the file be comma separated and have a header row.
    ### It is also expected that the format be x, y, z, c1, ..., cm.
    ### Where x and y are geographic coordinates, z is the observed dependent variable,  
    ### and c1, ..., cm are additional independent variables.
    ### args.eval should be the same format, but lacking the z column.

    original_values = np.loadtxt(args.fileName, delimiter=args.delimiter, skiprows=args.headerRows)
    print(f"\n{len(original_values)} lines of original data have been loaded from {args.fileName}.\n")

    values_to_model = np.loadtxt(args.eval, delimiter=args.delimiter, skiprows=args.headerRows)
    print(f"\n{len(values_to_model)} lines of evaluation data have been loaded from {args.eval}.\n")

    output = main(original_values, values_to_model, depIndex=args.depIndex, model=args.model, k=args.k, spatialVars=args.variables)

    np.savetxt(args.out, output, delimiter=",")

