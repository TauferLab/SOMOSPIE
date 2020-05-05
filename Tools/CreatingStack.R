#!/usr/bin/Rscript
library(raster)

args = commandArgs(trailingOnly=TRUE) 

S <- raster()

for (lista in args){
    temp <-raster(lista)
    projection(temp) <- "+proj=utm +zone=17 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs"
    S <-stack(S,temp)
    }

# Save this Raster as UTM tiff and CSV
writeRaster(S,'Evaluation/AllParametersUTM.tif',overwrite=TRUE)
temp <- as(S, 'SpatialPixelsDataFrame') 
temp <- data.frame(temp@coords, temp@data)
write.csv(temp, file = 'Evaluation/AllParametersUTM.csv',row.names = FALSE)

S <-projectRaster(S, crs="+proj=longlat +datum=WGS84 +ellps=WGS84 +towgs84=0,0,0")
writeRaster(S,'Evaluation/AllParametersLONGLAT.tif',overwrite=TRUE)
temp <- as(S, 'SpatialPixelsDataFrame') 
temp <- data.frame(temp@coords, temp@data)

names(temp) <- c('x','y','CONUSDEM1km','Aspect','ChannelNetworkBaseLevel','FlowAccumulation','ConvergenceIndex','CrossSectionalCurvature','LSFactor','RelativeSlopePosition','AnalyticalHillshading','Slope','VerticalDistancetoChannelNetwork','TopographicWetnessIndex','LongitudinalCurvature','ValleyDepth')

write.csv(temp, file = 'Evaluation/AllParametersLONGLAT.csv',row.names = FALSE)