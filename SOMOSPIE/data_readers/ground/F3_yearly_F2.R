#!/usr/bin/env Rscript

# Ricardo Llamas, 2018
# Modified by Danny Rorabaugh, 2018 Dec

sourceFolder <- "~/TAMU_NASDM_Full-2013-12-10"
outFolder <- "extracted"
start_year <- 2010 # No 5cm data before 1996.
end_year <- 2013 # No data after 2013.


library(dplyr) 

folders <- list.dirs(path=sourceFolder, full.name=T) 

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
        
        readings_file <- paste0(folders[i], "/", filez[2]) 
        
        readings <- read.table(readings_file, sep="\t", header=T)
        
        for (year in start_year:end_year){
    
            m <- readings
            m <- subset(m, m$Y == year)
            m <- subset(m, m$depth_5 != -9999)
            #print(m)

            if (nrow(m)>0) {
                sm_station <- data.frame(Month=m$M, Day=m$D, DayOfYear=m$DOY, sm_depth_5cm=m$depth_5)
                
                write.csv(sm_station, file=paste0(outFolder, "/", year, "/", name_station, ".csv"), row.names=F)
            }
        } 
  
    }

}
