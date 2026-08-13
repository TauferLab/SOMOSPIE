"""Build per-tile median composites from downloaded HLS granules.

The compositor scans a raw HLS download tree, groups scenes by MGRS tile,
applies the matching Fmask QA raster, and calculates blockwise per-pixel
medians. Outputs contain only the named bands used by the model:
B02, B03, B04, B8A, B11, and B12.

Band files must be single-band GeoTIFFs ending in .BXX.tif (B08A and B8A are
both accepted). Landsat bands B05, B06, and B07 are mapped to their
Sentinel-named spectral equivalents B8A, B11, and B12. Scenes belonging to one
tile must use the same pixel grid and an equivalent projection.
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
from osgeo import gdal, gdal_array, osr

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
L30_TO_MODEL_BAND = {
    "B02": "B02",
    "B03": "B03",
    "B04": "B04",
    "B05": "B8A",
    "B06": "B11",
    "B07": "B12",
}

TILE_RE = re.compile(r"(T\d{2}[A-Z]{3})", re.IGNORECASE)
DATE_RE = re.compile(r"\.(\d{7})")
BAND_RE = re.compile(
    r"\.(B(?:0[1-9]|1[0-2]|08A|8A))\.tiff?$",
    re.IGNORECASE,
)


def _nanmedian(stack: np.ndarray) -> np.ndarray:
    """Compute a temporal per-pixel median without noisy empty-pixel warnings.

    Parameters
    ----------
    stack : numpy.ndarray
        Scene stack whose first axis is reduced; invalid observations are NaN.

    Returns
    -------
    numpy.ndarray
        Median image, with NaN where every scene is invalid.

    Raises
    ------
    TypeError
        Propagated by NumPy for unsupported input dtypes.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="All-NaN slice encountered",
            category=RuntimeWarning,
        )
        return np.nanmedian(stack, axis=0)


def parse_date_from_name(path: Path) -> dt.date | None:
    """Parse the first HLS ``yyyyddd`` acquisition token in a filename.

    Parameters
    ----------
    path : pathlib.Path
        HLS band file whose basename may contain a Julian day token.

    Returns
    -------
    datetime.date or None
        Valid acquisition date, or ``None`` for absent/malformed tokens.

    Notes
    -----
    Parse errors are intentionally converted to ``None`` for discovery filters.
    """
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
    """Extract a canonical HLS spectral-band name from a GeoTIFF basename.

    Parameters
    ----------
    path : pathlib.Path
        Candidate file ending in ``.BXX.tif`` or ``.BXX.tiff``.

    Returns
    -------
    str or None
        Canonical band name, normalizing ``B08A`` to ``B8A``, or ``None``.
    """
    match = BAND_RE.search(path.name)
    if not match:
        return None
    band = match.group(1).upper()
    return "B8A" if band == "B08A" else band


def model_band_from_name(path: Path) -> str | None:
    """Return the model channel represented by an HLS source-band file.

    HLS uses sensor-native band identifiers even though its reflectance is
    harmonized. For Landsat L30, near-infrared and shortwave-infrared bands
    B05/B06/B07 therefore correspond to the model's Sentinel-style channel
    names B8A/B11/B12. Sentinel S30 and sensor-neutral filenames retain their
    canonical names.

    Parameters
    ----------
    path : pathlib.Path
        Candidate HLS single-band GeoTIFF.

    Returns
    -------
    str or None
        Model channel name, or ``None`` when the filename is not a recognized
        spectral band or an L30 band is not one of the six model inputs.
    """
    source_band = band_from_name(path)
    if source_band is None:
        return None
    if ".L30." in path.name.upper():
        return L30_TO_MODEL_BAND.get(source_band)
    return source_band


