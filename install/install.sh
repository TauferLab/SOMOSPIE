#!/bin/bash

# Install script for repository: https://github.com/TauferLab/Src_SOMOSPIE
# For installation on an Ubuntu 20.04 VM on Jetstream
# This installs R, R libraries, Java 11, Spark, pip, Python libraries
# INSTRUCTIONS:
# Execute this script with: . install.sh
# If you run with ./install.sh, then after you will have to: source ~/.bashrc

# Add CRAN repository for more up-to-date r and r packages
# https://vitux.com/how-to-install-and-use-the-r-programming-language-in-ubuntu-18-04-lts/
sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys E298A3A825C0D65DFD57CBB651716619E084DAB9
sudo add-apt-repository 'deb https://cloud.r-project.org/bin/linux/ubuntu focal-cran40/'
sudo apt update
sudo apt upgrade

# Get libraries for R usage
sudo apt -y install r-base-core
sudo apt -y install libgdal-dev
sudo apt -y install libudunits2-dev
sudo apt -y install libssl-dev

# Install latest Java (2022 -> Java11)
sudo apt install curl mlocate default-jdk -y

# Define JAVA_HOME and add to PATH
echo 'export JAVA_HOME=/usr/local/java' >> ~/.bashrc
echo 'export PATH=$JAVA_HOME/bin:$PATH' >> ~/.bashrc

# Install Spark
curl -o ~/spark.tgz -L https://dlcdn.apache.org/spark/spark-3.2.1/spark-3.2.1-bin-hadoop3.2.tgz
sudo rm -rf /usr/local/spark
sudo mkdir /usr/local/spark
sudo tar -xzf ~/spark.tgz -C /usr/local/spark --strip-components=1
rm ~/spark.tgz

# Define SPARK_HOME and add to PATH
echo 'export SPARK_HOME=/usr/local/spark' >> ~/.bashrc
echo 'export PATH=$SPARK_HOME/bin:$PATH' >> ~/.bashrc
echo 'export SPARK_LOCAL_IP="127.0.0.1"' >> ~/.bashrc


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
