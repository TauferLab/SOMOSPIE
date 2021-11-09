#!/usr/bin/Rscript

# Ricardo Llamas, 2018
# Modified by Danny Rorabaugh, 2018 Dec
# This script generates a general list of the NASMDB stations, including coordinates and basic information 
# to be used for the generation of a shapefile and then the intersection to determine the stations within 
# the study area  

sourceFolder <- "~/TAMU_NASDM_Full-2013-12-10"
outFile <- "validation_stations_coordinates.csv"
outFile2 <- "station_map.csv"

library(dplyr)

folders <- list.dirs(path=sourceFolder, full.name=TRUE) 

folders[1:3]

stations_coordinates_final <- data_frame(Station_code=character(), Network=character(), State=character(),
                                         Longitude=numeric(), Latitude=numeric(), Elevation=numeric(),
                                         Start_year=numeric(), End_year=numeric())

for (i in 2:length(folders)){ 

    filez <- list.files(paste0(folders[i]), pattern="\\.txt$") 

    if(length(filez)==3){ 

        station_file <- paste0(folders[i], "/", filez[3])
        stations <- read.table(station_file, sep="\t", header=T, fill=T, quote="\"", comment.char = "", nrows=1)

        station_ID <- as.character(stations$StationID)
        Network <- as.character(stations$Network) 
        State <- as.character(stations$State)
        Longitude <- as.numeric(stations$Longitude)
        Latitude <- as.numeric(stations$Latitude)
        Elevation <- as.numeric(stations$Elevation)
        Start_year <- as.numeric(stations$StartYear)
        End_year <- as.numeric(stations$EndYear)

        stations_coordinates_temp <- data_frame(Station_code=station_ID, Network=Network, State=State,
                                                Longitude=Longitude, Latitude=Latitude, Elevation=Elevation,
                                                Start_year=Start_year, End_year=End_year) 

        stations_coordinates_final <- rbind(stations_coordinates_final, stations_coordinates_temp)

    }
}
write.csv(stations_coordinates_final, file=outFile, row.names=F)

map <- data_frame(x=stations_coordinates_final$Longitude, y=stations_coordinates_final$Latitude, id=stations_coordinates_final$Station_code)
write.csv(map, file=outFile2, row.names=F)


