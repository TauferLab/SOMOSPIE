#!/usr/bin/Rscript
## Script Tiff_2_csv.R
## PREPARED BY LEOBARDO VALERA TO MICHELA TAUFER, 2020

## Commandline example: 
## ./Cropping.R input.tif substring_name num_col_rasters um_col_rasters 

library(raster)

args = commandArgs(trailingOnly=TRUE) # read the input *tif file and the output *.csv
raster <- raster(args[1])
num_col_rasters <-as.numeric(args[3])
num_row_rasters <-as.numeric(args[4])

save <- T

h        <- ceiling(ncol(raster)/num_col_rasters)
v        <- ceiling(nrow(raster)/num_row_rasters)
agg      <- aggregate(raster,fact=c(h,v))
agg[]    <- 1:ncell(agg)
agg_poly <- rasterToPolygons(agg)
  names(agg_poly) <- "polis"
  r_list <- list()
  for(i in 1:ncell(agg)){
    e1          <- extent(agg_poly[agg_poly$polis==i,])
    r_list[[i]] <- crop(raster,e1)
  }
  if(save==T){
    for(i in 1:length(r_list)){
      writeRaster(r_list[[i]],filename=paste(args[2],i,sep=""),
                  format="GTiff",datatype="FLT4S",overwrite=TRUE)  
    }
  }
  