#!/usr/bin/Rscript

# Script by Mario Guevara and Danny Rorabaugh, 2018-9.
# Crops a spatial file to the region defined in a specified file.
# Command-line example:
# $ ./crop_to_shape.R ../data/topo15_CONUS_1km.tif ../data/shapes/Arizona.rds ../data/topo15_Arizona_1km.csv 0 Aspect Analytical_Hillshading Channel_Network_Base_Level Closed_Depressions CONUS_DEM1km Convergence_Index Cross-Sectional_Curvature Flow_Accumulation Longitudinal_Curvature LS_Factor Relative_Slope_Position Slope Topographic_Wetness_Index Valley_Depth Vertical_Distance_to_Channel_Network

args <- commandArgs(trailingOnly=T)

if (length(args) < 3) {
  print("At least 3 arguments expected.")
  quit()
}

library(raster) # Also loads package sp
##library(rasterVis)
library(tools) # For get_ext()

in_file <- args[1]
# The shape_path should be an RDS file path
shape_path <- args[2]
out_file <- args[3]

# Buffer in meters; if 0, no buffer.
if (length(args) < 4) {
  buffer <- 0
} else {
  buffer <- as.integer(args[4]) 
}
if (buffer > 0) {
  library(rgeos) #For gBuffer()
}

# Layer names.
if (length(args) > 4) {
    layer_names <- args[5:length(args)]
} else {
    layer_names <- c()
}

# Import data.
ext <- file_ext(in_file)
if (ext %in% c("rds", "RDS")) {
  data <- stack(readRDS(in_file))
  print("RDS loaded.")
} else if (ext %in% c("tif", "TIF", "tiff", "TIFF", "sdat", "SDAT")) {
  data <- stack(in_file)
  print("Raster loaded.")
} else if (ext %in% c("csv", "CSV", "txt", "TXT")) {
  data <- read.csv(in_file, header=F)
  coordinates(data) <- c(1, 2)
  print("CSV loaded.")
} else {
  print(in_file)
  print("Expected in_file to have one of these extensions: .rds, .tif, .tiff, .csv, .txt, .sdat!")
  quit
}
#str(data)
#print(head(data))

# Data prjection.
if (is.na(projection(data))) {
  proj4string(data) <- "+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs"
  print("Data had no projection; standard projection applied.")
}
print("The input data has the following projection:")
print(projection(data))

# Import shape
reg <- readRDS(shape_path)
if (is.na(projection(reg))) {
  proj4string(reg) <- "+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs"
  print("Region had no projection; standard projection applied.")
}
reg <- spTransform(reg, CRS=projection(data))
  
# Deal with buffer, if requested.
if (buffer > 0) {
  print(paste("You asked to expand with a buffer of width", as.character(buffer), "m."))
  ##plot(reg)
  #projection(reg)  

  # The following projection was selected for CONUS and should work well. 
  planar <- spTransform(reg, CRS("+proj=aeqd +lat_0=52 +lon_0=-97.5 +x_0=8264722.17686 +y_0=4867518.35323 +datum=WGS84 +units=m   +no_defs +ellps=WGS84 +towgs84=0,0,0"))
  #projection(planar)

  buff <- gBuffer(planar, width = buffer)
  reg <- spTransform(buff, projection(data))
  ##plot(reg)
}

# Cut data to ecoregion.
if (ext %in% c("rds", "RDS", "tif", "TIF", "tiff", "TIFF", "sdat", "SDAT")) {
  # https://www.rdocumentation.org/packages/raster/versions/2.6-7/topics/crop
  data <- crop(data, reg) #, snap="out")
  # https://www.rdocumentation.org/packages/raster/versions/2.6-7/topics/mask
  data <- mask(data, reg)
} else {
  data <- data[reg, ]
}
print("Data chopped down to the region you chose.")

if (nrow(data) == 0) {
    print("WARNING! The dataset you gave has empty intersection with the region you gave.")
}
#sprintf("There are %d data points in regions %s.", nrow(data), region) #Does not give number of data points.

#str(data)
#print(head(data))
##plot(data)

# The following is hardcoded until I figure out how to generalize.
if (length(layer_names) > 0) {
    names(data) <- layer_names
} else if (ext %in% c("rds", "RDS")) {
  # If monthly sm data, we want the following:
  #names(data) <- month.abb
  #data <- as.data.frame(data, xy=T)
} else if (ext %in% c("tif", "TIF", "tiff", "TIFF")) {
  # If 15 topographic parameters, we want the following:
  namesTopo <- c("DEM", "HILL", "SLP", "ASP", "CSC", "LC", "CI", "CD", 
		 "FA", "TWI", "LSF", "CNB", "VDC", "VD", "RSP")
  names(data) <- namesTopo
  #data <- as.data.frame(data, xy=T)
} else if (ext %in% c("sdat", "SDAT")) {
  print(names(data))
} else if (ext %in% c("csv", "CSV", "txt", "TXT")) {
  data <- as.data.frame(data)
}
#str(data)
##par(mfrow=c(2, 2))
##plot(data)

print("Saving to file...")

ext <- file_ext(out_file)
if (ext %in% c("tif", "TIF", "tiff", "TIFF")) {
  writeRaster(data, out_file)
} else if (ext %in% c("rds", "RDS")) {
  saveRDS(data, file=out_file)
} else {
  data <- as.data.frame(data, xy=T)
  #write.table(data, file=out_file, row.names=F, col.names=F, sep=",", quote=F)
  write.csv(data, file=out_file, row.names=F)
}
