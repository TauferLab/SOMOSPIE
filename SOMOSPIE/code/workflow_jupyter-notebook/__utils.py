# Many of the functions in __utils.py use variables defined within SOMOSPIE.ipynb,
#  so those function can only be used from within that notebook by running the following:
#  %run -i code/__utils.py

import pandas as pd
import numpy as np
from datetime import datetime as dt

def log(item, file=""):
    if file:
        with open(file, "a") as log_file:
            log_file.write(f"{item}")
    else:
        print(item)
        
###############################################################################################################
## Bash/system/OS interaction.

import sys
import os
import subprocess
from subprocess import Popen

def bash(argv):
    arg_seq = [str(arg) for arg in argv]
    #print(arg_seq)
    proc = Popen(arg_seq)#, shell=True)
    proc.wait() #... unless intentionally asynchronous

###############################################################################################################
## Path stuff.

import pathlib

def append_to_folder(folder_path, suffix):
    if type(folder_path)==str:
        return folder_path.rstrip("/") + str(suffix)
    else:
        folder = folder_path.name + str(suffix)
        return folder_path.parent.joinpath(folder)
    
# Names of the subfolders
SUB_SOIL = "./data_readers/satellite"
SUB_DATA = "data"
SUB_CODE = "code"
SUB_OUTP = "out"
SUB_RESI = "residuals"
SUB_PRED = "predictions"
SUB_FIGS = "figures"
SUB_SHAP = "shapes"
SUB_TOPO = "topo_predictors"

###############################################################################################################
## Argument parsing.

from configparser import ConfigParser
from ast import literal_eval

