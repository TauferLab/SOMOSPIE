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
There are three ways to install and run SOMOSPIE: i) [Using your local machine](#using-your-local-machine), ii) [Using a virtual machine (VM) on Jetstream](#using-a-vm-on-jetstream), and iii) [Using a Docker container](#using-a-docker-container). The installation process for each od these options will be presented next.

### Using your local machine
Currently, the installation is supported on Debian, and Debian-based Linux distributions. This script installs all the necessary packages (R>4, R libraries, Java 11, Spark, pip, Python libraries) for your local computer.
**Requirement: Debian-based Linux distributions with Anaconda installed.** To install Anaconda, you can follow the instructions [here.](https://docs.anaconda.com/anaconda/install/linux/)
```
./install.sh
source ~/.bashrc
```

### Using a VM on Jetstream
Instructions to create a VM with the SOMOSPIE image which includes all the necessary software stack. As well as instructions to activate the environment.
* Go to https://use.jetstream-cloud.org. Login with the XSEDE credentials.
* Create a project and within this project create the SOMOSPIE virtual machine.
* When creating the VM, Under "First choose an image for your instance", select "Show All" and search for "Spark". Then select "SOMOSPIE on Ubuntu 20.04".
* Specify launching options such as instance name, allocation source, provider, and instance size and click on `LAUNCH INSTANCE`.
* When instance is launched and the status is Active (green circle), you can access the VM [via SSH](https://iujetstream.atlassian.net/wiki/spaces/JWT/pages/17465502/Logging+in+with+SSH) or [through the Web shell](https://iujetstream.atlassian.net/wiki/spaces/JWT/pages/778698753/Logging+in+with+Web+Shell+-+also+copying+and+pasting).
* Once you are inside the shell of your VM, you need clone the repository and activate the software environment.
```
git clone --recursive https://github.com/TauferLab/Src_SOMOSPIE.git
cd Src_SOMOSPIE
./install/bash_setup.sh
source ~/.bashrc
```

To continue setup, we need to activate the anaconda evironment that will be used for SOMOSPIE.ipynb. On Jetstream, use the built-in "ez" method:

```
$ ezj
```

Once you see URL for accessing Jupyter Notebook, return to the command-line: force exit by pressing Ctrl+C twice. 

YOU SHOULD BE RUNNING THIS ON THE FOLLOWING JETSTREAM VM IMAGE: Ubuntu 18.04 for SOMOSPIE
If you are, the final setup step is simple:

```
$ make bash
```

If you are not, you can install everything yourself, but this takes over an hour:

```
$ make jetstream
```

You are now ready to start using SOMOSPIE! Launch Jupyter Notebooks with `ezj -q`, click the link provided, and open `SOMOSPIE.ipynb`.

You can use [Jetstream cloud computer](https://jetstream-cloud.org) image for SOMOSPIE titled ["Ubuntu 18_04 for SOMOSPIE V1_2"](https://use.jetstream-cloud.org/application/images/946).


### Using a Docker container
To pull the image from Dockerhub: 
```
docker pull globalcomputinglab/somospie
```

To build the image:
```
docker build -t <your-docker-user>/somospie:<optional-tag> .
docker push <your-docker-user>/somospie:<optional-tag>
```

To run:
```
docker run --rm -it -P -name somospie  <your-docker-user>/somospie:<optional-tag>
```

### Dependencies

Once you have cloned the SOMOSPIE repository to your local machine, be sure to enter the project root for setup.

If you will install the dependencies of SOMOSPIE manually, see the following list of them here.
* Ananconda-py3
* gis
* Java 8
* Jupyter Notebook
* R
* Raster
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
  * time

## Acknowledgments

This work partially developed and tested using the following [XSEDE computing resources](https://portal.xsede.org/group/xup/resource-monitor):
* Stampede2
* Jetstream

### Project Team

Developers:
* Paula Olaya
* Ricardo Llamas
* Dr. Naweiluo Zhou
* Dr. Danny Rorabaugh
* Dr. Leobardo Valera

Project Advisors:
* Dr. Rodrigo Vargas
* Dr. Michela Taufer (Project Lead)

## Publications

*This paper presents theory, artifacts, and results on which SOMOSPIE is built:*

D. Rorabaugh, M. Guevara, R. Llamas, J. Kitson, R. Vargas, and M. Taufer. **SOMOSPIE: A Modular SOil MOisture SPatial Inference Engine based on Data Driven Decisions.** *In Proceedings of the IEEE eScience Conference*, pp. 1-10. San Diego, CA, USA. September 24-27, (2019).
[Link to Publication](https://ieeexplore.ieee.org/document/9041768)


## Copyright and License

Copyright (c) 2021, Global Computing Lab



