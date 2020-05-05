#!/usr/bin/Rscript
## Script Tiff_2_csv.R
## PREPARED BY LEOBARDO VALERA TO MICHELA TAUFER, 2020

## Commandline example: 
## ./Tiff_2_csv.R input.csv output.csv

library(raster)

args = commandArgs(trailingOnly=TRUE) # read the input *csv file and the output *.tif
temp <- read.csv(args[1])
cord.dec = SpatialPoints(cbind(temp$x, temp$y), proj4string=CRS("+proj=longlat"))
z <- data.frame(cord.dec,temp[,3:ncol(temp)])
b <- rasterFromXYZ(z)
projection(b) <- "+proj=longlat +datum=WGS84 +ellps=WGS84 +towgs84=0,0,0"
b <- projectRaster(b, crs="+proj=utm +zone=17 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs")
temp <- as(b, 'SpatialPixelsDataFrame') 
temp <- data.frame(temp@coords, temp@data)
names(temp) <- c('x', 'y', 'Moisture', 'Elevation')
write.csv(temp, file = args[2],row.names = FALSE)
