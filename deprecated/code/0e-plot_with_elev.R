#!/usr/bin/Rscript

########################
# The following was removed from code/README.txt:
#
#    0e-plot_with_elev.R
#        Plots a heatmap with elevation cross-sections
#
########################

#libraries
library(rgdal)
library(raster)
library(rasterVis)

#specifications, example with elevation map (DEM)
#./0e-plot_with_elev ../from_Mario/10.2.4_topos.csv ../from_Mario/10.2.4_topos.png
input <- '../from_Mario/10.2.4_topos.csv'
output <- '../from_Mario/10.2.4_topos.jpg'
input2 <- 'GADM_2.8_USA_adm1.rds'
jet.colors <- colorRampPalette(c("#00007F", "blue", "#007FFF", "cyan", "#7FFF7F", "yellow", "#FF7F00", "red", "#7F0000"))

#index of required variables
idx <- c('x', 'y', 'DEM')

#polygons to overlay
polys <- readRDS(input2)

#import datasets
dat <- read.csv(input)
dat <- dat[idx]

#define coordinates
coordinates(dat) <- ~ x + y

#define a gridded object
gridded(dat) <- TRUE

#rasterize
dat <- raster(dat)
proj4string(dat) <- CRS(projection(polys))

#saving parameters
#dev.copy(png,output)

#plot 
jpeg(output)
levelplot(dat, par.settings = rasterTheme(jet.colors(10)))+ layer(sp.polygons(polys, lwd=2.5, col='black'))

#https://www.rdocumentation.org/packages/imguR/versions/0.1.5/topics/dev.off
dev.off()
#

