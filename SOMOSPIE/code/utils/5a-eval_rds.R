#!/usr/bin/Rscript

## Prepared by Mario Guevara and Danny Rorabaugh, 2018
## This scripts takes a model and a data file of the same format for which the model has been trained.
## Assumption: the model outputs a prediction for each point in the data
## Assumption: the first two columns of the data file are coordinates.
##
## Note: With the R-scripts for KKNN and RF, if you do not specify an eval file, 
##       the scripts will output a model that can be used by this script

### ToDo: DOESN'T WORK WITH THE KKNN MODEL; fix.

args = commandArgs(trailingOnly=TRUE)
#sprintf("args: %s", args)
if (length(args) < 3) {
    print("3 arguments expected: input rds file (with a model to apply), input data file (on which to apply the model), output path.")
    quit()
} else {
    rdsFile = args[1]
    evalFile = args[2]
    path = args[3]
}

library(raster)
library(rgdal)

# Load in the model and data
model <- readRDS(rdsFile)
x <- read.table(evalFile, sep=",", header=T) ## (low resolution DEM and SAGA standard terrain parameters)

# Apply the model to the data to get a prediction
pred <- predict(model, x)

# Attach the prediction to the coordinates of the original data
pred <- data.frame(x[c(1,2)], pred)#RF=pred)

# Write out the prediction to specified path
write.table(pred, 
            file=path, 
            row.names=F,
            col.names=F,
            sep=",")

