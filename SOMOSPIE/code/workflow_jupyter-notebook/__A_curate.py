# Appending the path of the panda_scripts module
import sys
sys.path.append("./data_preprocessing")
sys.path.append("./analysis_visualization")
sys.path.append("./utils")
import pathlib
import pandas as pd
import panda_scripts as ps
import joint_pca as pca
from argument_validators import alphanumeric
from shutil import rmtree
from math import floor
from numpy.random import randint
from os import remove
import inspect

from __utils import *

# This is a wrapper for all the data-processing scripts below.
#
#       Arguments:
#         MONTH_DICT      A dictionary from the scope above this level, to be filled by this function
#         PARAMS_FILE     _______
#         LOG_FILE        Path for the log file
#         SM_FILE         File with sm data
#         COV_FILE        File with cov data
#         COV_LAYERS      List of strings, length must match the number of layers in the COV_FILE
#         EVAL_FILE       File with eval data
#         SHAPE_DIR       Folder path where shape .rds files are (to be) stored
#         REG_LIST        List of regions to cut out of the sm file
#         BUFFER          km of buffer around each region
#         TRAIN_DIR       The directory of training files
#         MONTH           Numeric month to use in the train data
#         EVAL_DIR        The directory of the evaluation files
#         USE_PCA         Run PCA dimension reduction on both train and eval files
#                         Assumes same covariate columns are present in same order
#         VALIDATE        1 to save SM values from TEST for residuals
#                         2 to save SM values from EVAL for comparison
#         STATS_FILE      Path to function for computing statistics on test data
#                         Default empty string, no stats computed
#         RAND            Random seed; default 0 generates new seed
#         SUPER           If 1/True, expands test file of ecoregions to one level up;
#                         Default 0, nothing changed
#         MIN_T_POINTS    Minimum number of training points required in each region;
#                         Default -1 doesn't check
#         
#       Output:
#         The output folder depends on which preprocessing steps are taken
#         A log file is generated in LOG_DIR/proc-log#.txt,
#          where # is the least unused natural number

def curate(MONTH_DICT, PARAMS_FILE, LOG_FILE, SM_FILE, COV_FILE, COV_LAYERS, EVAL_FILE, SHAPE_DIR, 
           REG_LIST, BUFFER, TRAIN_DIR, MONTH, 
           EVAL_DIR, USE_PCA, VALIDATE, STATS_FILE="", RAND=0, SUPER=0, MIN_T_POINTS=-1):
    MASK_PATH = pathlib.Path("data_preprocessing/create_shape.R").resolve()
    CROP_PATH = pathlib.Path("data_preprocessing/crop_to_shape.R").resolve()
    ADD_COV_PATH = pathlib.Path("data_preprocessing/add_topos.R").resolve()
    DROP_COLS_PATH = pathlib.Path("data_preprocessing/drop_cols.py").resolve()
    
    # Prepare shape for cropping.
    def create_shape(reg_type, reg, SHAPE_DIR=SHAPE_DIR):
        if not SHAPE_DIR.is_dir():
            SHAPE_DIR.mkdir(parents=True)
        SHAPE_FILE = SHAPE_DIR.joinpath(f"{reg}.rds")
        if SHAPE_FILE.is_file():
            log.write(f"shape for {reg} exists in {SHAPE_DIR}\n")
        else:
            shape_args = [MASK_PATH, reg_type, reg, SHAPE_FILE]
            log.write(f"{shape_args}\n")
            #print(shape_args)
            bash(shape_args)
            log.write(f"Created shape for {reg} in {SHAPE_DIR}")
        return SHAPE_FILE
    
    print(f"Curation log file: {LOG_FILE}")
    with open(LOG_FILE, "w") as log:
        log.write("----------------------------------------\n")
        log.write("Begin data processing with the following arguments...\n")
        #https://stackoverflow.com/questions/582056/getting-list-of-parameter-names-inside-python-function
        frame = inspect.currentframe()
        args, _, _, vals = inspect.getargvalues(frame)
        for i in args:
            log.write(f"{i}={vals[i]}\n")
        log.write("----------------------------------------\n")
        
        # Establish random seed:
        if (VALIDATE<=1) or (VALIDATE>=2):
            seed=0
        else:
            if RAND:
                seed = int(RAND)
            else:
                seed = randint(2**16)
            log.write(f"For randomization, using {seed}.\n")
        
        #suffix = ""
 
        
        MONTH_DICT[MONTH] = {}
        suffix = f"month{MONTH}"
        if SUPER:
            suffix += "-LvlUp"
        if BUFFER:
            suffix += f"-{BUFFER}meter"
            MONTH_DICT[MONTH]["buffer"] = BUFFER
        if USE_PCA:
            suffix += "-PCA"
        if seed:
            suffix += f"-{VALIDATE-1:.2f}_{seed}"
            MONTH_DICT[MONTH]["seed"] = seed 
       
            
