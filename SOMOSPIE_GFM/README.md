# SOMOSPIE-GFM

SOMOSPIE-GFM is an end-to-end workflow for producing dense soil-moisture
predictions from Harmonized Landsat Sentinel-2 (HLS) imagery, terrain
parameters, and ESA Climate Change Initiative (ESA-CCI) soil moisture. It
prepares geospatial inputs, fine-tunes a Prithvi EO v2 backbone, performs
overlapping inference, masks the result to an EPA/CEC ecoregion, and renders a
publication-ready PNG preview.

The workflow is designed for large rasters: preprocessing uses GDAL-backed
windowed operations, reprojection can run across multiple workers, terrain is
aligned once before training, and inference mosaics are assembled without
holding the complete output grid in memory.

## Pipeline

```text
HLS granules ──> cloud-masked monthly medians ──> EPSG:4326 tiles ──┐
                                                                    ├─> manifest
terrain rasters ──> ecoregion crop ──> stack ──> aligned terrain ──┤
                                                                    ├─> statistics
ESA-CCI daily files ──> monthly table ──> tile-mean targets ───────┘

manifest + statistics ──> Prithvi fine-tuning ──> overlapping inference
    ──> Hann-blended mosaic ──> ecoregion crop/mask ──> GeoTIFF + PNG
```

The six optical channels are fixed throughout the workflow, in Prithvi order:
`B02`, `B03`, `B04`, `B8A`, `B11`, and `B12`. The monthly-composite stage uses
the HLS Fmask layer to reject unusable observations and does not retain bands
that the model does not consume.

## Requirements

- Linux; the automatic native-package installer targets Ubuntu and Debian.
- Python 3.10, 3.11, or 3.12.
- GDAL command-line tools and development headers.
- Enough storage for HLS granules, prepared tiles, aligned terrain, and model
  checkpoints. A Prithvi-600 checkpoint can be several gigabytes.
- An NVIDIA GPU is strongly recommended for Prithvi-600 training. CPU-only
  installation and inference are supported but training will be slow.
- Source terrain-parameter GeoTIFFs covering every requested ecoregion.
- A NASA Earthdata Login entry in `~/.netrc` when acquisition is enabled.

The HLS downloader expects an entry similar to the following. Protect the file
with `chmod 600 ~/.netrc` and never commit it.

```text
machine urs.earthdata.nasa.gov login YOUR_USERNAME password YOUR_PASSWORD
```

CEC North American ecoregion shapefiles and ESA-CCI files are retrieved by the
workflow. Downloaded shapefile sidecars and all generated raster/model outputs
are intentionally excluded from Git.

## Installation

From the `SOMOSPIE_GFM` directory, create an isolated environment and activate
it:

```bash
./install.sh
source .venv/bin/activate
```

The installer follows the GDAL setup used by GEOtiled: it installs native GDAL
first and builds the matching `gdal[numpy]` Python bindings. It automatically
selects CUDA 12.1 PyTorch wheels when `nvidia-smi` is available and CPU wheels
otherwise. Selection and environment location can also be explicit:

```bash
./install.sh --cuda --venv /path/to/somospie-gfm-env
./install.sh --cpu
```

On a non-Debian system, install Python venv support, GDAL headers and tools,
`curl` or `wget`, and `unzip` with the system package manager, then run:

```bash
./install.sh --skip-system-packages
```

The project is installed in editable mode. To verify the principal entry
points:

```bash
somospie-gfm-train --help
somospie-gfm-infer --help
somospie-gfm-postprocess --help
somospie-gfm-visualize --help
```

## Configuration

Create a machine-local configuration from the documented template:

```bash
cp configs/example.yaml configs/config.yaml
```

Edit at least these settings:

- `train_ecoregions`: one or more ecoregion codes supplying labelled tiles.
- `infer_ecoregion`: the one ecoregion receiving the final prediction.
- `results_slug`: a safe, unique name for this experiment's artifacts.
- `year` and `month`: the common HLS and ESA-CCI observation window.
- `workdir`: storage root for raw data, intermediates, models, logs, and output.
- `terrain_dir`: optional source terrain directory; when omitted, the workflow
  reads `<workdir>/raw/terrain`.

Ecoregion levels are inferred from their codes (`6` is Level I, `6.2` is Level
II, and `6.2.13` is Level III). Separate level settings are neither needed nor
accepted. Input bands, dense prediction mode, tile-mean supervision, and use of
all terrain parameters are deliberate fixed pipeline behavior rather than
configuration switches. Every remaining setting and its trade-off is described
inline in `configs/example.yaml`.

`configs/config.yaml` is ignored because it normally contains host-specific
paths. The workflow copies the exact configuration used for each experiment to
`<workdir>/run-metadata/<results_slug>/config.yaml`.

## Running the workflow

Run every stage with persistent logging:

```bash
workflows/local/run_workflow.sh configs/config.yaml all
```

The runner validates its configuration and dependencies before each major
phase. It writes a timestamped log under `<workdir>/logs` (or
`workflow-logs/` if the work directory cannot yet be created), records the Git
commit and executable path, and places completion markers under
`run-metadata/<results_slug>/stages`.

Available modes are:

