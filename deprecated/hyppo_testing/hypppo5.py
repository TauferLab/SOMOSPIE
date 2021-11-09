#!/usr/bin/env python3

# Code by Travis Johnston, 2017.
# Modified and parallelized by Danny Rorabaugh, 2018/9.
# HYbrid Parallel Piecewise POlynomial.


import argparse, csv, random
import numpy as np
### https://docs.python.org/3.1/library/itertools.html#itertools.combinations_with_replacement
from itertools import combinations_with_replacement as cwr 
from itertools import chain
from time import time
### https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Lasso.html
from sklearn.linear_model import Lasso
from os import cpu_count, sched_getaffinity
from scipy.special import comb


# Function for logging to specified file, or printing if no file given.
def log(item, file=""):
    if file:
        with open(file, "a") as log_file:
            log_file.write(f"{item}")
    else:
        print(item)


# Parallelization initialization.
def init_parallel():
    print(f"There are {cpu_count()} cores, of which {len(sched_getaffinity(0))} are available.")

    import findspark
    findspark.init()
    # https://spark.apache.org/docs/0.9.0/api/pyspark/
    global SC
    from pyspark import SparkContext as SC


# This function expects:
# * a list of coefficients for the polynomial in order: 
# * the degree of the polynomial (integer).
# * a point (list of floats) of where to evaluate the polynomial.
# This function returns the value of the polynomial evaluated at the point provided.
def evaluate_polynomial(coefficients, degree, point):
    if degree == 0:
        return coefficients[0]
    
    monomials = [ np.product(x) for x in cwr(chain([1.0], point), degree) ]
    return sum( [ a[0]*a[1] for a in zip(coefficients, monomials) ] )


# Given a list coefs of coefficients, and polynomial dimension n and degree d, 
# This returns the number of non-zero monomials of each degree up to d.
def degree_counts(coefs, n, d):
    i = 0
    tallies = []
    for deg in range(d + 1):
        #print(len(coefs), n, d, i, deg)
        terms = comb(n, deg, exact=True, repetition=True)
        # Quick check to make sure coefs is still as long as it needs to be for given n and d
        if (i + terms) > len(coefs):
            print(coefs, n, d, tallies, i, terms)
            return False
        tallies.append(np.count_nonzero(coefs[i:(i + terms)]))
        i += terms
    #print(d, coefs, tallies, len(coefs), i)
    return tallies


# This function uses the Lasso method with a dynamically modified penalty
# to find which monomials should be used for polynomial construction.
# The target number of monomials is from bottom to top. 
def determine_terms(A, Z, bottom, top, init_alpha=1.0, min_alpha=2**(-10), try_lstsq=False):
    if (bottom > top):
        raise ValueError(f"Error! low must be less than or equal to high, but you gave {low} and {high}.")
    high = top
    low = bottom
    
    if try_lstsq:
        # First solve the system with least squares to see if we even need Lasso method.
        coef = np.linalg.lstsq(A, Z)[0]
        alpha = 2*init_alpha
    else:
        alpha = init_alpha
        Lassy = Lasso(alpha)
        coef = Lassy.fit(A, Z).coef_
    
    nonzeros = np.count_nonzero(coef)
        
    # The value of alpha is used by Lasso to penalize non-zero monomials
    # so, higher alpha corresponds to fewer terms.
    while (nonzeros < low) or (nonzeros > high):
        # If there are too few nonzero terms, cut the penalty alpha in half...
        alpha /= 2
        # ... but if there are too many, multiply the penatly by 3/2.
        if nonzeros > high:
            alpha *= 3
        # Use of 1/2 and 3/2 prevents repeated values of alpha.
            
        # If the penalty has gotten too small, something is wrong
        if alpha<2**(-10):
            # If possible, decriment low for a larger range of target values...
            if low>1:
                low -= 1
                alpha = init_alpha
            # ... otherwise, terminate the process and just use degree 0.
            else:
                coef = [np.mean(Z)]
                nonzeros = 1
                print("Alpha too small. Using degree=0.")
                break
        
        # Use lasso with the current alpha to solve the system
        Lassy = Lasso(alpha)
        coef = Lassy.fit(A, Z).coef_
        nonzeros = np.count_nonzero(coef)
        #print(f"low={low} ; nonzeros={nonzeros} ; high={high} ; alpha={alpha}")
    
    #print(f"With alpha={alpha}, we have selected {nonzeros} terms, where {low}<={nonzeros}<={high}.")
    #print(f"The largest |coefficient| is {max([abs(c) for c in coef if c])}")
    return [bool(c) for c in coef]


