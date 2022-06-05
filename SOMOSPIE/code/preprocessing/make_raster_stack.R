#!/usr/bin/Rscript

# Script by Danny Rorabaugh, 2019.
# Combines specified files from specified folder 
#  into single raster file with specified name.
# Command-line example:
# $ ./make_raster_stack.R ../data/topo_predictors/ ../data/topo15_CONUS_1km.tif Analytical_Hillshading.tif Aspect.tif Channel_Network_Base_Level.tif Closed_Depressions.tif CONUS_DEM1km.tif Convergence_Index.tif Cross-Sectional_Curvature.tif Flow_Accumulation.tif Longitudinal_Curvature.tif LS_Factor.tif Relative_Slope_Position.tif Slope.tif Topographic_Wetness_Index.tif Valley_Depth.tif Vertical_Distance_to_Channel_Network.tif

args <- commandArgs(trailingOnly=T)

if (length(args) < 3) {
  print("At least 3 arguments expected.")
  quit()
}

library(raster)

# Store all the initial arguments to variables
in_folder <- args[1]
out_file <- args[2]
in_files <- args[3:length(args)]

# Create the list of file names to stack
files_to_stack <- c()
for (i in 1:length(in_files)) {
    files_to_stack[i] <- paste0(in_folder, "/", in_files[i])
}

# Stack all the input files into a single RasterStack
rastack <- stack(files_to_stack)

# Write out the raster stack to the specified file
writeRaster(rastack, out_file, overwrite=T)