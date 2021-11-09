#!/usr/bin/env python3

# Code by Travis Johnston, 2017.
# Modified and parallelized by Danny Rorabaugh, 2018.


import argparse, csv, random
import numpy as np
### https://docs.python.org/3.1/library/itertools.html#itertools.combinations_with_replacement
from itertools import combinations_with_replacement as cwr 
from scipy.special import comb # Use comb(n, r, exact=True) to return int instead of float.
from time import time
import os


# Parallelization.
def init_parallel():
    print(f"There are {os.cpu_count()} cores, of which {len(os.sched_getaffinity(0))} are available.")

    import findspark
    findspark.init()
    # https://spark.apache.org/docs/0.9.0/api/pyspark/
    global SC
    from pyspark import SparkContext as SC
    #sc = SC.getOrCreate()
    #data = sc.parallelize(range(10))
    #print(data.collect())
    #sc.close()


### This function expects a list of coefficients for the polynomial in order: 
### This function expects the degree of the polynomial (integer).
### This function expects a point (list of floats) of where to evaluate the polynomial.
### This function returns the value of the polynomial evaluated at the point provided.
def evaluate_polynomial(coefficients, degree, point):
    if degree == 0:
        return coefficients[0]
    
    monomials = [ np.product(x) for x in cwr([1.0] + point, degree) ]
    return sum( [ a[0]*a[1] for a in zip(coefficients, monomials) ] )


