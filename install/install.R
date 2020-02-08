needed.packages <- c("raster", "caret", "quantregForest", "kknn", "rgdal", "rasterVis", "optigrab", "rgeos", "ncdf4", "plotKML")
for (pack in needed.packages) {
    if (!require(pack, character.only=T)) install.packages(pack)
}
