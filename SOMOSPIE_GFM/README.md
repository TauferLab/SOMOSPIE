# SOMOSPIE-GFM

SOMOSPIE-GFM prepares HLS, terrain, and ESA-CCI inputs and fine-tunes Prithvi
for dense soil-moisture downscaling. Python 3.10 through 3.12 is supported.

## Local Python environment

The installer follows GEOtiled's proven GDAL setup: it installs native GDAL,
creates an isolated virtual environment, and builds matching Python bindings
with NumPy support. On Ubuntu or Debian, run:

```bash
cd SOMOSPIE_GFM
./install.sh
source .venv/bin/activate
```

The installer selects CUDA 12.8 wheels when `nvidia-smi` is available and CPU
wheels otherwise. Selection and environment location can be explicit:

```bash
./install.sh --cuda --venv /path/to/somospie-gfm-env
./install.sh --cpu
```

On a non-Debian system, install Python venv support, GDAL development headers,
GDAL command-line tools, `curl` or `wget`, and `unzip` with the system package
manager. Then run:

```bash
./install.sh --skip-system-packages
```

The project is installed in editable mode. The training and inference entry
points are therefore available after activation:

```bash
somospie-gfm-train --help
somospie-gfm-infer --help
```

## Docker

Build the CUDA 12.8 image from this directory:

```bash
docker build -t somospie-gfm .
```

Run it with GPU access and mount the workflow storage at `/workdir`:

```bash
mkdir -p workdir
docker run --rm -it \
  --gpus all \
  --volume "$(pwd)/workdir:/workdir" \
  somospie-gfm
```

The image can run preprocessing or CPU inference without `--gpus all`; its
PyTorch installation still includes CUDA support. Inside the container, use
the same console commands or module entry points as the local environment.

The mounted directory should use the structure documented in
`workflows/local/test.sh`: `raw`, `intermediate`, `prepared`, `models`,
`predictions`, `evaluation`, `logs`, and `run-metadata`.
