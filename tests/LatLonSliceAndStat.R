#!/usr/bin/Rscript

# Script by Danny Rorabaugh, Oct 2019.
# Goals:
# A function to split a specified area in a uniform grid.
# A function to compute eco-region related statistics on a specified shape.
# A function to run the above function on every box of the uniform grid.

# Arguments:
# * input path for tif file
# * output path for folder
# * xstep
# * ystep
# * * * * extent (optional): xmin xmax ymin ymax (otherwise, will use extent of input file)
# 

args <- commandArgs(trailingOnly=T)

if (length(args) < 4) {
  print("4 or 8 arguments expected.")
  quit()
}

library(raster)
library(GSIF)

# Input file should be a stackable file with a built-in projection
in_file <- args[1]
out_folder <- args[2]

# x_step and y_step should be integers giving the widths and height of each tile
# Note that the units are never specified here; we assume the units of the input file's projection
x_step <- as.integer(args[3])
y_step <- as.integer(args[4])

# Set the extent to be sliced into tiles:
# If at least 7 arguments were given, use 4 through 7 (these must be integers) ...
if (length(args) >= 8) {
    ext <- extent(as.integer(args[5:8]))
# ... otherwise, use the extent of the input file
} else {
    ext <- extent(data)
}
#print(ext)

data <- stack(in_file)

# Make the extent a spatial extent and give it the same projection as the input file
ext <- as(ext, 'SpatialPolygons')
proj4string(ext) <- CRS(projection(data))

# Create the tiles from the extent
tiles <- getSpatialTiles(ext, x_step, y_step, return.SpatialPolygons = TRUE)
#print(length(tiles))
#extent(tiles[0])[1]

tile_name <- function(tile) {
    name <- paste(extent(tile)[1], extent(tile)[2], extent(tile)[3], extent(tile)[4], sep="_")
    name <- paste0(name, ".tif")
    return(name)
}

for (i in 1:length(tiles)) {
    tile <- tiles[i]
    name <- tile_name(tile)
    datile <- crop(data, tile)
    writeRaster(datile, paste0(out_folder, "/", name))#, overwrite=T)
}
