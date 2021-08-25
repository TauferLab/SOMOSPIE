#!/usr/bin/Rscript

# Script by Danny Rorabaugh, 2019.
# Creates a shapefile for a specified region.
# Command-line example: 
# $ ./create_shape.R STATE Arizona ../data/shapes/Arizona.rds

args <- commandArgs(trailingOnly=T)

if (length(args) < 3) {
  print("3 arguments expected.")
  quit()
}

library(raster)

type <- args[1]
if (!(type %in% c("STATE", "BOX", "CEC", "NEON"))) {
  print("Unrecognized first argument.")
  quit()
}
region <- args[2]
out_path <- args[3]

if (type == "CEC") {
  eco_loc1 <- "../data/NA_Terrestrial_Ecoregions_Level_I_Shapefile/data/NA_Terrestrial_Ecoregions_v2_level1.shp"
  eco_loc2 <- "../data/NA_Terrestrial_Ecoregions_Level_II_Shapefile/data/NA_Terrestrial_Ecoregions_v2_level2.shp"
  eco_loc3 <- "../data/NA_Terrestrial_Ecoregions_v2_Level_III_Shapefile/data/NA_Terrestrial_Ecoregions_v2_level3.shp"

#"../data/TerrestrialEcoregions_L2_Shapefile/NA_Terrestrial_Ecoregions_Level_II/data/terrestrial_Ecoregions_updated/terrestrial_Ecoregions_updated.
#shp"
  
  # Procure specified ecoregion.
  ECOsh1 <- shapefile(eco_loc1)
  ECOsh2 <- shapefile(eco_loc2)
  ECOsh3 <- shapefile(eco_loc3)
  print("CEC ecoregion shapefile loaded.")
  # The following counts the number of periods in the command-line argument.
  # This is one less than the level; for example LEVEL3 10.2.4 has 2 periods.
  num_periods <- (nchar(region) - nchar(gsub("\\.", "", region)))
  print(paste0("Ready to cut to level ", num_periods + 1, " region ", region, "."))
  if (num_periods == 0) {
    regs <- unique(ECOsh1$LEVEL1)
    if (region %in% regs) {
        reg <- ECOsh1[ECOsh1$LEVEL1 == region, ]
    } else {
        print("Unrecognized CEC level 1 ecoregion. Options are:")
        print(regs)
        quit()
    }
  } else if (num_periods == 1) {
    regs <- unique(ECOsh2$LEVEL2)
    if (region %in% regs) {
        reg <- ECOsh2[ECOsh2$LEVEL2 == region, ]
    } else {
        print("Unrecognized CEC level 2 ecoregion. Options are:")
        print(regs)
        quit()
    }
  } else if (num_periods == 2) {
    regs <- unique(ECOsh3$LEVEL3)
    if (region %in% regs) {
        reg <- ECOsh3[ECOsh3$LEVEL3 == region, ]
    } else {
        print("Unrecognized CEC level 3 ecoregion. Options are:")
        print(regs)
        quit()
    }
  } else {
    print("Not a valid CEC ecoregion code!")
    quit()
  }
    
# if type "REGION", name should be specified in commandline using the 1-, 2- or 3-number region code.
# 8.5 is Mississippi Alluvial and Southeast USA Costal Plains.
# 8.5.1 is Middle Atlantic Coastal Plain.


} else if (type == "NEON") {
  eco_loc <- "../data/NEONDomains_0/NEON_Domains.shp"
  
  # Procure specified ecoregion.
  ECOsh <- shapefile(eco_loc)
  print("NEON eco-climactic domain shapefile loaded.")
  
  ids <- unique(ECOsh$DomainID)
  doms <- unique(ECOsh$DomainName)
  if (region %in% ids) {
    reg <- ECOsh[ECOsh$DomainID == region,]
  } else if (region %in% doms) {
    reg <- ECOsh[ECOsh$DomainName == region,]
  } else {
    print("Unrecognized NEON domain. Options are:")
    print(doms)
    print(ids)
    quit()
  }
} else if (type == "STATE") {
  reg <- getData("GADM", country="USA", level=1)
  
  if (region == "CONUS") {
    reg <- reg[reg$NAME_1 != "Alaska",]
    reg <- reg[reg$NAME_1 != "Hawaii",] 
  } else {
    states <- unique(reg$NAME_1)
    if (!(region %in% states)) {
      print("Unrecognized state name. Options are:")
      print(states)
      quit()
    }
    reg <- reg[reg$NAME_1 == region,]
  }

} else if (type == "BOX") {
  # https://www.math.ucla.edu/~anderson/rw1001/library/base/html/strsplit.html
  xxyy <- strsplit(region, "_")[[1]]
  #print(length(xxyy))
  if (length(xxyy) != 4) {
    print("For first argument BOX, second argument expects four numbers, seperated by '_'.")
    quit()
  }
  x1 <- as.numeric(xxyy[1])
  x2 <- as.numeric(xxyy[2])
  y1 <- as.numeric(xxyy[3])
  y2 <- as.numeric(xxyy[4])
  #print(c(x1,x2,y1,y2))
  
  # https://rstudio-pubs-static.s3.amazonaws.com/202536_7a122ff56e9f4062b6b012d9921afd80.html
  x_coord <- c(x1, x1, x2, x2, x1)
  y_coord <- c(y1, y2, y2, y1, y1)
  reg <- cbind(x_coord, y_coord)
  reg <- Polygon(reg)
  reg <- Polygons(list(reg),1)
  reg <- SpatialPolygons(list(reg)) 
}

saveRDS(reg, file=out_path)