#This class stores all instances of arguments needed to run SOMOSPIE, as well as output to a config file.
class Arg_Handler:
    #Takes the ini_export filename, a list of the ML methods to be used, and, optionally, an input object.
    def __init__(self,out_name, methods, input_file=None):
        self.methods = methods
        self.output = ConfigParser()
        self.output["DEFAULT"] = {}
        self.output_location = out_name
        self.input_conf = input_file
        
        # This dictionary is the basis of all other data structures in the class, 
        # with an entry for each argument. 
        # Can be updated in the future to add additional arguments, 
        # but requires the same structure to be followed. 
        # If a new type/category is added, more function edits are necessary.
        self.desc_vars = {
        "START": {"category":"setup", "type":"dir", \
                  "description":"The main working directory, containing relevant code and data subdirectories."},
        "CODE": {"category":"setup", "type":"dir", \
                 "description":"The subdirectory with code."}, 
        "DATA": {"category":"setup", "type":"dir", \
                 "description":"The subdirectory for data."},
        "OUTPUT": {"category":"setup", "type":"dir", \
                   "description":"The subdirectory for SOMOSPIE output."}, 
        "REGIONS": {"category":"data", "type":"file", \
                    "description":"The file with list of all regions."}, 
        "SM_FILE": {"category":"data", "type":"file", \
                    "description":"The file with soil moisture data."}, 
        "COV_FILE": {"category":"data", "type":"file", \
                     "description":"The file with covariate data."}, 
        "COV_LAYERS": {"category":"select", "type":"text", \
                     "description":"A list of layers of COV_FILE."}, 
        "EVAL_FILE": {"category":"data", "type":"file", \
                      "description":"The file with evaluation data."}, 
        "YEAR": {"category":"select", "type":"text", \
                 "description":"A list of years."}, 
        "MONTHS": {"category":"proc", "type":"text", \
                   "description":"A list of months."}, 
        "MAKE_T_E": {"category":"proc", "type":"bool", \
                     "description":"True if you want to generate (using SM_FILE and COV_FILE) a train and eval file for each region "}, 
        "USE_PCA": {"category":"proc", "type":"bool", \
                    "description":"True if you want to perform PCA dimension reduction on the covariate data."}, 
        "VALIDATE": {"category":"proc", "type":"float", \
                     "description":"0 for no validation; 1.xx to compare predictions to xx% of the original data; 2 to compare prediction to the training data"}, 
        "RAND_SEED": {"category":"proc", "type":"int", \
                      "description":"Specify a positive integer, or 0 to generate a new random seed."}, 
        "USE_VIS": {"category":"proc", "type":"bool", \
                    "description":"True if you want to generate images for the predictions."}, 
        "MIN_T_POINTS": {"category":"proc", "type":"int", \
                         "description":"The minimum number of train points required for a region to be used."},  
        "BUFFER": {"category":"proc", "type":"int", \
                   "description":"Specify a positive integer for the nubmer of kms you want to expand the training data around each region; 0 for no buffer."},  
        "SUPER": {"category":"proc", "type":"bool", \
                  "description":"If true, then training data for ESA-CCI ecoregions will be expanded to one higher level."},  
        "MODICT": {"category":"method", "type":"modict", \
                   "description":"Dictionary of modeling methods and their parameter specifications"}, 
        }
        
        #This dict stores arrays of arguments, based upon their type.
        self.titled_dict = {}
        for entry in self.desc_vars:
            entry_type = self.desc_vars[entry]["type"]
            # Add the title to the list of titles with that type, or create a new list for a new type
            if entry_type in self.titled_dict:
                self.titled_dict[entry_type].append(entry)
            else:
                self.titled_dict[entry_type] = [entry]
        
        #This dict stores arrays of arguments, based upon their category.
        self.cat_vars = {}
        for entry in self.desc_vars:
            entry_type = self.desc_vars[entry]["category"]
            # Add the title to the list of titles with that type, or create a new list for a new type
            if entry_type in self.cat_vars:
                self.cat_vars[entry_type].append(entry)
            else:
                self.cat_vars[entry_type] = [entry]
        
        #The args dict is where all argument values, keyed off of the argument names. 
        self.args = {}
        
        #This establishes default values for the arguments.
        defaults_by_type = {"dir": "../", "file": "../", "text": "../", "bool": False, "int": 0, "float": 0.0}
        for arg_type in defaults_by_type:
            for title in self.titled_dict[arg_type]:
                self.args[title] = defaults_by_type[arg_type]
        
        #If custom default arguments were supplied, however, the arguments are updated accordingly.
        if self.input_conf:
            for j in self.titled_dict["dir"]:
                self.args[j] = defaultconf["DEFAULT"][j]
            for j in self.titled_dict["file"]:
                self.args[j] = defaultconf["DEFAULT"]["DATA"] + "/" + defaultconf["DEFAULT"][j]
            for j in self.titled_dict["text"]:
                self.args[j] = defaultconf["DEFAULT"][j]
            for j in self.titled_dict["bool"]:
                self.args[j] = bool(int(defaultconf["DEFAULT"][j]))
            for j in self.titled_dict["int"]:
                self.args[j] = int(defaultconf["DEFAULT"][j])
            for j in self.titled_dict["float"]:
                self.args[j] = float(defaultconf["DEFAULT"][j])
            #Literal eval is used here because the anticipated format has a standard Pythonic dictionary for modict.
            self.args["modict"] = literal_eval(defaultconf["DEFAULT"]["modict"])
        else:
            #self.args["modict"] = {"1NN":{}, "KKNN":{}, "RF":{}, "HYPPO":{}, "SBM":{}} 
            self.args["modict"] = {}
        
    #While this function could be used manually, it is only used for the ipywe FileSelectorPanel used later, 
    # which can use a function to automatically update a variable storing the path.
    def setPath(self, pathvar, newpath):
        self.args[pathvar] = newpath
    #A lambda version is necessary for actual use. 
    def setPathFunc(self, pathvar):
        return lambda x: self.setPath(pathvar, x)
    
    # Takes the Jupyter widgets used in the Notebook, and, implicitly, the existing args dictionary, 
    # and writes the config file.
    def updateVars(self, procacc, modictacc):
        # Updates the modict by stepping through each HBox used in the modict accordion, 
        # and filling the variables which have their corresponding Checkbox checked. 
        for learners in modictacc.children[0].children:
            if learners.children[0].value:
                self.args["modict"][learners.children[1].value] = literal_eval(learners.children[2].value)
            #If the corresponding variable was unchecked, remove it from the dict entirely.
            else:
                self.args["modict"].pop(learners.children[1].value, None)
        #Update the args dictionary.
        for step, var in enumerate(procacc.children):
            self.args[procacc.get_title(step)] = var.children[1].value
        
        # Using the up-to-date args dictionary, 
        # fill then write the output ConfigParser to the specified file. 
        for title in self.titled_dict["dir"]:
            self.output["DEFAULT"][title] = self.args[title]
        for title in self.titled_dict["file"]:
            self.output["DEFAULT"][title] = self.args[title]
        for title in self.titled_dict["text"]:
            self.output["DEFAULT"][title] = self.args[title]
        for title in self.titled_dict["bool"]:
            self.output["DEFAULT"][title] = str(int(self.args[title]))
        for title in self.titled_dict["int"]:
            self.output["DEFAULT"][title] = str(self.args[title])
        for title in self.titled_dict["float"]:
            self.output["DEFAULT"][title] = str(self.args[title])
        self.output["DEFAULT"]["modict"] = str(self.args["modict"])
        with open(self.output_location, 'w+') as file:
            self.output.write(file)

    # Empty any files that have been set to a folder.
    def clear_empty_files(self):
        for j in self.titled_dict["file"]:
            if self.args[j] and self.args[j][-1]=='/':
                self.args[j] = ""