########################################
# Create train and eval files

        if VALIDATE:
            SM_BEFORE = TRAIN_DIR.parent.joinpath("original_sm-"+suffix)
            log.write(f"Soil Moisture data from before preprocessing will go in {SM_BEFORE}\n")
            if not SM_BEFORE.is_dir():
                SM_BEFORE.mkdir(parents=True)
        else:
            SM_BEFORE = None

        if SM_FILE:
            log.write("Extracting sm data from the specified source.\n")
            for reg_type,reg in REG_LIST:
                if not TRAIN_DIR.is_dir():
                    TRAIN_DIR.mkdir(parents=True)

                REG_TR_FILE = TRAIN_DIR.joinpath(f"{reg_type}_{reg}.csv")
                if SUPER and (reg_type=="ECOREGION" or reg_type=="CEC"):
                    reg = ".".join(reg.split(".")[:-1])

                SHAPE_FILE = create_shape(reg_type, reg)

                # Crop soil moisture file to shape.
                crop_args = [CROP_PATH, SM_FILE, SHAPE_FILE, REG_TR_FILE, BUFFER]
                #print(crop_args)
                log.write(f"{crop_args}\n")
                bash(crop_args)

                if COV_FILE:
                    cov_args = [ADD_COV_PATH, REG_TR_FILE, COV_FILE, REG_TR_FILE] + COV_LAYERS
                    log.write(f"{cov_args}\n")
                    bash(cov_args)
        else:
            log.write("No SM_FILE specified, so train folder assumed populated.\n")
                
        if EVAL_FILE:

            log.write("Creating eval files from specified source.\n")
            for reg_type, reg in REG_LIST:
                log.write(f"Creating EVAL file for {reg}.\n")
                if not EVAL_DIR.is_dir():
                    EVAL_DIR.mkdir(parents=True)

                REG_EV_FILE = EVAL_DIR.joinpath(f"{reg_type}_{reg}.csv")

                SHAPE_FILE = create_shape(reg_type, reg)

                # Crop evaluation file to shape.
                crop_args = [CROP_PATH, EVAL_FILE, SHAPE_FILE, REG_EV_FILE]
                log.write(f"{crop_args}\n")
                bash(crop_args)

                if VALIDATE==2:
                    VALID_FILE = SM_BEFORE.joinpath(REG_EV_FILE.name)
                    log.write(f"cp {REG_EV_FILE} {VALID_FILE}")
                    bash(["cp", REG_EV_FILE, VALID_FILE])

                print(f"{DROP_COLS_PATH} {REG_EV_FILE} {REG_EV_FILE} -k 0,1")
                bash([DROP_COLS_PATH, REG_EV_FILE, REG_EV_FILE, "-k", "0,1"])

                if COV_FILE:
                    cov_args = [ADD_COV_PATH, REG_EV_FILE, COV_FILE, REG_EV_FILE] + COV_LAYERS
                    log.write(f"{cov_args}\n")
                    bash(cov_args)

        elif COV_FILE:
            log.write("Extracting covariate data from the specified source.\n")
            for reg_type, reg in REG_LIST:
                log.write(f"Creating EVAL file for {reg}.\n")
                if not EVAL_DIR.is_dir():
                    EVAL_DIR.mkdir(parents=True)

                REG_EV_FILE = EVAL_DIR.joinpath(f"{reg_type}_{reg}.csv")

                SHAPE_FILE = create_shape(reg_type, reg)

                # Crop covariate file to shape.
                crop_args = [CROP_PATH, COV_FILE, SHAPE_FILE, REG_EV_FILE, 0] + COV_LAYERS
                #print(crop_args)
                log.write(f"{crop_args}\n")
                bash(crop_args)

                if VALIDATE==2:
                    VALID_FILE = SM_BEFORE.joinpath(REG_EV_FILE.name)
                    log.write(f"cp {REG_EV_FILE} {VALID_FILE}")
                    bash(["cp", REG_EV_FILE, VALID_FILE])

        else:
            log.write("No EVAL_FILE or COV_FILE specified, so eval folder assumed populated.\n")

