#!/usr/bin/env python3

#load_ESACCI_file.py

#This file contains functions to load in the raw CCI data


#os.path.abspath(relative_path) converts a relative path to an absolute path
from os.path import abspath
#os.listdir(path) lists all entries in the path
from os import listdir
#os.path.join(folder, file) joins folder and file into a single path string
from os.path import join

#netCDF4 is used to read in .cn files
#http://www.ceda.ac.uk/static/media/uploads/ncas-reading-2015/10_read_netcdf_python.pdf
from netCDF4 import Dataset

#numpy is a standard mathematical package for python
import numpy as np


#This creates the path for a specified year, or returns False if that folder does not exist
def create_folder_path(year = 2015, source_type  = "C"):
    #year must be an integer
    #  from 1978 to 2015 if source_type is "C" or "A"
    #  from 1991 to 2015 if source_type is "P"
    type_str = {"A": "S-ACTIVE", 
                "P": "V-PASSIVE", 
                "C": "V-COMBINED"}
    first_year = {"A": 1991, "P": 1978, "C": 1978}
    if (year < first_year[source_type]) or (year > 2015):
        print("A folder doesn't exists for {} in {}.".format(source_type, year))
        return False
    folder_path = abspath("../Ricardo_Llamas/Soil_Moisture_Products/ESA_CCI/Original_Data/ESACCI-SOILMOISTURE-L3S-SSM{}_{}-2015-v03.2/{}"\
                          .format(type_str[source_type], first_year[source_type], year))
    return folder_path


#This creates the file name for a specified year, month, and day
def create_file_name(year, month, day, source_type = "C"):
    #year must be an integer
    #  from 1978 to 2015 if source_type is "C" or "A"
    #  from 1991 to 2015 if source_type is "P"
    #month must be an integer from 1 to 12
    #  or from 10 to 12 if year is 1978
    #  or from 8 to 12 if year is 1991 and source_type is "P"
    type_str = {"A": "S-ACTIVE_1991", 
                "P": "V-PASSIVE_1978", 
                "C": "V-COMBINED_1978"}
    return "ESACCI-SOILMOISTURE-L3S-SSM{}-{}{:02}{:02}000000-fv03.2.nc"\
           .format(type_str[source_type], year, month, day)


def test_print():
    for st in ["A", "P", "C"]:
        print(st+":")
        for yr in [1978, 2000, 2016]:
            folder_path = create_folder_path(yr, st)
            if folder_path:
                print(folder_path)
                print(len(listdir(folder_path)))
#            print("Example file: " + create_file_name(yr, 1, 1, st))

#test_print()


#This loads the contents of the data file for a specified year, month, and day
def load_file(year, month, day, source_type = "C"):
    
    #First check if the relevant folder exists
    folder_path = create_folder_path(year, source_type)
    if not folder_path:
        return False
    
    #Second make sure there is exactly one matching data file in the relevant folder
    yyyymmdd = "{}{:02}{:02}".format(year, month, day)
    file_names = [name for name in listdir(folder_path) if (yyyymmdd in name)]
    if len(file_names)==0:
        print("There are no files matching {}.".format(yyyymmdd))
        return False
    if len(file_names)>1:
        print("There are {} files matching {}.".format(len(file_names), yyyymmdd))
        return False
    
    #Now return the content of the data file
    file_path = join(folder_path, file_names[0])
#    print(file_path)
    return Dataset(join(folder_path, file_names[0]))

#Here's a test load to see how what's inside a NETCDF4_CLASSIC object
test = load_file(1998, 11, 2)
print("\nThe file_format is:\n{}".format(test.file_format))
print("\nThe data_model is:\n{}".format(test.data_model))
print("\nThe dimensions.keys() are:\n{}".format(test.dimensions.keys()))
print("\nThe dimensions are:\n{}".format(test.dimensions))
print("\nThe groups are:\n{}".format(test.groups))
print("\nThe variables.keys() are:\n{}".format(test.variables.keys()))
#for key in test.variables.keys():
#    print("\nThe variables[{}] is:\nP{}".format(key, test.variables[key]))

#d = np.array(test.variables['sm'])[0]
#print(len(d), len(d[0]), [entry for row in d for entry in row if entry != d[0][0]])

def extract_data(ncdf):
    #the data is stored within the variables
    v = ncdf.variables

    #lat range [-90, 90]
    lat = np.array(v['lat'])
    X = len(lat)

    #lon range [-180, 180]
    lon = np.array(v['lon'])
    Y = len(lon)

    #days since 1970-01-01
    T = int(np.array(v['time'])[0])

    #print([dir(v[key]) for key in v.keys()])
    
    data_keys = ['t0', 'sm', 'sm_uncertainty', 'dnflag', 'flag', 'freqbandID', 'mode', 'sensor']
    #data_keys = [key for key in v.keys() if 'long_name' in dir(v[key])] 
    #print("data_keys: ", data_keys)
    
    data = {}
    for key in data_keys:
        data[key] = np.array(v[key])[0]
    long_names = {key: v[key].long_name for key in data_keys}
    fill_values = {key: v[key]._FillValue for key in data_keys}

    flag_keys = ['dnflag', 'flag', 'freqbandID', 'mode', 'sensor']
    #flag_keys = [key for key in v.keys() if 'flag_values' in dir(v[key])] 
    #print("flag_keys: ", flag_keys)
    
    flag_dicts = {key: dict(zip(v[key].flag_values, v[key].flag_meanings.split(' '))) \
                  for key in flag_keys}
    #for fdb = flag_dict_bins[key], fdb[i] is the flag corresponding to 2**i
    # for example, when key='sensor', fdb[0]='SSMR' and fdb[2]='TMI'
    #              so 'SSMR+TMI' is flag 2**0 + 2**2 = 1 + 4 = 5
    flag_dicts_bin = {key: [flag_dicts[key][2**i] \
                            for i in range(len(flag_dicts[key])) \
                            if 2**i in flag_dicts[key]] \
                      for key in flag_keys}

    #print(Y, X, T, '\n', long_names, fill_values, '\n', flag_dicts_bin)

    return T, X, Y, data, long_names, fill_values, flag_dicts_bin

test_data = extract_data(test)
print(test_data[:3], test_data[3].keys(), test_data[4:])
print(test_data[3]['sm'][0])

def count_flags(year, month, day, source_type="C"):
    ncdf = load_file(year, month, day, source_type)
    T, X, Y, data, long_names, fill_values, flag_dicts_bin = extract_data(ncdf)
    
    flag_keys = flag_dicts_bin.keys()
    print(flag_keys)
    counts = {key: {flag: 0 for flag in flag_dicts_bin[key]} for key in flag_keys}

   # def bin_pows(n):
   #     bp = []
   #     i = 0
   #     while n>0:
   #         if n%2 == 1:
   #             bp.append(i)
   #         n = n//2
   #         i += 1
   #     return bp

    def bin_pows(n):
        return [p for p,x in enumerate(reversed(bin(n))) if x=='1']

    sm = data['sm']
    for x in range(X):
        for y in range(Y):
            if sm[x][y] != fill_values['sm']:
                for key in flag_keys:
                    b = data[key][x][y]
                    #print(x, y, key, b, bin_pows(b))
                    for p in bin_pows(b):
                        counts[key][flag_dicts_bin[key][p]] += 1

    print(counts)

count_flags(2000, 1, 1)

