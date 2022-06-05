#!/usr/bin/env python3

from time import time, strftime, gmtime
T0 = time()

from sys import argv
if len(argv)>1:
    init_file = argv[1]
else:
    init_file = "SOMOSPIE_input.ini"

import pathlib
from os import listdir, chdir 
from utils import *

from curate import curate
from model import model
from analyze import analysis
from visualize import visualize

import configparser
from ast import literal_eval
from SOMOSPIE_input_parser import conf_parse
SOMOSPIE_vars = conf_parse(init_file)
for v in SOMOSPIE_vars:
    exec(f"{v}={SOMOSPIE_vars[v]}")

########################################
# Wrapper script for most of the workflow
#

START = pathlib.Path(START).resolve()
print(f"Starting folder: {START}\n")
    
# Set the working directory to the code subfolder, for running the scipts       
chdir(pathlib.Path(CODE))

# Change data files and folders to full paths
DATA = pathlib.Path(DATA).resolve()
if MAKE_T_E:
    if SM_FILE:
        SM_FILE = DATA.joinpath(SM_FILE)
        if not SM_FILE.exists():
            print(f"ERROR! File does not exist:\n{SM_FILE}")
    if COV_FILE:
        COV_FILE = DATA.joinpath(COV_FILE)
        if not COV_FILE.exists():
            print(f"ERROR! File does not exist:\n{COV_FILE}")
    if EVAL_FILE:
        EVAL_FILE = DATA.joinpath(EVAL_FILE)
        if not EVAL_FILE.exists():
            print(f"ERROR! File does not exist:\n{EVAL_FILE}")
else:
    SM_FILE = ""
    COV_FILE = ""
    EVAL_FILE = ""
if BUFFER:
    TRAIN_DIR += f"-{BUFFER}"
if SUPER:
    TRAIN_DIR += "-LvlUp"
TRAIN_DIR = DATA.joinpath(TRAIN_DIR)
EVAL_DIR = DATA.joinpath(EVAL_DIR)
SHAPES = DATA.joinpath(SUB_SHAP)
OUTPUT = pathlib.Path(OUTPUT).resolve().joinpath(strftime("job_%Y_%m_%d_%H_%M_%S",gmtime()))
if not OUTPUT.exists():
    OUTPUT.mkdir(parents=True)

print(f"Original training data in {TRAIN_DIR}")
print(f"Original evaluation data in {EVAL_DIR}")
    
##########################################
#
# 0 Set up Job details and logging
#

JOB = OUTPUT.joinpath("job")

PARAMS_FILE = append_to_folder(JOB, ".params")
with open(PARAMS_FILE, "w") as params:
    params.write(f"{SOMOSPIE_vars}\n")

JOB_FILE = append_to_folder(JOB, ".txt")
with open(JOB_FILE, "w") as job:
    job.write(f"T0={T0}\n")
    job.write(f"{OUTPUT}\n")
    job.write(f"{REG_LIST}\n")
LOG_FILE = append_to_folder(JOB, ".log")  

MONTH_DICT = {}

# For now, we can only handle 1 year at a time.
for year in YEAR[:1]:
    folder = OUTPUT.joinpath(str(year))
    if not folder.exists():
        folder.mkdir()
#####################################

    for MONTH in MONTHS:
        # This suffix is for future use.
        MNTH_SUFX = f"-{MONTH}"

        ##########################################
        # 1 Data Processing

        # ORIG is the sm data before any filtering, for use with analysis()
        # TRAIN is the training set after filtering and pca, if specified
        # EVAL is the evaluation set after filtering and pca, if specified
    
        curate_input = [MONTH_DICT, PARAMS_FILE, LOG_FILE, SM_FILE, COV_FILE, COV_LAYERS, 
                        EVAL_FILE, SHAPES, REG_LIST, BUFFER, 
                        TRAIN_DIR, MONTH, EVAL_DIR, USE_PCA, VALIDATE, 
                        "", RAND_SEED, SUPER, MIN_T_POINTS]
        print(f"curate(*{curate_input})")
    
        t0 = time()
        ORIG, TRAIN, EVAL, REG_LIST, seed, suffix = curate(*curate_input)
        with open(LOG_FILE, "a") as log:
            log.write(f"Data curation for month {MONTH} took {time() - t0} seconds.\n")
            log.write(f"Curated data:\nORIG={ORIG}\nTRAIN={TRAIN}\nEVAL={EVAL}\n")
            log.write(f"The following regions had sufficient training points:\n{REG_LIST}\n")
    
        print("Data curated.")

        ##########################################
        # 2 Modeling

        PRED = folder.joinpath(suffix)
        model_input = [0, TRAIN, EVAL, PRED, MODICT, suffix]
        print(f"model(*{model_input})")
        model(*model_input)
        
        print("Prediction completed with modeling methods.")

        ##########################################
        # 3 Analysis & Visualization

        for reg_type, reg in REG_LIST:
            region = f"{reg_type}_{reg}"
            
            if VALIDATE:
                R2_FILE = append_to_folder(JOB, ".r2")
                RMSE_FILE = append_to_folder(JOB, ".rmse")
                analysis_input = [region, PRED, ORIG, VALIDATE, R2_FILE, RMSE_FILE]
                print(f"analysis(*{analysis_input})")
                analysis(*analysis_input)

            if USE_VIS:
                # Specify the input data folder and the output figures folder
                DATS = PRED.joinpath(region)
                OUTS = DATS.joinpath(SUB_FIGS)
                ORIGFOLDER = ORIG.joinpath(region)
                visualize_input = [DATS, OUTS, ORIGFOLDER, reg_type, reg, 1, 0]
                print(f"visualize(*{visualize_input})")
                visualize(*visualize_input)

T1 = time()
with open(JOB_FILE, "a") as job:
    job.write(f"T1={T1}\n")
    job.write(f"T={T1-T0}\n")
with open(PARAMS_FILE, "a") as params:
    params.write(f"{MONTH_DICT}\n")
    params.write(f"{T1}\n")
    params.write(f"{T1-T0}\n")