#!/usr/bin/Rscript

library(raster) # Also loads package sp
##library(rasterVis)
library(tools) # For get_ext()
eco_loc <- "../data/TerrestrialEcoregions_L2_Shapefile/NA_Terrestrial_Ecoregions_Level_II/data/terrestrial_Ecoregions_updated/terrestrial_Ecoregions_updated.
shp"

# Script by Mario Guevara and Danny Rorabaugh, 2018.
# Crops a spatial file to a specified region.

#################
# The following was removed from code/README.txt:
#
#    crop_to_ecoregion.R
#        Generalized 0a and 0c (both defunct)  below.
#        Can handle RDS (.rds), Raster (.tif, .tiff), and CSV (.csv, .txt).
#
##############

args <- commandArgs(trailingOnly=T)

in_file <- args[1]
out_file <- args[2]

# The region should be specified in commandline using the 1-, 2- or 3-number region code.
# 8.5 is Mississippi Alluvial and Southeast USA Costal Plains.
# 8.5.1 is Middle Atlantic Coastal Plain.
if (length(args) < 3) {
  region <- 0
} else {
  region <- args[3]
}

# Buffer in meters; if 0, no buffer.
if (length(args) < 4) {
  buffer <- 0
} else {
  buffer <- as.integer(args[4]) 
}
if (buffer > 0) {
  library(rgeos) #For gBuffer()
}

# Import data.
ext <- file_ext(in_file)
if (ext %in% c("rds", "RDS")) {
  data <- stack(readRDS(in_file))
  print("RDS loaded.")
} else if (ext %in% c("tif", "TIF", "tiff", "TIFF")) {
  data <- stack(in_file)
  print("Raster loaded.")
} else if (ext %in% c("csv", "CSV", "txt", "TXT")) {
  data <- read.csv(in_file, header=F)
  coordinates(data) <- c(1, 2)
  print("CSV loaded.")
} else {
  print("Expected in_file to have one of these extensions: .rds, .tif, .tiff, .csv, .txt!")
  quit()
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


if (region %in% c(0, "0")) {
  # Restrict to CONUS.
  # https://www.rdocumentation.org/packages/raster/versions/2.6-7/topics/getData
  # Import the USA shapefile from GADM with state boundaries (level 1) included
  us <- getData("GADM", country="USA", level=1)
  # https://www.rdocumentation.org/packages/sp/versions/1.2-7/topics/spTransform
  # Match the us shapefile to the projection of the sm data
  us <- spTransform(us, CRS=projection(data))
  # The next two lines to restrict to CONUS
  us <- us[us$NAME_1 != "Alaska",]
  us <- us[us$NAME_1 != "Hawaii",] 
  # Cut data to CONUS
  if (ext %in% c("rds", "RDS", "tif", "TIF", "tiff", "TIFF")) {
    # https://www.rdocumentation.org/packages/raster/versions/2.6-7/topics/crop
    data <- crop(data, us) #, snap="out")
    # https://www.rdocumentation.org/packages/raster/versions/2.6-7/topics/mask
    data <- mask(data, us)
  } else {
    data <- data[us, ]
  }
  print("You didn't specify an ecoregion, so data chopped down to CONUS.")
  #str(data)
  #print(head(data))
} else {
  # Procure specified ecoregion.
  ECOsh <- shapefile(eco_loc)
  ECOsh <- spTransform(ECOsh, CRS=projection(data))
  print("Ecoregion shapefile loaded.")
  # The following counts the number of periods in the command-line argument.
  # This is one less than the level; for example LEVEL3 10.2.4 has 2 periods.
  num_periods <- (nchar(region) - nchar(gsub("\\.", "", region)))
  print(paste0("Ready to cut to level ", num_periods + 1, " region ", region, "."))
  if (num_periods == 0) {
    reg <- ECOsh[ECOsh$LEVEL1 == region, ] 
  } else if (num_periods == 1) {
    reg <- ECOsh[ECOsh$LEVEL2 == region, ] 
  } else if (num_periods == 2) {
    reg <- ECOsh[ECOsh$LEVEL3 == region, ] 
  } else {
    print("Not a valid ecoregion code!")
    quit()
  }
  
  # Deal with buffer, if requested.
  if (buffer > 0) {
    print(paste("You asked to expand with a buffer of width", as.character(buffer), "m."))
    ##plot(reg)
    #projection(reg)  
  
    # The following projection was selected for CONUS and should work well. 
    planar <- spTransform(reg, CRS("+proj=aeqd +lat_0=52 +lon_0=-97.5 +x_0=8264722.17686 +y_0=4867518.35323 +datum=WGS84 +units=m +no_defs +ellps=WGS84 +towgs84=0,0,0"))
    #projection(planar)
    
    buff <- gBuffer(planar, width = buffer)
    reg <- spTransform(buff, projection(data))
    ##plot(reg)
  }
  
  # Cut data to ecoregion.
  if (ext %in% c("rds", "RDS", "tif", "TIF", "tiff", "TIFF")) {
    # https://www.rdocumentation.org/packages/raster/versions/2.6-7/topics/crop
    data <- crop(data, reg) #, snap="out")
    # https://www.rdocumentation.org/packages/raster/versions/2.6-7/topics/mask
    data <- mask(data, reg)
  } else {
    data = data[reg, ]
  }
  print("Data chopped down to the ecoregion you chose.")
  #sprintf("There are %d data points in regions %s.", nrow(data), region) #Does not give number of data points.
  #str(data)
  #print(head(data))
  ##plot(data)
}

# The following is hardcoded until I figure out how to generalize.
if (ext %in% c("rds", "RDS")) {
  # If monthly sm data, we want the following:
  names(data) <- month.abb
  #data <- as.data.frame(data, xy=T)
} else if (ext %in% c("tif", "TIF", "tiff", "TIFF")) {
  # If 15 topographic parameters, we want the following:
  namesTopo <- c("DEM", "HILL", "SLP", "ASP", "CSC", "LC", "CI", "CD", 
		 "FA", "TWI", "LSF", "CNB", "VDC", "VD", "RSP")
  names(data) <- namesTopo
  #data <- as.data.frame(data, xy=T)
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
  
