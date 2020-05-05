#!/usr/bin/Rscript
## Script CroppingRegion.R
## PREPARED BY LEOBARDO VALERA TO MICHELA TAUFER, 2020

## Commandline example: 
## ./CroppingRegion.R input.tif min_log max_long min_lat max_lat outpu.tif 

library(raster)

args = commandArgs(trailingOnly=TRUE) # read the input *tif file and the output *.csv
r <- raster(args[1])

r

min_long <-as.numeric(args[2])
max_long <-as.numeric(args[3])
min_lat  <-as.numeric(args[4])
max_lat  <-as.numeric(args[5])

r <- crop(r, extent(min_long,max_long,min_lat,max_lat))

writeRaster(r, file=args[6])
