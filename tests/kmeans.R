#cluster analysis of satellite uncertainty estimates for soil moisture data
#mg, 2018
#data preparation
#raster files library
library(raster)
#make a list of nc files 
lis <- list.files(pattern='nc')
#stack the uncertainty maps 
u <- stack(lis, varname='sm_uncertainty')
#plot one Jan 1 2016 (1-366)
plot(u[[1]])
#draw a extent 
e <- drawExtent()
#crop the data to your extent
u2 <- crop (u, e)
#convert to data frame or sample
	u2 <- as.data.frame(u2, xy=TRUE)
	u2[is.na(u2)] <- 10# maximum uncertainty
#PCA library
library(FactoMineR)
#library(FactoInvestigate)
fitpca<- PCA(u2)
#summary of the PCA
summary(fitpca)
#get the dimentions
#dims <- data.frame(fit$var$coord)
#Extract dimensions 
dims <- data.frame((fitpca$ind[[1]]))
#grouping method: kmeans from 2 to 10 groups
fitclus2 <- kmeans(dims, 2, iter.max = 10, nstart = 1)
fitclus3 <- kmeans(dims, 3, iter.max = 10, nstart = 1)
fitclus4 <- kmeans(dims, 4, iter.max = 10, nstart = 1)
fitclus5 <- kmeans(dims, 5, iter.max = 10, nstart = 1)
fitclus6 <- kmeans(dims, 6, iter.max = 10, nstart = 1)
fitclus7 <- kmeans(dims, 7, iter.max = 10, nstart = 1)
fitclus8 <- kmeans(dims, 8, iter.max = 10, nstart = 1)
fitclus9 <- kmeans(dims, 9, iter.max = 10, nstart = 1)
fitclus10 <- kmeans(dims, 10, iter.max = 10, nstart = 1)
#add results to the data frame
u2$groups2 <- fitclus2$cluster
u2$groups3 <- fitclus3$cluster
u2$groups4 <- fitclus4$cluster
u2$groups5 <- fitclus5$cluster
u2$groups6 <- fitclus6$cluster
u2$groups7 <- fitclus7$cluster
u2$groups8 <- fitclus8$cluster
u2$groups9 <- fitclus9$cluster
u2$groups10 <- fitclus10$cluster
#make a map of groups
vis <- u2[c(1:2, 369:377)]
 coordinates(vis) <- ~x+y
gridded(vis) <- TRUE
vis <- stack(vis)
#make an column average and standard deviation
u2$meanSoilMoisture <- apply(u2[3:368], 1, mean)
u2$sdevSoilMoisture <- apply(u2[3:368], 1, sd)
#interpret results
boxplot(u2$meanSoilMoisture ~ as.factor(u2$groups2))
boxplot(u2$meanSoilMoisture ~ as.factor(u2$groups3))
boxplot(u2$meanSoilMoisture ~ as.factor(u2$groups4))
boxplot(u2$meanSoilMoisture ~ as.factor(u2$groups5))
boxplot(u2$meanSoilMoisture ~ as.factor(u2$groups6))
boxplot(u2$meanSoilMoisture ~ as.factor(u2$groups7))
boxplot(u2$meanSoilMoisture ~ as.factor(u2$groups8))
boxplot(u2$meanSoilMoisture ~ as.factor(u2$groups9))
boxplot(u2$meanSoilMoisture ~ as.factor(u2$groups10))
#end of exercise today ...


