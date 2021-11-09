#!/usr/bin/Rscript

library(raster) #Also loads package sp
library(rasterVis)

# Script by Danny Rorabaugh, 2018

input_file <- "station_map.csv"
output_file <- "stations_per_region/stations_per_region.csv"

data <- read.csv(input_file)
coordinates(data) <- c(1, 2)
if (is.na(projection(data))) {
    proj4string(data) <- "+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs"
}
print(data)

print("Data loaded.")

ECOsh <- shapefile('../data/terrestrial_Ecoregions_updated/terrestrial_Ecoregions_updated.shp')
print("Ecoregion shapefile loaded.")
ECOsh <- spTransform(ECOsh, projection(data))
print(ECOsh)
#data <- spTransform(data, CRS=projection(ECOsh))
#print(data)
 
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
        cropped_data <- data[ecoreg, ]
        n <- nrow(cropped_data)
        if (n>0) {
            #print(cropped_data)
            #print(paste0("Number of stations in ", reg, ": ", n))
            area <- sum(ecoreg$AREA)
            row <- data.frame(level=i, region=reg, area=area, stations=n)
            counts <- rbind(counts, row)
        }
    }
}    
print(counts)
write.csv(counts, file=output_file, row.names=F)

