ARG CUDA_IMAGE=nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04
FROM ${CUDA_IMAGE}

ARG DEBIAN_FRONTEND=noninteractive
ARG PYTORCH_VERSION=2.5.1
ARG TORCHVISION_VERSION=0.20.1

ENV VIRTUAL_ENV=/opt/somospie-gfm-venv \
    PATH=/opt/somospie-gfm-venv/bin:${PATH} \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Native GDAL comes from the selected Ubuntu base. Build tools are retained
# because the matching Python bindings and some TerraTorch dependencies do not
# publish wheels for every supported architecture.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        gdal-bin \
        libgdal-dev \
        libgl1 \
        libglib2.0-0 \
        python3 \
        python3-dev \
        python3-venv \
        unzip \
        wget \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv "${VIRTUAL_ENV}"

# Install NumPy before matching Python GDAL bindings so gdal_array is built.
# Pinning the bindings to gdal-config prevents Python/native ABI mismatches.
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install "numpy>=2.2,<3" \
    && GDAL_VERSION="$(gdal-config --version)" \
    && python -m pip install --no-build-isolation --force-reinstall "gdal[numpy]==${GDAL_VERSION}"

# The CUDA wheel index keeps the Python framework aligned with the CUDA 12.1
# runtime in the base image. Project metadata supplies the remaining packages.
RUN python -m pip install \
        --extra-index-url https://download.pytorch.org/whl/cu121 \
        "torch==${PYTORCH_VERSION}" \
        "torchvision==${TORCHVISION_VERSION}"

WORKDIR /opt/somospie-gfm
COPY . .
RUN python -m pip install . \
    && python -c "from osgeo import gdal, gdal_array; import somospie_gfm.nn, terratorch, torch"

# A stable, writable mount point mirrors the workdir layout in example.yaml.
RUN useradd --create-home --uid 1000 --shell /bin/bash somospie \
    && mkdir -p /workdir \
    && chown somospie:somospie /workdir

USER somospie
WORKDIR /workdir

CMD ["bash"]
