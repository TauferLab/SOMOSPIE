#!/usr/bin/env Rscript

# Ricardo Llamas, 2018
# Modified by Danny Rorabaugh, 2018 Dec

sourceFolder <- "~/TAMU_NASDM_Full-2013-12-10"
outFolder <- "extracted"

library(dplyr) 

folders <- list.dirs(path=sourceFolder, full.name=T) 

#Start_End_Years <- data.frame(Station_ID=character(), Start_Year=numeric(), End_Year=numeric())

for (i in 2:length(folders)){ 

  filez <- list.files(folders[i], pattern="\\.txt$") 
  
  if(length(filez)==3){ 
    
    station_folder <- as.character(folders[i])
    #print(station_folder)
    dirs <- unlist(strsplit(station_folder, "/"))
    #print(dirs)
    name_station <- dirs[length(dirs)]
    #print(name_station)
 
    station_file <- paste0(folders[i], "/", filez[3]) 

    station <- read.table(station_file, sep="\t", header=T, fill=T, quote="\"", comment.char = "", nrows=1) 
    
    #xy <- station[,8:7]    
    ##print(xy)

    readings_file <- paste0(folders[i], "/", filez[2]) 
    
    #readings <- read.table(readings_file, sep="\t", header=T)
    #m <- merge(readings, xy)
    
    m <- read.table(readings_file, sep="\t", header=T)
    m <- subset(m, m$Y > 1992)
    m <- subset(m, m$Y < 2014)
    m <- subset(m, m$depth_5 != -9999)
 
    # Drop the columns for the other depths deeper than 5 cm. 
    # This is unnecessary, since these columns are not selected below.
    #m$depth_25 <- NULL
    #m$depth_60 <- NULL
    #m$depth_75 <- NULL

    sm_station <- data.frame(Year=m$Y, Month=m$M, Day=m$D, DayOfYear=m$DOY, sm_depth_5cm=m$depth_5)
    
    #name_station <- as.character(sm_station[1,1])
    
#    start_ <- min(sm_station$Year)
#    end_ <- max(sm_station$Year)
#    
#    Start_End_Years_temp <- data.frame(Station_ID=name_station, Start_Year=start_, End_Year=end_)
#    Start_End_Years <- rbind(Start_End_Years, Start_End_Years_temp)
      
    write.csv(sm_station, file=paste0(outFolder, "/", name_station, ".csv"), row.names=F)

  } 
}

#write.csv(Start_End_Years, file="Start_End_Years_validation_stations.csv")

