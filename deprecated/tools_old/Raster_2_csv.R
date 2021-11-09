#!/usr/bin/Rscript
## Script Tiff_2_csv.R
## PREPARED BY LEOBARDO VAERA TO MICHELA TAUFER, 2020

## Commandline example: 
## ./Tiff_2_csv.R input.tif output.csv

library(raster)

args = commandArgs(trailingOnly=TRUE) # read the input *tif file and the output *.csv
temp <- raster(args[1])
temp <- as(temp, 'SpatialPixelsDataFrame') 
temp <- as.data.frame(temp, xy=T)
write.csv(temp, file = args[2],row.names = FALSE)