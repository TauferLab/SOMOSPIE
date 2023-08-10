FROM continuumio/miniconda3
COPY ./environment.yml .
SHELL ["/bin/bash", "--login", "-c"]

RUN conda env create -f environment.yml 
RUN conda init bash
RUN conda activate somospie 
# ENTRYPOINT ["conda", "activate", "somospie"]
    
# To build for multiple architectures: docker buildx build --platform linux/amd64,linux/arm64 -t <docker user>/somospie:latest --push .