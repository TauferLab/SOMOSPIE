#!/usr/bin/Rscript
## Script Tiff_2_csv.R
## PREPARED BY LEOBARDO VALERA TO MICHELA TAUFER, 2020

## Commandline example: 
## ./Tiff_2_csv.R input.csv output.img

library(raster)

args = commandArgs(trailingOnly=TRUE) # read the input *csv file and the output *.tif
temp <- read.csv(args[1])
cord.dec = SpatialPoints(cbind(temp$x, temp$y), proj4string=CRS("+proj=longlat"))
z <- data.frame(cord.dec,temp[,1])
b <- rasterFromXYZ(z)
writeRaster(b, file=args[2])