def collect_files(
    root: Path,
    start: dt.date | None,
    end: dt.date | None,
    bands: tuple[str, ...] = DEFAULT_BANDS,
) -> dict[str, dict[str, list[Path]]]:
    """Group requested HLS scenes by MGRS tile and spectral band.

    Parameters
    ----------
    root : pathlib.Path
        Raw HLS download tree searched recursively.
    start, end : datetime.date or None
        Inclusive acquisition-date limits. Files without parseable dates are
        excluded whenever either limit is active.
    bands : tuple of str, optional
        Canonical bands to retain.

    Returns
    -------
    dict
        Nested ``tile -> band -> sorted scene paths`` mapping.

    Raises
    ------
    OSError
        If recursive directory enumeration fails.
    """
    requested = set(bands)
    mapping: dict[str, dict[str, list[Path]]] = {}
    candidates = (
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".tif", ".tiff"}
    )

    for path in sorted(candidates):
        band = model_band_from_name(path)
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
    """Cover a raster with edge-clipped native storage blocks.

    Parameters
    ----------
    ds : osgeo.gdal.Dataset
        Reference raster defining dimensions and preferred block size.

    Returns
    -------
    list of tuple
        ``(x_offset, y_offset, width, height)`` windows covering every pixel.

    Raises
    ------
    RuntimeError
        Propagated if GDAL cannot read band/block metadata.
    """
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
    """Open a raster through a warning-based, nonfatal discovery boundary.

    Parameters
    ----------
    path : pathlib.Path
        Raster to open read-only.
    label : str, optional
        Human-readable role used in warning messages.

    Returns
    -------
    osgeo.gdal.Dataset or None
        Open dataset, or ``None`` after reporting an unreadable source.

    Notes
    -----
    GDAL open errors are deliberately caught so other scenes can still compose.
    """
    try:
        dataset = gdal.Open(str(path))
    except RuntimeError as exc:
        print(f"[warn] Skipping unreadable {label}: {path} ({exc})", flush=True)
        return None
    if dataset is None:
        print(f"[warn] Skipping unreadable {label}: {path}", flush=True)
    return dataset


def infer_nodata(path: Path) -> float:
    """Choose an output nodata value compatible with a sample granule.

    Parameters
    ----------
    path : pathlib.Path
        Representative single-band HLS GeoTIFF.

    Returns
    -------
    float
        Declared source nodata, NaN for undeclared floating data, or ``-9999``.

    Raises
    ------
    RuntimeError
        If the sample cannot be opened.
    """
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
    """Resolve the sidecar Fmask GeoTIFF corresponding to one HLS band.

    Parameters
    ----------
    path : pathlib.Path
        Spectral-band path matching the module's HLS filename convention.

    Returns
    -------
    pathlib.Path or None
        Existing sidecar path, or ``None`` when absent/not derivable.
    """
    candidate = path.with_name(BAND_RE.sub(f".Fmask{path.suffix}", path.name))
    return candidate if candidate != path and candidate.exists() else None


