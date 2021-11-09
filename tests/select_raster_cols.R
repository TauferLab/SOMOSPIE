#!/usr/bin/Rscript

# Script by Danny Rorabaugh, Oct 2019.
# Imports a specified raster (1st argument)
# Selects only the secified layers (3rd+ arguments)
# Saves to specified path (2nd argument)

args <- commandArgs(trailingOnly=T)

if (length(args) < 3) {
  print("3+ arguments expected.")
  quit()
}

library(raster) # Also loads package sp

in_file <- args[1]
out_file <- args[2]
layers <- as.integer(args[3:length(args)])

data <- stack(in_file)
subset(data, layers, filename=out_file)