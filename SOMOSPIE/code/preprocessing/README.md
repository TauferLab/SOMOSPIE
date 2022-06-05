# Data (pre-)processing and general purpose scripts

add_topos.R

        Affixes columns of covariate data to in_file

      Call with:
        ./1a-add_topos.R out_file in_file [COV] [NAMES*]

      Arguments:
        out_file    path of output column-added
        in_file     path of csvfile or other stack-able that needs columns added
                    headers of cols 1 and 2 should be x and y
        COV         optional path of raster file with covariate data
                    USA_topos.tif by default
        NAMES*      optional list of names of the covariate columns


coarsify.R

        Imports a specified file to a raster, mean-aggregates by a specified factor 
        (increasing coarseness), and saves to specified path.

      Call with:
        ./coarsify.R [in_file] [out_file] [agg_fact]


create_shape.R

        Given a specified region type and region name, creates an shapefile to the specified path.

      Call with:
        ./create_shape.R [type] [region] [out_path]


crop_to_shape.R

        Given a specified data file and shape file, crops data to shape and saves to specified target.

      Call with:
        ./crop_to_shape.R [in_file] [shape_path] [out_file]


drop_cols.py

        Make a copy of a csv with only specified columns kept/dropped.


extract_SM_monthly.R

        Given folder of ESA-CCI satellite data, extracts monthly sm averages.

      Call with:
        ./extract_SM_monthly.R year [location]

      Arguments:
        year            Required: name of directory, containing one .nc file per day
        location        Directory containing the year directory; default is ~


joint_pca.py

        Normalises and then performs PCA on the specified training data
        and applies the same transformation to the specified prediction data 
    
      Call with:
        ./joint_pca.py IN_TRAIN IN_PREDI OUT_TRAIN OUT_PREDI LOG_FILE

      Arguments:
        IN_TRAIN        training data file name
        IN_PREDI        prediction data file name
        OUT_TRAIN       desired out-name for pca'd training data file
        OUT_PREDI       desired out-name for pca'd prediction data file
        LOG_FILE        the path to a .txt where logging will be appended


panda_scripts.py

        Data curation functions for importing data and working with pandas dataframes
        Generally loaded into other scripts with: import panda_scripts as ps
        

make_raster_stack.R

        Given a folder path, out_path, and list of spatial data files from the specified folder,
        creates a single raster stack and saves to specified target.

      Call with:
        ./create_shape.R [in_folder] [out_file] [in_files*]


reproject_raster.R

        Given the path to a spatial data file and a target, 
        reprojects data to a standard WGS84 lon-lat project and saves to specified target.

      Call with:
        ./reproject_raster.R [in_folder] [out_file]


