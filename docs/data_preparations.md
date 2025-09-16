Data Preparation & Preprocessing
=================================

SOMOSPIE supports a variety of preprocessing functions, which allow users to modify custom data before being used by any [machine learning algorithms](soil_moisture_predictions.md). Once the data has been installed, it should be preprocessed using the following methods. 

!!! note

    - All preprocessing methods are found within the directory `SOMOSPIE/code/preprocessing/`. 
    - The [Data Guide](data_guide.md) elaborates on the data necessary for SOMOSPIE, in case of confusion.
    - The data must be downloaded. This guide assumes data is within a directory located at `SOMOSPIE/data`.
        - See the "Data Fetching" section of [Additional Features](additional_features.md) for a guide on fetching data.

## Preparing Soil Moisture Data
Soil moisture data should be obtained from the European Space Agency Climate Change Initiative (ESA-CCI) soil moisture dataset. This dataset captures the available soil moisture at a 27km x 27km resolution for the entire world, allowing for accurate reading of the data for a specified year; however, some gaps may appear due to various factors. The data is formatted as a NetCDF (.nc) file for each day for a specified year. 

Once downloaded, the data can be preprocessed from daily soil moisture data into monthly soil moisture data within the specified year using `extract_SM_monthly.R`. This results in a structured dataset similar to the following:

| Column | Description                                | Example   |
|--------|--------------------------------------------|-----------|
| x      | Longitude location                         | -101.375  |
| y      | Latitude location                          | 37.125    |
| X1     | Soil moisture average for January          | 0.112     |
| X2     | Soil moisture average for February         | 0.160     |
| ...    | ...                                        | ...       |
| X12    | Soil moisture average for December         | 0.349     |
*Table 1: example results of extract_SM_monthly.R*

The data will be available in an .rds format, which will eventually be converted into a .csv with added terrain parameters. 

**Example**:
```bash
./extract_SM_monthly.R 2017
```

## Preparing Terrain Parameters