### independent_variable_points is a list of settings for the independent variables that were observed.
### dependent_variable_values is a list of observed values of the dependent variable.
### It is important that for each i the result of independent_variable_points[i] is stored as dependent_variable_values[i].
### degree is the degree of the polynomial to build.
### This function returns the list of coefficients of the best fit polynomial surface of degree "degree".
def determine_coefficients(independent_variable_points, dependent_variable_values, degree, lasso):
    
    ### If degree==0, cwr returns [()], then np.product[()] is 1.0.
    #print(degree, list(cwr(chain([1.0], independent_variable_points[0]), degree)))
    A = [ [np.product(x) for x in cwr(chain([1.0], iv), degree)] for iv in independent_variable_points ]
    Z = np.array(dependent_variable_values)
    Zbar = np.mean(Z)
    
    ### https://docs.scipy.org/doc/numpy/reference/generated/numpy.linalg.solve.html
    ### We need matrix A to be square to solve AX=Z for vector X with np.linalg.solve
    ### So multiply both sides on the left by the transpose of A. 
    At = np.transpose(A)
    AtA = np.dot(At, A)
    
    #if degree:
        #print(f"\nAt.shape: {At.shape}\nnp.linalg.matrix_rank(At): {np.linalg.matrix_rank(At)}")#\nA: {A}")
        #print(f"degree: {degree}\nlen(Z): {len(Z)}\nnp.mean(Z): {np.mean(Z)}\nZ: {Z}")
        #print(f"AtA.shape: {AtA.shape}\nnp.linalg.det(AtA): {np.linalg.det(AtA)}")
    
    # If the polynomial is degree zero, just the the average.
    if not degree:
        coef = [Zbar]
        
    # Otherwise, if the determinant of A.transpose() * A is non-zero, 
    #  we can solve the system with the least-squares method
    #elif abs(np.linalg.det(AtA))>2**(-20):
    elif np.linalg.matrix_rank(At) >= At.shape[0]:
        #print(f"AtA has determinent {np.linalg.det(AtA)}")
        coef = np.linalg.solve(AtA, np.dot(At, Z))
        #print(f"solve'd coef: {coef}")
        
    else:
        #### https://docs.scipy.org/doc/numpy/reference/generated/numpy.linalg.lstsq.html
        
        #rank = np.linalg.matrix_rank(At)
        #print(At.shape, rank)
        
        #print(f"lasso={lasso} ; len(A)={len(A)} ; len(Z)={len(Z)} ; degree={degree}")
            
        # If the system is under-determined, 
        # we need something like Lasso to reduce the number of terms, ...
        if lasso>0:
            # Shift the dep. var. values to be 0-mean.
            # This is because Lasso seems to be biased toward higher degree terms.
            Z = Z - Zbar
            
            # This creates a 0/1 array indicating which columns to use.
            coef = determine_terms(A, Z, len(Z) - 1, len(Z) - 1)
            #print(f"The number of terms of each degree are: {degree_counts(coefs, len(independent_variable_points[0]), degree)}")
            
            # Cut down A to only the terms/columns selected by Lasso
            A = [[a for a,i in zip(row,coef) if i] for row in A]
            
            # Apply the lstsq solving method to what's left, now that there aren't too many columns
            At = np.transpose(A)
            AtA = np.dot(At, A)
            neoef = np.linalg.solve(AtA, np.dot(At,Z))
            
            # Determine the indices of the terms selected by Lasso...
            nzs = [i for i in range(len(coef)) if coef[i]]
            # ... and use those indices to but the solved coefficients in the right place.
            for i,c in zip(nzs, neoef):
                coef[i] = c
            
            # Couteract the earlier shift of the dep. var. values.
            coef[0] += Zbar
            
            #print(f"lasso'd coef: {coef}")
        
        # ... or dangerously and naively use lstsq's built-in handling of underdetermined systems.
        else:
            coef = np.linalg.lstsq(A, Z)[0]#, rcond=None)[0]
        
            #print(f"lstsq'd coef: {coef}")
    
    return list( coef )


