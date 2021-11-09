#!/usr/bin/Rscript
## Script Change_Raster_Format.R
## PREPARED BY LEOBARDO VALERA TO MICHELA TAUFER, 2020

## Commandline example: 
## ./Change_Raster_Format.R input.img output.tif

library(raster)

args = commandArgs(trailingOnly=TRUE) # read the input *img file and the output *.tif
temp <- raster(args[1])
writeRaster(temp, file=args[2])