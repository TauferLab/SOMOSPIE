# Models

IMPORTANT!

Every model script should work with .csv files in which
* the top row is the header data,
* the first two columns are the lat/lon coords, 
* the third column is the sm data,
* all other columns are covariates

    hyppo.py
    
        Travis and Danny's scipt for HYPPO, KNN, and SBM.
        
        Call with:
        hyppo.py -t IN_TRAIN -e IN_EVAL -l LOG_FILE -m MODEL -o OUT_PATH
        
        Arguments:
        IN_TRAIN        train file; path of .csv file
        IN_EVAL         eval file; path of .csv file with points to evaluate the model at,
                        or "0" (default) to output the model
        LOG_FILE        log file path,
                        or "0" (default) to print logging statements
        MODEL           HYPPO, KNN, or SBM
        OUT_PATH        out file path 

    knn.py
    
        This is Paula's knn script.
 
      Call with:
        knn.R -t IN_TRAIN -e IN_EVAL -l LOG_FILE -o OUT_PATH -k K_CAP

      Arguments:
        IN_TRAIN        train file; path of .csv file
        IN_EVAL         eval file; path of .csv file with points to evaluate the model at,
                        or "0" (default) to output the model
        LOG_FILE        log file path,
                        or "0" (default) to print logging statements
        OUT_PATH        out file path 
        


    rf.py
    
        This is Paula's random forests script. 
 
      Call with:
        knn.R -t IN_TRAIN -e IN_EVAL -l LOG_FILE -o OUT_PATH -k K_CAP

      Arguments:
        IN_TRAIN        train file; path of .csv file
        IN_EVAL         eval file; path of .csv file with points to evaluate the model at,
                        or "0" (default) to output the model
        LOG_FILE        log file path,
                        or "0" (default) to print logging statements
        OUT_PATH        out file path
