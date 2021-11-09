import pathlib
from os import listdir
from __utils import *
import pandas as pd
import pandas as pd
from math import floor
from time import time

# This is a wrapper script for analysis of predictions produced in stage 2-model
#
#       Arguments:
#         REGION          name of region
#         PRED_DIR        path to folder with region predictions
#         ORIG_DIR        path to folder of training data
#         VALIDATE        1 <= x <2 for r^2 / RMSE; 2 for deltas
#         R2_FILE         path of file in which to drop r^2 values
#         RMSE_FILE       path of file in which to drop RMSE values

def analysis(REGION, PRED_DIR, ORIG_DIR, VALIDATE, R2_FILE, RMSE_FILE):

    RESID_COMP = pathlib.Path("analysis_visualization/3c-obs_vs_pred.R").resolve()

    PREDS = PRED_DIR.joinpath(REGION, SUB_PRED)
    RESIDS = PRED_DIR.joinpath(REGION, SUB_RESI)
    #RES_FIGS = PRED_DIR.joinpath(REGION, SUB_FIGS, SUB_RESI)
    if not RESIDS.is_dir():
        RESIDS.mkdir(parents=True)
    #if not RES_FIGS.is_dir():
    #    RES_FIGS.mkdir(parents=True)

    ORIG = append_to_folder(ORIG_DIR.joinpath(REGION), ".csv")
    for pred in (file for file in listdir(PREDS) if file.endswith(".csv")):
        PRED = PREDS.joinpath(pred)
        RESID = RESIDS.joinpath(pred)
        LOG = RESID.with_suffix(".log")
                
        with open(LOG, "w") as log:
            t0 = time()
            log.write(f"t0={t0}\n")
            
            if floor(VALIDATE)==1:
                # ToDo: Save the differences to RESID.
                log.write(f"floor(VALIDATE)==1: Computing residuals between prediction and the portion of original satellite data removed for testing.\n")
                #RES_COMP = RES_FIGS.joinpath(pred).with_suffix(".png")
                #resid_args = [RESID_COMP, ORIG, PRED, RES_COMP, SCORE_FILE]
                resid_args = [RESID_COMP, ORIG, PRED, R2_FILE, RMSE_FILE]
                log.write(f"resid_args: {resid_args}\n")
                bash(resid_args)
                
            elif VALIDATE==2:
                log.write(f"VALIDATE==2: Computing differences between prediction and supplied validation data.\n")
                
                # Load in known sm values.
                old = pd.read_csv(ORIG)
                old.columns = ["x", "y", "old"]
                old.set_index(["x", "y"], inplace=True)
                
                # Load in predicted sm values.
                new = pd.read_csv(PRED, header=None)
                new = new[new.columns[:3]]
                new.columns = ["x", "y", "new"]
                new.set_index(["x", "y"], inplace=True)
                
                # Join old and new.
                # Will only keep data points for which the same x/y exists in both.
                compare = old.join(new)#[new.columns[2]])#"new"])
                #compare.columns = ["x", "y", "old", "new"]
                compare.dropna(inplace=True)
                
                # Compute stats and save to files.
                corr = (compare["new"].corr(compare["old"]))**2
                log.write(f"The correlation between the original and predicted data is {corr}.\n")
                with open(R2_FILE, 'a') as r2_out:
                    r2_out.write(f"{corr},{PRED}")
                rmse = np.sqrt(np.mean((compare["new"] - compare["old"])**2))
                log.write(f"The RMSE between the original and predicted data is {rmse}.\n")
                with open(RMSE_FILE, 'a') as rmse_out:
                    rmse_out.write(f"{rmse},{PRED}")
                
                # Find differences and save to file.
                compare["deltas"] = compare["new"] - compare["old"]
                compare["reltas"] = compare["deltas"]/compare["old"]
                log.write(f"The first few rows of differences and relative differences:\n{compare.head()}\n")
                resid = compare[["deltas"]]#"x","y","reltas"]]
                resid.to_csv(path_or_buf=RESID, header=False)#, index=False)
            
            t1 = time()
            log.write(f"t1={t1}\n")
            log.write(f"t={t1 - t0}\n")
