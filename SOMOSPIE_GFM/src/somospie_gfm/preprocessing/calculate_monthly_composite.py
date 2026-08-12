"""Build per-tile median composites from downloaded HLS granules.

The compositor scans a raw HLS download tree, groups scenes by MGRS tile,
applies the matching Fmask QA raster, and calculates blockwise per-pixel
medians. Outputs contain only the named bands used by the model:
B02, B03, B04, B8A, B11, and B12.

Band files must be single-band GeoTIFFs ending in .BXX.tif (B08A and B8A are
both accepted). Scenes belonging to one tile are expected to use the same
grid and projection.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import re
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np

warnings.filterwarnings(
    "ignore",
    message="Neither gdal.UseExceptions\\(\\) nor gdal.DontUseExceptions\\(\\).*",
    category=FutureWarning,
)
from osgeo import gdal, gdal_array

gdal.UseExceptions()

BANDS_UNION = (
    "B01",
    "B02",
    "B03",
    "B04",
    "B05",
    "B06",
    "B07",
    "B08",
    "B8A",
    "B09",
    "B10",
    "B11",
    "B12",
)
DEFAULT_BANDS = ("B02", "B03", "B04", "B8A", "B11", "B12")
DEFAULT_FMASK_INVALID_BITS = (0, 1, 2, 3, 4)

TILE_RE = re.compile(r"(T\d{2}[A-Z]{3})", re.IGNORECASE)
DATE_RE = re.compile(r"\.(\d{7})")
BAND_RE = re.compile(
    r"\.(B(?:0[1-9]|1[0-2]|08A|8A))\.tiff?$",
    re.IGNORECASE,
)


def _nanmedian(stack: np.ndarray) -> np.ndarray:
    """Return the per-pixel median, suppressing expected all-NaN warnings."""
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="All-NaN slice encountered",
            category=RuntimeWarning,
        )
        return np.nanmedian(stack, axis=0)


def parse_date_from_name(path: Path) -> dt.date | None:
    """Extract an HLS yyyyddd acquisition date from a filename."""
    match = DATE_RE.search(path.name)
    if not match:
        return None
    value = match.group(1)
    try:
        year, day = int(value[:4]), int(value[4:])
        result = dt.date(year, 1, 1) + dt.timedelta(days=day - 1)
    except (OverflowError, ValueError):
        return None
    return result if day > 0 and result.year == year else None


def band_from_name(path: Path) -> str | None:
    """Return the canonical HLS band name represented by path."""
    match = BAND_RE.search(path.name)
    if not match:
        return None
    band = match.group(1).upper()
    return "B8A" if band == "B08A" else band


def collect_files(
    root: Path,
    start: dt.date | None,
    end: dt.date | None,
    bands: tuple[str, ...] = DEFAULT_BANDS,
) -> dict[str, dict[str, list[Path]]]:
    """Collect requested HLS band files as tile -> band -> paths."""
    requested = set(bands)
    mapping: dict[str, dict[str, list[Path]]] = {}
    candidates = (
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".tif", ".tiff"}
    )

    for path in sorted(candidates):
        band = band_from_name(path)
        tile_match = TILE_RE.search(path.name)
        if band not in requested or tile_match is None:
            continue

        if start is not None or end is not None:
            acquired = parse_date_from_name(path)
            if acquired is None:
                continue
            if start is not None and acquired < start:
                continue
            if end is not None and acquired > end:
                continue

        tile = tile_match.group(1).upper()
        mapping.setdefault(tile, {}).setdefault(band, []).append(path)
    return mapping


def block_windows(ds: gdal.Dataset) -> list[tuple[int, int, int, int]]:
    """Split a dataset into native block windows clipped at its edges."""
    block_x, block_y = ds.GetRasterBand(1).GetBlockSize()
    if not block_x or not block_y:
        block_x, block_y = ds.RasterXSize, ds.RasterYSize

    return [
        (
            x,
            y,
            min(block_x, ds.RasterXSize - x),
            min(block_y, ds.RasterYSize - y),
        )
        for y in range(0, ds.RasterYSize, block_y)
        for x in range(0, ds.RasterXSize, block_x)
    ]


def open_dataset(path: Path, label: str = "dataset") -> gdal.Dataset | None:
    """Open a raster, warning and returning None when it is unreadable."""
    try:
        dataset = gdal.Open(str(path))
    except RuntimeError as exc:
        print(f"[warn] Skipping unreadable {label}: {path} ({exc})", flush=True)
        return None
    if dataset is None:
        print(f"[warn] Skipping unreadable {label}: {path}", flush=True)
    return dataset


def infer_nodata(path: Path) -> float:
    """Infer an output nodata value from a sample granule."""
    dataset = open_dataset(path)
    if dataset is None:
        raise RuntimeError(f"Could not open {path}")
    try:
        band = dataset.GetRasterBand(1)
        nodata = band.GetNoDataValue()
        if nodata is not None:
            return float(nodata)
        np_type = gdal_array.GDALTypeCodeToNumericTypeCode(band.DataType)
        if np_type is not None and np.issubdtype(np_type, np.floating):
            return np.nan
        return -9999.0
    finally:
        dataset = None


def fmask_for_band(path: Path) -> Path | None:
    """Return the Fmask raster accompanying a band file, if it exists."""
    candidate = path.with_name(BAND_RE.sub(f".Fmask{path.suffix}", path.name))
    return candidate if candidate != path and candidate.exists() else None


def fmask_clear_mask(
    fmask: np.ndarray,
    mode: str,
    valid_values: tuple[int, ...],
    invalid_bits: tuple[int, ...],
) -> np.ndarray:
    """Return True for pixels accepted by the selected Fmask policy."""
    if mode == "values":
        return np.isin(fmask, valid_values)

    values = fmask.astype(np.uint16, copy=False)
    clear = values != 255
    for bit in invalid_bits:
        clear &= (values & (1 << bit)) == 0
    return clear


def _same_grid(
    dataset: gdal.Dataset,
    width: int,
    height: int,
    geotransform: tuple[float, ...],
    projection: str,
) -> bool:
    """Check that a scene can be read on the reference tile grid."""
    return (
        dataset.RasterXSize == width
        and dataset.RasterYSize == height
        and dataset.GetGeoTransform() == geotransform
        and dataset.GetProjection() == projection
    )


def _read_window(
    dataset: gdal.Dataset,
    window: tuple[int, int, int, int],
    label: str,
    warned: set[str],
) -> np.ndarray | None:
    """Read one window, warning once per source when a read fails."""
    xoff, yoff, width, height = window
    source = dataset.GetDescription() or label
    try:
        array = dataset.GetRasterBand(1).ReadAsArray(xoff, yoff, width, height)
        if array is None or array.shape != (height, width):
            raise RuntimeError("ReadAsArray returned no data or an unexpected shape")
        return array
    except RuntimeError as exc:
        if source not in warned:
            warned.add(source)
            print(
                f"[warn] Skipping unreadable {label} window at x={xoff}, "
                f"y={yoff}; further failures for {source} are suppressed ({exc})",
                flush=True,
            )
        return None


def _as_float(array: np.ndarray, nodata: float | None) -> np.ndarray:
    """Convert a source window to float32 and replace invalid values with NaN."""
    result = array.astype(np.float32, copy=True)
    invalid = ~np.isfinite(result)
    if nodata is not None:
        invalid |= np.isnan(result) if np.isnan(nodata) else result == nodata
    result[invalid] = np.nan
    return result


def _find_reference(
    tile: str,
    bands_to_paths: dict[str, list[Path]],
) -> gdal.Dataset:
    """Open the first readable scene for a tile."""
    for paths in bands_to_paths.values():
        for path in paths:
            dataset = open_dataset(path, "reference scene")
            if dataset is not None:
                return dataset
    raise RuntimeError(f"Could not open any reference scenes for tile {tile}")


def compute_tile(
    tile: str,
    bands_to_paths: dict[str, list[Path]],
    out_dir: Path,
    nodata_default: float,
    use_fmask: bool,
    fmask_mode: str,
    clear_fmask_values: tuple[int, ...],
    invalid_fmask_bits: tuple[int, ...],
    fallback_to_raw: bool,
    output_bands: tuple[str, ...] = DEFAULT_BANDS,
) -> tuple[Path, list[dict[str, Any]]]:
    """Build one named, Fmask-filtered median composite."""
    if not any(bands_to_paths.values()):
        raise ValueError(f"No files for tile {tile}")

    reference = _find_reference(tile, bands_to_paths)
    geotransform = reference.GetGeoTransform()
    projection = reference.GetProjection()
    width, height = reference.RasterXSize, reference.RasterYSize
    windows = block_windows(reference)
    reference = None

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{tile}_HLS_median_composite.tif"
    temp_path = out_path.with_suffix(out_path.suffix + ".tmp")
    temp_path.unlink(missing_ok=True)

    driver = gdal.GetDriverByName("GTiff")
    if driver is None:
        raise RuntimeError("GDAL GTiff driver is unavailable")
    try:
        destination = driver.Create(
            str(temp_path),
            width,
            height,
            len(output_bands),
            gdal.GDT_Float32,
            options=[
                "TILED=YES",
                "COMPRESS=ZSTD",
                "ZSTD_LEVEL=9",
                "PREDICTOR=3",
                "BIGTIFF=IF_SAFER",
                "NUM_THREADS=ALL_CPUS",
            ],
        )
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    if destination is None:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(f"Could not create {temp_path}")
    destination.SetGeoTransform(geotransform)
    destination.SetProjection(projection)

    output_band = None
    stats: list[dict[str, Any]] = []
    warned_reads: set[str] = set()
    try:
        for band_index, band_name in enumerate(output_bands, start=1):
            output_band = destination.GetRasterBand(band_index)
            output_band.SetDescription(band_name)
            output_band.SetNoDataValue(nodata_default)

            entries: list[tuple[gdal.Dataset, gdal.Dataset | None]] = []
            for path in bands_to_paths.get(band_name, []):
                dataset = open_dataset(path, f"{band_name} scene")
                if dataset is None:
                    continue
                if not _same_grid(dataset, width, height, geotransform, projection):
                    print(f"[warn] Skipping off-grid {band_name} scene: {path}", flush=True)
                    dataset = None
                    continue

                fmask_dataset = None
                if use_fmask:
                    fmask_path = fmask_for_band(path)
                    if fmask_path is not None:
                        fmask_dataset = open_dataset(fmask_path, "Fmask scene")
                        if fmask_dataset is not None and not _same_grid(
                            fmask_dataset, width, height, geotransform, projection
                        ):
                            print(f"[warn] Ignoring off-grid Fmask scene: {fmask_path}", flush=True)
                            fmask_dataset = None
                entries.append((dataset, fmask_dataset))

            if not entries:
                output_band.Fill(nodata_default)

            fmask_scene_count = sum(mask is not None for _, mask in entries)
            for window in windows:
                xoff, yoff, block_width, block_height = window
                raw_arrays: list[np.ndarray] = []
                clear_arrays: list[np.ndarray] = []

                for dataset, fmask_dataset in entries:
                    source = _read_window(dataset, window, f"{tile} {band_name}", warned_reads)
                    if source is None:
                        continue
                    array = _as_float(
                        source,
                        dataset.GetRasterBand(1).GetNoDataValue(),
                    )
                    raw_arrays.append(array)

                    if use_fmask and fmask_dataset is not None:
                        fmask = _read_window(
                            fmask_dataset,
                            window,
                            f"{tile} {band_name} Fmask",
                            warned_reads,
                        )
                        clear_arrays.append(
                            array
                            if fmask is None
                            else np.where(
                                fmask_clear_mask(
                                    fmask,
                                    fmask_mode,
                                    clear_fmask_values,
                                    invalid_fmask_bits,
                                ),
                                array,
                                np.nan,
                            )
                        )
                    elif use_fmask:
                        clear_arrays.append(array)

                pixel_count = block_width * block_height
                fallback_count = 0
                raw_observation_count = 0
                clear_observation_count = 0

                if raw_arrays:
                    raw_stack = np.stack(raw_arrays)
                    raw_median = _nanmedian(raw_stack)
                    raw_observation_count = int(np.isfinite(raw_stack).sum())

                    if use_fmask:
                        clear_stack = np.stack(clear_arrays)
                        clear_median = _nanmedian(clear_stack)
                        clear_observation_count = int(np.isfinite(clear_stack).sum())
                        if fallback_to_raw:
                            fallback = ~np.isfinite(clear_median) & np.isfinite(raw_median)
                            fallback_count = int(fallback.sum())
                            composite = np.where(
                                np.isfinite(clear_median),
                                clear_median,
                                raw_median,
                            )
                        else:
                            composite = clear_median
                    else:
                        composite = raw_median
                        clear_observation_count = raw_observation_count

                    composite = np.where(
                        np.isfinite(composite),
                        composite,
                        nodata_default,
                    ).astype(np.float32)
                    output_band.WriteArray(composite, xoff, yoff)
                elif entries:
                    output_band.WriteArray(
                        np.full(
                            (block_height, block_width),
                            nodata_default,
                            dtype=np.float32,
                        ),
                        xoff,
                        yoff,
                    )

                stats.append(
                    {
                        "tile": tile,
                        "band": band_name,
                        "window_x": xoff,
                        "window_y": yoff,
                        "scene_count": len(entries),
                        "fmask_scene_count": fmask_scene_count,
                        "raw_observation_count": raw_observation_count,
                        "clear_observation_count": clear_observation_count,
                        "pixel_count": pixel_count,
                        "fallback_pixel_count": fallback_count,
                    }
                )

            entries.clear()
            dataset = fmask_dataset = None

        destination.FlushCache()
        output_band = None
        destination = None
        os.replace(temp_path, out_path)
    except Exception:
        output_band = None
        destination = None
        temp_path.unlink(missing_ok=True)
        raise

    return out_path, stats


def _task(
    tile: str,
    bands: dict[str, list[Path]],
    out_dir: Path,
    nodata_default: float,
    use_fmask: bool,
    fmask_mode: str,
    clear_fmask_values: tuple[int, ...],
    invalid_fmask_bits: tuple[int, ...],
    fallback_to_raw: bool,
    output_bands: tuple[str, ...],
) -> tuple[Path, list[dict[str, Any]]]:
    """Warn about missing model bands, then composite one tile."""
    missing = [band for band in output_bands if band not in bands]
    if missing:
        print(f"[warn] {tile} missing bands {missing}; filling with nodata.", flush=True)
    return compute_tile(
        tile,
        bands,
        out_dir,
        nodata_default,
        use_fmask,
        fmask_mode,
        clear_fmask_values,
        invalid_fmask_bits,
        fallback_to_raw,
        output_bands,
    )


def _parse_int_list(value: str, label: str, maximum: int) -> tuple[int, ...]:
    """Parse and validate a comma-separated integer option."""
    try:
        values = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise SystemExit(f"{label} must be a comma-separated list of integers") from exc
    invalid = [item for item in values if not 0 <= item <= maximum]
    if invalid:
        raise SystemExit(f"{label} values must be between 0 and {maximum}: {invalid}")
    return values


def _summarize_diagnostics(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Roll per-window diagnostics up to one row per tile and band."""
    totals: dict[tuple[str, str], dict[str, Any]] = {}
    summed = (
        "raw_observation_count",
        "clear_observation_count",
        "pixel_count",
        "fallback_pixel_count",
    )
    for row in rows:
        key = (row["tile"], row["band"])
        total = totals.setdefault(
            key,
            {
                "tile": row["tile"],
                "band": row["band"],
                "scene_count": 0,
                "fmask_scene_count": 0,
                **{field: 0 for field in summed},
            },
        )
        total["scene_count"] = max(total["scene_count"], row["scene_count"])
        total["fmask_scene_count"] = max(
            total["fmask_scene_count"], row["fmask_scene_count"]
        )
        for field in summed:
            total[field] += row[field]

    result = []
    for total in totals.values():
        raw = total["raw_observation_count"]
        pixels = total["pixel_count"]
        total["clear_observation_fraction"] = (
            total["clear_observation_count"] / raw if raw else ""
        )
        total["fallback_pixel_fraction"] = (
            total["fallback_pixel_count"] / pixels if pixels else ""
        )
        result.append(total)
    return sorted(result, key=lambda row: (row["tile"], row["band"]))


