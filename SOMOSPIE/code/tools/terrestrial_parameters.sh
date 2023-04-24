#!/bin/sh

# Closed Depressions can be added: -SINKS closed_depressions.sgrd

 saga_cmd ta_compound 0 -ELEVATION $1elevation.sgrd -SHADE $1hillshading.sgrd -SLOPE $1slope.sgrd -ASPECT $1aspect.sgrd -HCURV $1plan_curvature.sgrd -VCURV $1profile_curvature.sgrd -CONVERGENCE $1convergence_index.sgrd -FLOW $1total_catchment_area.sgrd -WETNESS $1twi.sgrd -LSFACTOR $1lsfactor.sgrd  -CHNL_BASE $1channel_network_base_level.sgrd -CHNL_DIST $1channel_network_distance.sgrd -VALL_DEPTH $1valley_depth.sgrd -RSP $1relative_slope_position.sgrd