"""Run dense soil-moisture inference on a prepared-tile manifest.

Inference restores the architecture and normalization contract from a training
checkpoint, reads the same prepared HLS and aligned-terrain inputs used during
training, and writes georeferenced prediction tiles plus a CSV summary. Optional
Monte Carlo dropout adds pixelwise standard deviation and interval bands.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from contextlib import nullcontext
from pathlib import Path
from statistics import NormalDist
from typing import Any, Sequence

import numpy as np
import torch
import torch.nn as nn
from osgeo import gdal

if __package__:
    from .data import (
        PreparedTileDataset,
        TerrainResolver,
        TileRecord,
        load_manifest,
        load_terrain_map,
        select_records,
        stats_from_checkpoint,
    )
    from .model import ModelConfig, PrithviSoilMoisture
    from .train import make_loader
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from somospie_gfm.nn.data import (
        PreparedTileDataset,
        TerrainResolver,
        TileRecord,
        load_manifest,
        load_terrain_map,
        select_records,
        stats_from_checkpoint,
    )
    from somospie_gfm.nn.model import ModelConfig, PrithviSoilMoisture
    from somospie_gfm.nn.train import make_loader

gdal.UseExceptions()


def load_checkpoint(
    path: Path,
    device: torch.device,
) -> tuple[dict[str, Any], ModelConfig]:
    """Load and validate an inference checkpoint.

    Parameters
    ----------
    path : pathlib.Path
        Checkpoint written by :mod:`somospie_gfm.nn.train`.
    device : torch.device
        Target map location for tensors.

    Returns
    -------
    tuple
        Raw checkpoint mapping and validated :class:`ModelConfig`.

    Raises
    ------
    FileNotFoundError
        If the checkpoint is missing.
    RuntimeError, ValueError, KeyError, TypeError
        If deserialization fails or required model/statistics metadata is
        missing or invalid.
    """
    if not path.is_file():
        raise FileNotFoundError(f"checkpoint not found: {path}")
    try:
        checkpoint = torch.load(path, map_location=device, weights_only=True)
    except TypeError:
        checkpoint = torch.load(path, map_location=device)
    if checkpoint.get("checkpoint_version") != 1:
        raise ValueError(
            f"unsupported checkpoint version {checkpoint.get('checkpoint_version')!r}"
        )
    config = ModelConfig.from_dict(checkpoint["model_config"])
    stats = stats_from_checkpoint(checkpoint["normalization_stats"])
    if config.channel_names != stats.channel_names:
        raise ValueError("checkpoint model channels do not match embedded statistics")
    if not isinstance(checkpoint.get("model_state_dict"), dict):
        raise ValueError("checkpoint has no model_state_dict")
    return checkpoint, config


def enable_mc_dropout(model: nn.Module) -> None:
    """Enable dropout/drop-path while leaving normalization layers in eval mode."""
    model.eval()
    dropout_types = (
        nn.Dropout,
        nn.Dropout1d,
        nn.Dropout2d,
        nn.Dropout3d,
        nn.AlphaDropout,
    )
    for module in model.modules():
        if (
            isinstance(module, dropout_types)
            or module.__class__.__name__ == "DropPath"
        ):
            module.train()


def predict_batch(
    model: PrithviSoilMoisture,
    inputs: torch.Tensor,
    *,
    amp: bool,
    mc_samples: int,
    interval_alpha: float,
) -> tuple[torch.Tensor, ...]:
    """Predict one batch deterministically or with Monte Carlo dropout.

    Parameters
    ----------
    model : PrithviSoilMoisture
        Restored model on the same device as ``inputs``.
    inputs : torch.Tensor
        Normalized ``[B, C, T, H, W]`` batch.
    amp : bool
        Use float16 autocast for CUDA inputs.
    mc_samples : int
        Number of stochastic passes; zero selects one deterministic pass.
    interval_alpha : float
        Two-sided interval miscoverage probability.

    Returns
    -------
    tuple of torch.Tensor
        Deterministic mode returns ``(prediction,)``. MC mode returns
        ``(mean, std, lower, upper)`` in ``[B, H, W]`` form.

    Raises
    ------
    ValueError
        If sample count is negative or alpha is outside ``(0, 1)``.
    """
    if mc_samples < 0:
        raise ValueError("mc_samples cannot be negative")
    if not 0 < interval_alpha < 1:
        raise ValueError("interval_alpha must be in (0, 1)")
    amp_enabled = amp and inputs.device.type == "cuda"
    autocast = (
        torch.autocast(device_type="cuda", dtype=torch.float16)
        if amp_enabled
        else nullcontext()
    )
    if not mc_samples:
        model.eval()
        with torch.no_grad(), autocast:
            return (model(inputs).float(),)

    enable_mc_dropout(model)
    predictions = []
    with torch.no_grad():
        for _ in range(mc_samples):
            pass_context = (
                torch.autocast(device_type="cuda", dtype=torch.float16)
                if amp_enabled
                else nullcontext()
            )
            with pass_context:
                predictions.append(model(inputs).float())
    samples = torch.stack(predictions)
    mean = samples.mean(0)
    std = samples.std(0, unbiased=False)
    quantile = NormalDist().inv_cdf(1 - interval_alpha / 2)
    return mean, std, mean - quantile * std, mean + quantile * std


def _scaled_transform(
    transform: tuple[float, ...],
    source_width: int,
    source_height: int,
    output_width: int,
    output_height: int,
) -> tuple[float, ...]:
    """Preserve raster bounds when prediction resolution differs from input."""
    column_scale = source_width / output_width
    row_scale = source_height / output_height
    return (
        transform[0],
        transform[1] * column_scale,
        transform[2] * row_scale,
        transform[3],
        transform[4] * column_scale,
        transform[5] * row_scale,
    )


def write_prediction(
    record: TileRecord,
    arrays: Sequence[np.ndarray],
    descriptions: Sequence[str],
    output: Path,
    *,
    force: bool,
) -> None:
    """Write one or more prediction bands on a source tile's footprint.

    Parameters
    ----------
    record : TileRecord
        Source tile supplying CRS and bounds.
    arrays, descriptions : sequence
        Parallel float arrays and GDAL band descriptions.
    output : pathlib.Path
        Destination GeoTIFF.
    force : bool
        Permit replacing an existing output.

    Raises
    ------
    FileExistsError
        If ``output`` exists and force is false.
    ValueError
        If arrays are empty, non-2D, differently shaped, or descriptions do
        not align.
    RuntimeError, OSError
        If GDAL cannot read metadata or create/write the GeoTIFF.
    """
    if output.exists() and not force:
        raise FileExistsError(f"prediction exists; use --force to replace: {output}")
    if not arrays or len(arrays) != len(descriptions):
        raise ValueError("prediction arrays and descriptions must be non-empty and parallel")
    shape = arrays[0].shape
    if len(shape) != 2 or any(array.shape != shape for array in arrays):
        raise ValueError("all prediction bands must share one two-dimensional shape")

    source = gdal.Open(str(record.path))
    if source is None:
        raise RuntimeError(f"could not open source tile: {record.path}")
    try:
        transform = tuple(source.GetGeoTransform())
        projection = source.GetProjection()
        source_width, source_height = source.RasterXSize, source.RasterYSize
    finally:
        source = None
    if not projection:
        raise ValueError(f"source tile has no CRS: {record.path}")

    output.parent.mkdir(parents=True, exist_ok=True)
    height, width = shape
    driver = gdal.GetDriverByName("GTiff")
    dataset = driver.Create(
        str(output),
        width,
        height,
        len(arrays),
        gdal.GDT_Float32,
        options=("TILED=YES", "COMPRESS=DEFLATE", "PREDICTOR=3", "BIGTIFF=IF_SAFER"),
    )
    if dataset is None:
        raise RuntimeError(f"could not create prediction raster: {output}")
    try:
        dataset.SetGeoTransform(
            _scaled_transform(
                transform, source_width, source_height, width, height
            )
        )
        dataset.SetProjection(projection)
        for number, (array, description) in enumerate(
            zip(arrays, descriptions), start=1
        ):
            band = dataset.GetRasterBand(number)
            band.SetDescription(description)
            band.SetNoDataValue(float("nan"))
            band.WriteArray(array.astype(np.float32, copy=False))
        dataset.FlushCache()
    finally:
        dataset = None


def build_mosaic(tiles: Sequence[Path], output: Path, *, force: bool) -> None:
    """Mosaic georeferenced prediction tiles into a compressed GeoTIFF.

    Raises
    ------
    FileExistsError
        If the mosaic exists and force is false.
    ValueError
        If no tiles are supplied.
    RuntimeError
        If GDAL cannot build or translate the virtual mosaic.
    """
    if not tiles:
        raise ValueError("cannot build a mosaic without prediction tiles")
    if output.exists() and not force:
        raise FileExistsError(f"mosaic exists; use --force to replace: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    virtual_path = f"/vsimem/somospie_sm_{os.getpid()}.vrt"
    try:
        virtual = gdal.BuildVRT(virtual_path, [str(path) for path in tiles])
        if virtual is None:
            raise RuntimeError("GDAL could not build the prediction mosaic VRT")
        translated = gdal.Translate(
            str(output),
            virtual,
            creationOptions=(
                "TILED=YES",
                "COMPRESS=DEFLATE",
                "PREDICTOR=3",
                "BIGTIFF=IF_SAFER",
            ),
        )
        virtual = None
        if translated is None:
            raise RuntimeError(f"GDAL could not write prediction mosaic: {output}")
        translated = None
    finally:
        try:
            gdal.Unlink(virtual_path)
        except RuntimeError:
            pass


def write_summary(rows: Sequence[dict[str, Any]], path: Path, *, force: bool) -> None:
    """Atomically write per-tile prediction metadata as CSV.

    Raises
    ------
    FileExistsError
        If the summary exists and force is false.
    ValueError
        If no rows are supplied.
    csv.Error, OSError
        If CSV serialization or atomic publication fails.
    """
    if not rows:
        raise ValueError("cannot write an empty inference summary")
    if path.exists() and not force:
        raise FileExistsError(f"summary exists; use --force to replace: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _splits(value: str) -> tuple[str, ...]:
    """Parse a non-empty comma-separated inference split list."""
    result = tuple(item.strip() for item in value.split(",") if item.strip())
    if not result:
        raise argparse.ArgumentTypeError("split list must not be empty")
    return result


def _safe_region(value: str) -> str:
    """Convert a manifest region to a conservative output directory name."""
    cleaned = "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in value
    )
    return cleaned.strip("_") or "unassigned"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse and validate inference command-line arguments.

    Raises
    ------
    SystemExit
        Raised by ``argparse`` for invalid options or ``--help``.
    """
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    terrain = parser.add_mutually_exclusive_group()
    terrain.add_argument("--aligned-terrain", type=Path)
    terrain.add_argument("--aligned-terrain-map", type=Path)
    parser.add_argument(
        "--splits",
        type=_splits,
        default=("train", "holdout", "unlabeled"),
        help="manifest splits to predict, comma-separated",
    )
    parser.add_argument("--max-records", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--device")
    parser.add_argument("--amp", action="store_true")
    parser.add_argument("--mc-samples", type=int, default=0)
    parser.add_argument("--interval-alpha", type=float, default=0.1)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--mosaic", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    if args.max_records < 0 or args.mc_samples < 0:
        parser.error("--max-records and --mc-samples cannot be negative")
    if not 0 < args.interval_alpha < 1:
        parser.error("--interval-alpha must be in (0, 1)")
    return args


def main(argv: Sequence[str] | None = None) -> None:
    """Restore a checkpoint and write dense predictions for selected tiles.

    Parameters
    ----------
    argv : sequence of str or None, optional
        Explicit command-line arguments; ``None`` reads process arguments.

    Returns
    -------
    None
        Prediction GeoTIFFs, a summary CSV, and an optional mosaic are written.

    Raises
    ------
    FileNotFoundError, FileExistsError, ValueError
        If inputs, artifact contracts, selections, or output policies fail.
    ModuleNotFoundError
        If runtime neural/geospatial dependencies are unavailable.
    RuntimeError, OSError
        If model execution or GDAL/CSV output fails.
    """
    args = parse_args(argv)
    device = torch.device(args.device or ("cuda" if torch.cuda.is_available() else "cpu"))
    checkpoint, config = load_checkpoint(args.checkpoint, device)
    stats = stats_from_checkpoint(checkpoint["normalization_stats"])
    records = select_records(
        load_manifest(args.manifest),
        args.splits,
        require_targets=False,
        max_records=args.max_records,
    )
    terrain = TerrainResolver(
        stats.terrain_channels,
        shared=args.aligned_terrain,
        mapping=load_terrain_map(args.aligned_terrain_map),
    )
    dataset = PreparedTileDataset(records, stats, terrain, config.tile_size)
    loader = make_loader(
        dataset,
        args.batch_size,
        args.workers,
        shuffle=False,
        device=device,
    )
    model = PrithviSoilMoisture(config, pretrained=False).to(device)
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model.eval()

    descriptions = (
        ("soil_moisture",)
        if not args.mc_samples
        else (
            "soil_moisture_mean",
            "soil_moisture_std",
            "soil_moisture_lower",
            "soil_moisture_upper",
        )
    )
    outputs: list[Path] = []
    summary: list[dict[str, Any]] = []
    for inputs, _, indices in loader:
        inputs = inputs.to(device, non_blocking=True)
        predictions = predict_batch(
            model,
            inputs,
            amp=args.amp,
            mc_samples=args.mc_samples,
            interval_alpha=args.interval_alpha,
        )
        arrays = [prediction.cpu().numpy() for prediction in predictions]
        for batch_index, record_index in enumerate(indices.tolist()):
            record = records[record_index]
            output = (
                args.output_dir
                / _safe_region(record.region)
                / f"{record.path.stem}_soil_moisture.tif"
            )
            tile_arrays = [array[batch_index] for array in arrays]
            write_prediction(
                record,
                tile_arrays,
                descriptions,
                output,
                force=args.force,
            )
            mean = float(np.nanmean(tile_arrays[0]))
            row = {
                "tile": str(record.path),
                "region": record.region,
                "split": record.split,
                "target": "" if record.target is None else record.target,
                "prediction_mean": mean,
                "error": (
                    "" if record.target is None else mean - record.target
                ),
                "prediction_path": str(output.resolve()),
            }
            if args.mc_samples:
                row["prediction_std_mean"] = float(np.nanmean(tile_arrays[1]))
            outputs.append(output)
            summary.append(row)
            print(f"Predicted {record.path} -> {output}", flush=True)

    summary_path = args.summary or (args.output_dir / "predictions.csv")
    write_summary(summary, summary_path, force=args.force)
    if args.mosaic is not None:
        build_mosaic(outputs, args.mosaic, force=args.force)
    print(f"Wrote {len(outputs)} prediction tile(s) and {summary_path}")


if __name__ == "__main__":
    main()
