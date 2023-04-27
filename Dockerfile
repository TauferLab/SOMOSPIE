FROM jupyter/pyspark-notebook

USER root

RUN apt update -qqy && \
    apt-get install -y software-properties-common vim && \
    wget -qO- https://cloud.r-project.org/bin/linux/ubuntu/marutter_pubkey.asc | sudo tee -a /etc/apt/trusted.gpg.d/cran_ubuntu_key.asc && \
    add-apt-repository 'deb https://cloud.r-project.org/bin/linux/ubuntu bionic-cran40/' && \
    apt-get update && \
    apt-get upgrade && \
    apt-get install -y r-base-core libgdal-dev libudunits2-dev libssl-dev && \
    apt-get install -y grass grass-doc

USER $NB_USER
COPY . /home/jovyan/work

USER root
RUN chown -R jovyan:users /home/jovyan/work 
RUN Rscript /home/jovyan/work/install/install.R && \
    source /opt/conda/etc/profile.d/conda.sh && \
    conda activate && \
    conda env create -f /home/jovyan/work/install/environment.yml && \
    conda activate somospie

USER $NB_USER
RUN cd /home/jovyan/work && \ 
    git submodule update --init --recursive && \ 
    touch SOMOSPIE/modules/ipywe/ipywe/__init__.py
