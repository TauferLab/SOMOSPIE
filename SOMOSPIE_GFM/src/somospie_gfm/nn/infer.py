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
import tempfile
from contextlib import nullcontext
from pathlib import Path
from statistics import NormalDist
from typing import Any, Sequence

import numpy as np
import torch
import torch.nn as nn
from osgeo import gdal

from somospie_gfm.postprocessing import feather_weights, window_starts

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
    """Enable dropout/drop-path while leaving normalization layers in eval mode.

    Parameters
    ----------
    model : torch.nn.Module
        Inference model whose stochastic layers are enabled in place.

    Returns
    -------
    None
        Module training flags are mutated as a side effect.
    """
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
    """Scale a geotransform while preserving the source raster bounds.

    Parameters
    ----------
    transform : tuple of float
        Six-element source GDAL affine geotransform.
    source_width, source_height : int
        Source raster dimensions in pixels.
    output_width, output_height : int
        Prediction raster dimensions in pixels.

    Returns
    -------
    tuple of float
        Six-element affine transform for the prediction grid.
    """
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

    Returns
    -------
    None
        The georeferenced prediction GeoTIFF is written as a side effect.

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


def run_overlapping_inference(
    model: PrithviSoilMoisture,
    records: Sequence[TileRecord],
    stats,
    terrain: TerrainResolver,
    band_indices: Sequence[int],
    device: torch.device,
    output: Path,
    descriptions: Sequence[str],
    *,
    tile_size: int,
    stride: int,
    batch_size: int,
    amp: bool,
    mc_samples: int,
    interval_alpha: float,
    force: bool,
) -> list[dict[str, Any]]:
    """Predict overlapping windows and Hann-blend them into one raw mosaic.

    Prepared HLS tiles are first exposed as a virtual mosaic. The model then
    sees windows crossing the old tile boundaries, and overlapping predictions
    are feathered together. This removes the independent-context discontinuity
    that direct first-wins mosaicking leaves at every tile edge.

    Parameters
    ----------
    model : PrithviSoilMoisture
        Restored model on ``device``.
    records : sequence of TileRecord
        Inference-manifest records defining HLS coverage and summary rows.
    stats
        Validated normalization statistics from the checkpoint.
    terrain : TerrainResolver
        Resolver for the already-aligned terrain mosaic.
    band_indices : sequence of int
        Zero-based HLS bands read from the prepared-tile VRT.
    device : torch.device
        Inference device.
    output : pathlib.Path
        Raw seam-blended GeoTIFF destination.
    descriptions : sequence of str
        Output-band descriptions from deterministic or MC inference.
    tile_size, stride, batch_size : int
        Model window size, overlap step, and windows per forward pass.
    amp, mc_samples, interval_alpha
        Forwarded to :func:`predict_batch`.
    force : bool
        Replace ``output`` when it exists.

    Returns
    -------
    list of dict
        One prediction-summary record per original manifest tile.

    Raises
    ------
    FileExistsError
        If ``output`` exists and ``force`` is false.
    ValueError
        If grids, channels, window settings, or model outputs are incompatible.
    RuntimeError
        If GDAL cannot build/read the mosaic or model inference fails.
    OSError
        If temporary/output files or atomic publication fail.
    """
    if output.exists() and not force:
        raise FileExistsError(f"raw prediction exists; use --force to replace: {output}")
    if not records:
        raise ValueError("overlapping inference requires at least one record")
    if not 0 < stride < tile_size:
        raise ValueError("overlapping inference stride must be between 1 and tile_size - 1")
    if batch_size <= 0:
        raise ValueError("inference batch size must be positive")

    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, vrt_name = tempfile.mkstemp(
        prefix="somospie_inference_",
        suffix=".vrt",
        dir=output.parent,
    )
    os.close(descriptor)
    vrt_path = Path(vrt_name)
    vrt_path.unlink()
    hls = terrain_dataset = None
    try:
        vrt = gdal.BuildVRT(str(vrt_path), [str(record.path) for record in records])
        if vrt is None:
            raise RuntimeError("GDAL could not build the HLS inference mosaic")
        transform = tuple(vrt.GetGeoTransform())
        projection = vrt.GetProjection()
        width, height, source_bands = (
            vrt.RasterXSize,
            vrt.RasterYSize,
            vrt.RasterCount,
        )
        nodata = [
            vrt.GetRasterBand(index).GetNoDataValue()
            for index in range(1, source_bands + 1)
        ]
        vrt.FlushCache()
        vrt = None
        if not projection:
            raise ValueError("HLS inference mosaic has no CRS")

        aligned = terrain.resolve(records[0])
        resolved_paths = {
            resolved.path
            for record in records
            if (resolved := terrain.resolve(record)) is not None
        }
        if len(resolved_paths) > 1:
            raise ValueError(
                "overlapping inference currently requires one aligned terrain mosaic"
            )
        hls = gdal.Open(str(vrt_path))
        if hls is None:
            raise RuntimeError("could not reopen the HLS inference mosaic")
        terrain_x_base = terrain_y_base = 0
        if aligned is not None:
            terrain_dataset = gdal.Open(str(aligned.path))
            if terrain_dataset is None:
                raise RuntimeError(f"could not open aligned terrain: {aligned.path}")
            tolerance = max(abs(transform[1]), abs(transform[5])) * 1e-6
            terrain_transform = tuple(terrain_dataset.GetGeoTransform())
            matching = (
                terrain_dataset.GetProjection() == projection
                and np.allclose(
                    terrain_transform[1:3], transform[1:3], rtol=0.0, atol=tolerance
                )
                and np.allclose(
                    terrain_transform[4:6], transform[4:6], rtol=0.0, atol=tolerance
                )
            )
            if not matching:
                raise ValueError("HLS and aligned terrain mosaics use different grids")
            terrain_x_position = (transform[0] - terrain_transform[0]) / transform[1]
            terrain_y_position = (transform[3] - terrain_transform[3]) / transform[5]
            terrain_x_base, terrain_y_base = (
                round(terrain_x_position),
                round(terrain_y_position),
            )
            aligned_origin = np.isclose(
                terrain_x_position, terrain_x_base, rtol=0.0, atol=1e-6
            ) and np.isclose(
                terrain_y_position, terrain_y_base, rtol=0.0, atol=1e-6
            )
            covered = (
                terrain_x_base >= 0
                and terrain_y_base >= 0
                and terrain_x_base + width <= terrain_dataset.RasterXSize
                and terrain_y_base + height <= terrain_dataset.RasterYSize
            )
            if not aligned_origin or not covered:
                raise ValueError(
                    "HLS inference extent is not aligned within the terrain mosaic"
                )

        y_starts = window_starts(height, tile_size, stride)
        x_starts = window_starts(width, tile_size, stride)
        total_windows = len(y_starts) * len(x_starts)
        print(
            f"Overlapping inference: {total_windows} windows "
            f"({len(y_starts)} rows x {len(x_starts)} columns), "
            f"stride={stride}",
            flush=True,
        )
        base_weights = feather_weights(tile_size, tile_size)
        weighted_sums = [
            np.zeros((height, width), dtype=np.float32)
            for _ in descriptions
        ]
        weight_sum = np.zeros((height, width), dtype=np.float32)
        batch_inputs: list[np.ndarray] = []
        batch_windows: list[tuple[int, int, int, int, np.ndarray]] = []
        processed = 0

        def flush_batch() -> None:
            """Infer and accumulate the queued normalized overlap windows.

            Returns
            -------
            None
                Weighted prediction and coverage arrays are updated in place,
                progress is reported, and both queues are cleared.

            Raises
            ------
            ValueError
                If model output dimensions differ from ``tile_size``.
            RuntimeError
                If PyTorch cannot execute or transfer the queued batch.
            """
            nonlocal processed
            if not batch_inputs:
                return
            tensor = torch.from_numpy(np.stack(batch_inputs)).unsqueeze(2).to(
                device,
                non_blocking=True,
            )
            predictions = predict_batch(
                model,
                tensor,
                amp=amp,
                mc_samples=mc_samples,
                interval_alpha=interval_alpha,
            )
            arrays = [prediction.cpu().numpy() for prediction in predictions]
            for batch_index, (yoff, xoff, read_h, read_w, valid) in enumerate(
                batch_windows
            ):
                expected = (tile_size, tile_size)
                if any(array[batch_index].shape != expected for array in arrays):
                    shapes = [array[batch_index].shape for array in arrays]
                    raise ValueError(
                        f"overlap blending requires {expected} model output; got {shapes}"
                    )
                weights = base_weights[:read_h, :read_w] * valid
                target = np.s_[yoff : yoff + read_h, xoff : xoff + read_w]
                for destination, array in zip(weighted_sums, arrays):
                    destination[target] += array[batch_index, :read_h, :read_w] * weights
                weight_sum[target] += weights
            processed += len(batch_inputs)
            if processed % 200 < len(batch_inputs) or processed == total_windows:
                print(f"  {processed}/{total_windows} windows processed", flush=True)
            batch_inputs.clear()
            batch_windows.clear()

        for yoff in y_starts:
            for xoff in x_starts:
                read_h = min(tile_size, height - yoff)
                read_w = min(tile_size, width - xoff)
                raw = hls.ReadAsArray(xoff, yoff, read_w, read_h)
                if raw is None:
                    raise RuntimeError(
                        f"could not read HLS window at x={xoff}, y={yoff}"
                    )
                if raw.ndim == 2:
                    raw = raw[np.newaxis]
                raw = raw.astype(np.float32, copy=False)
                for index, value in enumerate(nodata):
                    if value is not None:
                        raw[index][raw[index] == value] = np.nan
                hls_data = raw[list(band_indices)]
                valid = np.any(np.isfinite(hls_data), axis=0)
                if not valid.any():
                    processed += 1
                    if processed % 200 == 0 or processed == total_windows:
                        print(f"  {processed}/{total_windows} windows processed", flush=True)
                    continue
                hls_data = np.where(
                    np.isfinite(hls_data),
                    hls_data,
                    stats.mean[: len(band_indices), None, None],
                )
                pieces = [hls_data]
                if terrain_dataset is not None:
                    terrain_data = terrain_dataset.ReadAsArray(
                        terrain_x_base + xoff,
                        terrain_y_base + yoff,
                        read_w,
                        read_h,
                    )
                    if terrain_data is None:
                        raise RuntimeError(
                            f"could not read terrain window at x={xoff}, y={yoff}"
                        )
                    if terrain_data.ndim == 2:
                        terrain_data = terrain_data[np.newaxis]
                    terrain_data = terrain_data.astype(np.float32, copy=False)
                    if aligned.nodata is not None:
                        terrain_data[terrain_data == aligned.nodata] = np.nan
                    terrain_mean = stats.mean[len(band_indices) :, None, None]
                    terrain_data = np.where(
                        np.isfinite(terrain_data), terrain_data, terrain_mean
                    )
                    pieces.append(terrain_data)
                data = np.concatenate(pieces)
                if data.shape[0] != len(stats.channel_names):
                    raise ValueError(
                        f"overlap window has {data.shape[0]} channels; "
                        f"statistics require {len(stats.channel_names)}"
                    )
                normalized = (
                    data - stats.mean[:, None, None]
                ) / stats.std[:, None, None]
                normalized[~np.isfinite(normalized)] = 0
                if read_h < tile_size or read_w < tile_size:
                    padded = np.zeros(
                        (normalized.shape[0], tile_size, tile_size),
                        dtype=np.float32,
                    )
                    padded[:, :read_h, :read_w] = normalized
                    normalized = padded
                batch_inputs.append(normalized.astype(np.float32, copy=False))
                batch_windows.append((yoff, xoff, read_h, read_w, valid))
                if len(batch_inputs) >= batch_size:
                    flush_batch()
        flush_batch()

        temporary = output.with_name(f".{output.stem}.{os.getpid()}.tmp.tif")
        temporary.unlink(missing_ok=True)
        driver = gdal.GetDriverByName("GTiff")
        destination = driver.Create(
            str(temporary),
            width,
            height,
            len(descriptions),
            gdal.GDT_Float32,
            options=(
                "TILED=YES",
                "COMPRESS=ZSTD",
                "ZSTD_LEVEL=1",
                "PREDICTOR=3",
                "BIGTIFF=IF_SAFER",
                "NUM_THREADS=ALL_CPUS",
            ),
        )
        if destination is None:
            raise RuntimeError(f"could not create blended prediction: {temporary}")
        destination.SetGeoTransform(transform)
        destination.SetProjection(projection)
        first_prediction = None
        try:
            for index, (values, description) in enumerate(
                zip(weighted_sums, descriptions),
                start=1,
            ):
                blended = np.divide(
                    values,
                    weight_sum,
                    out=np.full_like(values, np.nan),
                    where=weight_sum > 1e-8,
                )
                if first_prediction is None:
                    first_prediction = blended
                band = destination.GetRasterBand(index)
                band.SetDescription(description)
                band.SetNoDataValue(float("nan"))
                band.WriteArray(blended)
            destination.FlushCache()
            destination = None
            os.replace(temporary, output)
        except Exception:
            destination = None
            temporary.unlink(missing_ok=True)
            raise
        if first_prediction is None:
            raise RuntimeError("overlapping inference produced no output bands")

        summary: list[dict[str, Any]] = []
        for record in records:
            source = gdal.Open(str(record.path))
            if source is None:
                raise RuntimeError(f"could not reopen source tile: {record.path}")
            try:
                tile_transform = source.GetGeoTransform()
                tile_width, tile_height = source.RasterXSize, source.RasterYSize
            finally:
                source = None
            xoff = round((tile_transform[0] - transform[0]) / transform[1])
            yoff = round((tile_transform[3] - transform[3]) / transform[5])
            tile_values = first_prediction[
                max(0, yoff) : min(height, yoff + tile_height),
                max(0, xoff) : min(width, xoff + tile_width),
            ]
            finite_tile_values = tile_values[np.isfinite(tile_values)]
            prediction_mean = (
                float(finite_tile_values.mean())
                if finite_tile_values.size
                else float("nan")
            )
            summary.append(
                {
                    "tile": str(record.path),
                    "region": record.region,
                    "split": record.split,
                    "target": "" if record.target is None else record.target,
                    "prediction_mean": prediction_mean,
                    "error": "" if record.target is None else prediction_mean - record.target,
                    "prediction_path": str(output.resolve()),
                }
            )
        print(f"Wrote seam-blended raw prediction: {output}", flush=True)
        return summary
    finally:
        hls = None
        terrain_dataset = None
        vrt_path.unlink(missing_ok=True)