### data_points is a list of the observed independent variable settings.
### specific_points is one chosen setting of the independent variables.
### k is the number of nearest neighbors to find.
#### scale indicates how the coordinates can/should be re-scaled before the distance metric is computed.
### For example, if the points are of the form (x, y) and x's are measured in 1's and y's are measured by 100's.
### Then, it may be desirable to multiply the x-values by 100 to bring them onto the same scale as the y-values.
### To do this, set scale=[100, 1]. The default for CONUS is [1, 2],
### since each degree latitude (y step) is about twice as long as each degree longitude (x step).
### This function returns a list of indices (in data_points) of the k nearest neighbors.
def indices_of_kNN_ndim(data_points, specific_point, k, norm=2):#, scale=[]
    if len(data_points)==0:
        print("Error: data_points empty!")
        return False
    if len(data_points[0])!=len(specific_point):
        print("Error: specific_point not same dim as elements of data_points!")
        return False
    
##Scaling has been moved outside of this function
#    if scale:
#        if len(scale)!=len(specific_point):
#            print("Error: scale specified, but of different length then data!")
#            return False
#        scale = np.array(scale)
#        data_points = [ np.array(x)*scale for x in data_points ]
#        specific_point = np.array(specific_point)*scale
    
    distances = [ sum( (x - specific_point)**norm ) for x in data_points ]
    indices = np.argsort( distances, kind='mergesort' )[:k]
    return indices


### independent_data_points is a list of the observed independent variables to build models from.
### dependent_data_points is a list of the observed dependent variables (in the same order).
### k is the number of folds or partitions to divide the data into.
### num_random_partitions is the number of times the data is randomly partitioned (for averaging over many runs).
### D is a strict upper bound on degree.
### lasso is 0 to not use Lasso method, or a small positive float as a Lasso parameter.
def kfold_crossvalidation(independent_data_points, dependent_data_points, k, num_random_partitions, D, lasso):
    
    ### Number of data points.
    n = len(independent_data_points)
    
    ### A list of 0's of same length as possible degrees.
    Total_SSE = np.zeros(D)
    
    indices = list(range(n))
    
    for iteration in range(num_random_partitions):
        ### Randomly partition the data into k sets as equally sized as possible.

        ### Get a new random shuffling of the indices.
        random.shuffle(indices)
        Folds = [ [indices[i] for i in range(fold, n, k)] for fold in range(k) ]

        for d in range(D):

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
                    coefficients = determine_coefficients(model_independent_data, model_dependent_data, d, lasso)
                
                    ### Predict the testing points and add the error to the Total_SSE[d].
                    for x, z in zip(testing_independent_data, testing_dependent_data):
                        ### The square of the difference between polynomial prediction and observed value (z) at x.
                        Total_SSE[d] += (evaluate_polynomial(coefficients, d, x) - z)**2    
                    #print(f"d: {d}; Total_SSA[d]: {Total_SSE[d]}; \ncoefficients: {coefficients}\n")

                ### If there's an error, assume SSE too big to win
                except:
                    Total_SSE[d] += 2**10        

    ### Return index of minimum Total_SSE.
    ### Note: Total_SSE[i] corresponds to polynomial of degree i.
    winning_degree = np.argmin(Total_SSE)
    #print(f"n: {n}; D: {D}; winning_degree: {winning_degree}; \nTotal_SSE: {Total_SSE}\n")
    
    #print(f"Total_SSE: {Total_SSE}")
    return [winning_degree] + list(Total_SSE)


### Ideal for small sample sizes
def leave_one_out_crossvalidation(independent_data_points, dependent_data_points, D, lasso):
    return kfold_crossvalidation(independent_data_points, dependent_data_points, len(independent_data_points), 1, D, lasso)


