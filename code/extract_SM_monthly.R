#!/usr/bin/Rscript

library(raster)

# Script by Mario Guevara, 2018
# Modified by Danny Rorabaugh, 2018-9
# Required command-line argument: year
# Optional command-line argument: folder with year-named directory with sm files (default: ~)
# Optional command-line argument: start_month (default: 1)
# Optional command-line argument: end_month (default: 12, unless start_month specified, then default: start_month)
# Assumes satellite sm data is in one directory per year, named with the year.
# In the year's folder, there must be one .nc file for each day.

args <- commandArgs(trailingOnly=T)
year <- args[1]
if ( length(args) < 2 ) {
    dir_with_year <- "~"
} else {
    dir_with_year <- args[2]
}

# If a third argument (integer 1-12) is given,
# Monthly mean extaction begins with that month.
# If a fourth argument (args[3] <= args[4] <= 12) is given,
# Montlhy mean extractions ends with that month.
if ( length(args) < 3 ) {
    start_month <- 1
    end_month <- 12
} else {
    start_month <- args[3]
    if ( length(args) < 4) {
        end_month <- start_month
    } else {
        end_month <- args[4]
    }
}

m0 = as.integer(start_month)
m1 = as.integer(end_month)

# Set the start and end date to 
# the first day of the start months and the last day of the end month, respectively.
start_date <- as.Date(paste0(year, "-", start_month, "-01"))
# To get the end-date for the final month, 
# assume the month has 28 days, then increase by 1 so long as the month doesn't change.
end_date <- as.Date(paste0(year, "-", end_month, "-28"))
while (format(end_date + 1, format="%m") == format(end_date, format="%m")) {
    end_date <- end_date + 1
}

# Set the directory to look for .nx files to the <year> subdirectory
dir_in <- paste0(dir_with_year, "/", year)
print(paste("The directory with sm files is:", dir_in))

# Create the name for the output file.
if ( length(args) < 3 ) {
    file_out <- paste0(dir_with_year, "/", year, "_ESA_monthly.rds")
} else if ( length(args) < 4 ) {
    mm <- format(start_date, format="%m")
    file_out <- paste0(dir_with_year, "/", year, "_", mm, "_ESA_monthly.rds")
} else {
    m0 <- format(start_date, format="%m")
    m1 <- format(end_date, format="%m")
    file_out <- paste0(dir_with_year, "/", year, "_", m0, "-", m1, "_ESA_monthly.rds")
}
print(paste("The output file will be:", file_out))

# Stack in all relevant .nc files.
l <- list()
for (m in seq(m0, m1)) {
    mm = sprintf("%02d", m)
    pattern <- paste0(year, mm, "[[:print:]]*.nc$")
    print(paste("Extracting files matching pattern", pattern, "in", dir_in))
    l <- c(l, list.files(path=dir_in, pattern=pattern, full.names=T))
}
print(paste("The first in the list of sm files is: ", l[1]))
sm <- stack(l,  varname="sm")
print("All sm files have been raster-stacked.")
print(paste("The date range is", start_date, "through", end_date))

# Define each column name by the date
idx <- seq(start_date, end_date, "day")
sm <- setZ(sm, idx)
names(sm) <- idx

print("Calculating monthly means...")
monthly <- stack()
for (m in seq(m0, m1)) {
    mm = sprintf("%02d", m)
    new = calc(sm[[grep(paste0(".",mm,"."), names(sm), fixed=T)]], mean, na.rm=T)
    monthly <- stack(monthly, new)
}
names(monthly) <- as.character(seq(m0, m1))
print("Monthly means calculated.")

idx <- seq(start_date, end_date, "month")
monthly <- setZ(monthly, idx)
print("Converting data to 'SpatialPixelsDataFrame'...")
monthly <- as(monthly, "SpatialPixelsDataFrame")
print("Data converted to 'SpatialPixelsDataFrame'.")

print(paste("Saving data to:", file_out))
saveRDS(monthly, file=file_out)
print(paste("Data saved to:", file_out))

