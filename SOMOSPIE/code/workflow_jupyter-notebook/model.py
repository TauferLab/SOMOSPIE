import pathlib
from os import listdir
from utils import *
from itertools import product as iterprod
from time import time


# This is a wrapper that handles a single call to any of the models
#      
#       Input file format
#         CSV format
#         Header row with NO spaces
#         1st column X (x-values)
#         2nd column Y (y-values)
#         3rd column in train file(s) is for SM
#         The rest of the columns should have matching headers in the train and eval files
           
#       Arguments:
#         REGION          a .csv file name WITHOUT it's directory
#                         OR if set to 0, will use all regions in TRAIN_DIR
#         TRAIN_DIR       the directory where a training file with the above name
#                         can be found
#         EVAL_DIR        the directory where an evaluation file with the above name
#                         can be found
#         MODELS          Dictionary with keys including HYPPO or MARIO or KNN or SBM ...
#                         and values are model-specific parameter-arglist dictionaries
#         OUT_DIR         the folder where the results should be stored
#         NOTE            An optional output suffix such as __pca in case you are 
#                         rerunning a model with processed data and need the output
#                         model file to have a distinguishing name
#
#     Every model script should work with .csv files in which
#         the top row is the header data,
#         the first two columns are the lat/lon coords, 
#         the third column is the sm data,
#         all other columns are covariates

def model(REGION, TRAIN_DIR, EVAL_DIR, OUT_DIR, MODELS, NOTE):

    HYPPO_MODEL = pathlib.Path("modeling/hyppo.py").resolve()
    KNN_MODEL = pathlib.Path("modeling/knn.py").resolve()
    RF_MODEL = pathlib.Path("modeling/rf.py").resolve()
    
    # If 0 is given instead of a specified region, 
    # create list of all regions in the TRAIN_DIR
    if not REGION:
        REGIONS = listdir(TRAIN_DIR)
    else:
        REGIONS = [REGION]
    #print(REGIONS)
    
    
    # Prepare the list of parameter combinations for each model
    suffixes = {}
    for MODEL in MODELS:
            paramdict = MODELS[MODEL]
            params = paramdict.keys()
            argums = paramdict.values()
            arg_combos = iterprod(*argums)
            # Don't print the following! It exhausts the generator.
            ##print(f"The possible combinations of arguments are: {list(arg_combos)}")
            bash_suffixes = [list(zip(params, ac)) for ac in arg_combos]
            file_suffixes = ["".join([f"{par}{arg}" for par, arg in bashix]) for bashix in bash_suffixes]
            suffixes[MODEL] = list(zip(bash_suffixes, file_suffixes))
    for REGION in REGIONS:
        # Specify train and predi files
        TR = TRAIN_DIR.joinpath(REGION)
        EV = EVAL_DIR.joinpath(REGION)
        
        # Create an output folder for the region, with predictions and logs subfolders
        OUT = OUT_DIR.joinpath(REGION).with_suffix("")
        PRED = OUT.joinpath(SUB_PRED)
        if not PRED.is_dir():
            PRED.mkdir(parents=True)
        
        for MODEL in MODELS:

            # The following has been extracted outside the REGIONS loop for a one-time creation
            #paramdict = MODELS[MODEL]
            #params = paramdict.keys()
            #argums = paramdict.values()
            #arg_combos = iterprod(*argums)
            ## Don't print the following! It exhausts the generator.
            ###print(f"The possible combinations of arguments are: {list(arg_combos)}")
            #
            #for ac in arg_combos:
            #    file_name = f"{MODEL}"#{NOTE}"
            #    bash_suffix = []
            #    for p, a in zip(params, ac):
            #        file_name += f"{p}{a}"
            #        bash_suffix.extend([p, a])
     
            for bash_suf, file_suf in suffixes[MODEL]:
                
                t0 = time()
                
                # Specify paths of output files
                file_name = MODEL + file_suf
                PRD = PRED.joinpath(f"{file_name}.csv")
                LOG = PRED.joinpath(f"{file_name}.log")
                
                # Open the log file and start writing
                with open(LOG, "w") as log:
                    log.write(f"t0={t0}\n")
                    log.write(f"Prediction file: {PRD}\n")
                    log.write(f"Log file: {LOG}\n")
                    log.write(f"{REGION} {MODEL}\n")
                    log.write(f"bash_suffix: {bash_suf}\n")

                if (MODEL in ["HYPPO", "KNN", "SBM"]):
                    bash_args = [HYPPO_MODEL, "-t", TR, "-e", EV, "-m", MODEL, "-o", PRD, "-l", LOG]
                elif (MODEL == "1NN"):
                    bash_args = [HYPPO_MODEL, "-t", TR, "-e", EV, "-m", "KNN", "-o", PRD, "-s", 0, "-S", "1,2", "-v", 2, "-k", 1, "-l", LOG]
                elif (MODEL == "KKNN"):
                    bash_args = [KNN_MODEL, "-t", TR, "-e", EV, "-o", PRD, "-l", LOG]
                elif (MODEL == "RF"):
                    bash_args = [RF_MODEL, "-t", TR, "-e", EV, "-o", PRD, "-l", LOG]
                else:
                    print(f"Model \"{MODEL}\" unknown!")
                    bash_args = ["echo", f"Model \"{MODEL}\" unknown!"]

                for bashix in bash_suf:
                    bash_args.extend(bashix)
                with open(LOG, "a") as log:
                    log.write(f"bash_args: {bash_args}\n")
                bash(bash_args)
                
                t1 = time()
                with open(LOG, "a") as log:
                    log.write(f"t1={t1}\n")
                    log.write(f"t={t1 - t0}\n")