### Used by model_at_point to determine local model degree/
def determine_model_degree(model, indep=[], dep=[], k=0, max_d=0, use_Lasso=False):
    if model == "KNN":
        ### Setting the degree to 0 forces us to just average the nearest neighbors.
        ### This is exactly kNN (a degree 0 polynomial).
        degree_with_errors = [0]

    elif model == "SBM":
        degree_with_errors = kfold_crossvalidation(indep, dep, k, 10, max_d, use_Lasso)

    elif args.model=="HYPPO":
        degree_with_errors = leave_one_out_crossvalidation(indep, dep, max_d, use_Lasso)

    else:
        raise ValueError(f"\"{args.model}\" is not a valid model.")
        
    return degree_with_errors
    

### Main function for a single data point.
### This is the function that will be called independently many time.
### If this can be run on every element of a Spark RDD, we're golden.
def model_at_point(x, Independent_Data, Dependent_Data, args):
    
            ### Find Nearest neighbors
            indices_of_nearest_neighbors = indices_of_kNN_ndim(Independent_Data, x, args.k, norm=args.norm)
            neighborhood = frozenset(indices_of_nearest_neighbors)
            
            # If a file has been given for saving neighborhoods, 
            #  then store x in its neighborhood.
            if args.nbrhdFile:
                if neighborhood in stored_nbrs:
                    stored_nbrs[neighborhood].append(x)
                else:
                    stored_nbrs[neighborhood] = [x]
            
            # If memoization is on 
            #  AND the coefficients have previously been computed for the current neighborhood,
            #  then we don't need to compute coefficients.
            if args.memoize and (neighborhood in stored_coefs):
                coefficients, degree = stored_coefs[neighborhood]
      
            else:
                ### Select the data associated with the nearest neighbors for use with modeling
                selected_independent_data = [ Independent_Data[i] for i in indices_of_nearest_neighbors ]
                selected_dependent_data = [ Dependent_Data[i] for i in indices_of_nearest_neighbors ]

                ### Determine the best polynomial degree
                degree_errors = determine_model_degree(args.model, indep=selected_independent_data, dep=selected_dependent_data, k=args.k, max_d=args.degree + 1, use_Lasso=args.Lasso)
                degree = degree_errors.pop(0)
                if args.errorFile:
                    stored_errors[neighborhood] = degree_errors
            
                ### Compute the coefficients of the "best" polynomial of degree degree.
                #print(type(selected_independent_data), type(selected_dependent_data), type(degree), type(args.Lasso))
                coefficients = determine_coefficients(selected_independent_data, selected_dependent_data, degree, args.Lasso)
                
                if args.degreeCountFile:
                    # Dumps a line with number of coefficients of each degree into a file.        
                    with open(args.degreeCountFile, "a+") as degreeCount_dump:
                        #print(coefs, len(independent_variable_points[0]), degree)
                        counts = degree_counts(coefficients, len(selected_independent_data[0]), degree)
                        print(counts)
                        degreeCount_dump.write(",".join([str(count) for count in counts]) + "\n")
                
                if args.memoize:
                    stored_coefs[neighborhood] = (coefficients, degree)
                
            #print(f"coefficients: {coefficients}")
            
            ### Using the surface, predict the value of the point.
            z = evaluate_polynomial(coefficients, degree, x)
            z = min(max(z, args.lowerBound), args.upperBound)
            
            #if degree > 0:
            #    print(f"x: {x}; \nindices_of_nearest_neighbors: {indices_of_nearest_neighbors}; \ndegree: {degree}; coefficients: {coefficients}; \nz: {z}\n")
            return [z, degree]


