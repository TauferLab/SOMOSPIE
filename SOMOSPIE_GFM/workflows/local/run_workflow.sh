#!/usr/bin/env bash

# Run the local SOMOSPIE-GFM pipeline with persistent logs and resumable stages.
# Usage: run_workflow.sh [config.yaml] [all|prepare|train|infer|postprocess|visualize] [--force]
# Set SOMOSPIE_SKIP_ACQUISITION=1 to use raw inputs already in workdir/raw.

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CONFIG_PATH="${1:-${PROJECT_ROOT}/configs/config.yaml}"
MODE="${2:-all}"
FORCE=false
[[ "${3:-}" == "--force" ]] && FORCE=true
if [[ -n "${3:-}" && "${3}" != "--force" ]]; then
    echo "Unknown option: $3" >&2
    exit 2
fi
[[ -f "${CONFIG_PATH}" ]] || CONFIG_PATH="${PROJECT_ROOT}/${CONFIG_PATH}"
[[ -f "${CONFIG_PATH}" ]] || { echo "Configuration not found: ${CONFIG_PATH}" >&2; exit 2; }
CONFIG_PATH="$(realpath "${CONFIG_PATH}")"
case "${MODE}" in
    all|prepare|train|infer|postprocess|visualize) ;;
    *) echo "Invalid mode: ${MODE}" >&2; exit 2;;
esac

PYTHON="${SOMOSPIE_PYTHON:-}"
[[ -n "${PYTHON}" ]] || [[ ! -x "${PROJECT_ROOT}/.venv/bin/python" ]] || \
    PYTHON="${PROJECT_ROOT}/.venv/bin/python"
PYTHON="${PYTHON:-python3}"

# Validate YAML and return values separated by NUL characters. This avoids
# evaluating configuration text in the shell.
mapfile -d '' -t CFG < <("${PYTHON}" - "${CONFIG_PATH}" <<'PY'
import calendar
import datetime as dt
import re
import sys
from pathlib import Path
import yaml

path = Path(sys.argv[1])
config = yaml.safe_load(path.read_text(encoding="utf-8"))
required = (
    "train_ecoregions", "infer_ecoregion", "results_slug", "year", "month",
    "hls_cloud_coverage", "backbone_name", "tile_size", "patch_size",
    "decoder_type", "decoder_channels", "decoder_dropout",
    "backbone_drop_path_rate", "epochs", "batch_size", "unfreeze_after",
    "lr_head", "lr_backbone", "weight_decay", "tv_loss_weight",
    "grad_accum_steps", "num_workers", "amp", "inference_stride",
    "png_smooth_sigma", "workdir", "reproject_workers",
)
if not isinstance(config, dict):
    raise SystemExit(f"{path} must contain a YAML mapping")
missing = [key for key in required if key not in config]
if missing:
    raise SystemExit(f"Missing config settings: {', '.join(missing)}")
pattern = r"\d+(?:\.\d+){0,2}"
regions = config["train_ecoregions"]
if not isinstance(regions, list) or not regions or not all(
    isinstance(value, str) and re.fullmatch(pattern, value) for value in regions
):
    raise SystemExit("train_ecoregions must be a non-empty list of level I-III codes")
infer_region = config["infer_ecoregion"]
if not isinstance(infer_region, str) or not re.fullmatch(pattern, infer_region):
    raise SystemExit("infer_ecoregion must be a level I-III code")
slug = str(config["results_slug"])
if not re.fullmatch(r"[A-Za-z0-9._-]+", slug):
    raise SystemExit("results_slug contains unsafe filesystem characters")
year, month = int(config["year"]), int(config["month"])
if not 1 <= month <= 12:
    raise SystemExit("month must be between 01 and 12")
for key in ("tile_size", "patch_size", "decoder_channels", "epochs", "batch_size",
            "grad_accum_steps", "num_workers", "reproject_workers"):
    if int(config[key]) <= 0:
        raise SystemExit(f"{key} must be positive")
if int(config["unfreeze_after"]) < 0:
    raise SystemExit("unfreeze_after cannot be negative")
cloud = int(config["hls_cloud_coverage"])
if not 0 <= cloud <= 100:
    raise SystemExit("hls_cloud_coverage must be between 0 and 100")
if not isinstance(config["amp"], bool):
    raise SystemExit("amp must be true or false")
stride = int(config["inference_stride"])
if not 0 < stride < int(config["tile_size"]):
    raise SystemExit("inference_stride must be between 1 and tile_size - 1")
smooth_sigma = float(config["png_smooth_sigma"])
if smooth_sigma < 0:
    raise SystemExit("png_smooth_sigma cannot be negative")
start = dt.date(year, month, 1)
end = dt.date(year, month, calendar.monthrange(year, month)[1])
values = (
    str(Path(config["workdir"]).expanduser()), slug, str(year), f"{month:02d}",
    start.isoformat(), end.isoformat(), str(cloud), str(config["backbone_name"]),
    str(int(config["tile_size"])), str(int(config["patch_size"])),
    str(config["decoder_type"]), str(int(config["decoder_channels"])),
    str(float(config["decoder_dropout"])), str(float(config["backbone_drop_path_rate"])),
    str(int(config["epochs"])), str(int(config["batch_size"])),
    str(int(config["unfreeze_after"])), str(float(config["lr_head"])),
    str(float(config["lr_backbone"])), str(float(config["weight_decay"])),
    str(float(config["tv_loss_weight"])), str(int(config["grad_accum_steps"])),
    str(int(config["num_workers"])), "1" if config["amp"] else "0",
    str(stride), str(smooth_sigma), str(int(config["reproject_workers"])),
    str(len(regions)), *regions, infer_region,
    str(Path(config.get("terrain_dir", Path(config["workdir"]) / "raw" / "terrain")).expanduser()),
)
sys.stdout.write("\0".join(values) + "\0")
PY
)

