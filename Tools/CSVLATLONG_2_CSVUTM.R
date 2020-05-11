#!/usr/bin/Rscript
## Script Tiff_2_csv.R
## PREPARED BY LEOBARDO VALERA TO MICHELA TAUFER, 2020

## Commandline example: 
## ./Tiff_2_csv.R input.csv output.csv

library(raster)


args = commandArgs(trailingOnly=TRUE) # read the input *csv file and the output *.tif
temp <- read.csv(args[1])
xy <-data.frame(temp)
coordinates(xy) <- c("x", "y")
proj4string(xy) <- CRS("+proj=longlat +datum=WGS84")
xy <- spTransform(xy, CRS="+proj=utm +zone=17 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs")
xy <- data.frame(xy@coords, xy@data)
write.csv(xy, file = args[2],row.names = FALSE)