###############################################################################################################
## Widgets, general stuff.
sys.path.append("..")

import ipywidgets as widgets
from modules.ipywe.ipywe._utils import close, enable, disable
from modules.ipywe.ipywe.fileselector import FileSelectorPanel
import os
from IPython.display import Image
from itertools import product as iterprod
from ipywidgets import Output, Layout, HBox, VBox

# Takes a list/tuple of options and an (optional) list/tuple of uninitialized widgets.
# Returns a VBox that can be used within an accordian.
# The VBox will look like:
#  "options[0]", widgs[0], widgs[1] . . .
#  "options[1]", widgs[0], widgs[1] . . .
#  ...
def option_list_VBox(options, widgs=[widgets.Checkbox]):
    import ipywidgets as widgets
    box_to_fill = widgets.VBox()
    for j in options:
        lil_box = [widg() for widg in widgs] + [widgets.Label(str(j))] 
        box_to_fill.children += (widgets.HBox(lil_box),)
    return box_to_fill

# Generic method to create an accordion, takes a dictionary of form {key: box of widgets, key: box of widgets}, 
#  returns an accordion with an entry for each key.
def init_accordion(filled_entries):
    new_acc = widgets.Accordion()
    #For each key, add all its widgets to an accordion entry, then name the entry accordingly.
    for step, i in enumerate(filled_entries.keys()):
        new_acc.children += (filled_entries[i],)
        new_acc.set_title(step, i)
    return new_acc
    
# Widget for selecting a local file
def file_widget(start_dir="."):
    
    def save_selection(new_path):
        SelectFile.start_dir = new_path
    
    SelectFile = FileSelectorPanel( 'Select the File',
            start_dir=start_dir, type='file', next=save_selection,
            multiple=False, newdir_toolbar_button=False,
            custom_layout = None,
            filters=dict(), default_filter=None,
            stay_alive=True).panel
    
    return SelectFile

# Widget for selecting a url
def url_widget():
    url = widgets.Text(
        value='http://url.of.remote/file',
        placeholder='Type something',
        description='URL:'
    )
    
    return url

# Standard user options for data sources.
location_data_option = ['Select data source:','Fetch Default Data','Select Local File','Download Remote File']

# General widgets to select the desired desired data source: fetch defaults, select local, or download.
def source_widget(default_widget):
    # Selecting Location of the Data
    LocationData = widgets.Dropdown(
           options=location_data_option,
           value=location_data_option[1],
           description='Location:'
    ) 

    box = VBox(children = (LocationData,))

    # Development of the functions
    # Modify the ipwidget depending on the location of the data
    def action_LocationData(b):
        if LocationData.value==location_data_option[1]:
            box.children = (LocationData,default_widget)
        
        elif LocationData.value==location_data_option[2]:
            box.children = (LocationData,file_widget(SUB_DATA))
        
        elif LocationData.value==location_data_option[3]:
            box.children = (LocationData,url_widget())
            
        else:
            box.children = (LocationData,)
    
    action_LocationData(False)
    display(box)
    LocationData.observe(action_LocationData,names='value')
    
    return box

###############################################################################################################
## Widgets and scripts for soil moisture data.

# ToDo: This function needs to be moved out to it's own script 
#  and rewritten so that each year is completed in an independent shell (tmux?) so as not to hold up the process.
def sm_fetch(year=2017, sm_source="ESA"):
    if sm_source=="ESA":
        if (1978 < year < 2020):
            sm_file = f"{SUB_SOIL}/ESA_CCI/{year}_ESA_monthly.rds"
            if not os.path.exists(sm_file):
                if not os.path.exists(f"{SUB_SOIL}/ESA_CCI/{year}"):
                    bash([f"{SUB_SOIL}/fetch_soil_moisture.sh", year])
                bash([f"{SUB_CODE}/data_preprocessing/extract_SM_monthly.R", year, f"{SUB_DATA}/ESA_CCI"])
            if os.path.exists(sm_file):
                print(f"Monthly means generated for {year}.")
            else:
                print(f"Unknown error! Please delete {SUB_DATA}/ESA_CCI/{year} and try again.")
        else:
            print(f"Full-year ESA-CCI soil moisture data only available 1979 through 2019, not for {year} as requested.")
    else:
        print(f"Soil moisture source {sm_source} not recognized.")

# Widgets to select the desired source of soil moisture data.
# To test the Download file from a URL, try the following link:
# https://www.dropbox.com/s/vfn75swx5e05e3u/TestDownload.rds
def sm_source_widget():
    return source_widget(sm_widget())

