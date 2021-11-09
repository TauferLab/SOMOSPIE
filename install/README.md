# SOMOSPIE (SOil MOisture SPatial Inference Engine). Installation programs

#### install.sh

- Install script for repository: https://github.com/TauferLab/Src_SOMOSPIE
- For installation on an Ubuntu 18.04 VM on Jetstream
- This installs R, R libraries, Java 8, Spark, pip, Python libraries

#####  INSTRUCTIONS:

- Before executing this script, execute: ezj
- Execute this script with: . install.sh
- If you run with ./install.sh, then after you will have to: source ~/.bashrc

*** 

#### bash_setup.sh

- Define SPARK_HOME and add to PATH.
- Define JAVA_HOME and add to PATH.
- Add conda for user environment - even when ezj hasn't been run that session.
- It makes conda activate available.

***

#### install.R

- Install all the necessary R packages to used by SOMOSPIE.

***

#### install_docker.R

- Install all the necessary R packages to used by SOMOSPIE on a Docker container.
