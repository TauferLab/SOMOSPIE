# Here the user specify the working directory...
START = "../"
# ... the subfolder with the modular scripts...
CODE = "code/"
# ... the subfolder with the data...
DATA = "data/"
# ... the subfolder for output. 
OUTPUT = "out/"

YEAR = 2016
# Assuming SM_FILE below has multiple months of SM data, 
# specify the month here (1=January, ..., 12=December)
# The generated predictions will go in a subfolder of the data folder named by this number.
# Set to 0 if train file is already just 3-columns (lat, lon, sm).
MONTH = 4

#############################
# Within the data folder...

# ... there should be a subfolder with/for training data...
TRAIN_DIR = f"{YEAR}/t"#-100000"
# ... and a subfolder with/for evaluation data.
EVAL_DIR = f"{YEAR}/e"

# THE FOLLOWING 3 THINGS WILL ONLY BE USED IF MAKE_T_E = 1.
# Specify the location of the file with sm data.
# Use an empty string or False if the train folder is already populated.
SM_FILE = f"{YEAR}/{YEAR}_ESA_monthly.rds"
# Specify location of eval coordinates needing covariates attached.
# An empty string or False will indicate that the eval folder is already populated.
EVAL_FILE = f""#{YEAR}/{MONTH}/ground_sm_means_CONUS.csv"
# Specify location of the file with covariate data.
# An empty string or False will indicate that covariates are already attached to train and eval files.
COV_FILE = "8.5_topo.tif"#USA_topo.tif"#6.2_topo.tif"#

##########################
# If the Train and Eval files need to be generated, set MAKE_T_E = 1.
MAKE_T_E = 0
# If you wish to perform PCA, set USE_PCA = 1; otherwise USE_PCA = 0.
USE_PCA = 0
# Compute residuals from original test data? Set to 1.
# Split off (e.g.) 25% of the original for test for validation? Set to 1.25
# Use the EVAL_FILE as truth for validation? Set to 2.
# Split off a fraction of 
VALIDATE = 1.2
RAND_SEED = 0 #0 for new, random seed, to be found in log file
# Create images?
USE_VIS = 0

# Specify the ecoregions of interest.
#REG_LIST = ["6.2.10", "6.2.12", "6.2.13", "6.2.14"]
#REG_LIST = [f"6.2"]#.{l3}" for l3 in range(3, 16) if l3!=6]
REG_LIST = ["8.5.1"]#, "8.5.2"]#, "8.5.3"]#"8.5", 
# Specify the number of km of a buffer you want on the training data.
BUFFER = 100000
SUPER = 0

# Dictionary with a models as keys and model-specific parameter:arglist dictionaries as values.
MODICT = {
#          "1NN":{"-p":[1]}, 
          "KKNN":{"-k":[10]}, 
          "RF":{}, 
          "HYPPO":{"-p":[1], "-k":[10], "-D":[3], "-v":[2]},
#          "UNMODEL":{}
         }

REPEAT = 5
