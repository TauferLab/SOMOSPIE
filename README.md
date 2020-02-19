# SOMOSPIE (SOil MOisture SPatial Inference Engine)
[![DOI](https://zenodo.org/badge/228438205.svg)](https://zenodo.org/badge/latestdoi/228438205)

The code is still under development. If you find any problems, please contact us at taufer@utk.edu.

# Publication 
D. Rorabaugh, M. Guevara, R. Llamas, J. Kitson, R. Vargas, and M. Taufer. SOMOSPIE: A Modular SOil MOisture SPatial Inference Engine based on Data Driven Decisions. In Proceedings of the IEEE eScience Conference, pp. 1-10. San Diego, CA, USA. September 24-27, 2019.

# Requirement
* Software: Ananconda-py3, gis, Java 8, Jupyter Notebook, Python, R, Raster, Spark.
* Platform: NSF XSEDE Jetstream, local machine.

# Overview
Soil moisture is a critical variable that links climate dynamics with water and food security. It regulates land-atmosphere interactions (e.g., via evapotranspiration--the loss of water from evaporation and plant transpiration to the atmosphere), and it is directly linked with plant productivity and survival. Information on soil moisture is important to design appropriate irrigation strategies to increase crop yield, and long-term soil moisture coupled with climate information provides insights into trends and potential agricultural thresholds and risks. Thus, information on soil moisture is a key factor to inform and enable precision agriculture.

The current availability of soil moisture data over large areas comes from satellite remote sensing technologies (i.e., radar-based systems), but these data have coarse resolution and often exhibit large spatial information gaps. Where data are too coarse or sparse for a given need (e.g., precision farming and controlled burn), one can leverage machine-learning techniques coupled with other sources of environmental information (e.g., topography) to generate gap-free information at a finer spatial resolution (i.e., increased granularity). 

SOMOSPIE is a spatial inference engine consisting of modular stages for processing spatial environmental data,
generating fine-grained soil moisture predictions with machine-learning techniques, and analyzing these predictions. The Jupyter Notebook in this repositroy allows users to demonstrate the functionality of our prediction approach and the effects of data processing choices via multiple prediction maps over United States ecological regions with diverse soil moisture profiles. 

The relevance of this work derives from a pressing need to improve the spatial representation of soil moisture for applications in environmental sciences (e.g., ecological niche modeling, carbon monitoring systems, and other Earth system models) and precision farming (e.g., optimizing irrigation practices and other land management decisions).

This Jupyter Notebook is a result of a collaboration between computer scientists of the Global Computing Laboratory at the Universtiy of Tennessee, Knoxville and soil scientists at the University of Delware (funded by NSF awards #1724843 and #1854312).

# Setup instruction for the Jupyter Notebook file that runs 

Setup instruction for the Jupyter Notebook file that runs SOMOSPIE: SOil MOisture SPatial Inference Engine

Any command you are to run from the command-line are indicated in this document by $. Open your terminal or other CLI, and clone this repository:

$ git clone --recursive https://github.com/TauferLab/SOMOSPIE 

Move into your new repository:

$ cd Src_SOMOSPIE

The `--recursive` tag above also downloaded any required submodules. If you left off that tag, you can use our makefile to do that now:

$ make submodules

To continue setup, we need to activate the anaconda evironment that will be used for SOMOSPIE.ipynb. On Jetstream, use the built-in "ez" method:

$ ezj

Once you see URL for accessing Jupyter Notebook, return to the command-line: force exit by pressing Ctrl+C twice. 

YOU SHOULD BE RUNNING THIS ON THE FOLLOWING JETSTREAM VM IMAGE: Ubuntu 18.04 for SOMOSPIE
If you are, the final setup step is simple:

$ make bash

If you are not, you can install everything yourself, but this takes over an hour:

$ make jetstream

You are now ready to start using SOMOSPIE! Launch Jupyter Notebooks with `ezj -q`, click the link provided, and open `SOMOSPIE.ipynb`.

# Use SOMOSPIE with NSF XSEDE Jetstream

If you have an account on the NSF XSEDE Jetstream cloud, you can use our public VM available [here](https://use.jetstream-cloud.org/application/images/946).
