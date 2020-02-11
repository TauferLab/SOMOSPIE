# Overview

## SOMOSPIE (SOil MOisture SPatial Inference Engine)

### Publication 
D. Rorabaugh, M. Guevara, R. Llamas, J. Kitson, R. Vargas, and M. Taufer. SOMOSPIE: A Modular SOil MOisture SPatial Inference Engine based on Data Driven Decisions. . In Proceedings of the IEEE eScience Conference, pp. 1-10. San Diego, CA, USA. September 24-27, 2019.

### Introduction
Soil moisture is a critical variable that links climate dynamics with water and food security. It regulates land-atmosphere interactions (e.g., via evapotranspiration--the loss of water from evaporation and plant transpiration to the atmosphere), and it is directly linked with plant productivity and survival. Information on soil moisture is important to design appropriate irrigation strategies to increase crop yield, and long-term soil moisture coupled with climate information provides insights into trends and potential agricultural thresholds and risks. Thus, information on soil moisture is a key factor to inform and enable precision agriculture.

The current availability in soil moisture data over large areas comes from remote sensing (i.e., satellites with radar sensors) which provide daily, nearly global coverage of soil moisture. However, satellite soil moisture datasets have a major shortcoming in that they are limited to coarse spatial resolution (generally no finer than tens of kilometers).

There do exist at higher resolution other geographic datasets (e.g., climatic, geological, and topographic) that are intimately related to soil moisture values. SOMOSPIE is meant to be a general-purpose tool for using such datasets to downscale (i.e., increase resolution) satelite-based soil moisture products. This Jupyter Notebook is a result of a collaboration between computer scientists of the Global Computing Laboratory at the Universtiy of Tennessee, Knoxville and soil scientists at the University of Delware (funded by NSF awards #1724843 and #1854312).

# Requirement
Ananconda-py3, gis, Java 8, Jupyter, Python, R, Raster, Spark.

# Setup instruction for the Jupyter Notebook file that runs 

Setup instruction for the Jupyter Notebook file that runs 
 SOMOSPIE: SOil MOisture SPatial Inference Engine

Any command you are to run from the command-line are indicated in this document by $.
Open your terminal or other CLI, and clone this repository:
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