# Widgets to select the start year and the end year.
def sm_widget(source="ESA"):
    year_range = {"ESA": [1979, 2019]}
    
    earliest_year, latest_year = year_range[source]
    list_of_years = [str(year) for year in range(earliest_year, latest_year + 1)]

    wStart_year = widgets.Dropdown(
        options=list_of_years,
        value=str(latest_year-2),
        description='Start year:'
    )

    wEnd_year = widgets.Dropdown(
        options=list_of_years,
        value=str(latest_year-2),
        description='End year:'
    )

    # Modify the ipwidget such that the End year is always
    # greater or equal than the Initial Year
    def get_and_plot(b):
        final_years = range(int(wStart_year.value), latest_year + 1)
        wEnd_year.options = [str(final_year) for final_year in final_years]
        wEnd_year.value = wStart_year.value

    wStart_year.observe(get_and_plot)

    return VBox(children=(wStart_year, wEnd_year))

# Loads soil moisture data, depending on the use of the sm_source_widget().
# Returns a widget that can be used to select/specify data year.
def SoilMoistureData(sm_widgets):
    source = sm_widgets.children[0].value
    
    # Set-up the widget for year specification during the next phase (Data Selection).
    current_year = dt.today().year
    sm_widg = widgets.widgets.BoundedIntText(
                                value=current_year,
                                min=1900,
                                max=current_year,
                                description='What year is your dataset?'
                            )
        
    if source==location_data_option[1]:
        wStart_year, wEnd_year = sm_widgets.children[1].children
        start_year = int(wStart_year.value)
        end_year   = int(wEnd_year.value)
        year_range = range(start_year, end_year + 1)
        for year in year_range:
            sm_fetch(year)
        conf_storage.args["SM_FILE"] = conf_storage.args["DATA"] + f"/ESA_CCI/{end_year}_ESA_monthly.rds"
        
        # Update the year-specification widget to only allow the loaded years.
        sm_widg.min = start_year
        sm_widg.max = end_year
        sm_widg.value = end_year
        sm_widg.description = 'Which year do you want to use?'

    elif source==location_data_option[2]:
        path = sm_widgets.children[1].start_dir
        destination_path = f"{note_DATA}/LocalFile"
        if not os.path.exists(destination_path):
            os.makedirs(destination_path)
        local_to_data = ['cp', path, destination_path]
        bash(local_to_data)
        head, FileLoaded = os.path.split(path)
        conf_storage.args["SM_FILE"] = conf_storage.args["DATA"] + "/LocalFile/" + FileLoaded
        print("File Copied.")
        
    elif source==location_data_option[3]:
        url = sm_widgets.children[1].value
        destination_path = f"{note_DATA}/UrlFile"
        if not os.path.exists(destination_path):
            os.makedirs(destination_path)
        url_to_data = ['wget', '-P', destination_path, url]
        bash(url_to_data)
        head, FileLoaded = os.path.split(url)
        conf_storage.args["SM_FILE"] = conf_storage.args["DATA"] + "/UrlFile/" + FileLoaded
        print("File Downloaded.")
        
    else:
        raise ValueError("Error! You must select a data source in the Data Loading widget.")
        
    return sm_widg

###############################################################################################################
## Widgets and scripts for covariate data.

# Loads covariate data, depending on the use of the cd_source_widget().
# Returns a widget that can be used to select/specify layers.
def CovariateData(cd_widgets):
    source = cd_widgets.children[0].value
    
    # Set-up the widget for layer specification during the next phase (Data Selection).
    cov_widg = widgets.widgets.Text(value='["First layer name", ..., "Last layer name"]',
                                   description='What layers does your covariate file have?')
    
    if source==location_data_option[1]:
        entries = cd_widgets.children[1].children[0].children
        topos = [entry.children[1].value for entry in entries if entry.children[0].value]
        topo_fetch(topos)#, agg_fact=5)
        # With only the loaded layers as an option, 
        # we will generate a new widget for selecting which layers to use.
        cov_widg = topo_widget(topos)
        for child in cov_widg.children[0].children:
            child.children[0].value = False
        cov_widg.children[0].children[0].children[0].value = True

    elif source==location_data_option[2]:
        path = cd_widgets.children[1].start_dir
        destination_path = f"{note_DATA}/LocalFile"
        if not os.path.exists(destination_path):
            os.makedirs(destination_path)
        local_to_data = ['cp', path, destination_path]
        bash(local_to_data)
        head, FileLoaded = os.path.split(path)
        conf_storage.args["COV_FILE"] = conf_storage.args["DATA"] + "/LocalFile/" + FileLoaded
        print("File Copied.")

    elif source==location_data_option[3]:
        url = cd_widgets.children[1].value
        destination_path = f"{note_DATA}/UrlFile"
        if not os.path.exists(destination_path):
            os.makedirs(destination_path)
        url_to_data = ['wget', '-P', destination_path, url]
        bash(url_to_data)
        head, FileLoaded = os.path.split(url)
        conf_storage.args["COV_FILE"] = conf_storage.args["DATA"] + "/UrlFile/" + FileLoaded
        print("File Downloaded.")

    else:
        raise ValueError("Error! You must select a data source in the Data Loading widget.")
    
    return cov_widg

