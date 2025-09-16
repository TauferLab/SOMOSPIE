SOMOSPIE is a scalable model used for predicting soil moisture. 
This guide explains how to install and run SOMOSPIE using one of the three supported methods:

1. Using your local machine
2. Using a virtual machine on Jetstream
3. Using a Docker container

## Using Your Local Machine
The installation is only supported on Debian and Debian-based Linux distributions with [Anaconda installed](https://www.anaconda.com/docs/getting-started/anaconda/install).  The script below installs all the necessary packages (R>4, R libraries, Java 11, Spark, pip, Python Libraries)

```
git clone --recursive https://github.com/TauferLab/SOMOSPIE.git
cd SOMOSPIE/install
./install.sh
source ~/.bashrc
```
To open the repository, enter the project root and run:
```
jupyter lab
```
## Using a Virtual Machine (VM) on Jetstream
To create a VM with the SOMOSPIE image, which includes all the necessary software stack:

- Go to [https://js2.jetstream-cloud.org](https://js2.jetstream-cloud.org/) and login using "XSEDE Globus Auth" option.
- On any allocation go to Compute > Instance and click on "Launch Instance".
- Follow this guide from [Jetstream2 Documentation](https://docs.jetstream-cloud.org/ui/horizon/launch/) to adjust the configuration options on the instance, but on the "Source" tab under "Select Boot Source," make sure you choose "Instance Snapshot" and then pick "SOMOSPIE on Ubuntu 22.04" from the list.
- When the instance is launched and the status is Active, you can access the VM via SSH.
- Once you are inside the shell of your VM, you are ready to start using SOMOSPIE!

To launch the SOMOSPIE Jupyter Notebook on your browser, you can ssh using Local Forwarding (-L) :

```
ssh -L 8000:localhost:8000 <username>@<your_instance_ip>
cd SOMOSPIE
jupyter lab --ip 0.0.0.0 --port 8000 --allow-root
```

You can use [Jetstream cloud computer](https://jetstream-cloud.org/) image for SOMOSPIE titled ["SOMOSPIE on Ubuntu 22.04"](https://js2.jetstream-cloud.org/ngdetails/OS::Glance::Image/68fddeae-2e3e-41a6-ad33-b747df48e186).

## Using a Docker Container

To pull the image from DockerHub
```
docker pull globalcomputinglab/somospie
```
To create a container of the image and run the container, run:
```
docker run -it -P --name=somospie globalcomputinglab/somospie:<optional-tag>
```
To have the container removed at the end of runtime, add the --rm flag to the command. 

If any R packages are not installed in the container, you can install the missing packages by executing the container as
the root user and running the `install.R` script:
```
docker start <container_id>
docker exec -u root -t -i <container_id> bash
Rscript work/install/install.R
```
### Required dependencies
Downloading with any of the above methods will include the required dependencies. 

Dependencies:

- Anaconda-py3
- Java 11
- Jupyter Notebook
- R
- Spark
- Python
	- numpy
	- pandas
	- sklearn
	- argparse
	- pickle
	- random
	- itertools
	- scipy
	- matplotlib
	- pyspark
	- GRASS
	- GDAL=3.8.4