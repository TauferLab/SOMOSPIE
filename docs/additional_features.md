Additional Features
===================

SOMOSPIE features a variety of additional features, including optional preprocessing options, data fetching, and visualization/analysis tools. This guide demonstrates how to use any of these additional features to increase model accuracy, or analyze of results. 

## Data preprocessing 🧹
SOMOSPIE features optional preprocessing steps that potentially boost the accuracy of results. These include dropping columns in a prepared dataset, and Joint Principal Component Analysis. 

### Joint Principal Component Analysis ( joint PCA)

Joint PCA is a statistical method that analyzes multiple related datasets. It finds common patterns of variation across the datasets by training a model. The model identifies the relationships between variables and uses these relationships to reduce the dimensions of a dataset. `joint_pca.py` utilizes this model to remove original features from training and prediction data, replacing them with fewer columns called principal components. This helps capture the important features of the original variables.

Joint PCA can be run through the Python script `joint_pca.py`, using:
```
python3 ./joint_pca.py IN_TRAIN IN_PREDI OUT_TRAIN OUT_PREDI LOG_FILE
```
### Drop Columns
To reduce the dimensionality of training datasets, columns can be dropped according to the user's needs. The Python script `drop_cols.py` accomplishes this by allowing users to specify which columns to keep and drop. 

To drop columns, run the python script `drop_cols.py` using:
```
python3 ./drop_cols.py [input_file] [output_file] -k [cols_to_keep] -d [cols_to_drop]
```
!!! Note

    Use -d to drop columns, or -k to specify columns to keep. Do not use both. 

## Data Fetching 📡
SOMOSPIE features a collection of methods to retrieve data, including several shell scripts, which fetch and save relevant data locally. These methods are located within the `SOMOSPIE/data_readers/satellite` repository, and use shell to fetch the corresponding variables. 

### Fetching Soil Moisture
`fetch_soil_moisture.sh` fetches and saves ESA_CCI soil moisture data for each day of a specified year; it is saved into the data directory, in a directory `ESA_CCI/{year}/`. Fetch soil moisture can be run through the command `./fetch_soil_moisture.sh [YEAR]`

!!! Warning

    Fetching soil moisture through `fetch_soil_moisture.sh` can take up to 30 minutes.

### Fetching Terrain Parameters
Instead of using GEOtiled, terrain parameters can be fetched from HydroShare as well. `fetch_topo_predictors.sh` does this by fetching a specified terrain parameter one at a time as a .prj, .sdat, and .sgrd file. It can be run using: `./fetch_topo_predictors.sh topo_predictors [$TOPO]`. Topographic features are saved within data/topo_dir/. For a list of valid terrain parameters to fetch, see [data preparation](data_preparation.md).

### Fetching Ecoregions
`fetch_ecoregions.sh` retrieves CEC ecoregion shapefiles at each available level (I-III). It saves each ecoregion within its own directory; for example, level I CEC ecoregions are saved to `NA_Terrestrial_Ecoregions_Level_I_Shapefile/`. The script does not require any arguements and can be run using `./fetch_ecoregions.sh`. 

Within the Satellite directory, there also exists a reg_list.csv file, which contains labels describing each region's title. 

## Analytics & Visualization 📈 

### Compare Observations to Estimations
extracts the soil moisture predictions from the predictions and compares them to the observed soil moisture at said point, computing R<sup>2</sup> and MSE. These can be used as metrics for how well a model performed at making soil moisture predictions. `obs_vs_pred.R` performs these evaluations and can be called using:

```
./obs_vs_pred.R [observed_value_file] [prediction_file] [R^2 file] [rmse_output_file]
```

### Plotting dataframes
The `somosplot.py` script provides a variety of visualization tools for SOMOSPIE. Users can visualize soil moisture data using various plot types, such as: 
- histograms
- soil maps
- heat-maps
Any prepared CSV file can be plotted using the command line structure:

```
python3 ./somosplot.py [input_file] -c [has_header] -o [output_file] -p [plot_type] -t "[plot_title]" -s [point_size] -d [dependent_column_index] -m [min_value] -M [max_value]
```