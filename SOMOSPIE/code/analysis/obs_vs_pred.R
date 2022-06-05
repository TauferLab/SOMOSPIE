#!/usr/bin/Rscript

###Mario Guevara, Danny Rorabaugh, 2019-2020

###
###OBS vs PRED, R^2 and RMSE
###

# Load library for rasters.
library(raster)

args <- commandArgs(trailingOnly=T)
if ( length(args) < 4 ) {
  print("Please specify all necessary input and output file paths.")
  quit()
}

file_in_obs <- args[1]
file_in_pred <- args[2]
r2_out <- args[3]
rmse_out <- args[4]

# Read datasets.
obs <- read.csv(file_in_obs)
mod <- read.csv(file_in_pred)

# Manage format of spatial files.
# check names
names(obs) <- c('x', 'y', 'sm')
names(mod)[1:3] <- names(obs) 
# define coordinates
coordinates(mod) <- ~ x+y
# gridded surface
gridded(mod) <- TRUE
# convert to raster
mod <- raster(mod) 

# Extract values of the prediction (mod) at the coordinates of the observed data.
obs$pred <- extract(mod, obs[1:2])
obs <- na.omit(obs)

# Perform comparison analysis.
r2 <- cor(obs$pred, obs$sm)^2
rmse <- sqrt(mean((obs$pred - obs$sm)^2))

# Save the r^2 value to file.
r2_line <- paste0(r2, ",",  file_in_pred)
write(r2_line, file=r2_out, append=TRUE)
rmse_line <- paste0(rmse, ",",  file_in_pred)
write(rmse_line, file=rmse_out, append=TRUE)
