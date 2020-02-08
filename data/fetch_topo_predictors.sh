#!/bin/bash

# Suggested first argument:
# topo_predictors
# Allowable second argument:
# Aspect, Analytical_Hillshading, Channel_Network_Base_Level, Closed_Depressions, CONUS_DEM1km, Convergence_Index, Cross-Sectional_Curvature, Flow_Accumulation, Longitudinal_Curvature, LS_Factor, Relative_Slope_Position, Slope, Topographic_Wetness_Index, Valley_Depth, Vertical_Distance_to_Channel_Network
# Command-line use example:
# $ for topo in Aspect Analytical_Hillshading Channel_Network_Base_Level Closed_Depressions CONUS_DEM1km Convergence_Index Cross-Sectional_Curvature Flow_Accumulation Longitudinal_Curvature LS_Factor Relative_Slope_Position Slope Topographic_Wetness_Index Valley_Depth Vertical_Distance_to_Channel_Network; do ./fetch_topo_predictors.sh topo_predictor $topo; done

topo_dir=$1
param=$2
mkdir -p $topo_dir
folder=https://www.hydroshare.org/resource/b8f6eae9d89241cf8b5904033460af61/data/contents/explanatory_variables_dem/
#wget -c ${folder}${param}.mgrd -P $topo_dir/
wget -c ${folder}${param}.prj -P $topo_dir/
wget -c ${folder}${param}.sdat -P $topo_dir/
#wget -c ${folder}${param}.sdat.aux.xml -P $topo_dir/
wget -c ${folder}${param}.sgrd -P $topo_dir/