def fmask_clear_mask(
    fmask: np.ndarray,
    mode: str,
    valid_values: tuple[int, ...],
    invalid_bits: tuple[int, ...],
) -> np.ndarray:
    """Convert an HLS Fmask window into a boolean clear-pixel mask.

    Parameters
    ----------
    fmask : numpy.ndarray
        QA values parallel to one spectral window.
    mode : str
        ``"values"`` for an allow-list or ``"bitmask"`` for invalid bits.
    valid_values : tuple of int
        Accepted classes in values mode.
    invalid_bits : tuple of int
        Bit positions rejected in bitmask mode; fill value 255 is always bad.

    Returns
    -------
    numpy.ndarray
        Boolean array where true pixels may contribute to the median.

    Raises
    ------
    TypeError, ValueError
        Propagated by NumPy if QA values cannot be converted or shapes/types are
        unsuitable.
    """
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
    """Check whether a scene matches the reference pixel grid and CRS.

    Parameters
    ----------
    dataset : osgeo.gdal.Dataset
        Candidate spectral or Fmask raster.
    width, height : int
        Expected pixel dimensions.
    geotransform : tuple of float
        Expected affine transform.
    projection : str
        Expected CRS WKT.

    Returns
    -------
    bool
        True when dimensions and transforms match and both CRS definitions are
        geospatially equivalent. Equivalent WKT spellings are accepted.
    """
    if (
        dataset.RasterXSize != width
        or dataset.RasterYSize != height
        or not np.allclose(
            dataset.GetGeoTransform(), geotransform, rtol=0.0, atol=1e-6
        )
    ):
        return False

    candidate_projection = dataset.GetProjection()
    if not candidate_projection or not projection:
        return False
    candidate_crs = osr.SpatialReference()
    reference_crs = osr.SpatialReference()
    try:
        candidate_crs.ImportFromWkt(candidate_projection)
        reference_crs.ImportFromWkt(projection)
    except RuntimeError:
        return False
    if candidate_crs.IsSame(reference_crs):
        return True

    # HLS L30 v2 labels its WGS84 ellipsoid as an unknown datum, while S30
    # identifies EPSG:4326 explicitly. GDAL therefore reports different CRS
    # objects even though the projected coordinate systems are numerically
    # identical. Compare the defining projection values for that known case.
    candidate_method = candidate_crs.GetAttrValue("PROJECTION")
    reference_method = reference_crs.GetAttrValue("PROJECTION")
    if not candidate_method or candidate_method != reference_method:
        return False
    parameters = (
        osr.SRS_PP_LATITUDE_OF_ORIGIN,
        osr.SRS_PP_CENTRAL_MERIDIAN,
        osr.SRS_PP_SCALE_FACTOR,
        osr.SRS_PP_FALSE_EASTING,
        osr.SRS_PP_FALSE_NORTHING,
    )
    candidate_values = [
        candidate_crs.GetSemiMajor(),
        candidate_crs.GetInvFlattening(),
        candidate_crs.GetLinearUnits(),
        *(candidate_crs.GetProjParm(name) for name in parameters),
    ]
    reference_values = [
        reference_crs.GetSemiMajor(),
        reference_crs.GetInvFlattening(),
        reference_crs.GetLinearUnits(),
        *(reference_crs.GetProjParm(name) for name in parameters),
    ]
    return bool(np.allclose(candidate_values, reference_values, rtol=0.0, atol=1e-9))


def _read_window(
    dataset: gdal.Dataset,
    window: tuple[int, int, int, int],
    label: str,
    warned: set[str],
) -> np.ndarray | None:
    """Read one band window while suppressing repeated source-level failures.

    Parameters
    ----------
    dataset : osgeo.gdal.Dataset
        Open single-band source.
    window : tuple of int
        ``(x_offset, y_offset, width, height)`` read request.
    label : str
        Human-readable source role for warnings.
    warned : set of str
        Mutable set tracking sources that have already emitted a warning.

    Returns
    -------
    numpy.ndarray or None
        Expected-shape array, or ``None`` after a reported read failure.

    Raises
    ------
    RuntimeError
        Propagated only when GDAL fails while identifying the dataset before
        the guarded read; window read failures themselves return ``None``.

    Notes
    -----
    GDAL ``RuntimeError`` is intentionally caught so other observations remain
    usable.
    """
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
    """Normalize a source window to float32 with NaN invalid pixels.

    Parameters
    ----------
    array : numpy.ndarray
        Source band window.
    nodata : float or None
        Declared source nodata, including NaN.

    Returns
    -------
    numpy.ndarray
        Independent float32 copy with non-finite/nodata pixels set to NaN.

    Raises
    ------
    TypeError, ValueError
        If NumPy cannot convert the input to float32.
    """
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
    """Find a readable scene whose header defines one composite's grid.

    Parameters
    ----------
    tile : str
        MGRS tile identifier used in error reporting.
    bands_to_paths : dict of str to list of pathlib.Path
        Candidate scenes grouped by band.

    Returns
    -------
    osgeo.gdal.Dataset
        First readable source dataset; caller owns the handle.

    Raises
    ------
    RuntimeError
        If every candidate is unreadable.
    """
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
    """Build one blockwise, named, Fmask-filtered HLS median composite.

    Parameters
    ----------
    tile : str
        MGRS tile identifier used for output naming.
    bands_to_paths : dict
        Requested band names mapped to temporal scene paths.
    out_dir : pathlib.Path
        Composite destination directory.
    nodata_default : float
        Output fill/nodata value.
    use_fmask : bool
        Apply QA masks when sidecars are available.
    fmask_mode : {"bitmask", "values"}
        QA interpretation policy.
    clear_fmask_values, invalid_fmask_bits : tuple of int
        Values-mode allow-list and bitmask-mode reject list.
    fallback_to_raw : bool
        Fill pixels with no clear observation from the unmasked median.
    output_bands : tuple of str, optional
        Output channel names and order; missing bands are filled with nodata.

    Returns
    -------
    tuple
        Published composite path and per-window diagnostic records.

    Raises
    ------
    ValueError
        If the tile has no source files or the reference lacks a CRS.
    RuntimeError
        If no reference/GTiff driver is available or GDAL cannot create/write.
    OSError
        If directories, temporary output, or atomic replacement fail.
    """
    if not any(bands_to_paths.values()):
        raise ValueError(f"No files for tile {tile}")

    reference = _find_reference(tile, bands_to_paths)
    geotransform = reference.GetGeoTransform()
    projection = reference.GetProjection()
    width, height = reference.RasterXSize, reference.RasterYSize
    windows = block_windows(reference)
    reference = None
    if not projection:
        raise ValueError(f"reference scene for {tile} has no CRS")

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
    """Report missing bands and execute one process-pool-safe tile task.

    Parameters
    ----------
    tile, bands, out_dir, nodata_default, use_fmask, fmask_mode,
    clear_fmask_values, invalid_fmask_bits, fallback_to_raw, output_bands
        Picklable arguments forwarded directly to :func:`compute_tile`.

    Returns
    -------
    tuple
        Composite path and diagnostic rows from :func:`compute_tile`.

    Raises
    ------
    ValueError, RuntimeError, OSError
        Propagated from :func:`compute_tile`.
    """
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
    """Parse a non-empty, bounded comma-separated integer CLI option.

    Parameters
    ----------
    value : str
        Raw comma-separated integers.
    label : str
        Option name included in errors.
    maximum : int
        Inclusive upper bound; zero is the lower bound.

    Returns
    -------
    tuple of int
        Parsed values in source order.

    Raises
    ------
    SystemExit
        If values are absent, noninteger, or outside ``0..maximum``.
    """
    try:
        values = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise SystemExit(f"{label} must be a comma-separated list of integers") from exc
    if not values:
        raise SystemExit(f"{label} must contain at least one integer")
    invalid = [item for item in values if not 0 <= item <= maximum]
    if invalid:
        raise SystemExit(f"{label} values must be between 0 and {maximum}: {invalid}")
    return values