# Topographic covariates available from https://www.hydroshare.org/resource/b8f6eae9d89241cf8b5904033460af61
topo_options = ['CONUS_DEM1km', # Elevation.
                'Aspect', # Angle of slope-face away from North.
                'Analytical_Hillshading', # ???
                'Channel_Network_Base_Level', # ???
                # 'Closed_Depressions' # ???; 60% of entries are NA.
                'Convergence_Index', # ???
                'Cross-Sectional_Curvature', # ???
                'Flow_Accumulation', # ???
                'Longitudinal_Curvature', # ??? 
                'LS_Factor', # ???
                'Relative_Slope_Position', # ???
                'Slope', # First derivative of elevation
                'Topographic_Wetness_Index', #???
                'Valley_Depth', # ???
                'Vertical_Distance_to_Channel_Network', # ???
               ]
        
# Given a list of topos (topographic covariates), download the covariates and convert them to lat-lon .tif files.
# The list must be a subset of topo_options.
# If agg_fact > 1, the files are made more coarse, using mean-aggragation to go from 1km to (agg_fact)km resolution.
def topo_fetch(topos=["Slope"], agg_fact=1):
    # If agg_fact is less than 1, set it to 1.
    agg_fact = max(1, int(agg_fact))
    
    topo_folder = f"{SUB_DATA}/{SUB_TOPO}/"
    
    for t in topos:
        
        topo_file = f"{topo_folder}{agg_fact}{t}.tif"
        
        # If the mean-aggregated, reprojected raster doesn't exist, make it.
        if not os.path.exists(topo_file):
            bash([f"{SUB_SOIL}/fetch_topo_predictors.sh", topo_folder, t])
            pre_file = f"{topo_folder}{t}.sdat"
            if agg_fact>1:
                print(f"Scaling {t} to be more coarse, mean-aggragating by a factor of {agg_fact}.")
                bash([f"{SUB_CODE}/data_preprocessing/coarsify.R",  pre_file, topo_file, agg_fact])
                pre_file = topo_file
            bash([f"{SUB_CODE}/data_preprocessing/reproject_raster.R", pre_file, topo_file])
            print(f"Topo layer {t} loaded.")
        
    print("A .tif is ready for every topography layer.")
        
    return topos

# Given a list of topos (topographic covariates), make sure they are downloaded, then stack them in a single .tif file.
# The list must be a subset of topo_options.
def topo_stack(topos=["Slope"], agg_fact=1, out_file=""):
    # If the specified out_file already exists, we can skip this whole function.
    if out_file and os.path.exists(out_file):
        return (out_file, topos)
    
    # If agg_fact is less than 1, set it to 1.
    agg_fact = max(1, int(agg_fact))
        
    topo_fetch(topos, agg_fact)
    
    topo_folder = f"{SUB_DATA}/{SUB_TOPO}/"
    stack_file = f"{topo_folder}stack.tif"
    
    for t in topos:
        topo_file = f"{agg_fact}{t}.tif"
        
        stack_args = [f"{SUB_CODE}/data_preprocessing/make_raster_stack.R", topo_folder, stack_file, "stack.tif", topo_file]
        if t==topos[0]:
            stack_args.pop(-2)
        bash(stack_args)
            
        #print(f"Topo layer {t} stacked.")
    
    print("Topography layers stacked.")
    return (stack_file, topos)
    
# Widgets to select the desired source of covariate data.
def cd_source_widget():
    return source_widget(topo_widget())

# Widget to select topographic covariates.
def topo_widget(topos=topo_options):
    topo_VBox = option_list_VBox(topos)
    topo_acc = init_accordion({"Available Topographic Parameters": topo_VBox})
    
    # Automatically check default option.
    #topo_acc.children[0].children[0].children[0].value = True
    #for child in topo_acc.children[0].children:
    #    child.children[0].value = True
    for i in range(0,len(topo_acc.children[0].children),4):
        topo_acc.children[0].children[i].children[0].value = True
    
    return topo_acc

###############################################################################################################
## Widgets and scripts for region data.