### Obtaining Terrain Parameters
Terrain parameters can be obtained in two ways: GEOtiled or HydroShare. GeoTiled is an open-source software that efficiently generates terrain parameters from Digital Elevation Models (DEMs). For more information on generating terrain parameters using GEOtiled, please visit [GEOtiled](https://globalcomputing.group/GEOtiled/).

HydroShare contains a dataset "Explanatory Variables and DEMs," whose columns describe the following terrain parameters, all of which can be used within SOMOSPIE.

| Parameter                   | Description                                                                                                                       | Units                    |
| --------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | ------------------------ |
| Terrain Aspect              | The orientation of the terrain slope                                                                                              | Radians                  |
| Catchment Area              | Specific catchment area, the area from which rainfall flows into a river, lake, or reservoir                                      | Square meters            |
| Channel Network Base Level  | Channel network base level, the distance of each pixel to the highest surrounding elevation                                           | Meters                   |
| Distance to Channel Network | Distance from each pixel to the nearest channel network, stream, or river                                                          | Meters                   |
| Convergence Index           | Convergence index obtained by averaging the bias of the slope directions of adjacent cells from the central cell, subtracting 90° | -90° to +90°             |
| Horizontal Curvature        | Plan curvature, the curvature of the hillside in a horizontal plane. Indicates concavity or convexity of terrain                  | Unitless (centered at 0) |
| DEM, Elevation              | Digital elevation model 1x1km                                                                                                     | Meters above sea level   |
| Length Slope Factor         | Length of constant slopes from-to a given point                                                                                   | Meters                   |
| Relative Slope Position     | Position of relative height maxima as a function of slope. 0 = valley floor, 100 = ridge top                                      | Continuous (0–100)       |
| Analytical Hillshading      | Representation of topographic relief simulating the effect of natural light on the surface                                        | Adimensional             |
| Filtered DEM                | Elevation data after identifying and filling surface depressions for hydrologic analysis                                          | Meters above sea level   |
| Terrain Slope               | The change of elevation relative to horizontal distance; measure of steepness or inclination                                      | Radians                  |
| Valley Depth Index          | Interpolation of channel network base level elevation and subtraction from original elevations                                    | Meters                   |
| Vertical Curvature          | Profile curvature intersecting the plane defined by the Z axis and the maximum gradient. Positive = convex, negative = concave                | Unitless (centered at 0) |
| Topographic Wetness Index   | Indicator of likelihood of saturated soil during rain events and sediment/matter accumulation                                     | Adimensional             |
*Table 2: acceptable terrain features accepted from HydroShare*

## Coarisfying Parameters [Optional]
With terrain parameters downloaded, an optional step is to coarsen the parameters, which will ultimately result in quicker soil moisture predictions at the cost of resolution. The resolution can be coarsened by an integer factor greater than 1. This is not a necessary step, as the data can be used at its native resolution. The script `coarsify.R` coarsens the resolution through the command: `./coarsify.R [input_file] [output_file] [aggregation_factor]`. 

**Example**: Scale the resolution by a factor of 5
```bash
./coarsify.R topo.tif coarse_topo.tif 5
```

### Reprojecting the raster
Although the terrain parameters are obtained, they might not be in a usable format for SOMOSPIE. The raster file with the terrain parameters should be standardized to the WGS84 format, which uses the geographic coordinate system (longitude/latitude). The file may already be in this format, but for safety, it is recommended to reproject the raster to ensure compatibility. 

To reproject the raster, run `./reproject_raster.R [Input_files] [Output_files]` in the command line.

**Example**:
```bash
./reproject_raster.R ../data/topo_predictors/${topo}.tif ../data/topo_predictors/${topo}.tif`. 
```

!!! warning

    `reproject_raster.R` is currently depricated; the required R library PlotKML is depricated. 

### Stacking the Rasters
The terrain parameters come as multiple raster files that describe each terrain parameter. These features need to be combined into a single file that encapsulates all features into a raster format. Merging the files into a single file is performed through a raster stack, which stacks the terrain parameters into a single raster. 

To make the raster stack, run the command `./make_raster_stack.R [output_directory] [input_files]`.

**Example**:
```bash
./make_raster_stack.R ./topo_predictors/ ./data/topo15_CONUS_1km.tif Analytical_Hillshading.tif Aspect.tif 
```

## Preparing Ecoregions
### Creating Ecoregion shape
Ecoregions can be obtained from the [Commission for Environmental Cooperation (CEC) website](https://www.cec.org/north-american-environmental-atlas/terrestrial-ecoregions-level-iii/). They should be downloaded as a shapefile. Other options for ecoregion preparation include states and boxes. These ecoregions must be converted to an .rds shape file through `create_shape.R` before proceeding. To create this .rds file, run:`./create_shape.R [region_type] [region] [output_path]`.

**Example 1**: Using the state of Arizona
```
./create_shape.R STATE ARIZONA ./data/shapes/Arizona.rds
```
**Example 2**: Using CEC level III region 10.2.4
```
./create_shape.R CEC 10.2.4 ./data/shapes/CEC_10_2_4.rds
```
**Example 3**: Using a box to set an ecoregion
```
./create_shape.R BOX -120_-110_30_40 ./data/shapes/box.rds
```

## Creating the Final Dataset
### Merging Soil Moisture and Terrain Parameters
With the prepared soil moisture stack and terrain parameters stack, the two files can be combined into one .csv file for training. Combining the files is done through the R script `add_topos.R`. The script can be run through the command line using:
```
./add_topos.R [soil_moisture_file] [covariates_stack_file] [output_file] [terrain_parameters (optional)]
```
**Example**: 
```bash
./add_topos.R soil_moisture.rds cov.tif prepared_data.csv SLOPE ASPECT HILLSHADING
```
### Cropping to Ecoregion
While the prepared .csv could technically run, it is essential to crop data to the region of interest defined by the ecoregions. Doing so results in substantial speedups for SOMOSPIE and requires significantly less memory than working on a large, uncropped area. Cropping the prepared data is done through the `crop_to_shape.R` script, using the previously created shapefile. It accepts the prepared dataset, along with the prepared ecoregion shape as parameters.

**Example**:
```bash
./crop_to_shape.R prepared_data.csv ./data/shapes/CEC_10_2_4.rds prepared_data_cropped.csv
```

## Example Prepared Dataset
train.csv for State of Oklahoma:

| index | x        | y      | z           | elevation | aspect      | slope       |
| ----- | -------- | ------ | ----------- | --------- | ----------- | ----------- |
| 0     | -101.375 | 37.125 | 0.112136401 | 960       | 1.435353398 | 0.002797498 |
| 1     | -101.125 | 37.125 | 0.160304278 | 911       | 1.291842222 | 0.002738319 |
| 2     | -100.875 | 37.125 | 0.184895456 | 863       | 1.106565714 | 0.004054314 |
| ...   | ...      | ...    | ...         | ...       | ...         | ...         |
| 450   | -94.125  | 33.625 | 0.348578483 | 91        | 4.439002514 | 0.004484821 |
*Table 3: prepared dataset*

!!! info ""

    Note: X is longitude, y is latitude, and z is soil moisture values. 