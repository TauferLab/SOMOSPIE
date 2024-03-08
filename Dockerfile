FROM jupyter/pyspark-notebook

USER root

RUN apt update -qqy && \
    apt-get install -y software-properties-common vim && \
    apt-get install -y curl

RUN apt install -y --no-install-recommends software-properties-common dirmngr && \
    wget -qO- https://cloud.r-project.org/bin/linux/ubuntu/marutter_pubkey.asc | sudo tee -a /etc/apt/trusted.gpg.d/cran_ubuntu_key.asc && \
    add-apt-repository "deb https://cloud.r-project.org/bin/linux/ubuntu $(lsb_release -cs)-cran40/" && \
    apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y r-base-core libgdal-dev libudunits2-dev libssl-dev
    
RUN apt-get install -y grass grass-doc

USER $NB_USER
COPY . /home/jovyan/work

USER root
RUN chown -R jovyan:users /home/jovyan/work 
RUN Rscript /home/jovyan/work/install/install.R

RUN source /opt/conda/etc/profile.d/conda.sh && \
    conda activate && \
    conda env create -f /home/jovyan/work/install/environment.yml && \
    conda activate somospie

USER $NB_USER
RUN cd /home/jovyan/work && \ 
    git submodule update --init --recursive && \ 
    touch SOMOSPIE/modules/ipywe/ipywe/__init__.py

# To build for multiple architectures: docker buildx build --platform linux/amd64,linux/arm64 -t <docker user>/somospie:latest --push .
