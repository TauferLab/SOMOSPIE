#!/usr/bin/Rscript

#Code by Mario Guevarra and Danny Rorabaugh, 2018-2020
#This script should be run from command line with 3+ arguements
#First argument: 2+ column file with first 2 cols x and y values
#Second argument: raster file with covariates/predictors
#Third argument: path of where to save file
#Fourth+ arguments: names of columns in raster file
#Output: file with same rows as First arg, but added columns

args <- commandArgs(trailingOnly=T)

if ( length(args) < 3 ) {
    print("in_file, cov_file, and out_file needed")
    quit()
} else {
    in_file <- args[1]
    cov_file <- args[2]
    out_file <- args[3]
} 

library(raster)
COV <- stack(cov_file)

if ( length(args) > 3 ) {
    names(COV) <- args[4:length(args)]
}

SM <- read.csv(in_file)
SM <- cbind(SM, extract(COV, SM[c('x','y')]))
#str(SM)

write.csv(SM, file=out_file, row.names=F)
