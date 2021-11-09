
# Code from Mario, 12 Sep 2019 for:
# * splitting a raster file into tiles
# * running an plotting kmeans

library(GSIF)

library(raster)
s <- raster('SOC_30cm_mx_conus_250m_iscn_inegi_1991_2000.tif')
ex <- extent(s)
ex <- as(ex, 'SpatialPolygons')
plot(ex)
proj4string(ex) <- CRS(projection(s))
plot(ex)
x <- getSpatialTiles(ex, 1000000, 1000000,return.SpatialPolygons = TRUE)
plot(x)

#tile 12 

 cr <- crop(s, x[12])

plot(cr, add=TRUE)
cellStats(cr, mean)
cellStats(cr, sd)
va <- getValues(cr)
class(va)
fit <- kmeans(va, 3)
v <- getValues(cr)
i <- which(!is.na(v))
v <- na.omit(v)
E <- kmeans(v, 3, iter.max = 100, nstart = 10)
clara_raster <- raster(s)
clara_raster <- raster(cr)
clara_raster[i] <- clus$clustering
kmeans_raster[i] <- E$cluster
kmeans_raster <- raster(cr)
kmeans_raster[i] <- E$cluster
plot(kmeans_raster, col=c('red','blue', 'gray'))
class1 <- kmeans_raster
class1[class1 != 1] <- NA
plot(class1)
as.data.frame(stack(kmeans_raster, s))
as.data.frame(stack(kmeans_raster, cr ))
df <- as.data.frame(stack(kmeans_raster, cr ))
