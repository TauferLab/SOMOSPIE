#!/usr/bin/env bash

# Submit the complete SOMOSPIE-GFM workflow to one GPU node.
#
# Run from the SOMOSPIE_GFM checkout:
#   sbatch workflows/slurm/sm_workflow.sbatch [config.yaml] \
#     [all|prepare|train|infer|postprocess|visualize] [--force]
#
# A mode may be supplied without a config path; configs/config.yaml is then
# used. The canonical workflows/local/run_workflow.sh remains responsible for
# configuration validation, stage markers, persistent workflow logs, and the
# actual preprocessing/training/inference commands.

#SBATCH --account=bebq-delta-gpu
#SBATCH --partition=gpuA100x4
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus-per-task=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=192G
#SBATCH --time=04:00:00
#SBATCH --job-name=sm_workflow
#SBATCH --output=slurm-%x-%j.out
#SBATCH --error=slurm-%x-%j.err

set -Eeuo pipefail

usage() {
    cat <<'EOF'
Usage:
  sbatch workflows/slurm/sm_workflow.sbatch [CONFIG] [MODE] [--force]

Arguments:
  CONFIG   YAML configuration (default: configs/config.yaml)
  MODE     all, prepare, train, infer, postprocess, or visualize
           (default: all)
  --force  Rerun stages even when completion markers exist

Environment overrides:
  SOMOSPIE_GFM_ROOT       Absolute path to the SOMOSPIE_GFM checkout
  SOMOSPIE_PYTHON         Python executable for the installed environment
  SOMOSPIE_MODULES        Space-separated modules to load (default: python)
  SOMOSPIE_SKIP_MODULES   Set to 1 to retain the submitted module environment
  SOMOSPIE_SKIP_ACQUISITION
                          Set to 1 to use inputs already under workdir/raw

Examples:
  sbatch workflows/slurm/sm_workflow.sbatch configs/config.yaml all
  sbatch workflows/slurm/sm_workflow.sbatch train
  sbatch workflows/slurm/sm_workflow.sbatch configs/config.yaml infer --force
EOF
}

is_mode() {
    case "$1" in
        all|prepare|train|infer|postprocess|visualize) return 0 ;;
        *) return 1 ;;
    esac
}

SUBMIT_DIR="${SLURM_SUBMIT_DIR:-${PWD}}"
CONFIG_ARGUMENT="configs/config.yaml"
MODE="all"
FORCE_ARGUMENT=()

