#!/bin/bash

# Install script for repository: https://github.com/TauferLab/Src_SOMOSPIE
# For installation on an Ubuntu 18.04 VM on Jetstream
# This installs R, R libraries, Java 8, Spark, pip, Python libraries
# INSTRUCTIONS:
# Before executing this script, execute: ezj
# Execute this script with: . install.sh
# If you run with ./install.sh, then after you will have to: source ~/.bashrc

# Add CRAN repository for more up-to-date r and r packages
# https://vitux.com/how-to-install-and-use-the-r-programming-language-in-ubuntu-18-04-lts/
#sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys E298A3A825C0D65DFD57CBB651716619E084DAB9
#sudo add-apt-repository 'deb https://cloud.r-project.org/bin/linux/ubuntu bionic-cran35/'
#sudo apt update

# Get libraries for R usage
sudo apt -y install r-base-core
sudo apt -y install libgdal-dev
sudo apt -y install libudunits2-dev
sudo apt -y install libssl-dev

# Install Spark
curl -o ~/spark.tgz -L http://apache.cs.utah.edu/spark/spark-2.4.4/spark-2.4.4-bin-hadoop2.7.tgz
sudo rm -rf /usr/local/spark
sudo mkdir /usr/local/spark
sudo tar -xzf ~/spark.tgz -C /usr/local/spark --strip-components=1
rm ~/spark.tgz

# Define SPARK_HOME and add to PATH
echo 'export SPARK_HOME=/usr/local/spark' >> ~/.bashrc
echo 'export PATH=$SPARK_HOME/bin:$PATH' >> ~/.bashrc
echo 'export SPARK_LOCAL_IP="127.0.0.1"' >> ~/.bashrc

# Install Java 8
curl -o ~/java.tgz -L https://javadl.oracle.com/webapps/download/AutoDL?BundleId=236878_42970487e3af4f5aa5bca3f542482c60
sudo rm -rf /usr/local/java
sudo mkdir /usr/local/java
sudo tar -xzf ~/java.tgz -C /usr/local/java --strip-components=1
rm ~/java.tgz

# Define JAVA_HOME and add to PATH
echo 'export JAVA_HOME=/usr/local/java' >> ~/.bashrc
echo 'export PATH=$JAVA_HOME/bin:$PATH' >> ~/.bashrc

# This command ensures that the conda environment is active 
# - using pip outside of this enviornment results in
# the python in ezj not having access to the libraries being installed.
conda activate

# Ensure pip3 is available
sudo apt -y install python3-pip

# Update pip
pip install --upgrade pip

# Install pyspark, findspark, sklearn, ipywe, and matplotlib
pip install pyspark
pip install findspark
pip install sklearn
#pip install ipywe # Installs old version of ipywe; conda does newer, but not new enough; we are using git submodules instead
pip install matplotlib
python3 install.py # ToDo: Investigate when and whether this is useful

# Install R libraries
sudo Rscript install.R
# Rscript comes from r-base-core. If this doesn't run, the r-base-core install likely failed

# Submodules: ipywe (for its file_selector widget)
# In case you didn't use --recursive when cloning this repository:
git submodule update --init --recursive
touch code/ipywe/__init__.py

# The following command only works 
# if this install script is run in highest shell level, 
# i.e. `. install.sh` or `source install.sh`. 
# Otherwise, it must be executed after use of this script.
source ~/.bashrc
