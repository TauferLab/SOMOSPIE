ARG CUDA_IMAGE=nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04
FROM ${CUDA_IMAGE}

ARG DEBIAN_FRONTEND=noninteractive
ARG PYTORCH_VERSION=2.9.1
ARG TORCHVISION_VERSION=0.24.1

ENV VIRTUAL_ENV=/opt/somospie-gfm-venv \
    PATH=/opt/somospie-gfm-venv/bin:${PATH} \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Ubuntu 24.04 provides GDAL 3.8.4, the same platform/version combination used
# by GEOtiled. Build tools are retained because some TerraTorch dependencies do
# not publish wheels for every supported architecture.
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
    && python -m pip install --force-reinstall "gdal[numpy]==${GDAL_VERSION}"

# The CUDA wheel index keeps the Python framework aligned with the CUDA 12.8
# runtime in the base image. Project metadata supplies the remaining packages.
RUN python -m pip install \
        --index-url https://download.pytorch.org/whl/cu128 \
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
