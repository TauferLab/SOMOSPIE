#!/usr/bin/Rscript

# Script by Danny Rorabaugh, 2019.
# Imports a specified file to a raster, converts to a standard projection, and saves to specified path
# Command-line example:
# $ for topo in Aspect Analytical_Hillshading Channel_Network_Base_Level Closed_Depressions CONUS_DEM1km Convergence_Index Cross-Sectional_Curvature Flow_Accumulation Longitudinal_Curvature LS_Factor Relative_Slope_Position Slope Topographic_Wetness_Index Valley_Depth Vertical_Distance_to_Channel_Network; do ./reproject_raster.R ../data/topo_predictors/${topo}.tif ../data/topo_predictors/${topo}.tif; done

args <- commandArgs(trailingOnly=T)

if (length(args) < 2) {
  print("2 arguments expected.")
  quit()
}

library(raster)
library(plotKML)

# Store all the initial arguments to variables
in_file <- args[1]
out_file <- args[2]
projection <- CRS("+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs")

# Stack the input files into a raster stack
rast <- stack(in_file)

# Transform the raster to a standard projection
rast <- reproject(rast, projection)

# Write out the final raster stack to the specified file
writeRaster(rast, out_file, overwrite=T)