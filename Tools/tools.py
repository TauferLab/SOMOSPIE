###############################################################################################################
## Bash/system/OS interaction.

import sys
import os
import subprocess
from subprocess import Popen
import numpy as np
import pandas as pd
import math
import matplotlib.pyplot as plt
import time

def bash(argv):
    arg_seq = [str(arg) for arg in argv]
    #print(arg_seq)
    proc = Popen(arg_seq)#, shell=True)
    proc.wait() #... unless intentionally asynchronous
    
################################################################################################################
# Models Available

Models = {'KKNN' : '/home/lvalera/Src_SOMOSPIE/code/2b-kknn.R',
          'SBM'   : '/home/lvalera/Src_SOMOSPIE/code/hypppo7.py',
          'HYPPO' : '/home/lvalera/Src_SOMOSPIE/code/hypppo7.py',
          'RF'    : '/home/lvalera/Src_SOMOSPIE/code/2c-rf.R'
}

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
    
    n = len(List_of_Rasters)
    if n == 1:
        command = ['cp',  List_of_Rasters[0], 'Mosaicking.img']
        bash(command)
    else:
          
        # Merge the two first Raster from the list
        commands = ['./Mosaicking.R', List_of_Rasters[0], List_of_Rasters[1], 'Temp_Mosaicking.img']
        bash(commands)

        List_of_Rasters = List_of_Rasters[2:]
        for list in List_of_Rasters:
            print(list)
            commands = ['./Mosaicking.R', 'Temp_Mosaicking.img', list, 'Temp_Mosaicking.img']
            bash(commands)
        os.rename('Temp_Mosaicking.img', 'Mosaicking.img')
    
#################################################################################################################

def croping_region(Raster_input, min_long, max_long, min_lat, max_lat, Raster_output):
    
    # Converting the raster to a temporal CSV file
    command = ['./CroppingRegion.R', Raster_input, min_long, max_long, min_lat, max_lat, Raster_output]
    bash(command)
    
##################################################################################################################   
    
def convert_to_sdat(Raster):
    
    command = ['./Change_Raster_Format.R', Raster, Raster[0:-4]+'.sdat']
    bash(command)
 
 ##################################################################################################################  

def terrestrial_parameters(name_file):
    command = ['./terrestrial_parameters.sh', name_file]
    bash(command)
    
###################################################################################################################

def creating_stack(command):
    bash(command)

#####################################################################################################################

def creating_moisture(model, training, evaluation, moisture):  
        if model in ['SBM', 'HYPPO']:
            command = [Models[model], '-m', model, '-t', training, '-e', evaluation, '-o', moisture]
        else:
            command = [Models[model], '-t', training, '-e', evaluation, '-o', moisture]
        bash(command)
    
#####################################################################################################################

def changing_to_utm(Input_file, Output_file):
    command = ['./CSVLATLONG_2_CSVUTM.R', Input_file, Output_file]
    bash(command)
    