# Widget to select region boundary types.
def reg_type_widget():
    type_description = {
        "STATE": "50 states of the USA, 'District of Columbia', or 'CONUS'.",
        "NEON": "20 NEON ecoclimatic domains (neonscience.org/about/about/spatiotemporal-design).",
        "CEC": "Level 1, 2, or 3 CEC ecoregions (cec.org/tools-and-resources/map-files/terrestrial-ecoregions-level-iii)",
        "BOX": "A longitude/latitude-defined box, uniformly divided into sub-boxes."
                       }
    for reg_type in type_description:
        print(f"{reg_type}: {type_description[reg_type]}")
    
    reg_types = type_description.keys()
    reg_type_VBox = option_list_VBox(reg_types)
    reg_type_acc = init_accordion({"Region Types": reg_type_VBox})
    
    # Automatically check default option.
    reg_type_acc.children[0].children[0].children[0].value = True
    
    display(reg_type_acc)
    
    return reg_type_acc

# Create a region_selection widget based on the reg_type widget.
def region_widget(reg_type_acc):
    # Make a list of region types that were selected in the widget above.
    #print(reg_type_acc.children[0].children)
    region_types = [entry.children[1].value for entry in reg_type_acc.children[0].children if entry.children[0].value]
    #print(region_types)

    # Download shapefiles for ecoregions.
    if (("CEC" in region_types) and (not os.path.exists(f"{SUB_SOIL}/NA_Terrestrial_Ecoregions_Level_I_Shapefile"))) \
      or (("NEON" in region_types) and (not os.path.exists(f"{SUB_SOIL}/NEONDomains_0"))):
        bash([f"{SUB_SOIL}/fetch_ecoregions.sh"])

    # Prepare region lists for regions in region_types.
    possible_regions = f"{SUB_SOIL}/reg_list.csv"
    regs = pd.read_csv(possible_regions, skiprows=[1])
    
    #Modified by Leo to eliminate the .0 from the widget
    regs["CEC.lvl1"]=regs["CEC.lvl1"].fillna(-1)
    regs["CEC.lvl1"] = regs["CEC.lvl1"].astype(int)
    regs["CEC.lvl1"]= regs["CEC.lvl1"].astype(str)
    regs["CEC.lvl1"] =  regs["CEC.lvl1"].replace('-1', '')
    
    if "CEC" in region_types:
        region_types.pop(region_types.index("CEC"))
        region_types += ["CEC.lvl1", "CEC.lvl2", "CEC.lvl3"]
    else:
        conf_storage.args["SUPER"] = False
    
    regs = regs[region_types]
    regs = regs.fillna('')
    
    reg_lists = regs.to_dict('list')
    for instance in reg_lists:
        reg_lists[instance] = list(filter(None, reg_lists[instance]))
    
    def reg_type_widgs(reg_type):
        if reg_type=="BOX":
            return [widgets.IntText]
        else:
            return [widgets.Checkbox]
    
    reg_VBoxes = {reg_type: option_list_VBox(reg_lists[reg_type], reg_type_widgs(reg_type)) for reg_type in reg_lists}
    
    reg_acc = init_accordion(reg_VBoxes)
    
    # Of the VBoxes within the accordion that have a list of Checkbox options, 
    #  check the first of the first by default.
    for i in range(len(reg_acc.children)):
        if reg_acc._titles[str(i)]!="BOX":
            reg_acc.children[i].children[0].children[0].value = True
            break
    
    display(reg_acc)
    return reg_acc

def box_list(x1, x2, y1, y2, nx, ny):
    boxes = []
    
    if (-180 <= x1 < x2 <= 180) and (-90 <= y1 < y2 <= 90) and (nx > 0) and (ny > 0):
        # If integer values are possible, stick with integers.
        if ((x2 - x1)%nx == 0):
            dx = (x2 - x1)//nx
        else: 
            x1 = float(x1)
            dx = (x2 - x1)/nx
        if ((y2 - y1)%ny == 0):
            dy = (y2 - y1)//ny
        else:
            y1 = float(y1)
            dy = (y2 - y1)/ny

        # Build the boxes.
        for ix in range(nx):
            for iy in range(ny):
                boxes.append(f"{x1 + ix*dx}_{x1 + (ix + 1)*dx}_{y1 + iy*dy}_{y1 + (iy + 1)*dy}")
    
    else:
        print("Invalid values for BOX: must have -180 <= x1 < x2 <= 180; -90 <= y1 < y2 <= 90; 0 < nx; 0 < ny.")
    
    return boxes    