def _summarize_diagnostics(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Aggregate window diagnostics into one record per tile and band.

    Parameters
    ----------
    rows : list of dict
        Per-window records emitted by :func:`compute_tile`.

    Returns
    -------
    list of dict
        Sorted totals plus clear-observation and fallback fractions.

    Raises
    ------
    KeyError
        If a row does not follow the diagnostic schema.
    """
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
    """Write aggregated compositing diagnostics as CSV.

    Parameters
    ----------
    rows : list of dict
        Per-window diagnostic rows; an empty list produces no file.
    path : pathlib.Path
        Destination CSV.

    Returns
    -------
    None
        The CSV is written as a side effect when rows exist.

    Raises
    ------
    KeyError
        If rows do not match the diagnostic schema.
    OSError
        If the directory or CSV cannot be created.
    """
    summary = _summarize_diagnostics(rows)
    if not summary:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse monthly HLS compositing options.

    Parameters
    ----------
    argv : list of str or None, optional
        Explicit arguments; ``None`` reads process arguments.

    Returns
    -------
    argparse.Namespace
        Parsed date, bands, nodata, Fmask, worker, and directory options.

    Raises
    ------
    SystemExit
        Raised by ``argparse`` for invalid options or ``--help``.
    """
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
    """Discover and composite every requested MGRS tile, then report QA.

    Parameters
    ----------
    argv : list of str or None, optional
        Command-line arguments forwarded to :func:`parse_args`.

    Returns
    -------
    None
        Per-tile composites and a diagnostics CSV are written as side effects.

    Raises
    ------
    SystemExit
        If dates, bands, Fmask policies, or discovery results are invalid.
    ValueError, RuntimeError
        If a reference/grid is invalid or GDAL cannot produce a tile.
    OSError
        If outputs or diagnostics cannot be written.
    """
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
