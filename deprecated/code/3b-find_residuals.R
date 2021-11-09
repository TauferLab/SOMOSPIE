#!/usr/bin/Rscript

# Compare predicted soil moisture with the original satellite soil moisture product
# Script by Mario Guevara and Danny Rorabaugh, 2018

######################
# The following was removed from code/README.txt:
#
#    3b-find_residuals.R
#        Computes relative residuals between a prediction and the original data.
#        Uses resample() to average the fine-grain predictions in all cells that fall
#         within a course cell of the original data.
#
#      Call with:
#        Rscript 3b-find_residuals.R orig_file pred_file out_file log_file [figs]
#
#      Arguments:
#        orig_file       .csv file with original data
#        pred_file       .csv file with predicted data
#        out_file        path to where residuals should be saved as a new .csv file
#        log_file        path to where logs are stored
#        figs            optional; add ANYTHING here and figures will be saved to Rplot.pdf in the working directory
#
######################

############
##Setup
############

library(rgdal)
library(raster)
library(rasterVis)

args <- commandArgs(trailingOnly=T)

#import original satellite data
#csv with header
orig_file <- read.csv(args[1])

#import soil moisture prediction file
#csv with no header
pred_file <- read.csv(args[2], header=FALSE)

#save locations for output of logs and risiduals
resid_loc <- args[3]
log_loc <- args[4]

#Open the log file for all print() statements
#https://www.rdocumentation.org/packages/base/versions/3.5.1/topics/sink
sink(file = log_loc, append=T)
print("---------------------------------------------------------")
print("Running the residual script with the following arguments:")
print(args)

##############
##Algorithms
##############

#Ignore covariates (everything past the third column) in the original file
dat <- orig_file[,1:3]

#Eliminate rows with NAs
#dat <- na.omit(dat)
pred_file <- na.omit(pred_file)

#Set lat&lon(first two columns) as independent variables
colnames(dat)[1:2] <- c("X", "Y")
colnames(pred_file)[1:2] <- c("X", "Y")
coordinates(dat) <- ~X+Y
coordinates(pred_file) <- ~X+Y

latLong <- '+proj=longlat +datum=WGS84 +no_defs '
proj4string(dat) <- CRS(latLong)

#Grid the original data
datGrid <- dat
gridded(datGrid) <- TRUE
datRast <- raster(datGrid)

proj4string(pred_file) <- CRS(latLong)

gridded(pred_file) <- TRUE

predRast <- raster(pred_file)
pred <- resample(predRast, datRast)

dif <- calc(stack(datRast, pred), diff)

print(names(dat))

#Define scatterplot data
sp_data <- extract(pred, dat) ~ dat$X4

############
##Outputs
############

#Save residuals to output file
residuals <- as.data.frame(dif, xy=T, na.rm=T)
write.table(residuals, file=resid_loc, row.names=F, sep=",", col.names=F)

#A fifth argument, if present, turns on visualization
if (length(args)>4) {

    #Call on GADM for visualization
    country <- getData("GADM", country='United States', level=1)
    country <- spTransform(country, CRS=projection(latLong))

    #Plot map of difference
    levelplot(dif, par.settings = RdBuTheme) + layer(sp.polygons(country))

    #Plot scatterplot
    plot(sp_data, 
         xlab='observed', 
         ylab='predicted', 
         cex.axis=1.5, 
         cex.lab=1.5)

    #Add linear regression to scatterplot
    abline(lm(sp_data))
}

#Log regression data
regression_info <- summary(lm(sp_data))
print("Scatterplot regression data:")
print(regression_info, file=log_loc, append=T)

#Close the log file
sink()

