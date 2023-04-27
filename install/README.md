# Installing SOMOSPIE

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

You can use [Jetstream cloud computer](https://jetstream-cloud.org) image for SOMOSPIE titled ["SOMOSPIE on Ubuntu 22.04"](https://js2.jetstream-cloud.org/ngdetails/OS::Glance::Image/d30ce87f-563b-4159-9433-22b61a94cbb0).

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
