#!/usr/bin/Rscript

# Script by Danny Rorabaugh, Jan 2020.
# Imports a specified datafile (1st argument)
# Prints number of NA and non-NA cells

args <- commandArgs(trailingOnly=T)

if (length(args) < 1) {
  print("1 arguments expected.")
  quit()
}

library(raster) # Also loads package sp

in_file <- args[1]
data <- stack(in_file)
print("NAs:")
print(sum(is.na(getValues(data))))
print("Non-NAs:")
print(sum(!is.na(getValues(data))))