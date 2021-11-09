#!/usr/bin/Rscript

## Plots a heatmap of a 3-column .csv file
## lat/lon coords in first two columns, 
## value to plot (e.g., soil moisture) in third column

library(raster)

#Specify input file, whether there's a header, and output file
#Example calls:
#   ./4c-plot_png.R ../from_Mario/10.2.4.csv T ../from_Mario/1_10.2.4.png
#   ./4c-plot_png.R ../data/2016/4/8.5.1/predictions/KKNN.csv F ../figs/4_8.5.1_KKNN.png
args <- commandArgs(trailingOnly=T)

h <- as.logical(args[2])
data <- read.csv(args[1], header=h)

str(data)

if (h) {
    coordinates(data) <- ~x+y
} else {
    coordinates(data) <- ~V1+V2
}

#https://www.rdocumentation.org/packages/sp/versions/1.3-1/topics/spplot
#http://www.cookbook-r.com/Graphs/Output_to_a_file/
png(args[3])
spplot(data[3])
dev.off()
