#!/usr/bin/Rscript

# Script by Danny Rorabaugh, 2020.
# Imports a specified file to a raster, resamples more coarsly, and saves to specified path
# Command-line example:
# $ for topo in Aspect Analytical_Hillshading Channel_Network_Base_Level Closed_Depressions CONUS_DEM1km Convergence_Index Cross-Sectional_Curvature Flow_Accumulation Longitudinal_Curvature LS_Factor Relative_Slope_Position Slope Topographic_Wetness_Index Valley_Depth Vertical_Distance_to_Channel_Network; do ./coarsify.R ../data/topo_predictors/${topo}.sdat ../data/topo_predictors/${topo}.tif 5; done

args <- commandArgs(trailingOnly=T)

if (length(args) < 3) {
  print("3 arguments expected.")
  quit()
}

library(raster)

# Store all the initial arguments to variables
in_file <- args[1]
out_file <- args[2]
agg_fact <- as.integer(args[3])

# Stack the input files into a raster stack
rast <- stack(in_file)

# This step increases the coarseness of the raster
rast <- aggregate(rast, fact=agg_fact)

# Write out the final raster stack to the specified file
writeRaster(rast, out_file)