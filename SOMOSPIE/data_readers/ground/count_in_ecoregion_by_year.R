#!/usr/bin/Rscript

library(raster) # Also loads package sp

# Script by Danny Rorabaugh, 2018
# Command-line Example:
# $ Rscript count_in_ecoregion_by_year.R 8.3 2012

args <- commandArgs(trailingOnly=T)
region <- args[1]
year <- args[2]

input_file <- "station_map.csv"
data_dir <- "extracted/"


in_dir <- paste0(data_dir, year, "/")
out_dir <- paste0(data_dir, year, "_region", region)
y_stations <- paste0(in_dir, "station_list.csv")


stations <- read.csv(input_file)
coordinates(stations) <- ~x+y
WGS84 <- "+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs"
proj4string(stations) <- WGS84
#print(stations)
print("Station coordinates loaded.")

ECOsh <- shapefile('../data/terrestrial_Ecoregions_updated/terrestrial_Ecoregions_updated.shp')
print("Ecoregion shapefile loaded.")
#print(ECOsh)
ECOsh <- spTransform(ECOsh, WGS84)
#print(ECOsh)


# The following counts the number of periods in the command-line argument.
# This is one less than the level; for example LEVEL3 10.2.4 has 2 periods.
num_periods <- (nchar(region) - nchar(gsub('\\.', '', region)))
print(paste0("Ready to cut to level ", num_periods + 1, " region ", region, "."))

if ( num_periods == 0 ) {
  reg <- ECOsh[ECOsh$LEVEL1 == region, ] 
} else if ( num_periods == 1 ) {
  reg <- ECOsh[ECOsh$LEVEL2 == region, ] 
} else if ( num_periods == 2 ) {
  reg <- ECOsh[ECOsh$LEVEL3 == region, ] 
} else {
  print("Not a valid ecoregion code!")
}
print("Region selected from shapefile.")


reg_stations <- stations[reg, ]
region_stations <- unlist(reg_stations[["id"]])
#print(region_stations)

year_stations <- as.numeric(as.vector(read.csv(y_stations, header=F)))
#print(year_stations)
print(paste0("List of stations active in ", year, " loaded."))

ry_stations <- intersect(region_stations, year_stations)
#print(ry_stations)
print(paste0("There were ", length(ry_stations), " station active in ecoregion ", region, " in ", year, "."))

# ToDo: Save results to a file in out_dir

## 6.2
### 253 in 2010, 272 in 2011, 264 in 2012
## 8
### 147 in 2010, 164 in 2011, 152 in 2012
## 2012
### 7 in 8.1, 13 in 8.2, 67 in 8.3, 29 in 8.4, 36 in 8.5

