#!/usr/bin/Rscript

##Script RF
##Prepared by Mario Guevara and Danny Rorabaugh, 2018
library(optigrab)
trainFile <- opt_get(c("train", "t"), required=T)
evalFile <- opt_get(c("eval", "e"), default="0")
logFile <- opt_get(c("log", "l"), default="0")
outPath <- opt_get(c("out", "o"), required=T)

log <- function(log_item, file=logFile){
    if (file=="0") {
        print(log_item)
    } else {
        write(log_item, file=file, append=T)
    }
}

# Load required libraries
library(quantregForest)
library(caret)

# Read in the training data
y <- read.table(trainFile, sep=",", header=T) ## lat, long, soil moisture average per year, and potentially covariates
log(sprintf("trainFile loaded: has %s rows and %s columns.", nrow(y), ncol(y)))

# Move the third column (dependent variable) to the front
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
log(sprintf("rf training data created from trainFile: has %s rows and %s columns.", nrow(z), ncol(z)))

# Train the rf model
ctrl <- trainControl(method="cv", savePred=T) #method="repeatedcv", number=5, repeats=5
rfmodel <- train(z~., data=z, method="rf", trControl=ctrl, importance=T)
log("Training complete!")
print(rfmodel)

# If no eval file is specified, save the model.
# In an eval file is specified, load it in and evaluate the model on the eval data.
if (evalFile=="0") {
    log(sprintf("Out path for RF model: %s", outPath))
    saveRDS(rfmodel, file=outPath)
} else {
    x <- read.table(evalFile, sep=",", header=T) ## (low resolution DEM and SAGA standard terrain parameters)

    predrf <- predict(rfmodel, x)
    pred <- data.frame(x[c(1,2)], RF=predrf)
    
    log(sprintf("Out path for RF prediction: %s", outPath))
    write.table(pred, file=outPath, row.names=F, col.names=F, sep=",")
}

