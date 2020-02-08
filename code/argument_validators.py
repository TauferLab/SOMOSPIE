# Danny Rorabaugh, 2018
# Various functions for validating argparse arguments.

import pathlib, re, string 


# Converts common representations of a bool to True or False.
def str_to_bool(bstring):
    if type(bstring)==bool:
        #print(f"{bstring} is already type bool.")
        return bstring
    elif type(bstring)==int:
        #print(f"{bstring} is an int, which casts to {bool(bstring)}.")
        return bool(bstring)
    elif type(bstring)==str:
        if bstring.lower().strip()in ("t", "true", "y", "yes", "1"):
            return True
        elif bstring.lower().strip() in ("f", "false", "n", "no", "0", ""):
            return False
        else:
            raise ValueError(f"Could not interpret '{bstring}' as bool.") 
    else:
        raise TypeError(f"str_to_bool failed because it expected input type in [str, int, bool] but got {type(string)}.")

        
# Check that input path exists and is a file.
# Required packages: pathlib
def validate_input_file(input_file, exists=True):
    if input_file:
        input_file_path = pathlib.Path(input_file)
        if input_file_path.is_file():
            print(f"Will read data from {input_file_path}.")
            return input_file_path
        else:
            raise ValueError(f"Provided input file: \"{input_file}\" does not exist.")
    elif exists:
        raise ValueError("Input file unspecified!")
    else:
        return None


# Check that output path is valid; warn if it is a file.
# Required packages: pathlib
def validate_output_file(output_file):
    if output_file:
        output_file_path = pathlib.Path(output_file)
        if output_file_path.is_file():
            print(f"Warning! There is already a file at {output_file_path}.")
        else:
            print(f"Will save file to {output_file_path}.")
        return output_file_path
    else:
        return None


# Function to remove all non-alphanumeric characters.
# Required packages: re
def alphanumeric(dirty_string):
    try:
        dirty_string = str(dirty_string)
    except TypeError:
        print(f"What monster is this?! Cannot cast to a string!")
    clean_string = re.sub(r"[\W_]+", "", dirty_string)    
    return clean_string


# Function to convert a month string into its corresponding integer (1-12).
# Required packages: re, string
def month_to_int(month_string):
    # First, check if the input was already an integer.
    if type(month_string) == int:
        if (0 < month_string) and (month_string < 13):
            #print(f"{month_string} is already a valid month integer.")
            return month_string
        else:
            #print(f"{month_string} is already an integer, but not in the 1-12 range.")
            return 0

    # If it's not an integer or string, raise Cain.
    try:
         month_string = str(month_string)    
    except TypeError:
        print(f"Not able to cast 'month_string' to a string!")
        return 0
    
    # Now it must be a string.
    # Remove non-alphanumeric characters and change all letters to upper-case.
    MONTHSTRING = alphanumeric(month_string).upper()
    if len(MONTHSTRING)==0:
        #print(f"{month_string} has no alphanumeric characters to interpret.")
        return 0

    # If it starts with a numeral, we remove all non-numeric characters and change to an integer.
    if MONTHSTRING[0] in string.digits or (len(MONTHSTRING)>1 and MONTHSTRING[1] in string.digits):
        ms = int(re.sub(r"[^0-9]+", "", MONTHSTRING))
        if (0 < ms < 13):
            #print(f"{month_string} is month number {ms}.")
            return ms
        else:
            #print(f"{month_string}, interpretted as {ms}, is not in the 1-12 range.")
            return 0

    # Otherwise, we assume that the month is spelled out with at least three letters.
    # Any month should be identifiable by the first three letters of the English spelling.
    name_dict = {"JAN":1, "FEB":2, "MAR":3, "APR":4, "MAY":5, "JUN":6, 
                 "JUL":7, "AUG":8, "SEP":9, "OCT":10, "NOV":11, "DEC":12}
    #name_dict = {"JAN":1, "ENE":1, "FEB":2, "MAR":3, "APR":4, "ABR":4, "MAY":5, "JUN":6, 
    #             "JUL":7, "AUG":8, "AGO":8, "SEP":9, "OCT":10, "NOV":11, "DEC":12, "DIC":12}
    
    # Language supplements
    # https://web.library.yale.edu/cataloging/months
    supplements = {
        ## Spanish
        "ES":{"ENE":1, "ABR":4, "AGO":8, "DIC":12}, 
        ## French June and July both begin "jui"--not distinguished with this 3-letter system
        ## German 
        "DE":{"MAI":5, "OKT":10, "DEZ":12}, 
        ## Italian
        "IT":{"GEN":1, "MAG":5, "GIU":6, "LUG":7, "AGO":8, "SET":9, "OTT":10, "DIC":12}, 
        ## Estonian June and July both begin with "juu"
        ## Portuguese
        "PT":{"FEV":2, "ABR":4, "MAI":5, "AGO":8, "OUT":10, "DEZ":12}, 
        ## Russian June and July both begin with "iiu"
        ## Serbian
        "SR":{"MAJ":5, "AVG":8, "OKT":10}, 
    }
    # This update for-loop can be commented out if you only want English month specification
    #for lang in supplements:
    #    name_dict.update(supplements[lang])
    
    if (len(MONTHSTRING) > 2):
        MON = MONTHSTRING[:3]
        if MON in name_dict:
            #print(f"{month_string}, interpretted as {MON}, is month number {name_dict[MON]}.")
            return name_dict[MON]
        else:
            #print(f"{month_string}, interpretted as {MON}, is not a valid month.")
            return 0
    else:
        #print(f"{month_string}, interpretted as {MONTHSTRING}, starts with a letter, but is too short to be a month.")
        return 0


