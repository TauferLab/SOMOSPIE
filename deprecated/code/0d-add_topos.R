#!/usr/bin/Rscript

###############
# The following was removed from code/README.txt:
#    
#    0d-add_topos.R
#        Attaches covariate data to a file, 
#        coercing to the coordinates of the file to which it is being added
#
#      Call with:
#        Rscript 0d-add_topos.R region_file covars_file
#
#      Arguments:
#        region_file     csv with (sm) data
#        covars_file     csv with covariate data to attach
#
###############

library(raster)

## Specify files
args <- commandArgs(trailingOnly=T)

region_file <- args[1]
#covars_file <- "../data/USA_topo.tif"
covars_file <- args[2]

xyCols <- c(1, 2)
namesTopo <- c('DEM', 'HILL', 'SLP', 'ASP', 'CSC', 
               'LC', 'CI', 'CD', 'FA', 'TWI', 
               'LSF', 'CNB', 'VDC', 'VD', 'RSP')


## Import USA topos
COV <- stack(covars_file)

names(COV) <- namesTopo

## Load sm file
SM <- read.csv(region_file)

## Extract covariate data to sm coordinates
SM <- cbind(SM, extract(COV, SM[xyCols]))
#str(SM)

## Save sm+topo data.frame
#out_file <- paste0(substr(region_file, 1, nchar(region_file)-4), '_topos.csv')
write.csv(SM, file=region_file, row.names=F)

