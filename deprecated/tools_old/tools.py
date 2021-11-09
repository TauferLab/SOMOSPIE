###############################################################################################################
## Bash/system/OS interaction.

import sys
import os
import subprocess
from subprocess import Popen
import numpy as np
import pandas as pd

def bash(argv):
    arg_seq = [str(arg) for arg in argv]
    #print(arg_seq)
    proc = Popen(arg_seq)#, shell=True)
    proc.wait() #... unless intentionally asynchronous
    
    
##################################################################################################################    

def download_dem(file):
    with open(file, 'r', encoding='utf8') as dsvfile:
        lines = dsvfile.readlines()
    lines = [line.rstrip() for line in lines]
    
    for line in lines:
        comands = ['wget', line]
        bash(comands)
        
##################################################################################################################

def mergin_raster(List_of_Rasters):
    
    # Merge the two first Raster from the list
    commands = ['./Mosaicking.R', List_of_Rasters[0], List_of_Rasters[1], 'Temp_Mosaicking.img']
    bash(commands)
    
    List_of_Rasters = List_of_Rasters[2:]
    for list in List_of_Rasters:
        print(list)
        commands = ['./Mosaicking.R', 'Temp_Mosaicking.img', list, 'Temp_Mosaicking.img']
        bash(commands)
    os.rename('Temp_Mosaicking.img', 'Mosaicking.img')
    
##################################################################################################################

def croping_desired_region(Raster, boundary):
    
    # Converting the raster to a temporal CSV file
    command = ['./Raster_2_csv.R', Raster, 'temp.csv']
    bash(command)
    temp = pd.read_csv('temp.csv')
    temp = temp[(temp['x'] >= boundary[0]) & (temp['x'] <= boundary[1]) & (temp['y'] >= boundary[2]) & (temp['y'] <= boundary[3])]
    temp.to_csv('temp.csv', index = False, header=True)
    command = ['./Csv_2_raster.R', 'temp.csv', 'desired_region.img']
    bash(command)
    return temp

##################################################################################################################   
    
def convert_to_sdat(File_name_of_region):
    command = ['./Change_Raster_Format.R', File_name_of_region, File_name_of_region[0:-4]+'.sdat']
    bash(command)
    
    return command

##################################################################################################################  

def Change_Raster_Format(List_of_Files, new_format):
    
    for list in List_of_Files:
        command = ['./Change_Raster_Format.R', list, 'TIFF'+list[4:-5]+new_format]
        print(command)
        bash(command)

################################################################################################################## 

def Create_Evaluation_file(Name_of_File, Name_of_parameter):
    
    command = ['./Raster_2_csv.R', Name_of_File[0], 'evaluation.csv']
    evaluation = pd.read_csv('evaluation.csv')
    evaluation = evaluation[['x', 'y']]
    evaluation.to_csv('evaluation.csv', index = False, header=True)
    i = 0
    for file in Name_of_File:
        command = ['./add_topos.R', 'evaluation.csv', file, 'evaluation.csv', Name_of_parameter[i]]
        i = i+1
        bash(command)

