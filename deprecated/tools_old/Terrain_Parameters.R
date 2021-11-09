#!/usr/bin/Rscript
## Script Tiff_2_csv.R
## PREPARED BY LEOBARDO VALERA TO MICHELA TAUFER, 2020

## Commandline example: 
 

library(sp)
library(rgdal)
library(raster)
library(kknn)
library(RSAGA)
library(RColorBrewer)

rsaga.geoprocessor("ta_compound", module = "Basic Terrain Analysis",
                   param = list(ELEVATION = paste0("Gatlinburg_1m_grid_elev.sdat"),
                                SHADE = paste0("Gatlinburg_1m_grid_hillshading.sdat"),
                                SLOPE = paste0("Gatlinburg_1m_grid_slope.sdat"),
                                ASPECT = paste0("Gatlinburg_1m_grid_aspect.sdat"),
                                HCURV = paste0("Gatlinburg_1m_grid_plan_curvature.sdat"),
                                VCURV = paste0("Gatlinburg_1m_grid__profile_curvature.sdat"),
                                CONVERGENCE = paste0("Gatlinburg_1m_grid_convergence_index.sdat"),
                                SINKS = paste0("Gatlinburg_1m_grid_closed_depressions.sdat"),
                                FLOW = paste0("Gatlinburg_1m_grid_total_catchment_area.sdat"),
                                WETNESS = paste0("Gatlinburg_1m_grid_topographic_wetness_index.sdat"),
                                LSFACTOR = paste0("Gatlinburg_1m_grid_ls_factor.sdat"),
                                CHNL_BASE = paste0("Gatlinburg_1m_grid_channel_network_base_level.sdat"),
                                CHNL_DIST = paste0("Gatlinburg_1m_grid_channel_network_distance.sdat"),
                                VALL_DEPTH = paste0("Gatlinburg_1m_grid_valley_depth.sdat"),
                                RSP = paste0("Gatlinburg_1m_grid_relative_slope_position.sdat")),
                   show.output.on.console = TRUE)

#1. Elevation, the elevation in meters above the sea level 
elev_gatlinburg_1m <- raster(paste0("Gatlinburg_1m_grid_elev_.sdat"))
elev_gatlinburg_1m <- projectRaster(elev_gatlinburg_1m, crs=projection(usa_wgs84_boundary))
plot(elev_gatlinburg_1m)
writeRaster(elev_gatlinburg_1m, filename = paste0("Gatlinburg_1m_grid_elev_wgs84.tif"), overwrite = TRUE)