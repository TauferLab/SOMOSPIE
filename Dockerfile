FROM jupyter/pyspark-notebook:7a0c7325e470

USER root

RUN apt update -qqy && \
    apt-get install -y software-properties-common vim && \
    apt-key adv --keyserver keyserver.ubuntu.com --recv-keys E298A3A825C0D65DFD57CBB651716619E084DAB9 && \
    add-apt-repository 'deb https://cloud.r-project.org/bin/linux/ubuntu bionic-cran35/' && \
    apt-get install -y libcurl4 r-base-core r-base-dev libgdal-dev libudunits2-dev libssl-dev

USER $NB_USER
COPY . /home/jovyan/work

USER root
RUN chown -R jovyan:users /home/jovyan/work 
RUN Rscript /home/jovyan/work/install.R
RUN conda env update --name base -f /home/jovyan/work/environment.yml 

USER $NB_USER
RUN cd /home/jovyan/work && \ 
    git submodule update --init --recursive && \ 
    touch code/ipywe/__init__.py
