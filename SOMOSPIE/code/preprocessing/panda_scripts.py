#!/usr/bin/env python3

# Sample code by Dylan Chapp, Oct 2018
# This should walk you through the following:
# 1. Reading in comma or tab delimited data from a file
# 2. Slicing columns and rows
# 3. Replacing NaNs
# Modified by Danny Rorabaugh

import argparse
import pandas as pd 
import somosplot as splot
import argument_validators as arg_val


def validate_args(args):
    validated_args = {}

    # Validate file paths.
    validated_args["input_file"] = arg_val.validate_input_file(args.input_file)
    validated_args["plot"] = arg_val.validate_output_file(args.plot)

    # Does the input file have column headers or not?
    validated_args["header"] = arg_val.str_to_bool(args.header)

    # Has a numeric month been specified?
    validated_args["month"] = arg_val.month_to_int(args.month) 

    # Is a point-size specified?
    if args.size:
        validated_args["size"] = float(args.size)

    return validated_args 


# Function that takes iterable and returns dictionary of replacements to make.
# If any of the column headings can be interpretted as months--
#  that is, if it starts with a number or the same first three letters as a month--
#  then they WILL BE interpretted as months.
def monthify(cols):
    #print(f"Columns before: {cols}")
    replacements = {c:arg_val.month_to_int(c) for c in cols}
    replacements = {key:str(val) for key, val in replacements.items() if val}
    #print(f"The columns to rename are: {replacements}")
    return replacements    

    #dataframe = dataframe.rename(replacements, axis='columns')
    #print(f"Columns after: {dataframe.columns}")
    #return dataframe            

    
# Function to remove all monthly columns, except the one specified
def keep_month(df, month):
    # This assumes the df has some monthly columns headed 1 through 12    
    # Let's grab the x- and y-coordinate columns, the specified month, and the
    # remaining co-variate data columns
    # There are lots of ways to do this (See: https://stackoverflow.com/questions/14940743/selecting-excluding-sets-of-columns-in-pandas)
    # But we're going do it in an... unsophisticated way
    columns_to_exclude = [str(x) for x in range(1, 13) if (x != month and str(x) in df.columns)]
    #columns_to_keep = [col for col in df.columns if col not in columns_to_exclude]
    return df.drop(columns_to_exclude, axis=1)


# Cut out rows of a dataframe whose values in specified column are not in specified range
def clear_outliers(df, col=2, a=0, b=1, strict=False):

    # First, make sure the specified column exists
    headers = df.columns
    if type(col)==int:
        try:
            col = headers[col]
        except ValueError:
            print(f"There is no column number {col}.")
    elif col not in headers:
        raise ValueError(f"There is no column {col}.")
   
    # Then drop all rows with NA in specified column.
    df = df.dropna(subset=[col]) 

    # Finally, drop values outside the specified range.
    if strict:
        return df[(a < df[col]) and (df[col] < b)]
    else:
        return df[(a <= df[col]) and (df[col] <= b)]


# Cut to specified longitude and lattitude ranges.
# Assumes first column is x-values (lon), second is y-values (lat)
# World default: lon=[-180, 180], lat=[-90, 90]
# CONUS: lon=[-124.7844079, -66.9513812], lat=[24.7433195, 49.3457868]
# CONUS bounds from https://gist.github.com/jsundram/1251783
def crop_to_region(df, lon=[-180, 180], lat=[-90, 90]):
    if (len(lon) != 2) or (len(lat) !=2 ):
        print("You have the wrong number of entries in your bounding lists!")
        return False
    try:
        lon.sort()
        lat.sort()
    except:
        print(f"Tried to .sort() lon {lon} and lat {lat}, but failed.")
        return False
    # Clear x-values outside of longitude range.
    df = clear_outliers(df, col=0, a=lon[0], b=lon[1])
    # Clear y-values outside of lattitude range.
    return clear_outliers(df, col=1, a=lat[0], b=lat[1])


# Demonstrate month-related dataframe stuff, assuming the dataframe has month-headed columns
def month_demo(dataframe, m):
    # Let's convert all month column headers to integers.
    print(f"\nColumns before: {dataframe.columns}")
    replacements = monthify(dataframe.columns)
    dataframe = dataframe.rename(index=str, columns=replacements)
    print(f"\nColumns before: {dataframe.columns}")
    
    # Now lets do something practical
    # Let's grab the X and Y coordinate columns, the column for April, and the
    # remaining co-variate data columns
    month_data = keep_month(dataframe, m)
    print(f"\nmonth_data:\n{month_data.head()}") 

    # Now that we have our data for one month, lets do something about all of those NaNs
    # See for details: https://pandas.pydata.org/pandas-docs/stable/generated/pandas.DataFrame.fillna.html
    
    # We can replace with zeros
    zero_fill = month_data.fillna(0).head()
    print(f"\nzero_fill:\n{zero_fill}")

    # We can replace with a fixed value for each column
    # WARNING: Don't actually fill NaNs with the hash of the column name... 
    column_to_fill = {col_name: hash(col_name) for col_name in month_data.columns}
    constant_fill_by_column = month_data.fillna(value = column_to_fill).head()
    print(f"\nconstant_fill_by_column:\n{constant_fill_by_column}")

    # Or we can drop them altogether.
    dropped_nas = month_data.dropna().head()
    print(f"\ndropped_nas:\n{dropped_nas}")