WORKDIR="${CFG[0]}" RESULTS_SLUG="${CFG[1]}" YEAR="${CFG[2]}" MONTH="${CFG[3]}"
START_DATE="${CFG[4]}" END_DATE="${CFG[5]}" HLS_CLOUD_COVERAGE="${CFG[6]}"
BACKBONE="${CFG[7]}" TILE_SIZE="${CFG[8]}" PATCH_SIZE="${CFG[9]}"
DECODER="${CFG[10]}" DECODER_CHANNELS="${CFG[11]}" DECODER_DROPOUT="${CFG[12]}"
DROP_PATH_RATE="${CFG[13]}" EPOCHS="${CFG[14]}" BATCH_SIZE="${CFG[15]}"
UNFREEZE_AFTER="${CFG[16]}" HEAD_LR="${CFG[17]}" BACKBONE_LR="${CFG[18]}"
WEIGHT_DECAY="${CFG[19]}" TV_WEIGHT="${CFG[20]}" ACCUMULATION_STEPS="${CFG[21]}"
NUM_WORKERS="${CFG[22]}" AMP="${CFG[23]}" INFERENCE_STRIDE="${CFG[24]}"
PNG_SMOOTH_SIGMA="${CFG[25]}" REPROJECT_WORKERS="${CFG[26]}"
TRAIN_REGION_COUNT="${CFG[27]}"
TRAIN_REGIONS=("${CFG[@]:28:${TRAIN_REGION_COUNT}}")
INFER_REGION="${CFG[$((28 + TRAIN_REGION_COUNT))]}"
RAW_TERRAIN="${CFG[$((29 + TRAIN_REGION_COUNT))]}"
ALL_REGIONS=("${TRAIN_REGIONS[@]}")
[[ " ${ALL_REGIONS[*]} " =~ " ${INFER_REGION} " ]] || ALL_REGIONS+=("${INFER_REGION}")

RUN_TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
if mkdir -p "${WORKDIR}/logs" 2>/dev/null; then
    LOG_DIR="${WORKDIR}/logs"
else
    LOG_DIR="${PROJECT_ROOT}/workflow-logs"
    mkdir -p "${LOG_DIR}"
fi
LOG_FILE="${LOG_DIR}/${RESULTS_SLUG}_${MODE}_${RUN_TIMESTAMP}.log"
exec > >(tee -a "${LOG_FILE}") 2>&1
CURRENT_STAGE=startup
trap 'status=$?; printf "[%s] ERROR stage=%s line=%s status=%s command=%q\n" "$(date -u +%FT%TZ)" "$CURRENT_STAGE" "$LINENO" "$status" "$BASH_COMMAND" >&2; printf "Full log: %s\n" "$LOG_FILE" >&2; exit "$status"' ERR