if (($#)) && [[ "$1" != "--force" ]] && ! is_mode "$1"; then
    CONFIG_ARGUMENT="$1"
    shift
fi
if (($#)) && is_mode "$1"; then
    MODE="$1"
    shift
fi
if (($#)) && [[ "$1" == "--force" ]]; then
    FORCE_ARGUMENT=(--force)
    shift
fi
if (($#)); then
    echo "Unexpected argument: $1" >&2
    usage >&2
    exit 2
fi

# Slurm executes a spooled copy of this file, so BASH_SOURCE does not reliably
# identify the checkout. Prefer an explicit override, then search upward from
# the submission directory and finally try its SOMOSPIE_GFM child.
PROJECT_ROOT="${SOMOSPIE_GFM_ROOT:-}"
if [[ -z "${PROJECT_ROOT}" ]]; then
    candidate="${SUBMIT_DIR}"
    while [[ "${candidate}" != "/" ]]; do
        if [[ -f "${candidate}/pyproject.toml" && \
              -x "${candidate}/workflows/local/run_workflow.sh" ]]; then
            PROJECT_ROOT="${candidate}"
            break
        fi
        candidate="$(dirname "${candidate}")"
    done
fi
if [[ -z "${PROJECT_ROOT}" && \
      -f "${SUBMIT_DIR}/SOMOSPIE_GFM/pyproject.toml" && \
      -x "${SUBMIT_DIR}/SOMOSPIE_GFM/workflows/local/run_workflow.sh" ]]; then
    PROJECT_ROOT="${SUBMIT_DIR}/SOMOSPIE_GFM"
fi
if [[ -z "${PROJECT_ROOT}" ]]; then
    echo "Could not locate the SOMOSPIE_GFM checkout from ${SUBMIT_DIR}." >&2
    echo "Set SOMOSPIE_GFM_ROOT to its absolute path before calling sbatch." >&2
    exit 2
fi
PROJECT_ROOT="$(realpath "${PROJECT_ROOT}")"
WORKFLOW="${PROJECT_ROOT}/workflows/local/run_workflow.sh"

if [[ "${CONFIG_ARGUMENT}" = /* ]]; then
    CONFIG_PATH="${CONFIG_ARGUMENT}"
elif [[ -f "${SUBMIT_DIR}/${CONFIG_ARGUMENT}" ]]; then
    CONFIG_PATH="${SUBMIT_DIR}/${CONFIG_ARGUMENT}"
else
    CONFIG_PATH="${PROJECT_ROOT}/${CONFIG_ARGUMENT}"
fi
if [[ ! -f "${CONFIG_PATH}" ]]; then
    echo "Configuration not found: ${CONFIG_PATH}" >&2
    usage >&2
    exit 2
fi
CONFIG_PATH="$(realpath "${CONFIG_PATH}")"

# Match the reference Delta job while permitting sites or preconfigured jobs
# to retain a different module environment.
if [[ "${SOMOSPIE_SKIP_MODULES:-0}" != "1" ]] && type module >/dev/null 2>&1; then
    module purge
    read -r -a requested_modules <<< "${SOMOSPIE_MODULES:-python}"
    if ((${#requested_modules[@]})); then
        module load "${requested_modules[@]}"
    fi
fi

PYTHON="${SOMOSPIE_PYTHON:-}"
if [[ -z "${PYTHON}" && -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
    PYTHON="${PROJECT_ROOT}/.venv/bin/python"
fi
PYTHON="${PYTHON:-python3}"
if ! command -v "${PYTHON}" >/dev/null 2>&1; then
    echo "Python executable not found: ${PYTHON}" >&2
    echo "Run install.sh ahead of submission or set SOMOSPIE_PYTHON." >&2
    exit 2
fi

export SOMOSPIE_PYTHON="${PYTHON}"
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
export GDAL_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
export TMPDIR="${SLURM_TMPDIR:-${TMPDIR:-/tmp}}"

job_id="${SLURM_JOB_ID:-interactive}"
job_name="${SLURM_JOB_NAME:-sm_workflow}"
node_list="${SLURM_JOB_NODELIST:-$(hostname)}"
started="$(date -u +%FT%TZ)"

on_error() {
    status=$?
    printf '[%s] Slurm wrapper failed: job=%s mode=%s line=%s status=%s\n' \
        "$(date -u +%FT%TZ)" "${job_id}" "${MODE}" "${BASH_LINENO[0]}" \
        "${status}" >&2
    exit "${status}"
}
trap on_error ERR

printf '[%s] SOMOSPIE-GFM Slurm job starting\n' "${started}"
printf '  job_id      = %s\n' "${job_id}"
printf '  job_name    = %s\n' "${job_name}"
printf '  nodes       = %s\n' "${node_list}"
printf '  submit_dir  = %s\n' "${SUBMIT_DIR}"
printf '  project     = %s\n' "${PROJECT_ROOT}"
printf '  config      = %s\n' "${CONFIG_PATH}"
printf '  mode        = %s\n' "${MODE}"
printf '  force       = %s\n' "$([[ ${#FORCE_ARGUMENT[@]} -gt 0 ]] && echo true || echo false)"
printf '  python      = %s\n' "$(command -v "${PYTHON}")"
printf '  cpus        = %s\n' "${SLURM_CPUS_PER_TASK:-not-set}"
printf '  gpus        = %s\n' "${SLURM_GPUS_ON_NODE:-${CUDA_VISIBLE_DEVICES:-not-set}}"
printf '  tmpdir      = %s\n' "${TMPDIR}"

"${PYTHON}" - <<'PY'
from importlib.metadata import PackageNotFoundError, version
import sys

print(f"  python_ver  = {sys.version.split()[0]}")
for package in ("somospie-gfm", "torch", "terratorch"):
    try:
        print(f"  {package:11s}= {version(package)}")
    except PackageNotFoundError:
        print(f"  {package:11s}= not installed")
PY

if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=index,name,memory.total,driver_version \
        --format=csv,noheader
fi

cd "${PROJECT_ROOT}"
if command -v srun >/dev/null 2>&1 && [[ -n "${SLURM_JOB_ID:-}" ]]; then
    srun --kill-on-bad-exit=1 --unbuffered \
        bash "${WORKFLOW}" "${CONFIG_PATH}" "${MODE}" "${FORCE_ARGUMENT[@]}"
else
    echo "[warn] SLURM_JOB_ID or srun is unavailable; running without a job step."
    bash "${WORKFLOW}" "${CONFIG_PATH}" "${MODE}" "${FORCE_ARGUMENT[@]}"
fi

printf '[%s] SOMOSPIE-GFM Slurm job complete: job=%s mode=%s\n' \
    "$(date -u +%FT%TZ)" "${job_id}" "${MODE}"