# Demonstration of what you can do with a dataframe.
def dataframe_demo(dataframe):
    # What are the columns called? 
    #headers = dataframe.head(0)
    headers = dataframe.columns
    print(f"\nheaders:\n{headers}")

    # What type is the head?
    head_type = type(headers)
    print(f"\nhead_type:\n{head_type}")

    # I look at a column's values if I know only the column's name but not its index 
    # df.head(n=5) shows the first n (default 5) rows of the df.
    #x_coordinate_column = dataframe['X'].head()
    #print(f"x_coordinate_column:\n{x_coordinate_column}")
    # How about if I know the index but not the name? 
    zeroth_column = dataframe[ dataframe.columns[0] ].head()
    print(f"\nzeroth_column:\n{zeroth_column}")

    # WARNING! A column selected from a dataframe is not itself a dataframe!
    # Instead it is a "series" 
    type_of_column = type(zeroth_column)
    print(f"\ntype_of_column:\n{type_of_column}") 

    # What if I want multiple columns? 
    #x_and_y_coordinate_columns = dataframe[ ['X', 'Y'] ]
    x_and_y_coordinate_columns = dataframe[ headers[:2] ].head()
    print(f"\nx_and_y_coordinate_columns:\n{x_and_y_coordinate_columns}") 

    # WARNING! Multiple columns selected from a dataframe are themselves a dataframe!
    type_of_multiple_columns = type(x_and_y_coordinate_columns)
    print(f"\ntype_of_multiple_columns:\n{type_of_multiple_columns}") 

    # What if I want to select a row instead? 
    # Notice how in the above printed output, dataframe rows have an index 
    # printed to their left. We can access rows using this index, but there are
    # two subtly different ways of doing so. 
    # The first way is with "iloc"
    # Suppose we want to get the 17th row:
    seventeenth_row = dataframe.iloc[17]
    print(f"\nseventeenth_row:\n{seventeenth_row}")

    # However, suppose we wanted to get the row that **is labeled** "row 17".
    # In that case, we'd use "loc" instead
    # In our case, these are the same row, but in practice they don't have to
    # be. Row labels might change during, e.g., data cleaning. 
    row_labeled_seventeen = dataframe.loc[17]
    print(f"\nrow_labeled_seventeen:\n{row_labeled_seventeen}") 


    # Print min and max values for the columns.
    print(f"min values:\n{dataframe.min(axis=0)}")
    print(f"max values:\n{dataframe.max(axis=0)}")

    # Let's plot this dataframe
    splot.soil_map(dataframe)


if __name__ == "__main__":
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file", 
                        help="The input file should be a csv or tsv.")
    parser.add_argument("-c", "--header",
                        help="Binary value to indicate whether the input_file has a header row.",
                        default="true")
    parser.add_argument("-m", "--month",
                        help="Indicates that the fine has monthly data, and only the specified month should be kept.",
                        default="0")
    parser.add_argument("-p", "--plot",
                        help="Path where to save a soil moisture plot of the input.")
    parser.add_argument("-s", "--size",
                        help="Point size for heatmap. Will only use if --plot also specified. 0.3 is default.",
                        default=".3")
    args = parser.parse_args()

    # Check that arguments are sane
    validated_args = validate_args(args)

    # Read a delimited file (e.g., .csv) into a dataframe
    # The regular expression below only matches a single-comma or single-tab
    # delimiter right now, but you can change it to whatever you need later
    delimiter_regex = "[,\t]"
    if validated_args["header"]:
        head = 0
    else:
        head = None
    dataframe = pd.read_csv(validated_args["input_file"], delimiter=delimiter_regex, header=head, engine='python')

    # Make sure column headers are alphanumeric
    dataframe = dataframe.rename(columns=arg_val.alphanumeric)
    
    # The argument -m/--month triggers month_demo on the specified month
    if validated_args["month"]:
        month_demo(dataframe, validated_args["month"])
        
    # The argument -p/--plot gives a path where to save a plot of the input file
    if validated_args["plot"]:
        splot.soil_map(dataframe, out=validated_args["plot"], size=validated_args["size"])
    else:
        dataframe_demo(dataframe)