# Given a region accordian reg_acc, this saves a list of selected regions to out_file.
def update_regs(reg_acc, out_file):
    region_output = []
    for i, region in enumerate(reg_acc.children):
        # The use of split here strips off the level specifier from the CECs.
        reg_type = reg_acc.get_title(i).split(".")[0]
        
        if reg_type=="BOX":
            x1, x2, y1, y2, nx, ny = (child.children[0].value for child in region.children)
            #print(x1, x2, y1, y2, nx, ny)
            
            boxes = box_list(x1, x2, y1, y2, nx, ny)

            # Add the boxes to the list of regions.
            for box in boxes:
                region_output.append((reg_type, box))
                
        else:
            for entry in region.children:
                if entry.children[0].value:
                    children_value = entry.children[1].value
                    if children_value[-1]=='0':
                        children_value = children_value[0:-2] 
                    region_output.append((reg_type, children_value))

    if len(region_output):
        with open(out_file, 'w') as file:    
            file.write(str(region_output))
    else:
        raise ValueError("Error! You must select a region in the Data Processing Decisions widget.")
            
###############################################################################################################
## Widgets and update scripts for data processing and mdoeling.

# Takes an Arg_Handler object.
# Returns an accordion of all members in the proc (data processing) category.
def init_proc_widgets(arg_set):
    proc_set = {}
    #Each argument is set up with its description and appropriate widget for its data type.
    for j in arg_set.cat_vars["proc"]:
        arg_type = arg_set.desc_vars[j]["type"]
        arg_description = arg_set.desc_vars[j]["description"]
        if arg_type == "bool":
            proc_set[j] = widgets.VBox((widgets.Label(arg_description), widgets.Checkbox(arg_set.args[j])))
        elif arg_type == "int":
            proc_set[j] = widgets.VBox((widgets.Label(arg_description), widgets.IntText(arg_set.args[j])))
        elif arg_type == "float":
            proc_set[j] = widgets.VBox((widgets.Label(arg_description), widgets.FloatText(arg_set.args[j])))
        elif arg_type == "text":
            proc_set[j] = widgets.VBox((widgets.Label(arg_description), widgets.Text(arg_set.args[j])))
                                       
    proc_acc = init_accordion(proc_set)
    display(proc_acc)
    return proc_acc

# Takes a string and an Arg_Handler object.
# Returns a tuple of widgets for each ML method.
def boxpop(label, arg_set):
    #If the method already has information, that is automatically filled in.
    if label in arg_set.args["modict"]:
        return (widgets.Checkbox(True), widgets.Label(label), widgets.Text(str(arg_set.args["modict"][label])))
    #Otherwise, the widgets are returned, but with no default values other than title.
    else:
        return (widgets.Checkbox(), widgets.Label(label), widgets.Text("{}"))

# Takes an Arg_Handler object.
# Returns an Accordion with one entry, containing an HBox for each ML method used in SOMOSPIE.
def init_modict_widgets(arg_set):
    #Uses boxpop to make an HBox per method.
    items = [widgets.HBox(boxpop(method, arg_set)) for method in arg_set.methods]
    #Makes a VBox out of the HBoxes, so the alignment in the accordion is guaranteed to be correct.
    modict = widgets.VBox(items)
    acc = widgets.Accordion((modict,))
    acc.set_title(0,"MODICT")
    return acc

###############################################################################################################
## Wrangle the output.