########################################
# Compute statistics on train files

        if STATS_FILE:
            stat_args = [STATS_FILE, TRAIN_DIR]
            log.write(f"{stat_args}\n")
            bash(stat_args)

########################################
# Process train and eval files

        TRAIN_DIR_TEMP = append_to_folder(TRAIN_DIR, "-postproc-"+suffix)
        log.write(f"Processed training data to go in {TRAIN_DIR_TEMP}\n")
        if TRAIN_DIR_TEMP.is_dir():
            rmtree(TRAIN_DIR_TEMP)
        TRAIN_DIR_TEMP.mkdir(parents=True)
        
        EVAL_DIR_TEMP = append_to_folder(EVAL_DIR, "-postproc-"+suffix)
        log.write(f"Processed evaluation data to go in {EVAL_DIR_TEMP}\n")
        if EVAL_DIR_TEMP.is_dir():
            rmtree(EVAL_DIR_TEMP)
        EVAL_DIR_TEMP.mkdir(parents=True)

        for reg_type, reg in REG_LIST:
            region = f"{reg_type}_{reg}.csv"
            if not os.path.isfile(TRAIN_DIR.joinpath(region)):
                continue
                
            tdf = pd.read_csv(TRAIN_DIR.joinpath(region))#, dtype=float)#.astype(object).infer_objects()
            #print(f"before: {tdf.columns}")
            tdf.rename(columns=alphanumeric, inplace=True) 
            #print(f"after: {tdf.columns}")
            
            if not os.path.isfile(EVAL_DIR.joinpath(region)):
                continue
            edf = pd.read_csv(EVAL_DIR.joinpath(region))#, dtype=float)#.astype(object).infer_objects()  
            log.write(f"imported edf; first 3 rows:\n{edf.head(3)}\n")
            #print(f"before: {edf.columns}")
            edf.rename(columns=alphanumeric, inplace=True)
            ecols = {edf.columns[0]: tdf.columns[0], edf.columns[1]: tdf.columns[1]} 
            edf.rename(columns=ecols, inplace=True)
            #print(f"after: {edf.columns}")

            if MONTH:
                replacements = ps.monthify(tdf.columns)
                tdf = tdf.rename(columns=replacements)
                tdf = ps.keep_month(tdf, MONTH)
            
            ######################################################
            ## Dealing with NAs
            ######################################################
            # Show how many non-NA's there are in each column
            log.write(f"Number of non-NA values in tdf by column:\n{tdf.count()}\n")
            log.write(f"Number of non-NA values in edf by column:\n{edf.count()}\n")
            # LSF is mostly NA in this region; replace it with 0, appropriate for a costal pixel
            # Dict of cols with specified NA replacement value
            bad_cols = {"LSF":0}
            tdf.fillna(value=bad_cols, inplace=True)#[["LSF"]] = tdf[["LSF"]].fillna(0)
            edf.fillna(value=bad_cols, inplace=True)#[["LSF"]] = edf[["LSF"]].fillna(0)
            for col in bad_cols:
                log.write(f"NA's in '{col}' replaced with {bad_cols[col]}.\n")
            # Show how many non-NA's there are in each column
            #log.write(f"Number of non-NA values in tdf by column:\n{tdf.count()}\n")
            #log.write(f"Number of non-NA values in edf by column:\n{edf.count()}\n")
            
            tdf = tdf.dropna()#thresh=4).fillna(0)
            log.write(f"First 3 rows of tdf:\n{tdf.head(3)}\n")
            #log.write(f"Number of non-NA values in tdf by column:\n{tdf.count()}\n")
            edf = edf.dropna()#thresh=4).fillna(0)
            log.write(f"First 3 rows of edf:\n{edf.head(3)}\n")
            #log.write(f"Number of non-NA values in edf by column:\n{edf.count()}\n")
            ############################################
            
            trows = tdf.shape[0]
            if trows:
                log.write(f"There are {trows} training points in {region}.\n")
            else:
                log.write(f"Warning: there are no training points in {region}!\n")
                continue
            
            erows = edf.shape[0]
            if erows:
                log.write(f"There are {erows} evaluation points in {region}.\n")
            else:
                log.write(f"Warning: there are no evaluation points in {region}!\n")
                continue
            
            if floor(VALIDATE)==1:
                before = tdf[tdf.columns[:3]]#.dropna() 
                if VALIDATE>1:
                    log.write(f"For before.sample, {seed}.\n")
                    before = before.sample(frac=(VALIDATE - 1), random_state=seed)
                    tdf.drop(before.index.tolist(), inplace=True)
                    trows = tdf.shape[0]
                    if trows:
                        log.write(f"There are {trows} training points in {region}.\n")
                    else:
                        log.write(f"Warning: there are no training points in {region}!\n")
                        continue
                brows = before.shape[0]
                if brows:
                    log.write(f"There are {brows} validation points in {region}.\n")
                else:
                    log.write(f"Warning: there are no validation points in {region}!\n")
                    continue
                before_path = SM_BEFORE.joinpath(region)
                before.to_csv(path_or_buf=before_path, index=False, header=False, na_rep="NA")
                if BUFFER or SUPER:
                    log.write("Trimming validation file back down to {region}.\n")
                    crop_args = [CROP_PATH, before_path, before_path, r]
                    log.write(f"{crop_args}\n")
                    bash(crop_args)
            
            if USE_PCA:
                params = pca.get_params(tdf)
                log.write(f"Performing PCA.\n")
                #log.write(f"tdf pre-PCA: {tdf.shape}\n{tdf.head(3)}\n")
                #log.write(f"edf pre-PCA: {edf.shape}\n{edf.head(3)}\n")
                log.write(f"pre-PCA:\n{params}\n")
                if len(params) > min(tdf.shape[0], edf.shape[0]):
                    log.write(f"Error: region {region} skipped! You have {tdf.shape[0]} rows of training data and {edf.shape[0]} rows of evaluation data, but you need at least {len(params)} of each to perform PCA on your params.\n")
                    continue
                                
                tdf, edf, comps = pca.joint_pca(tdf, edf, params)
                log.write(f"post-PCA:\n{tdf.shape}\n{tdf.head(3)}\n{edf.shape}\n{edf.head(3)}\n{comps}\n")
                log.write(f"Completed PCA for {region} with these eigenvalues:\n{comps}\n")

                trows = tdf.shape[0]
                if trows:
                    log.write(f"There are {trows} training points in {region}.\n")
                else:
                    log.write(f"Warning: there are no training points in {region}!\n")
                    continue

                erows = edf.shape[0]
                if erows:
                    log.write(f"There are {erows} evaluation points in {region}.\n")
                else:
                    log.write(f"Warning: there are no evaluation points in {region}!\n")
                    continue
               
            tdf.to_csv(path_or_buf=TRAIN_DIR_TEMP.joinpath(region), index=False)
            edf.to_csv(path_or_buf=EVAL_DIR_TEMP.joinpath(region), index=False)

        TRAIN_DIR = TRAIN_DIR_TEMP
        EVAL_DIR = EVAL_DIR_TEMP
        

        # Update region list to only include those regions with at least a minimum number of test points
        if (MIN_T_POINTS > -1):
            NEW_REG_LIST = []
            for reg_type, reg in REG_LIST:
                REG_TR_FILE = TRAIN_DIR.joinpath(f"{reg_type}_{reg}.csv")
                if REG_TR_FILE.is_file():
                    with open(REG_TR_FILE ,'r') as regtrfile:
                        num_lines = sum(1 for line in regtrfile)
                    if num_lines > MIN_T_POINTS:
                        NEW_REG_LIST.append((reg_type, reg))
                        log.write(f"Region {reg} has {num_lines - 1} data points ({MIN_T_POINTS} required). Kept in region list.\n")
                    else:
                        log.write(f"Warning! Region {reg} only has {num_lines - 1} data points ({MIN_T_POINTS} required). Removed from region list.\n")
                        remove(REG_TR_FILE)
                else:
                    log.write(f"Warning! Region {reg} does not have a test file. Removed from region list.\n")
            REG_LIST = NEW_REG_LIST
            
        NEW_REG_FILE = LOG_FILE.with_suffix(f".{MONTH}reg")
        with open(NEW_REG_FILE, "w") as reg_out:
            for reg_type, reg in REG_LIST:
                reg_out.write(f"{reg_type},{reg}\n")

###############################################
        log.write("Data curation complete!!\n")

    return(SM_BEFORE, TRAIN_DIR, EVAL_DIR, REG_LIST, seed, suffix)
