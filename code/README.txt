The files in this 'code' folder, described below, 
are the elements of the modular SOMOSPIE workflow.

Any no-longer-used script should be moved to the 'retired' subfolder.

-------------------------------------------------------------------------------

SOMOSPIE.ipynb
    The wrapper for the full SOMOSPIE workflow

    Run via Jupyter Notebook

For testing and development, this has been split into:
    SOMOSPIE_input.ini
    SOMOSPIE_input_parser.py
    __A_curate.py
    __B_model.py
    __C_analyze.py
    __D_visualize.py
    __utils.py
    SOMOSPIE_wrapper.py

Mid May 2019:
    Modify arguments in SOMOSPIE_input.py 
    Then execute ./SOMOSPIE_wrapper.py from the commandline

Late May 2019:
    Modify arguments in SOMOSPIE_input.ini
    Then execute from the commandline: ./SOMOSPIE_wrapper.py, which uses ./SOMOSPIE_input_parser.py
        or
    Create new argument file file_name.ini
    Then execute from the commanline: ./SOMOSPIE_wrapper.py file_name.ini

Late October 2019:
    Begin development of new SOMOSPIE.ipynb in repository's main directory
     as wrapper for both data acquisition and SOMOSPIE execution.

Late 2019 -- January 2020:
    Major development of widgets and data acquisition procedures.

--------------------------------------------------------------------------------

0/1. Data (pre-)processing and general purpose scripts

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


---------------------------------------------------------------------------------------

2. Models

IMPORTANT!
Every model script should work with .csv files in which
* the top row is the header data,
* the first two columns are the lat/lon coords, 
* the third column is the sm data,
* all other columns are covariates


    hypppo7.py
        Travis and Danny's scipt for HYPPO, KNN, and SBM.
        See work and previous version in ../hyppo_testing


    2b-kknn.R
        This is Mario's knn script.
 
      Call with:
        Rscript 2b-kknn.R -t IN_TRAIN -e IN_EVAL -l LOG_FILE -o OUT_PATH -k K_CAP

      Arguments:
        IN_TRAIN        train file; path of .csv file
        IN_EVAL         eval file; path of .csv file with points to evaluate the model at,
                        or "0" (default) to output the model
        LOG_FILE        log file path,
                        or "0" (default) to print logging statements
        OUT_PATH        out file path 
        K_CAP           max number of nearest neighbors


    2c-rf.R
        This is Mario's random forests script. 
        Same arguments as 2b-kknn.R except for no -k.


    2d-parallel.R
        An in-progress script that is intended to run rf knn and other R scripts in parallel

-------------------------------------------------------------------------------

3/4. Analysis & Visualization

    3c-obs_vs_pred.R
    Takes two .csv files, 
          extracts the points in pred to the grid of obs, 
          produces a scatterplot to compare the values,
          and computes the R^2 correlation


    somosplot.py
        Functions for plotting pandas dataframes
        Generally imported with: import somosplot as splot

--------------------------------------------------------------------------------