| Mode | Work performed |
| --- | --- |
| `all` | Acquisition, preparation, training, inference, postprocessing, and visualization. |
| `prepare` | Acquisition and all preprocessing through manifests, aligned terrain, and normalization statistics. |
| `train` | Fine-tuning from already prepared inputs. |
| `infer` | Overlapping inference followed by postprocessing and visualization. |
| `postprocess` | Crop and mask an existing raw prediction to the inference ecoregion. |
| `visualize` | Render the final cropped GeoTIFF as a PNG. |

Completed stages are skipped on subsequent runs. Pass `--force` after the mode
to rerun them:

```bash
workflows/local/run_workflow.sh configs/config.yaml infer --force
```

Completion markers are keyed by `results_slug`, not by a hash of the
configuration. Use a new slug for a distinct experiment, or use `--force` when
changing a setting that affects an already completed stage.

To operate on HLS, ESA-CCI, and ecoregion files already present under
`<workdir>/raw`, skip network acquisition:

```bash
SOMOSPIE_SKIP_ACQUISITION=1 \
  workflows/local/run_workflow.sh configs/config.yaml all
```

Set `SOMOSPIE_PYTHON=/path/to/python` to override the interpreter. Otherwise,
the runner prefers `.venv/bin/python` and falls back to `python3`.

## Data and output layout

The workflow creates this storage contract:

```text
<workdir>/
├── raw/
│   ├── esa_cci/
│   ├── hls/
│   └── terrain/
├── intermediate/<results_slug>/
│   ├── aligned_terrain/
│   ├── band_stats.json
│   ├── hls_composites/
│   ├── hls_wgs84/
│   ├── infer_manifest.csv
│   ├── terrain_regions/
│   ├── terrain_stacks/
│   └── train_manifest.csv
├── prepared/<results_slug>/
├── models/<results_slug>/
│   ├── prithvi_sm_best.pt
│   ├── prithvi_sm_last.pt
│   └── training_history.json
├── predictions/<results_slug>/
│   ├── predictions.csv
│   ├── soil_moisture_raw.tif
│   └── final/
│       ├── soil_moisture.tif
│       └── soil_moisture.png
├── logs/
└── run-metadata/<results_slug>/
```

`final/soil_moisture.tif` is the authoritative deliverable: overlapping model
windows have been blended and its bounds and valid pixels have been cropped to
the requested ecoregion. The PNG is a visualization of that GeoTIFF. The
`png_smooth_sigma` option affects only the preview and never changes scientific
raster values.

## Individual modules

Every Python stage can also run independently. Use module help for required
arguments and overwrite behavior:

```bash
python -m somospie_gfm.preprocessing.calculate_monthly_composite --help
python -m somospie_gfm.preprocessing.reproject --help
python -m somospie_gfm.preprocessing.tile --help
python -m somospie_gfm.preprocessing.prune_tiles_to_ecoregion --help
python -m somospie_gfm.preprocessing.produce_ecoregion_terrain --help
python -m somospie_gfm.preprocessing.stack_parameters --help
python -m somospie_gfm.preprocessing.attach_targets --help
python -m somospie_gfm.preprocessing.build_aligned_terrain_map --help
python -m somospie_gfm.preprocessing.compute_band_stats --help
```

These commands document their parameters, results, and failure conditions in
both their command-line help and source docstrings.

## Docker

Build the CUDA 12.1 image from this directory:

```bash
docker build -t somospie-gfm .
```

Run it with GPU access and mount durable workflow storage at `/workdir`:

```bash
mkdir -p workdir
docker run --rm -it \
  --gpus all \
  --volume "$(pwd)/workdir:/workdir" \
  somospie-gfm
```

Mount terrain data and a configuration file as needed, and ensure configuration
paths refer to their locations inside the container. The image can run
preprocessing or CPU inference without `--gpus all`; its PyTorch installation
still includes CUDA support.

## Interpretation and validation

Keep these limits visible when evaluating or publishing predictions:

- ESA-CCI supplies coarse, roughly 27 km supervision. Training compares each
  tile's mean dense prediction with that coarse target; fine-scale spatial
  texture is model-derived and is not direct 30 m ground truth.
- The workflow does not create a spatial holdout automatically. Without a
  holdout list in a separately prepared manifest, `prithvi_sm_best.pt` is chosen
  using training MSE. Establish spatial and temporal holdouts before reporting
  generalization performance.
- Reprojection currently uses EPSG:4326 at `0.0003` degrees. This is near 30 m
  in north-south spacing, but east-west ground spacing varies with latitude. A
  projected CRS is needed when constant metric pixel area is a requirement.
- The decoder output is not physically clipped. Check valid ranges, bias,
  calibration, and performance against independent in-situ or higher-resolution
  observations before treating outputs as operational soil moisture.
- HLS availability and cloud masking can leave sparse or invalid pixels. Review
  `band_stats.json`, preparation logs, and final raster coverage for every run.

## Development checks

Before committing changes, run at least:

```bash
python -m compileall -q src/somospie_gfm
bash -n install.sh workflows/local/run_workflow.sh \
  src/somospie_gfm/acquisition/*.sh
git diff --check
```

For a low-cost integration check, use a small ecoregion, a distinct
`results_slug`, and reduced epochs. Do not reuse a scientific experiment's slug
for smoke tests because the workflow is resumable by design.