### independent_variable_points is a list of settings for the independent variables that were observed.
### dependent_variable_values is a list of observed values of the dependent variable.
### It is important that for each i the result of independent_variable_points[i] is stored as dependent_variable_values[i].
### degree is the degree of the polynomial to build.
### This function returns the list of coefficients of the best fit polynomial surface of degree "degree".
def determine_coefficients(independent_variable_points, dependent_variable_values, degree):
    
    ### If degree==0, cwr returns [()], then np.product[()] is 1.0.
    A = [ [np.product(x) for x in cwr([1.0] + iv, degree)] for iv in independent_variable_points ]
    Z = np.array(dependent_variable_values)
    
    ### https://docs.scipy.org/doc/numpy/reference/generated/numpy.linalg.solve.html
    ### We need matrix A to be square to solve AX=Z for vector X with np.linalg.solve
    ### So multiply both sides on the left by the transpose of A. 
    At = np.transpose(A)
    AtA = np.dot(At, A)
    if np.linalg.det(AtA):
        coef = np.linalg.solve(AtA, np.dot(At, Z))
    else:
        print("Use hypppo if you want to be able to handle singular matrices.")
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
def indices_of_kNN_ndim(data_points, specific_point, k, scale=[]):
    if len(data_points)==0:
        print("Error: data_points empty!")
        return False
    if len(data_points[0])!=len(specific_point):
        print("Error: specific_point not same dim as elements of data_points!")
        return False

    if scale:
        if len(scale)!=len(specific_point):
            print("Error: scale specified, but of different length then data!")
            return False
        scale = np.array(scale)
        data_points = [ np.array(x)*scale for x in data_points ]
        specific_point = np.array(specific_point)*scale
    
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
    while ( comb(degree_cap + dim, dim, exact=True) <= size_of_smallest_learning_set ) and ( degree_cap < D ):
        degree_cap += 1

    fold_sizes = [n//k]   ### Integer division rounds down.
    first_index = [0]     ### Index of first element of the fold in the indices list (below).
    for i in range(1, k):
        fold_sizes.append( (n - sum(fold_sizes))//(k - i) )
        first_index.append( first_index[i - 1] + fold_sizes[i - 1] )
    first_index.append(n)

    ### A list of 0's of same length as possible degrees.
    Total_SSE = [0]*degree_cap
    
    indices = list(range(n))
    
    for iteration in range(num_random_partitions):
        ### Randomly partition the data into k sets as equally sized as possible.

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


### Main function for a single data point.
### This is the function that will be called independently many time.
### If this can be run on every element of a Spark RDD, we're golden.
def model_at_point(x, Independent_Data, Dependent_Data, K, model="HYPPO"):

            ### Find Nearest neighbors
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
                degree = kfold_crossvalidation(selected_independent_data, selected_dependent_data, K, 10)
            
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
def main(input1, input2, depIndex=2, model="HYPPO", k=6, indepStart=0, indepCount=2, scale=[], parallel=False):

    Independent_Data = []
    Dependent_Data = []
    for line in input1:
        numbers = list(line)
        Dependent_Data.append(numbers.pop(depIndex))
        Independent_Data.append(np.array(numbers[indepStart:indepStart+indepCount]))
        #Coordinate_Data.append(np.array(numbers[:2]))

    if scale:
        if len(scale)!=indepCount:
            print("Error: scale was specified, but isn't the same length as the sepcified number of independent variables!")
        scale = np.array(scale)
    else:
        scale = 1/np.std(Independent_Data, axis=0)
    print(scale)

    print(f"Dependent_Data is an array of length {len(Dependent_Data)} with first elements:\n{Dependent_Data[:5]}\n")
    print(f"Independent_Data is a length-{len(Independent_Data)} array of arrays with first element:\n{Independent_Data[0]}\n")    
    
    Independent_Data = [row*scale for row in Independent_Data]
    print(f"Independent_Data post-scaling is an array of arrays with first element:\n{Independent_Data[0]}\n")    
 
    ### Set K, the number of nearest neighbors to use when building the model.
    if model == "SBM":
        K = len(Dependent_Data) - 1
    else:
        K = k
    print(f"Each local model will be generated with {K} nearest neighbors.\n")

    t0 = time()
    
    if parallel:
        
        def MaP(x):
            a = x[0]
            b = x[1]
            x = np.array(x[indepStart:indepStart+indepCount])*scale
            (z,d) = model_at_point(x, Independent_Data, Dependent_Data, K, model)
            return [a, b, z, d]
            
        init_parallel()
        sc = SC.getOrCreate()
        data = sc.parallelize(input2)
        data = data.map(MaP)
        output = data.collect()
        sc.stop()
            
    else:
        
        output = []
    
        for x in input2:
            a = x[0]
            b = x[1]
            if spatialVars>2:
                x = np.array(x[:spatialVars])/scale

            #print(f"x: {x}; K: {K}; model: {model}")
            (z,d) = model_at_point(x, Independent_Data, Dependent_Data, K, model) 

            output.append([a, b, z, d])
    
    print(f"It took {time() - t0} seconds to perform model_at_point on all the evaluation points.")
    
    return output


'''
args_fileName = "test.csv"
args_delimiter = ","
args_headerRows = 1
args_eval = "eval.csv"
args_depIndex = 2
args_model = "HYPPO"
args_k = 6
args_variables = 2
args_skipVars = 0
args_scale = '1,2'
args_out = f"output{args_variables}d-{args_k}.csv"
args_parallel = True
'''

if __name__ == "__main__":    
    parser = argparse.ArgumentParser()
    parser.add_argument( "fileName", help="The path to the csv file containing the training data.")
    parser.add_argument( "-m", "--model", help="The type of model to build.", choices=["HYPPO", "KNN", "SBM"], default="HYPPO")
    parser.add_argument( "-k", "--k", help="The number of nearest neighbors to use for either the KNN or HYPPO model.", type=int, default=6)
    parser.add_argument( "-e", "--eval", help="Name of file where the evaluation points are stored.")
    parser.add_argument( "-o", "--out", help="Name of file where prediction is to be stored.")
    parser.add_argument( "-i", "--depIndex", help="Index of column in fileName with dependent variable to be tested for building a model.", type=int, default=2)
    parser.add_argument( "-r", "--headerRows", help="Number of rows to ignore, being header row(s).", type=int, default=1)
    parser.add_argument( "-d", "--delimiter", help="Delimiter of fileName and eval.", default=",")
    parser.add_argument( "-v", "--variables", help="Number of independent variables; if unspecified, will use only first two columns in the file.", type=int, default=2)
    parser.add_argument( "-s", "--skipVars", help="Number of independent variables to skip; e.g., 2 if you don't wish to use lon/lat.", type=int, default=0)
    parser.add_argument( "-S", "--scale", help="Specify the scale to multiply your independent variables by; for example -s0 -v2 -S1,2.")
    parser.add_argument( "-p", "--parallel", help="1 to run in parallel with Spark; 0 otherwise.", type=int, default=0)
    args=parser.parse_args()

    ### args.fileName contains the data from which to build the model.
    ### It is expected that the file be comma separated and have a header row.
    ### Default format is x, y, z, c1, ..., cm.
    ### Where x and y are geographic coordinates, z is the observed dependent variable,  
    ### and c1, ..., cm are additional independent variables.
    ### args.eval should be the same format, but lacking the z column.

if args.scale:
    scale = [float(s) for s in args.scale.split(',')]
else:
    scale = []

original_values = np.loadtxt(args.fileName, delimiter=args.delimiter, skiprows=args.headerRows)
print(f"\n{len(original_values)} lines of original data have been loaded from {args.fileName}.\n")

values_to_model = np.loadtxt(args.eval, delimiter=args.delimiter, skiprows=args.headerRows)
print(f"\n{len(values_to_model)} lines of evaluation data have been loaded from {args.eval}.\n")

output = main(original_values, values_to_model, depIndex=args.depIndex, model=args.model, 
              k=args.k, indepStart=args.skipVars, indepCount=args.variables, parallel=args.parallel, scale=scale)

np.savetxt(args.out, output, delimiter=",")
