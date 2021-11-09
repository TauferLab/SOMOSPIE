#!/usr/bin/env python3

import configparser
from ast import literal_eval

def conf_parse(init_loc):
    
    config = configparser.ConfigParser()
    config.read(init_loc)
    
    SOMOSPIE_vars = {}
    for var in ["START", "CODE", "DATA", "OUTPUT", "COV_FILE", "SM_FILE", "EVAL_FILE"]:
        SOMOSPIE_vars[var] = f'"{config["DEFAULT"][var]}"'
    for var in ["MAKE_T_E", "USE_PCA", "RAND_SEED", "USE_VIS", "BUFFER", "SUPER", "MIN_T_POINTS"]:
        SOMOSPIE_vars[var] = int(config["DEFAULT"][var])
    for var in ["VALIDATE"]:
        SOMOSPIE_vars[var] = round(float(config["DEFAULT"][var]), 4)
    
    regions = open(SOMOSPIE_vars["DATA"].strip('"') + config["DEFAULT"]["REGIONS"])
    SOMOSPIE_vars["REG_LIST"] = literal_eval(regions.readline().strip('\n'))
    
    for var in ["MONTHS", "MODICT", "YEAR", "COV_LAYERS"]:
        SOMOSPIE_vars[var] = literal_eval(config["DEFAULT"][var])
    
    YEARS = SOMOSPIE_vars['YEAR']
    #MONTH = SOMOSPIE_vars['MONTH']
    
    SOMOSPIE_vars["TRAIN_DIR"] = f'"{YEARS[0]}/t"'
    SOMOSPIE_vars["EVAL_DIR"] = f'"{YEARS[0]}/e"'
    #SOMOSPIE_vars["SM_FILE"] = f'"{YEAR}/{YEAR}_ESA_monthly.rds"'
    #SOMOSPIE_vars["EVAL_FILE"] = f'""'#{YEAR}/{MONTH}/ground_sm_means_CONUS.csv"
    
    return SOMOSPIE_vars
    
if __name__=="__main__":
    
    VARIABLES = conf_parse("SOMOSPIE_input.ini")
    
    for v in VARIABLES:
        print(f"{v}={VARIABLES[v]}")
