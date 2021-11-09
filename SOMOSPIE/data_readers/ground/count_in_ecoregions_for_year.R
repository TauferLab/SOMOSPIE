#!/usr/bin/Rscript

library(raster) # Also loads package sp

# Script by Danny Rorabaugh, 2018
# Command-line Example:
# $ Rscript count_in_ecoregions_for_year.R 2012

args <- commandArgs(trailingOnly=T)
year <- args[1]

input_file <- "station_map.csv"
data_dir <- "extracted/"
out_dir <- "stations_per_region/"
path_ecoregions <- '../data/TerrestrialEcoregions_L2_Shapefile/NA_Terrestrial_Ecoregions_Level_II/data/terrestrial_Ecoregions_updated/terrestrial_Ecoregions_updated.shp'

in_dir <- paste0(data_dir, year, "/")
y_stations <- paste0(in_dir, "station_list.csv")
output_file <- paste0(out_dir, year, ".csv")

stations <- read.csv(input_file)
coordinates(stations) <- ~x+y
WGS84 <- "+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs"
proj4string(stations) <- WGS84
#print(stations)
print("Station coordinates loaded.")

year_stations <- as.numeric(as.vector(read.csv(y_stations, header=F)))
#print(year_stations)
print(paste0("List of stations active in ", year, " loaded."))

ECOsh <- shapefile(path_ecoregions)
print("Ecoregion shapefile loaded.")
#print(ECOsh)
ECOsh <- spTransform(ECOsh, WGS84)
#print(ECOsh)

regions <- data.frame(L1=ECOsh$LEVEL1, L2=ECOsh$LEVEL2, L3=ECOsh$LEVEL3)
#print(regions)

L1 <- unique(regions$L1)
#print(L1)
L2 <- unique(regions$L2)
#print(L2)
L3 <- unique(regions$L3)
#print(L3)

counts <- data.frame(level=numeric(), region=character(), area=numeric(), stations=numeric())
for (i in 1:3) {
    if (i==1) {regs <- L1}
    else if (i==2) {regs <- L2}
    else if (i==3) {regs <- L3}
    print(regs)
    for (reg in regs){
        #print(paste0("Region: ", reg))
        if (i==1) {ecoreg <- ECOsh[ECOsh$LEVEL1 == reg, ]}
        else if (i==2) {ecoreg <- ECOsh[ECOsh$LEVEL2 == reg, ]}
        else if (i==3) {ecoreg <- ECOsh[ECOsh$LEVEL3 == reg, ]} 
        #print(ecoreg)
        reg_stations <- stations[ecoreg, ]
        region_stations <- unlist(reg_stations[["id"]])
        #print(region_stations)

        ry_stations <- intersect(region_stations, year_stations)
        #print(ry_stations)
        print(paste0("There were ", length(ry_stations), " station active in ecoregion ", reg, " in ", year, "."))
        
        n <- length(ry_stations)
        
        if (n>0) {
            #print(paste0("Number of stations in ", reg, " in ", year, ": ", n))
            area <- sum(ecoreg$AREA)
            row <- data.frame(level=i, region=reg, area=area, stations=n)
            counts <- rbind(counts, row)
        }
    }
}    
print(counts)
write.csv(counts, file=output_file, row.names=F)


