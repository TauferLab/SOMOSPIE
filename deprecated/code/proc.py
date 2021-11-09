#!/usr/bin/env python3

# Data processor for SOMOSPIE
# Danny Rorabaugh, Oct 2018, with help from Dylan Chapp

########################
# The following was removed from code/readme.txt:
#    
#    proc.py
#        Wrapper for pca, filter, month selection, etc.
#
########################

import argparse, pathlib, re, string
import pandas as pd
import panda_scripts as ps
import joint_pca as pca


def validate_args(args):
    print(f"args:\n{args}\n")

    valid_args = {}

    # Should we perform principal component analysis (PCA)?
    valid_args["PCA"] = ps.str_to_bool(args.PCA)

    # Validate file paths.
    # Whether input_2 is necessary depends on whether we're using PCA
    valid_args["input_file"] = ps.validate_input_file(args.input_file)
    valid_args["output_file"] = ps.validate_output_file(args.output_file)
    valid_args["input_2"] = ps.validate_input_file(args.input_2,
                                                    exists=valid_args["PCA"])
    valid_args["output_2"] = ps.validate_output_file(args.output_2)

    # Do the columns have headers in the input file(s)?
    valid_args["header"] = ps.str_to_bool(args.header)

    if valid_args["PCA"] and not valid_args["header"]:
        raise ValueError("We can't perform PCA without headers in your data.")

    # Has a numeric month been specified?
    valid_args["month"] = ps.month_to_int(args.month) 

    # Are there NAs to remove?
    valid_args["NAs"] = ps.str_to_bool(args.NAs)

    print(f"valid_args:\n{valid_args}\n")
    return valid_args 


if __name__ == "__main__":

    # Parse command-line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input_file", 
                        help="The input file should be a csv or tsv.")
    parser.add_argument("-c", "--header",
                        help="Binary value to indicate whether the input_file has a header row.",
                        default="true")
    parser.add_argument("-n", "--NAs",
                        help="Binary value to indicate whether the input_file has NAs that need to be removed.",
                        default="true")
    parser.add_argument("-m", "--month",
                        help="Indicates that the file has monthly data, and only the specified month should be kept.",
                        default="0")
    parser.add_argument("-o", "--output_file",
                        help="The location of the output csv file.")
    parser.add_argument("-I", "--input_2",
                        help="A secondary input file.")
    parser.add_argument("-O", "--output_2",
                        help="A secondary output location.")
    parser.add_argument("-P", "--PCA", 
                        help="Binary value to indicate whether to perform PCA on input file(s).", 
                        default="false")
    args = parser.parse_args()

    # Check that arguments are sane
    valid_args = validate_args(args)

    # Read a delimited file (e.g., .csv) into a dataframe
    # The regular expression below only matches a single-comma or single-tab
    # delimiter right now, but you can change it to whatever you need later
    delimiter_regex = "[,\t]"
    if valid_args["header"]:
        head = 0
    else:
        head = None
    df = pd.read_csv(valid_args["input_file"], 
                     delimiter=delimiter_regex,
                     engine='python',  
                     header=head,
                     na_filter=valid_args["NAs"])

    # Make sure column headers are alphanumeric
    df = df.rename(columns=ps.alphanumeric)
    
    m = valid_args["month"]
    if m:
        replacements = ps.monthify(df.columns)
        df = df.rename(index=str, columns=replacements)
        df = ps.keep_month(df, m)
        df = df.dropna(subset=[str(m)])

    if valid_args["PCA"]:
        # Read in second files for PCA dimension reduction.
        df2 = pd.read_csv(valid_args["input_2"], 
                          delimiter=delimiter_regex, 
                          engine='python',  
                          na_filter=valid_args["NAs"])
        df2 = df2.rename(columns=ps.alphanumeric)

        # Identify the paramaters to attack.
        params = pca.get_params(df)
        
        # Activate PCA-bot!
        df, df2, comps = pca.joint_pca(df, df2, params)

    # Write the results to file.
    out = valid_args["output_file"]
    o1 = df.to_csv(path_or_buf=out, index=False)
    if not out:
        print(o1)
    out2 = valid_args["output_2"]
    if out2:
        df2.to_csv(path_or_buf=out2, index=False)
    