class outVis:
    
    def __init__(self, out_path):
        self.out_path = out_path
        
        # By default, select the most recent job.
        jobs = sorted([folder for folder in os.listdir(out_path) if folder[0]=="j"])
        if jobs:
            self.display_output(f"{out_path}/{jobs[-1]}")
        else:
            print(f"No job folders found in {out_path}.")
    
    def select_Vis_Out(self, OUT):
        out_selector = FileSelectorPanel("Select vis target", \
                                            stay_alive=True, \
                                            newdir_toolbar_button=True, \
                                            next=self.display_output, \
                                            start_dir=OUT, \
                                            type="directory")
        return #widgets.VBox([out_selector.panel])
    
    def display_output(self, vis_target):
        from IPython.display import clear_output
        clear_output()
        
        display(self.select_Vis_Out(self.out_path))
        self.vis_target = vis_target
        
        path_stem = f"{self.vis_target}/job"
        if os.path.exists(path_stem + ".params"):
            self.plot_all_predictions(path_stem)
        else:
            print(f"The file {path_stem}.params does not exist. Did you select a valid job_... folder in the widget?")
    
    def plot_all_predictions(self, path_stem):
        a_dict = {}
        params_path = path_stem + ".params"
        with open(params_path,'r') as f:
            for step, line in enumerate(f.readlines()):
                a_dict[step] = literal_eval(line)
        #print(a_dict)

        # For the moment, if a list of years is given, we are only looking at the first year.
        year_path = f"{self.vis_target}/{a_dict[0]['YEAR'][0]}"

        def make_month_path(base_path, month, dict0, seed):
            suffix = ""
            if dict0["SUPER"]:
                suffix += "-LvlUp"
            if dict0["BUFFER"]:
                suffix += f"-{dict0['BUFFER']}meter"
            if dict0["USE_PCA"]:
                suffix += "-PCA"
            if dict0["VALIDATE"]:
                suffix += f"-{dict0['VALIDATE'] - 1:.2f}_{seed}"
            return f"{base_path}/month{month}{suffix}"

        month_paths = {}
        for month in a_dict[1]:
            month_paths[month] = make_month_path(year_path, month, a_dict[0], a_dict[1][month]["seed"])
        #print(month_paths)

        region_paths = {}
        for month in month_paths:
            region_paths[month] = {}
            for region in a_dict[0]["REG_LIST"]:
                reg_string = "_".join(region)
                region_paths[month][reg_string] = f"{month_paths[month]}/{reg_string}"
        #print(region_paths)

        method_paths = {}
        for month in a_dict[1]:
            print(f"month: {month}")
            method_paths[month] = {}
            reg_list = f"{path_stem}.{month}reg"
            with open(reg_list, 'r') as regions:
                for line in regions.readlines():#region in a_dict[0]["REG_LIST"]:
                    region = "_".join(line.strip().split(","))
                    #print(f"region: {region}")
                    method_paths[month][region] = {}
                    image_origen = f"{region_paths[month][region]}/{SUB_FIGS}/{SUB_PRED}/origen.png"
                    display(Image(filename=image_origen))
                    for method in a_dict[0]["MODICT"]:
                        #print(f"method: {method}")
                        paramdict = a_dict[0]["MODICT"][method]
                        params = paramdict.keys()
                        argums = paramdict.values()
                        arg_combos = iterprod(*argums)
                        # Don't print the following! It exhausts the generator.
                        ##print(f"The possible combinations of arguments are: {list(arg_combos)}")
                        bash_suffixes = [zip(params, ac) for ac in arg_combos]
                        file_suffixes = ["".join([f"{par}{arg}" for par, arg in bashix]) for bashix in bash_suffixes]
                        for suffix in file_suffixes:
                            image_path = f"{region_paths[month][region]}/{SUB_FIGS}/{SUB_PRED}/{method}{suffix}-plot.png"
                            if os.path.exists(image_path):
                                #print(image_path)
                                display(Image(filename=image_path))
                                with open(f"{region_paths[month][region]}/{SUB_PRED}/{method}{suffix}.log", 'r') as f:
                                    print("Method completion time:", f.readlines()[-1])

# Merge accuracy dataframes for multiple metrics.
def gather_analysis(folder, metrics=["rmse", "r2"]):
    combined = ""
    for met in metrics:
        file = f"{folder}/job.{met}"
        results = parse_analysis(file)
        if len(combined):
            indices = list(results.columns)[:-1]
            old = combined.set_index(indices)
            new = results.set_index(indices)
            combined = old.join(new).reset_index()
        else:
            combined = results
        #print(combined)
    return combined

# Create a dataframe from an accuracy file (e.g. job.r2, job.rmse).
def parse_analysis(file):
    import re
    
    path_chunks = file.split("/")
    job = path_chunks[-2]
    metric = path_chunks[-1].split(".")[-1]
    
    with open(file, "r") as results_file:
        results = []
        for line in results_file:
            #print(line)
            # Example line:
            # "0.236839839926393,/home/dror/Src_SOMOSPIE/out/job_2020_02_04_15_17_58/2017/month1-0.30_16496/Alabama/predictions/RF.csv"
            
            line2 = line.strip().split(",")
            if len(line2)>1:
                accuracy = float(line2[0])
                parts = line2[1].split("/")[-5:]
                #print(parts)
                # Example parts:
                # ["2017","month1-0.30_16496","Alabama","predictions","RF.csv"]
                
                year = int(parts[0])
                
                month_string = parts[1].split("-")
                month = int(re.sub(r'[a-zA-Z]', '', month_string.pop(0)))
                modifier = "-".join(month_string)
                
                region = parts[2].split("_")
                reg_type = region.pop(0)
                #if len(region)==4:
                #    box = [float(coord) for coord in region]
                reg = "_".join(region)
                
                method = parts[4].split(".")[0]
                
                results.append([year, month, reg_type, reg, method, accuracy]) # Modified by Leo 03-17-2020
                
    results = pd.DataFrame(results, columns=["Year", "Month", "RegType", "Region", "Method", metric]) # Modified by Leo 03-17-2020
    #print(results.head())
    
    return results

#########################