### input1 and input2 are arrays or ndarrays.
### Columns index 0 and 1 of input1 and input2 are the x/y-coordinates.
### input1 should have 1 more column than input2, the column with the dependent variable.
### depIndex is the index of the dependent variable column in input1.
### model is one of ["HYPPO", "KNN", "SBM"].
### Implementations of HYPPO and SBM are not well-suited for high dimensional data.
### k is the number of nearest neighbors for HYPPO or KNN (is overridden for SBM).
def main(input1, input2, args):
    
    indepStart=args.skipVars
    indepCount=args.variables

    # If data is to be flattened (raised to some positive power, presumably less than one)
    # then we need to shift it to all-positive values
    if args.Flatten:
        # Find the index of the minimum in ever column of the training data
        m1 = np.amin(input1, axis=0)
        # --except the dependent variable--
        m1 = np.delete(m1, args.depIndex)
        # and in every column of the testing data
        m2 = np.amin(input2, axis=0)
        # This shift forces every value of the predictors to be non-negative
        shift = np.minimum(m1,m2)[indepStart:indepStart+indepCount]
    else:
        #shift = np.zeros(indepCount)
        #print(np.mean(input1, axis=0))
        shift = np.mean(input1, axis=0)[indepStart:indepStart+indepCount]
        args.Flatten = 1

    # Extract from the training data the values for the dependent and independent variables. 
    # ToDo: Use pandas for importing train data and spliting into indep and dep.
    Independent_Data = []
    Dependent_Data = []
    for line in input1:
        numbers = list(line)
        Dependent_Data.append(numbers.pop(args.depIndex))
        Independent_Data.append(np.array(numbers[indepStart:indepStart+indepCount]))

    # Unless an array of scaling factors is specified, 
    # every column will be divided by the standard deviation of that column
    # to normalize the data.
    scale=args.scale
    if scale:
        if len(scale)!=indepCount:
            raise ValueError("Error: scale was specified, but isn't the same length as the sepcified number of independent variables!")
        scale = np.array(scale)
    else:
        scale = 1/np.std(Independent_Data, axis=0)
    log(f"scale: {scale}\n", file=args.logFile)

    log(f"Dependent_Data is an array of length {len(Dependent_Data)} with first elements:\n{Dependent_Data[:5]}\n", file=args.logFile)
    log(f"Independent_Data is a length-{len(Independent_Data)} array of arrays with first element:\n{Independent_Data[0]}\n", file=args.logFile)    
    
    # Perform any shifting, scaling, and flattening on the training data.
    # The same operations will also be performed on the evaluation data later as necessary.
    Independent_Data = [((row - shift)*scale)**args.Flatten for row in Independent_Data]
    log(f"Independent_Data post-scaling is an array of arrays with first element:\n{Independent_Data[0]}\n", file=args.logFile)
 
    ### Set K, the number of nearest neighbors to use when building the model.
    if args.model == "SBM":
        args.k = len(Dependent_Data) - 1
    log(f"Each local model will be generated with {args.k} nearest neighbors.\n", file=args.logFile)
    
    t0 = time()
     
    if args.memoize:
        global stored_coefs
        stored_coefs = {}
    
    if args.errorFile:
        global stored_errors
        stored_errors = {}
        
    if args.nbrhdFile:
        global stored_nbrs
        stored_nbrs = {}
    
    # This is the operation that will be performed on every point (x) in the eval data
    # to produce the prediction (local_model) at that point.
    def MaP(x):
        a = x[0]
        b = x[1]
        x = ((np.array(x[indepStart:indepStart+indepCount]) - shift)*scale)**args.Flatten
        local_model = model_at_point(x, Independent_Data, Dependent_Data, args)
            
        return [a, b] + local_model
    
    # Run the above operation on the eval data in parallel if directed to; ...
    if args.parallel:   
        init_parallel()
        sc = SC.getOrCreate()
        data = sc.parallelize(input2)
        data = data.map(MaP)
        output = data.collect()
        sc.stop()
    # ... otherwise, do it in serial with list comprehension.        
    else:
        output = [MaP(x) for x in input2]
    
    log(f"It took {time() - t0} seconds to perform model_at_point on all the evaluation points.\n", file=args.logFile)
    
    if args.errorFile:
        with open(args.errorFile, "w") as error_dump:
            for errors in stored_errors.values():
                error_dump.write(",".join([str(err) for err in errors]) + "\n")
        
    if args.nbrhdFile:
        with open(args.nbrhdFile, "w") as nbrhd_dump:
            for nbrs in stored_nbrs.values():
                nbrhd_dump.write(",".join([str(nbr) for nbr in nbrs]) + "\n")
    
    return output


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
    parser.add_argument( "-D", "--degree", help="Maximum polynomial degree. If -m KNN, this will be overrode with 0.", type=int, default=4)
    parser.add_argument( "-v", "--variables", help="Number of independent variables; if unspecified, will use only first two columns in the file.", type=int, default=2)
    parser.add_argument( "-s", "--skipVars", help="Number of independent variables to skip; e.g., 2 if you don't wish to use lon/lat.", type=int, default=0)
    parser.add_argument( "-S", "--scale", help="Specify the scale to multiply your independent variables by; for example -s0 -v2 -S1,2. Uses reciprocals of standard deviations if unspecified.")
    parser.add_argument( "-N", "--norm", help="Specify N for l_N norm; default is 2 (Euclidean). This is used for identifying the nearest neighbors.", type=int, default=2)
    parser.add_argument( "-p", "--parallel", help="1 to run in parallel with Spark; 0 otherwise (the default).", type=int, default=0)
    parser.add_argument( "-L", "--Lasso", help="Specify whether to use the Lasso value to limit the number of monomial in the local polynomial models. Default 1 is yes.", type=float, default=0)
    parser.add_argument( "-F", "--Flatten", help="Allow for sublinear models and lower degree by raising all predictors to a power p<1. Shifts predictors to 0-centered if 0; shifts predictors to strictly positive otherwise.", type=float, default=0)
    parser.add_argument( "-b", "--lowerBound", help="A firm lower bound for model output.", type=float, default=0)
    parser.add_argument( "-B", "--upperBound", help="A firm upper bound for model output.", type=float, default=1)
    parser.add_argument( "-l", "--logFile", help="The path for a log file; will print instead of logging if empty string (default).", default="")
    parser.add_argument( "-E", "--errorFile", help="The path for error data; will throw away if empty string (default).", default="")
    parser.add_argument( "-M", "--memoize", help="Store results for a given set of nearest neighbors in a global dictionary; default 1/True.", type=int, default="1")
    parser.add_argument( "-H", "--nbrhdFile", help="The path for neighborhoods; will not compute if empty string (default).", default="")
    parser.add_argument( "-C", "--degreeCountFile", help="The path for the number of coefficients of each degree; will not compute if empty string (default).", default="")

    args=parser.parse_args()

    ### args.fileName contains the data from which to build the model.
    ### It is expected that the file be comma separated and have a header row.
    ### Default format is x, y, z, c1, ..., cm.
    ### Where x and y are geographic coordinates, z is the observed dependent variable,  
    ### and c1, ..., cm are additional independent variables.
    ### args.eval should be the same format, but lacking the z column.
    
    ### Commandline test
    ### ./hypppo5.py ../data/2012/t-postproc/8.5.csv -e ../data/2012/e-postproc/8.5.csv -o out3.csv -v3 -s2 -p1 -D4 -k9
    
    if args.scale:
        args.scale = [float(s) for s in args.scale.split(',')]
    else:
        args.scale = []

    original_values = np.loadtxt(args.fileName, delimiter=args.delimiter, skiprows=args.headerRows)
    log(f"\n{len(original_values)} lines of original data have been loaded from {args.fileName}.\n", file=args.logFile)
    
    values_to_model = np.loadtxt(args.eval, delimiter=args.delimiter, skiprows=args.headerRows)
    log(f"{len(values_to_model)} lines of evaluation data have been loaded from {args.eval}.\n", file=args.logFile)

    output = main(original_values, values_to_model, args)

    # If the output filename isn't specified, 
    #  the name will be generated by the arguments, separated by _, 
    #  with a double (__) between the data arguements and the model parameters.
    if not args.out:
        args.out=f"{args.fileName.split('/')[-1]}_e-{args.eval.split('/')[-1]}_i-{args.depIndex}_s-{args.skipVars}_v-{args.variables}_m-{args.model}_k-{args.k}_D-{args.degree}_L-{args.Lasso}_p-{args.parallel}.csv"

    np.savetxt(args.out, output, delimiter=",", fmt='%.15f')
