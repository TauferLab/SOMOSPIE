#!/usr/bin/Rscript

##Script parallel RF
##Prepared by Mario Guevara and  Danny Rorabaugh, 2018
library(quantregForest)
library(caret)
library(raster)
library(rgdal)
library(doMC)
library(doParallel)

args = commandArgs(trailingOnly=TRUE)
trainFile = args[1]
prediFile = args[2]
path = args[3]
covars = as.integer(args[4])

#sprintf("args: %s", args)

y <- read.table(trainFile, sep=",", header=T) ## lat, long, soil moisture average per year, and potentially covariates

if (covars) {
  z <- data.frame(z=y[,3], y[,1:2], y[,4:ncol(y)])
} else {
  z <- data.frame(z=y[,3], y[,1:2])
}

cl <- makeCluster(detectCores(), type='PSOCK')
registerDoParallel(cl)

ctrl <- trainControl(method = "cv", 
                     savePred=T)

rfmodel <- train(z~., 
                 data=z,
                 method = "rf", 
                 trControl = ctrl, 
                 importance=T)

if (prediFile=="0") {
    saveRDS(rfmodel, file=path)
} else {
    x <- read.table(prediFile, sep=",", header=T) ## (low resolution DEM and SAGA standard terrain parameters)

    print(rfmodel)

    predrf <- predict(rfmodel, x)

    pred <- data.frame(x[c(1,2)], RF=predrf)

    write.table(pred, 
                file=path, 
                row.names=F,
                col.names=F,
                sep=",")
}

stopCluster(cl = cl)

