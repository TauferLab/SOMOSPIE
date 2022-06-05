#!/usr/bin/Rscript

# Script by Danny Rorabaugh, 2019.
# Combines specified files from specified folder
#  into single raster file with specified name.
# Command-line example:
# $ ./read_raster_layers_names.R /home/lvalera/Documents/Src_SOMOSPIE/SOMOSPIE/data/topo_predictors/stack.tif

library(raster)
terrain <- raster('../../data/stack2.tif')
print(nbands(terrain))