def build_mosaic(tiles: Sequence[Path], output: Path, *, force: bool) -> None:
    """Mosaic georeferenced predictions into a VRT or compressed GeoTIFF.

    Parameters
    ----------
    tiles : sequence of pathlib.Path
        Georeferenced prediction rasters in mosaic priority order.
    output : pathlib.Path
        VRT or GeoTIFF destination inferred from its suffix.
    force : bool
        Permit replacement of an existing mosaic.

    Returns
    -------
    None
        The mosaic is built and published as a side effect.

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
    if output.suffix.lower() == ".vrt":
        temporary = output.with_name(f".{output.stem}.{os.getpid()}.tmp.vrt")
        temporary.unlink(missing_ok=True)
        try:
            virtual = gdal.BuildVRT(str(temporary), [str(path) for path in tiles])
            if virtual is None:
                raise RuntimeError("GDAL could not build the prediction mosaic VRT")
            virtual.FlushCache()
            virtual = None
            os.replace(temporary, output)
        except Exception:
            virtual = None
            temporary.unlink(missing_ok=True)
            raise
        return

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

    Parameters
    ----------
    rows : sequence of dict
        Non-empty, schema-consistent prediction records.
    path : pathlib.Path
        CSV destination.
    force : bool
        Permit replacement of an existing summary.

    Returns
    -------
    None
        The CSV is atomically published as a side effect.

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
    """Parse a non-empty comma-separated inference split list.

    Parameters
    ----------
    value : str
        Raw command-line value such as ``"test,inference"``.

    Returns
    -------
    tuple of str
        Trimmed, non-empty split labels in their supplied order.

    Raises
    ------
    argparse.ArgumentTypeError
        If the value contains no usable split label.
    """
    result = tuple(item.strip() for item in value.split(",") if item.strip())
    if not result:
        raise argparse.ArgumentTypeError("split list must not be empty")
    return result


def _safe_region(value: str) -> str:
    """Convert a manifest region to a conservative directory name.

    Parameters
    ----------
    value : str
        Free-form ecoregion label stored in the training manifest.

    Returns
    -------
    str
        Filesystem-safe label containing only alphanumerics, hyphens, and
        underscores; ``"unassigned"`` is returned when nothing remains.
    """
    cleaned = "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in value
    )
    return cleaned.strip("_") or "unassigned"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse and validate inference command-line arguments.

    Parameters
    ----------
    argv : sequence of str or None, optional
        Explicit arguments; ``None`` reads process arguments.

    Returns
    -------
    argparse.Namespace
        Validated checkpoint, data, overlap, uncertainty, and output settings.

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
    parser.add_argument(
        "--stride",
        type=int,
        help="sliding-window stride; values below tile size enable Hann blending",
    )
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
    if args.stride is not None and args.stride <= 0:
        parser.error("--stride must be positive")
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
    if args.stride is not None and args.stride < config.tile_size:
        if args.mosaic is None:
            raise ValueError("overlapping inference requires --mosaic")
        summary = run_overlapping_inference(
            model,
            records,
            stats,
            terrain,
            dataset.band_indices,
            device,
            args.mosaic,
            descriptions,
            tile_size=config.tile_size,
            stride=args.stride,
            batch_size=args.batch_size,
            amp=args.amp,
            mc_samples=args.mc_samples,
            interval_alpha=args.interval_alpha,
            force=args.force,
        )
        summary_path = args.summary or (args.output_dir / "predictions.csv")
        write_summary(summary, summary_path, force=args.force)
        print(f"Wrote {len(summary)} summary row(s) and {summary_path}")
        return
    if args.stride is not None:
        print(
            f"[warn] stride {args.stride} is not below tile size "
            f"{config.tile_size}; using non-overlapping inference",
            flush=True,
        )
    loader = make_loader(
        dataset,
        args.batch_size,
        args.workers,
        shuffle=False,
        device=device,
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
                / record.path.parent.name
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
