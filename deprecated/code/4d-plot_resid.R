#!/usr/bin/Rscript

###Mario Guevara, Danny Rorabaugh, April 2019

# Takes the residual output from 3d and plots it on a state outline with extra info on the sides.
# Retired January 2020.

###
###RESIDUALS PLOT
###

#load libraries
library(rasterVis)
library(rgdal)

args <- commandArgs(trailingOnly=T)
file_in <- args[1]
file_out <- args[2]

#read datasets
dat <- read.csv(file_in)
#dat <- read.csv('HYPPO-resid.csv')
lim <- getData("GADM", country="USA", level=1)
#lim <- readRDS('GADM_2.8_USA_adm1.rds')

#check column names
names(dat)[1:2] <- c('x', 'y')
#define coordinates
coordinates(dat) <- ~ x+y
#gridded surface
gridded(dat) <- T
#converto to raster
dat <- raster(dat)
#trim borders to raster extent 
lim <- crop(lim, dat)
#calculate the mean value of residuals
meandat <- cellStats(dat, mean)

png(file_out)
#plot residuals
p <- levelplot(dat - meandat, par.settings = RdBuTheme)
# add the limit
p + layer(sp.polygons(lim))
dev.off()
