# <img src="somospie_pngs/logo_white.png" width="350">   
# SOMOSPIE (SOil MOisture SPatial Inference Engine)
[![DOI](https://zenodo.org/badge/228438205.svg)](https://zenodo.org/badge/latestdoi/228438205)

## Introduction

Soil moisture is a critical variable that links climate dynamics with water and food security. It regulates land-atmosphere interactions (e.g., via evapotranspiration--the loss of water from evaporation and plant transpiration to the atmosphere), and it is directly linked with plant productivity and survival. Information on soil moisture is important to design appropriate irrigation strategies to increase crop yield, and long-term soil moisture coupled with climate information provides insights into trends and potential agricultural thresholds and risks. Thus, information on soil moisture is a key factor to inform and enable precision agriculture.

The current availability of soil moisture data over large areas comes from satellite remote sensing technologies (i.e., radar-based systems), but these data have coarse resolution and often exhibit large spatial information gaps. Where data are too coarse or sparse for a given need (e.g., precision farming and controlled burn), one can leverage machine-learning techniques coupled with other sources of environmental information (e.g., topography) to generate gap-free information at a finer spatial resolution (i.e., increased granularity). 

**SOMOSPIE is a spatial inference engine consisting of modular stages for processing spatial environmental data,
generating fine-grained soil moisture predictions with machine-learning techniques, and analyzing these predictions.** The Jupyter Notebook in this repositroy allows users to demonstrate the functionality of our prediction approach and the effects of data processing choices via multiple prediction maps over United States ecological regions with diverse soil moisture profiles. 

The relevance of this work derives from a pressing need to improve the spatial representation of soil moisture for applications in environmental sciences (e.g., ecological niche modeling, carbon monitoring systems, and other Earth system models) and precision farming (e.g., optimizing irrigation practices and other land management decisions).

This Jupyter Notebook is a result of a collaboration between computer scientists of the Global Computing Laboratory at the Universtiy of Tennessee, Knoxville and soil scientists at the University of Delware (funded by NSF awards #1724843 and #1854312).

This repository contains a suite of tools for tprocessing spatial environmental data, generating fine-grained soil moisture predictions with machine-learning techniques, and analyzing these predictions. The core components of this tool suite are as follows.  
* The SOMOSPIE framework with the next stages:
  1. Preprocessing
  2. Modeling: ML models
  3. Analysis: Visual analysis and stastistical analysis
* Test cases for three regions


Check more of this project on [SOMOSPIE's website.](https://globalcomputing.group/somospie/)

This document is organized in the following order:
* [Installation](#installation)
  * [Dependencies](#dependencies)
* Additional Project Details
  1. [The project team](#project-team)
  2. [Publications associated with the software](#publications)
  3. [Copyright and license information](#copyright-and-license)


## **Installation**
There are three ways to install and run SOMOSPIE: i) [Using your local machine](#using-your-local-machine), ii) [Using a virtual machine (VM) on Jetstream](#using-a-vm-on-jetstream), and iii) [Using a Docker container](#using-a-docker-container). The installation process for each of these options is detailed below. 

## Using your local machine
Currently, the installation is supported on Debian, and Debian-based Linux distributions. This script installs all the necessary packages (R>4, R libraries, Java 11, Spark, pip, Python libraries) for your local computer.  
**Requirement: Debian-based Linux distributions with Anaconda installed.** To install Anaconda, you can follow the instructions [here.](https://docs.anaconda.com/anaconda/install/linux/)
```
git clone --recursive https://github.com/TauferLab/SOMOSPIE.git
cd SOMOSPIE/install
./install.sh
source ~/.bashrc
``` 

## Using a VM on Jetstream
To create a VM with the SOMOSPIE image which includes all the necessary software stack:
* Go to https://js2.jetstream-cloud.org and login using  "XSEDE Globus Auth" option.
* On any allocation go to Compute > Instance and click on "Launch Instance".
* Follow this guide from [Jetstream2 Documentation](https://docs.jetstream-cloud.org/ui/horizon/launch/) to adjust the configuration options on the instance, but on the "Source" tab under "Select Boot Source" make sure you choose "Instance Snapshot" and then pick "SOMOSPIE on Ubuntu 22.04" from the list.
* When the instance is launched and the status is Active, you can access the VM via SSH. 
* Once you are inside the shell of your VM, you are ready to start using SOMOSPIE!

To launch the SOMOSPIE Jupyter Notebook on your browser you can ssh using Local Forwarding (-L) :
```
ssh -L 8000:localhost:8000 <username>@<your_instance_ip>
cd SOMOSPIE
jupyter notebook --ip 0.0.0.0 --port 8000 --allow-root
```    

You can use [Jetstream cloud computer](https://jetstream-cloud.org) image for SOMOSPIE titled ["SOMOSPIE on Ubuntu 22.04"](https://js2.jetstream-cloud.org/ngdetails/OS::Glance::Image/68fddeae-2e3e-41a6-ad33-b747df48e186).

## Using a Docker container
To pull the image from Dockerhub: 
```
docker pull globalcomputinglab/somospie
```

To run:
```
docker run --rm -it -P --name=somospie  globalcomputinglab/somospie:<optional-tag>
```

If all required R packages are not installed in the container, you can install the missing packages executing the container as the root user and running the `install.R` script:
```
docker start <container_id>
docker exec -u root -t -i <container_id> bash
Rscript work/install/install.R
```

### Dependencies

Once you have cloned the SOMOSPIE repository to your local machine, be sure to enter the project root for setup.

If you will install the dependencies of SOMOSPIE manually, see the following list of them here.
* Ananconda-py3
* Java 11
* Jupyter Notebook
* R
* Spark
* Python
  * numpy
  * pandas
  * sklearn
  * argparse
  * pickle
  * random
  * itertools
  * scipy
  * matplotlib
  * pyspark
  * GRASS
  * GDAL

## Acknowledgments

SENSORY is funded by the National Science Foundation (NSF) under grant numbers [#1724843](https://www.nsf.gov/awardsearch/showAward?AWD_ID=1724843&HistoricalAwards=false), 
[#1854312](https://www.nsf.gov/awardsearch/showAward?AWD_ID=1854312&HistoricalAwards=false), [#2103836](https://www.nsf.gov/awardsearch/showAward?AWD_ID=2103836&HistoricalAwards=false), 
[#2103845](https://www.nsf.gov/awardsearch/showAward?AWD_ID=2103845&HistoricalAwards=false), [#2138811](https://www.nsf.gov/awardsearch/showAward?AWD_ID=2138811&HistoricalAwards=false), 
and [#2334945](https://www.nsf.gov/awardsearch/showAward?AWD_ID=2334945&HistoricalAwards=false).
Any opinions, findings, and conclusions, or recommendations expressed in this material are those of the author(s) 
and do not necessarily reflect the views of the National Science Foundation. 

This work partially developed and tested using the following [XSEDE computing resources](https://portal.xsede.org/group/xup/resource-monitor):
* Stampede2
* Jetstream

### Project Team

Developers:
* Jay Ashworth
* Gabriel Laboy
* Andrew Lindstrom
* Ricardo Llamas
* Paula Olaya
* Camila Roa
* Dr. Danny Rorabaugh
* Dr. Leobardo Valera
* Dr. Naweiluo Zhou

Project Advisors:
* Dr. Rodrigo Vargas
* Dr. Michela Taufer (Project Lead)

## Publications

*This paper presents theory, artifacts, and results on which SOMOSPIE is built:*

D. Rorabaugh, M. Guevara, R. Llamas, J. Kitson, R. Vargas, and M. Taufer. **SOMOSPIE: A Modular SOil MOisture SPatial Inference Engine based on Data Driven Decisions.** *In Proceedings of the IEEE eScience Conference*, pp. 1-10. San Diego, CA, USA. September 24-27, (2019).
[Link to Publication](https://ieeexplore.ieee.org/document/9041768)

## Copyright and License

Copyright (c) 2021, Global Computing Lab
