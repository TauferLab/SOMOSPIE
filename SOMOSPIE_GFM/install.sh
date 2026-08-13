#!/usr/bin/env bash

# Create a local SOMOSPIE-GFM Python environment on Ubuntu/Debian.
#
# Native GDAL and its Python bindings must have the same version. Following the
# pattern used by GEOtiled, this script installs libgdal-dev first, then builds
# gdal[numpy] at exactly the version reported by gdal-config.

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"
ACCELERATOR="auto"
INSTALL_SYSTEM=true
PYTHON_COMMAND="${PYTHON_COMMAND:-python3}"

usage() {
    cat <<'EOF'
Usage: ./install.sh [options]

Create a virtual environment and install SOMOSPIE-GFM in editable mode.

Options:
  --venv PATH             Environment directory (default: ./.venv)
  --cpu                   Install CPU-only PyTorch wheels
  --cuda                  Install CUDA 12.8 PyTorch wheels
  --skip-system-packages  Do not install apt packages; require GDAL beforehand
  -h, --help              Show this help

Environment:
  PYTHON_COMMAND          Python executable used to create the environment
EOF
}

while (($#)); do
    case "$1" in
        --venv)
            if (($# < 2)); then
                echo "--venv requires a path" >&2
                exit 2
            fi
            VENV_DIR="$2"
            shift 2
            ;;
        --cpu)
            ACCELERATOR="cpu"
            shift
            ;;
        --cuda)
            ACCELERATOR="cuda"
            shift
            ;;
        --skip-system-packages)
            INSTALL_SYSTEM=false
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

run_apt() {
    local -a command=(apt-get "$@")
    if ((EUID == 0)); then
        "${command[@]}"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "${command[@]}"
    else
        echo "Installing system packages requires root or sudo." >&2
        exit 1
    fi
}

if [[ "${INSTALL_SYSTEM}" == true ]]; then
    if ! command -v apt-get >/dev/null 2>&1; then
        echo "Automatic system setup supports Ubuntu/Debian only." >&2
        echo "Install Python venv support, libgdal-dev, GDAL tools, curl, wget, and unzip," >&2
        echo "then rerun with --skip-system-packages." >&2
        exit 1
    fi
    run_apt update
    run_apt install -y --no-install-recommends \
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
        wget
fi

for command_name in "${PYTHON_COMMAND}" gdal-config; do
    if ! command -v "${command_name}" >/dev/null 2>&1; then
        echo "Required command not found: ${command_name}" >&2
        exit 1
    fi
done

"${PYTHON_COMMAND}" - <<'PY'
import sys

if not (3, 10) <= sys.version_info < (3, 13):
    raise SystemExit(
        f"SOMOSPIE-GFM requires Python >=3.10,<3.13; found {sys.version.split()[0]}"
    )
PY

"${PYTHON_COMMAND}" -m venv "${VENV_DIR}"
VENV_PYTHON="${VENV_DIR}/bin/python"
"${VENV_PYTHON}" -m pip install --upgrade pip setuptools wheel

# NumPy must be present before GDAL is built so the gdal_array extension is
# included. --no-cache avoids reusing bindings built against another GDAL.
"${VENV_PYTHON}" -m pip install --no-cache-dir "numpy>=2.2,<3"
GDAL_VERSION="$(gdal-config --version)"
"${VENV_PYTHON}" -m pip install \
    --no-cache-dir \
    --force-reinstall \
    "gdal[numpy]==${GDAL_VERSION}"

if [[ "${ACCELERATOR}" == "auto" ]]; then
    if command -v nvidia-smi >/dev/null 2>&1; then
        ACCELERATOR="cuda"
    else
        ACCELERATOR="cpu"
    fi
fi

if [[ "${ACCELERATOR}" == "cuda" ]]; then
    TORCH_INDEX_URL="https://download.pytorch.org/whl/cu128"
else
    TORCH_INDEX_URL="https://download.pytorch.org/whl/cpu"
fi

"${VENV_PYTHON}" -m pip install \
    --index-url "${TORCH_INDEX_URL}" \
    "torch==2.9.1" \
    "torchvision==0.24.1"
"${VENV_PYTHON}" -m pip install --editable "${SCRIPT_DIR}"

"${VENV_PYTHON}" - <<'PY'
from osgeo import gdal, gdal_array
from importlib.metadata import version
import geopandas
import numpy
import pandas
import terratorch
import torch
import yaml

print(f"Python      : {__import__('sys').version.split()[0]}")
print(f"GDAL        : {gdal.VersionInfo('--version')}")
print(f"NumPy       : {numpy.__version__}")
print(f"Pandas      : {pandas.__version__}")
print(f"GeoPandas   : {geopandas.__version__}")
print(f"PyTorch     : {torch.__version__}")
print(f"TerraTorch  : {version('terratorch')}")
print(f"CUDA usable : {torch.cuda.is_available()}")
PY

printf '\nEnvironment ready. Activate it with:\n  source %q/bin/activate\n' "${VENV_DIR}"