def write_diagnostics(rows: list[dict[str, Any]], path: Path) -> None:
    """Write aggregated compositing diagnostics without external libraries."""
    summary = _summarize_diagnostics(rows)
    if not summary:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--input-root",
        type=Path,
        required=True,
        help="root directory containing downloaded HLS GeoTIFFs",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="directory for per-tile composites",
    )
    parser.add_argument("--start-date", help="inclusive start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="inclusive end date (YYYY-MM-DD)")
    parser.add_argument(
        "--bands",
        default=",".join(DEFAULT_BANDS),
        help=f"bands to retain, in order (default: {','.join(DEFAULT_BANDS)})",
    )
    parser.add_argument(
        "--nodata",
        type=float,
        default=None,
        help="output nodata value (default: inferred from the source)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=max(1, (os.cpu_count() or 1) // 4),
        help="number of tiles to process in parallel",
    )
    parser.add_argument(
        "--no-fmask",
        action="store_true",
        help="disable cloud, shadow, cirrus, and snow filtering",
    )
    parser.add_argument(
        "--fmask-mode",
        choices=("bitmask", "values"),
        default="bitmask",
        help="interpret Fmask as HLS v2 bits or legacy class values",
    )
    parser.add_argument(
        "--fmask-invalid-bits",
        default=",".join(map(str, DEFAULT_FMASK_INVALID_BITS)),
        help="Fmask bits considered invalid in bitmask mode",
    )
    parser.add_argument(
        "--fmask-valid-values",
        default="0,1",
        help="Fmask values considered clear in values mode",
    )
    parser.add_argument(
        "--no-fmask-fallback",
        action="store_true",
        help="leave cloud-only pixels as nodata instead of using the raw median",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Composite every MGRS tile found below the input root."""
    args = parse_args(argv)
    start = dt.date.fromisoformat(args.start_date) if args.start_date else None
    end = dt.date.fromisoformat(args.end_date) if args.end_date else None
    if start is not None and end is not None and start > end:
        raise SystemExit("--start-date must not be after --end-date")

    output_bands = tuple(
        "B8A" if band == "B08A" else band
        for band in (
            value.strip().upper()
            for value in args.bands.split(",")
            if value.strip()
        )
    )
    if not output_bands:
        raise SystemExit("--bands must contain at least one band")
    unknown = [band for band in output_bands if band not in BANDS_UNION]
    if unknown:
        raise SystemExit(f"unknown band(s) {unknown}; known bands are {BANDS_UNION}")
    if len(set(output_bands)) != len(output_bands):
        raise SystemExit("--bands must not contain duplicates")

    tile_map = collect_files(args.input_root, start, end, output_bands)
    if not tile_map:
        raise SystemExit(f"No requested HLS band files found under {args.input_root}")

    nodata_default = args.nodata
    if nodata_default is None:
        for tile_bands in tile_map.values():
            for paths in tile_bands.values():
                for path in paths:
                    try:
                        nodata_default = infer_nodata(path)
                        break
                    except RuntimeError:
                        continue
                if nodata_default is not None:
                    break
            if nodata_default is not None:
                break
    if nodata_default is None:
        nodata_default = -9999.0

    clear_values = _parse_int_list(
        args.fmask_valid_values,
        "--fmask-valid-values",
        255,
    )
    invalid_bits = _parse_int_list(
        args.fmask_invalid_bits,
        "--fmask-invalid-bits",
        7,
    )
    use_fmask = not args.no_fmask
    fallback_to_raw = not args.no_fmask_fallback
    workers = max(1, args.workers)
    tiles = sorted(tile_map.items())

    print(f"Found {len(tiles)} tile(s); retaining bands {list(output_bands)}")
    print(
        f"Fmask {'enabled' if use_fmask else 'disabled'} "
        f"(mode={args.fmask_mode}, fallback_to_raw={fallback_to_raw})"
    )

    diagnostics: list[dict[str, Any]] = []
    task_args = (
        args.output_dir,
        float(nodata_default),
        use_fmask,
        args.fmask_mode,
        clear_values,
        invalid_bits,
        fallback_to_raw,
        output_bands,
    )
    if workers == 1:
        for tile, bands in tiles:
            output, rows = _task(tile, bands, *task_args)
            diagnostics.extend(rows)
            print(f"[{tile}] wrote {output}")
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_task, tile, bands, *task_args): tile
                for tile, bands in tiles
            }
            for future in as_completed(futures):
                tile = futures[future]
                output, rows = future.result()
                diagnostics.extend(rows)
                print(f"[{tile}] wrote {output}")

    diagnostics_path = args.output_dir / "composite_diagnostics.csv"
    write_diagnostics(diagnostics, diagnostics_path)
    if diagnostics:
        print(f"Wrote composite diagnostics: {diagnostics_path}")


if __name__ == "__main__":
    main()