RAW_ESA="${WORKDIR}/raw/esa_cci" RAW_HLS="${WORKDIR}/raw/hls"
INTERMEDIATE="${WORKDIR}/intermediate/${RESULTS_SLUG}"
COMPOSITES="${INTERMEDIATE}/hls_composites" REPROJECTED="${INTERMEDIATE}/hls_wgs84"
TERRAIN_REGIONS="${INTERMEDIATE}/terrain_regions" TERRAIN_STACKS="${INTERMEDIATE}/terrain_stacks"
ALIGNED_TERRAIN="${INTERMEDIATE}/aligned_terrain" PREPARED="${WORKDIR}/prepared/${RESULTS_SLUG}"
MODEL_DIR="${WORKDIR}/models/${RESULTS_SLUG}" PREDICTION_DIR="${WORKDIR}/predictions/${RESULTS_SLUG}"
FINAL_DIR="${PREDICTION_DIR}/final"
METADATA_DIR="${WORKDIR}/run-metadata/${RESULTS_SLUG}" STATE_DIR="${METADATA_DIR}/stages"
SHAPEFILES="${PROJECT_ROOT}/resources/shapefiles" TILE_LIST="${METADATA_DIR}/hls_tiles.txt"
SOIL_MOISTURE_CSV="${INTERMEDIATE}/${YEAR}_ESA_monthly.csv"
TRAIN_MANIFEST="${INTERMEDIATE}/train_manifest.csv" INFER_MANIFEST="${INTERMEDIATE}/infer_manifest.csv"
STATS="${INTERMEDIATE}/band_stats.json" TERRAIN_SOURCE_MAP="${INTERMEDIATE}/terrain_source_map.json"
TERRAIN_ALIGNED_MAP="${INTERMEDIATE}/terrain_aligned_map.json"
CHECKPOINT="${MODEL_DIR}/prithvi_sm_best.pt"
RAW_PREDICTION="${PREDICTION_DIR}/soil_moisture_raw.tif"
FINAL_PREDICTION="${FINAL_DIR}/soil_moisture.tif"
FINAL_PNG="${FINAL_DIR}/soil_moisture.png"

log() { printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*"; }
die() { log "ERROR: $*" >&2; return 1; }
require_command() { command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"; }
require_imports() {
    "${PYTHON}" - "$@" <<'PY'
import importlib, sys
errors = []
for name in sys.argv[1:]:
    try: importlib.import_module(name)
    except Exception as exc: errors.append(f"{name}: {type(exc).__name__}: {exc}")
if errors: raise SystemExit("Required Python imports failed:\n  " + "\n  ".join(errors))
PY
}
run_stage() {
    local name="$1" function_name="$2" marker="${STATE_DIR}/$1.complete"
    CURRENT_STAGE="${name}"
    if [[ "${FORCE}" == false && -f "${marker}" ]]; then log "SKIP ${name}: complete"; return; fi
    log "BEGIN ${name}"
    "${function_name}"
    mkdir -p "${STATE_DIR}"; date -u +%FT%TZ > "${marker}"
    log "END ${name}"
}

preflight_common() {
    command -v "${PYTHON}" >/dev/null 2>&1 || die "Python not found: ${PYTHON}"
    require_imports yaml
    mkdir -p "${WORKDIR}" "${METADATA_DIR}" "${STATE_DIR}" || die "cannot create ${WORKDIR}"
    cp "${CONFIG_PATH}" "${METADATA_DIR}/config.yaml"
    { printf 'started_utc=%s\nmode=%s\nconfig=%s\npython=%s\nlog=%s\n' \
        "${RUN_TIMESTAMP}" "${MODE}" "${CONFIG_PATH}" "$(command -v "${PYTHON}")" "${LOG_FILE}"
      git -C "${PROJECT_ROOT}" rev-parse HEAD 2>/dev/null | sed 's/^/git_commit=/' || true; \
    } > "${METADATA_DIR}/run.env"
    log "Config: ${CONFIG_PATH}"; log "Mode: ${MODE}"; log "Workdir: ${WORKDIR}"
    log "Train: ${TRAIN_REGIONS[*]} | Infer: ${INFER_REGION} | Dates: ${START_DATE}..${END_DATE}"
    log "Terrain: ${RAW_TERRAIN}"
    log "Full log: ${LOG_FILE}"
}
preflight_prepare() {
    local failed=false
    require_imports numpy pandas geopandas shapely osgeo || failed=true
    require_command gdal-config || failed=true
    require_command unzip || failed=true
    if [[ "${SOMOSPIE_SKIP_ACQUISITION:-0}" != 1 ]]; then
        require_command curl || failed=true
        require_command wget || failed=true
        if [[ ! -f "${HOME}/.netrc" ]]; then
            log "ERROR: ${HOME}/.netrc is required for HLS downloads" >&2
            failed=true
        fi
    fi
    mkdir -p "${RAW_ESA}" "${RAW_HLS}" "${INTERMEDIATE}" "${PREPARED}"
    if ! find "${RAW_TERRAIN}" -type f \( -iname '*.tif' -o -iname '*.tiff' \) \
        -print -quit 2>/dev/null | grep -q .; then
        log "ERROR: place source terrain GeoTIFFs under ${RAW_TERRAIN}" >&2
        failed=true
    fi
    if ! grep -q '^def main' "${PROJECT_ROOT}/src/somospie_gfm/preprocessing/tile.py"; then
        log "ERROR: preprocessing/tile.py has no runnable tiling implementation" >&2
        failed=true
    fi
    [[ "${failed}" == false ]] || die "preparation preflight found missing prerequisites"
}
preflight_train() {
    require_imports numpy pandas osgeo torch terratorch
    [[ -f "${TRAIN_MANIFEST}" ]] || die "missing ${TRAIN_MANIFEST}"
    [[ -f "${STATS}" ]] || die "missing ${STATS}"
    [[ -f "${TERRAIN_ALIGNED_MAP}" ]] || die "missing ${TERRAIN_ALIGNED_MAP}"
}
preflight_infer() {
    require_imports numpy pandas osgeo torch terratorch
    [[ -f "${INFER_MANIFEST}" ]] || die "missing ${INFER_MANIFEST}"
    [[ -f "${CHECKPOINT}" ]] || die "missing ${CHECKPOINT}"
    [[ -f "${TERRAIN_ALIGNED_MAP}" ]] || die "missing ${TERRAIN_ALIGNED_MAP}"
}
preflight_postprocess() {
    require_imports numpy osgeo
    [[ -f "${RAW_PREDICTION}" ]] || die "missing ${RAW_PREDICTION}"
}
preflight_visualize() {
    require_imports numpy osgeo matplotlib
    [[ -f "${FINAL_PREDICTION}" ]] || die "missing ${FINAL_PREDICTION}"
}

acquire_shapefiles() { "${PROJECT_ROOT}/src/somospie_gfm/acquisition/retrieve_ecoregion_shapefiles.sh" "${SHAPEFILES}"; }
write_hls_tile_list() {
    "${PYTHON}" - "${PROJECT_ROOT}/resources" "${TILE_LIST}" "${ALL_REGIONS[@]}" <<'PY'
import csv, sys
from pathlib import Path
resources, output, *regions = sys.argv[1:]
tiles = set()
for region in regions:
    level = region.count(".") + 1
    with (Path(resources) / f"ecoregion_l{level}_overlaps.csv").open(newline="") as stream:
        tiles.update(row["tile"] for row in csv.DictReader(stream) if row[f"NA_L{level}CODE"] == region)
if not tiles: raise SystemExit(f"No HLS tiles found for {regions}")
path = Path(output); path.parent.mkdir(parents=True, exist_ok=True)
path.write_text("".join(f"{tile}\n" for tile in sorted(tiles)), encoding="utf-8")
print(f"Wrote {len(tiles)} HLS tile IDs to {path}")
PY
}
acquire_hls() { HLS_CLOUD_COVERAGE="${HLS_CLOUD_COVERAGE}" bash "${PROJECT_ROOT}/src/somospie_gfm/acquisition/retrieve_hls.sh" "${TILE_LIST}" "${START_DATE}" "${END_DATE}" "${RAW_HLS}"; }
acquire_soil_moisture() { bash "${PROJECT_ROOT}/src/somospie_gfm/acquisition/retrieve_sm.sh" "${YEAR}" "${RAW_ESA}" "${MONTH}"; }
prepare_soil_moisture() {
    local force=(); [[ "${FORCE}" == false ]] || force+=(--force)
    "${PYTHON}" -m somospie_gfm.preprocessing.prepare_monthly_sm --input-root "${RAW_ESA}" --year "${YEAR}" --output "${SOIL_MOISTURE_CSV}" "${force[@]}"
}
build_composites() { "${PYTHON}" -m somospie_gfm.preprocessing.calculate_monthly_composite --input-root "${RAW_HLS}" --output-dir "${COMPOSITES}" --start-date "${START_DATE}" --end-date "${END_DATE}" --workers "${REPROJECT_WORKERS}"; }
reproject_composites() { "${PYTHON}" -m somospie_gfm.preprocessing.reproject "${COMPOSITES}" "${REPROJECTED}" --dst-crs EPSG:4326 --resolution 0.0003 --target-aligned-pixels --resampling bilinear --workers "${REPROJECT_WORKERS}"; }
tile_and_prune() {
    local region region_root tile_root without_dots level
    for region in "${ALL_REGIONS[@]}"; do
        region_root="${PREPARED}/${region}"
        "${PYTHON}" -m somospie_gfm.preprocessing.tile --input-dir "${REPROJECTED}" --output-dir "${region_root}" --tile-size "${TILE_SIZE}"
        without_dots="${region//./}"; level=$((${#region} - ${#without_dots} + 1))
        while IFS= read -r -d '' tile_root; do
            "${PYTHON}" -m somospie_gfm.preprocessing.prune_tiles_to_ecoregion --tiles-root "${tile_root}" --ecoregion "${region}" --shapefiles-root "${SHAPEFILES}" --level "${level}" --manifest "${METADATA_DIR}/prune_${region}_$(basename "${tile_root}").txt" --apply
        done < <(find "${region_root}" -mindepth 1 -maxdepth 1 -type d -print0)
    done
}
prepare_terrain() {
    local region cropped stack overwrite=(); [[ "${FORCE}" == false ]] || overwrite+=(--overwrite)
    for region in "${ALL_REGIONS[@]}"; do
        cropped="${TERRAIN_REGIONS}/${region}"; stack="${TERRAIN_STACKS}/${region}_terrain.tif"
        "${PYTHON}" -m somospie_gfm.preprocessing.produce_ecoregion_terrain --input-dir "${RAW_TERRAIN}" --output-dir "${cropped}" --ecoregion "${region}" --shapefiles-root "${SHAPEFILES}" --recursive "${overwrite[@]}"
        "${PYTHON}" -m somospie_gfm.preprocessing.stack_parameters --input-dir "${cropped}" --output "${stack}" --recursive "${overwrite[@]}"
    done
    write_terrain_map "${TERRAIN_SOURCE_MAP}" "${TERRAIN_STACKS}" source
}
write_terrain_map() {
    "${PYTHON}" - "$1" "$2" "$3" "${ALL_REGIONS[@]}" <<'PY'
import json, sys
from pathlib import Path
output, root, kind, *regions = sys.argv[1:]
suffix = "_terrain.tif" if kind == "source" else "_terrain_aligned.tif"
mapping = {region: str((Path(root) / f"{region}{suffix}").resolve()) for region in regions}
Path(output).write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
print(f"Wrote terrain map: {output}")
PY
}
attach_manifests() {
    local roots=() force=() region; [[ "${FORCE}" == false ]] || force+=(--force)
    for region in "${TRAIN_REGIONS[@]}"; do roots+=(--tiles-root "${PREPARED}/${region}"); done
    "${PYTHON}" -m somospie_gfm.preprocessing.attach_targets "${roots[@]}" --soil-moisture-csv "${SOIL_MOISTURE_CSV}" --month "${MONTH}" --workers "${NUM_WORKERS}" --output "${TRAIN_MANIFEST}" "${force[@]}"
    "${PYTHON}" -m somospie_gfm.preprocessing.attach_targets --tiles-root "${PREPARED}/${INFER_REGION}" --soil-moisture-csv "${SOIL_MOISTURE_CSV}" --month "${MONTH}" --workers "${NUM_WORKERS}" --output "${INFER_MANIFEST}" "${force[@]}"
}
align_terrain_and_compute_stats() {
    local roots=() train_csv= force=() region; [[ "${FORCE}" == false ]] || force+=(--force)
    for region in "${ALL_REGIONS[@]}"; do roots+=("${PREPARED}/${region}"); done
    "${PYTHON}" -m somospie_gfm.preprocessing.build_aligned_terrain_map --tiles-root "$(IFS=,; echo "${roots[*]}")" --terrain-stack-map "${TERRAIN_SOURCE_MAP}" --output-dir "${ALIGNED_TERRAIN}"
    write_terrain_map "${TERRAIN_ALIGNED_MAP}" "${ALIGNED_TERRAIN}" aligned
    for region in "${TRAIN_REGIONS[@]}"; do train_csv+="${train_csv:+,}${PREPARED}/${region}"; done
    "${PYTHON}" -m somospie_gfm.preprocessing.compute_band_stats --tiles-root "${train_csv}" --terrain-stack-map "${TERRAIN_SOURCE_MAP}" --aligned-terrain-dir "${ALIGNED_TERRAIN}" --output "${STATS}" "${force[@]}"
}
train_model() {
    local amp=(); [[ "${AMP}" == 0 ]] || amp+=(--amp)
    "${PYTHON}" -m somospie_gfm.nn.train --manifest "${TRAIN_MANIFEST}" --stats "${STATS}" --aligned-terrain-map "${TERRAIN_ALIGNED_MAP}" --backbone "${BACKBONE}" --tile-size "${TILE_SIZE}" --patch-size "${PATCH_SIZE}" --decoder "${DECODER}" --decoder-channels "${DECODER_CHANNELS}" --decoder-dropout "${DECODER_DROPOUT}" --drop-path-rate "${DROP_PATH_RATE}" --epochs "${EPOCHS}" --unfreeze-after "${UNFREEZE_AFTER}" --batch-size "${BATCH_SIZE}" --workers "${NUM_WORKERS}" --head-lr "${HEAD_LR}" --backbone-lr "${BACKBONE_LR}" --weight-decay "${WEIGHT_DECAY}" --tv-weight "${TV_WEIGHT}" --accumulation-steps "${ACCUMULATION_STEPS}" "${amp[@]}" --output-dir "${MODEL_DIR}"
}
run_inference() {
    local amp=() force=(); [[ "${AMP}" == 0 ]] || amp+=(--amp); [[ "${FORCE}" == false ]] || force+=(--force)
    "${PYTHON}" -m somospie_gfm.nn.infer --checkpoint "${CHECKPOINT}" --manifest "${INFER_MANIFEST}" --aligned-terrain-map "${TERRAIN_ALIGNED_MAP}" --splits train,holdout,unlabeled --batch-size "${BATCH_SIZE}" --workers "${NUM_WORKERS}" --stride "${INFERENCE_STRIDE}" "${amp[@]}" --output-dir "${PREDICTION_DIR}" --summary "${PREDICTION_DIR}/predictions.csv" --mosaic "${RAW_PREDICTION}" "${force[@]}"
}
postprocess_predictions() {
    local force=(); [[ "${FORCE}" == false ]] || force+=(--force)
    "${PYTHON}" -m somospie_gfm.postprocessing.finalize_predictions --input "${RAW_PREDICTION}" --output "${FINAL_PREDICTION}" --ecoregion "${INFER_REGION}" --shapefiles-root "${SHAPEFILES}" "${force[@]}"
}
visualize_predictions() {
    "${PYTHON}" -m somospie_gfm.visualize.render_prediction --input "${FINAL_PREDICTION}" --output "${FINAL_PNG}" --title "Predicted soil moisture — ${INFER_REGION} (${YEAR}-${MONTH})" --smooth-sigma "${PNG_SMOOTH_SIGMA}"
}
run_prepare() {
    preflight_prepare
    if [[ "${SOMOSPIE_SKIP_ACQUISITION:-0}" != 1 ]]; then
        run_stage acquire_shapefiles acquire_shapefiles; run_stage write_hls_tile_list write_hls_tile_list
        run_stage acquire_hls acquire_hls; run_stage acquire_soil_moisture acquire_soil_moisture
    else log "Skipping acquisition; using ${WORKDIR}/raw"; fi
    run_stage prepare_soil_moisture prepare_soil_moisture; run_stage build_composites build_composites
    run_stage reproject_composites reproject_composites; run_stage tile_and_prune tile_and_prune
    run_stage prepare_terrain prepare_terrain; run_stage attach_manifests attach_manifests
    run_stage align_terrain_and_compute_stats align_terrain_and_compute_stats
}

preflight_common
export PYTHONPATH="${PROJECT_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"
case "${MODE}" in
    all)
        run_prepare
        preflight_train; run_stage train train_model
        preflight_infer; run_stage infer run_inference
        preflight_postprocess; run_stage postprocess postprocess_predictions
        preflight_visualize; run_stage visualize visualize_predictions
        ;;
    prepare) run_prepare;;
    train) preflight_train; run_stage train train_model;;
    infer)
        preflight_infer; run_stage infer run_inference
        preflight_postprocess; run_stage postprocess postprocess_predictions
        preflight_visualize; run_stage visualize visualize_predictions
        ;;
    postprocess) preflight_postprocess; run_stage postprocess postprocess_predictions;;
    visualize) preflight_visualize; run_stage visualize visualize_predictions;;
esac
CURRENT_STAGE=complete
log "Workflow completed successfully"
log "Full log: ${LOG_FILE}"
