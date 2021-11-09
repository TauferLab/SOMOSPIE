#!/usr/bin/Rscript
library(raster)

list_of_files =c("chimney.sdat","chimney_aspect.sdat","chimney_chanel_base.sdat","chimney_closed_depresion.sdat","chimney_convergence.sdat","chimney_hcurv.sdat","chimney_lsfactor.sdat","chimney_shade.sdat","chimney_slope.sdat","chimney_total_catch_area.sdat","chimney_twi.sdat","chimney_vcurv.sdat","chimney_vlley_depth.sdat")

 S <- raster()

for (lista in list_of_files){
    temp <-raster(lista)
    projection(temp) <- "+proj=utm +zone=17 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs"
    S <-stack(S,temp)
    }

S <-projectRaster(S, crs="+proj=longlat +datum=WGS84 +ellps=WGS84 +towgs84=0,0,0")
writeRaster(S,'AllParameters.tif',overwrite=TRUE)
temp <- as(S, 'SpatialPixelsDataFrame') 
temp <- as.data.frame(temp, xy=T)
write.csv(temp, file = 'AllParameters.csv',row.names = FALSE)