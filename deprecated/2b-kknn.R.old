#!/usr/bin/Rscript

## Script KKNN (http://cran.r-project.org/web/packages/kknn/kknn.pdf)
## PREPARED BY MARIO GUEVARA (UDEL) TO MICHELA TAUFER, 2017
## Modified by Danny Rorabaugh, 2018

## References
## Hechenbichler K. and Schliep K.P. (2004) Weighted k-Nearest-Neighbor Techniques and Ordinal
## Classification, Discussion Paper 399, SFB 386, Ludwig-Maximilians University Munich 
## (http://www.stat.uni-muenchen.de/sfb386/papers/dsp/paper399.ps)

## https://cran.r-project.org/web/packages/optigrab/readme/README.html
## Commandline example: 
## ./2b-kknn.R -t ../data/2012/t-postproc/6.2.csv -e ../data/2012/e-postproc/6.2.csv -o ../data/2012/example.csv -k 20
library(optigrab)
trainFile <- opt_get(c("train", "t"), required=T)
evalFile <- opt_get(c("eval", "e"), default="0")
logFile <- opt_get(c("log", "l"), default="0")
outPath <- opt_get(c("out", "o"), required=T)
kCap <- as.integer(opt_get(c("kcap", "k"), default=20))

log <- function(log_item, file=logFile){
    if (file=="0") {
        print(log_item)
    } else {
        write(log_item, file=file, append=T)
    }
}

# Install necessary libaries
library(kknn)
    
y <- read.table(trainFile, sep=",", header=T) ## lat, long, soil moisture average per year, and potentially covariates
log(sprintf("trainFile loaded: has %s rows and %s columns.", nrow(y), ncol(y)))

## https://www.rdocumentation.org/packages/base/versions/3.5.1/topics/data.frame
if (ncol(y)<3) {
    log("This training file doesn't have at least 3 columns!")
    q()
} else if (ncol(y)==3) {
    z <- data.frame(z=y[,3], y[,1:2])
} else {
    z <- data.frame(z=y[,3], y[,1:2], y[,4:ncol(y)])
    # The following line is necessary if ncol(y)==4.
    # That is because y[,4:ncol(y)] is an array and the name gets messed up. 
    names(z)[4] <- names(y)[4]
}
log(sprintf("kknn training data created from trainFile: has %s rows and %s columns.", nrow(z), ncol(z)))

## You must select the best parameters by tunning them with CV, the parameter k=kmax and the parameter kernel=kernelList. 
kmax <- min(kCap, nrow(z)-2)
log(sprintf("Begining knnTuning with kmax = %s", kmax))

kernelList <- c("rectangular", "triangular", "epanechnikov", "gaussian", "rank", "optimal")
log("We are trying the following kernels:")
log(paste(unlist(kernelList), collapse=", "))

## https://www.rdocumentation.org/packages/kknn/versions/1.2-4/topics/train.kknn
knnTuning <- train.kknn(z~., data=z, kmax=kmax, kernel=kernelList, kcv=10)
log("Training complete!")
print(knnTuning)

kknnTuned = knnTuning$best.parameters

kTuned <- kknnTuned$k
log(sprintf("kTuned: %s", kTuned))

kernelTuned <- kknnTuned$kernel
log(sprintf("kernelTuned: %s", kernelTuned))

kernelIndex <- which(kernelTuned==kernelList)
log(sprintf("kernelIndex: %s", kernelIndex))

mejorIndex <- (kmax*(kernelIndex-1)) + kTuned
log(sprintf("mejorIndex: %s", mejorIndex))

## Compute the RootMeanSquareError and CORrelation of the best result from the training.
## https://www.rdocumentation.org/packages/base/versions/3.5.1/topics/data.matrix
mejoresResultados <- data.matrix(unlist(knnTuning$fitted.values[[mejorIndex]]))
#print(head(mejoresResultados))
rmse <- sqrt(knnTuning$MEAN.SQU[kTuned, kernelIndex])
log(sprintf("rmse: %s", rmse))
## https://www.rdocumentation.org/packages/stats/versions/3.5.1/topics/cor
cd <- cor(z[,1], mejoresResultados) 
log(sprintf("cd: %s", cd))

if (evalFile=="0") {
    log(sprintf("Out path for KKNN model: %s", outPath))
    saveRDS(kknnTuned, file=outPath)
} else {
    ## https://www.rdocumentation.org/packages/utils/versions/3.5.1/topics/read.table
    x <- read.table(evalFile, sep=",", header=T) ## (low resolution DEM and SAGA standard terrain parameters)
    ## https://www.rdocumentation.org/packages/base/versions/3.5.1/topics/sprintf
    log(sprintf("evalFile loaded: has %s rows and %s columns.", nrow(x), ncol(x)))

    ## Build a model with best parameters, predicting for all points of the eval file.
    ## https://www.rdocumentation.org/packages/kknn/versions/1.3.1/topics/kknn
    mejorKKNN <- kknn(z~., train=z, test=x, kernel=kernelTuned, k=kTuned)

    #options("encoding"="UTF-8")
    
    kknn <- data.frame(x[,1:2], kknn=mejorKKNN$fitted.values)
    
    log(sprintf("Out path for KKNN predictions: %s", outPath))
    ## https://www.rdocumentation.org/packages/utils/versions/3.5.1/topics/write.table
    write.table(kknn, file=outPath, row.names=F, col.names=F, sep=",")
}