"""Attach monthly ESA-CCI soil-moisture targets to prepared HLS tiles.

The output manifest contains one row per tile, including unlabelled tiles, so
training can select the ``train`` and ``holdout`` rows without opening raster
headers. Soil-moisture coordinates are expected in EPSG:4326.
"""

from __future__ import annotations

import argparse
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from osgeo import gdal, osr

gdal.UseExceptions()

DEFAULT_METRIC_CRS = "EPSG:5070"
MONTHS = {
    name: index
    for index, name in enumerate(
        (
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ),
        start=1,
    )
}


@dataclass(frozen=True)
class TileHeader:
    """Store the manifest-ready spatial metadata for one prepared tile.

    Attributes
    ----------
    path : pathlib.Path
        Absolute path used as the stable manifest key.
    region : str
        Region label inherited from the tile root that discovered the file.
    left, right, bottom, top : float
        Axis-aligned tile bounds in ``crs``.
    width, height : int
        Raster dimensions in pixels.
    band_count : int
        Number of input channels stored in the tile.
    crs : str
        Tile coordinate reference system as WKT.
    """

    path: Path
    region: str
    left: float
    right: float
    bottom: float
    top: float
    width: int
    height: int
    band_count: int
    crs: str


def _month_candidates(month: str, fallback: str) -> list[str]:
    """Generate accepted ESA-CCI column spellings for a requested month.

    Parameters
    ----------
    month : str
        Full month name, month number, or an ``X<n>``-style column name.
    fallback : str
        Explicit soil-moisture column appended as the final candidate.

    Returns
    -------
    list of str
        Unique candidate names in resolution priority order.

    Notes
    -----
    This pure normalization helper performs no I/O and intentionally raises no
    domain-specific exceptions.
    """
    value = month.strip()
    lower = value.lower()
    if lower in MONTHS:
        number = MONTHS[lower]
        names = [
            f"X{number}",
            f"x{number}",
            lower,
            lower.title(),
            lower[:3],
            lower[:3].title(),
        ]
    else:
        numeric = lower[1:] if lower.startswith("x") else lower
        if numeric.isdigit():
            unpadded = str(int(numeric))
            names = [
                f"X{unpadded}",
                f"x{unpadded}",
                f"X{numeric}",
                f"x{numeric}",
            ]
        else:
            names = [value]
    return list(dict.fromkeys([*names, fallback]))


def load_soil_moisture(
    csv_path: Path,
    x_col: str,
    y_col: str,
    sm_col: str,
    month: str | None = None,
) -> tuple[pd.DataFrame, str]:
    """Load and sanitize coordinates plus one monthly target column.

    Parameters
    ----------
    csv_path : pathlib.Path
        Monthly CSV produced by :mod:`prepare_monthly_sm`.
    x_col, y_col : str
        Longitude and latitude column names in the source CSV.
    sm_col : str
        Explicit target column and fallback when ``month`` is provided.
    month : str or None, optional
        Human-readable month or number to resolve to an ``X1``-``X12`` column.

    Returns
    -------
    tuple of (pandas.DataFrame, str)
        A frame containing numeric ``x``, ``y``, and ``sm`` columns with
        invalid rows removed, plus the resolved source target-column name.

    Raises
    ------
    FileNotFoundError
        If ``csv_path`` does not exist.
    ValueError
        If coordinate/target columns cannot be resolved or no valid rows
        remain after numeric conversion.
    pandas.errors.ParserError
        If Pandas cannot parse the CSV structure.
    """
    if not csv_path.is_file():
        raise FileNotFoundError(f"soil-moisture CSV not found: {csv_path}")
    frame = pd.read_csv(csv_path)
    candidates = _month_candidates(month, sm_col) if month else [sm_col]
    resolved = next((name for name in candidates if name in frame.columns), None)
    if resolved is None:
        raise ValueError(
            f"could not resolve month {month!r}; tried {candidates}, "
            f"available columns are {list(frame.columns)}"
        )

    missing = [name for name in (x_col, y_col) if name not in frame.columns]
    if missing:
        raise ValueError(f"columns {missing} are missing from {csv_path}")

    result = frame[[x_col, y_col, resolved]].rename(
        columns={x_col: "x", y_col: "y", resolved: "sm"}
    )
    for name in ("x", "y", "sm"):
        result[name] = pd.to_numeric(result[name], errors="coerce")
    before = len(result)
    result = result.replace([np.inf, -np.inf], np.nan).dropna().reset_index(drop=True)
    if result.empty:
        raise ValueError(f"no valid soil-moisture rows in {csv_path}")
    print(
        f"Soil moisture: column {resolved!r}, {len(result)} cells "
        f"({before - len(result)} invalid rows dropped)",
        flush=True,
    )
    return result, resolved


def _raster_bounds(dataset: gdal.Dataset) -> tuple[float, float, float, float]:
    """Calculate a raster's axis-aligned bounds from all four grid corners.

    Parameters
    ----------
    dataset : osgeo.gdal.Dataset
        Open raster whose size and affine transform define the footprint.

    Returns
    -------
    tuple of float
        ``(left, bottom, right, top)`` in the dataset CRS.

    Raises
    ------
    RuntimeError
        Propagated by GDAL if the geotransform cannot be read or applied.
    """
    transform = dataset.GetGeoTransform()
    corners = [
        gdal.ApplyGeoTransform(transform, column, row)
        for column, row in (
            (0, 0),
            (dataset.RasterXSize, 0),
            (0, dataset.RasterYSize),
            (dataset.RasterXSize, dataset.RasterYSize),
        )
    ]
    x_values, y_values = zip(*corners)
    return min(x_values), min(y_values), max(x_values), max(y_values)


def _read_tile_header(job: tuple[Path, str]) -> TileHeader:
    """Read one tile's metadata without loading its pixel array.

    Parameters
    ----------
    job : tuple of (pathlib.Path, str)
        Tile path and the region label assigned by its discovery root.

    Returns
    -------
    TileHeader
        Resolved path, bounds, dimensions, band count, and CRS.

    Raises
    ------
    RuntimeError
        If GDAL cannot open the tile or read required metadata.
    ValueError
        If the tile does not declare a CRS.
    """
    path, region = job
    dataset = gdal.Open(str(path))
    if dataset is None:
        raise RuntimeError(f"could not open tile: {path}")
    try:
        crs = dataset.GetProjection()
        if not crs:
            raise ValueError(f"tile has no CRS: {path}")
        left, bottom, right, top = _raster_bounds(dataset)
        return TileHeader(
            path=path.resolve(),
            region=region,
            left=left,
            right=right,
            bottom=bottom,
            top=top,
            width=dataset.RasterXSize,
            height=dataset.RasterYSize,
            band_count=dataset.RasterCount,
            crs=crs,
        )
    finally:
        dataset = None


def read_tile_headers(
    roots: Sequence[Path],
    workers: int | None = None,
) -> list[TileHeader]:
    """Discover prepared tiles and read their headers concurrently.

    Parameters
    ----------
    roots : sequence of pathlib.Path
        Prepared-tile directories. The directory name becomes each tile's
        region label.
    workers : int or None, optional
        Thread count for I/O-bound GDAL header reads. ``None`` chooses a
        bounded default based on available CPUs.

    Returns
    -------
    list of TileHeader
        Headers sorted by absolute path and deduplicated across roots.

    Raises
    ------
    FileNotFoundError
        If a root is missing or no GeoTIFF tiles are found.
    ValueError
        If ``workers`` is not positive or a discovered tile lacks a CRS.
    RuntimeError
        If GDAL cannot open a discovered tile.
    """
    jobs: dict[Path, tuple[Path, str]] = {}
    for root in roots:
        if not root.is_dir():
            raise FileNotFoundError(f"tile root not found: {root}")
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".tif", ".tiff"}:
                jobs.setdefault(path.resolve(), (path, root.name))
    if not jobs:
        raise FileNotFoundError(
            f"no GeoTIFF tiles found under {[str(root) for root in roots]}"
        )

    count = workers if workers is not None else min(32, (os.cpu_count() or 8) * 4)
    if count < 1:
        raise ValueError("workers must be positive")
    ordered = [jobs[path] for path in sorted(jobs)]
    with ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(_read_tile_header, ordered))


def _spatial_reference(value: str) -> osr.SpatialReference:
    """Parse a CRS while enforcing traditional x/y axis order.

    Parameters
    ----------
    value : str
        User-input CRS definition such as WKT or ``"EPSG:4326"``.

    Returns
    -------
    osgeo.osr.SpatialReference
        Parsed reference configured for longitude/x followed by latitude/y.

    Raises
    ------
    ValueError
        If OSR cannot parse ``value``.
    """
    reference = osr.SpatialReference()
    result = reference.SetFromUserInput(value)
    if result not in (None, 0):
        raise ValueError(f"could not parse CRS: {value}")
    if hasattr(reference, "SetAxisMappingStrategy"):
        reference.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return reference


def check_tile_crs(headers: Sequence[TileHeader]) -> str:
    """Verify that all discovered tiles use one semantic CRS.

    Parameters
    ----------
    headers : sequence of TileHeader
        Tile metadata records to compare.

    Returns
    -------
    str
        WKT from the first tile, suitable as an OSR transformation target.

    Raises
    ------
    ValueError
        If ``headers`` is empty, a CRS is invalid, or any tile uses a
        different CRS.
    """
    if not headers:
        raise ValueError("at least one tile header is required")
    expected = _spatial_reference(headers[0].crs)
    mismatched = [
        header.path
        for header in headers[1:]
        if not expected.IsSame(_spatial_reference(header.crs))
    ]
    if mismatched:
        raise ValueError(
            f"{len(mismatched)} tile(s) use a different CRS; first is {mismatched[0]}"
        )
    return headers[0].crs


def transform_xy(
    x: np.ndarray,
    y: np.ndarray,
    source_crs: str,
    destination_crs: str,
    chunk_size: int = 100_000,
) -> tuple[np.ndarray, np.ndarray]:
    """Project parallel coordinate arrays in bounded-memory chunks.

    Parameters
    ----------
    x, y : numpy.ndarray
        One-dimensional coordinate arrays of equal length.
    source_crs, destination_crs : str
        CRS definitions accepted by OSR.
    chunk_size : int, optional
        Maximum points passed to one ``TransformPoints`` call.

    Returns
    -------
    tuple of numpy.ndarray
        Transformed x and y arrays as float64 values.

    Raises
    ------
    ValueError
        If array lengths differ, ``chunk_size`` is not positive, a CRS is
        invalid, or transformation produces non-finite coordinates.
    RuntimeError
        Propagated if OSR cannot transform a coordinate chunk.
    """
    if len(x) != len(y):
        raise ValueError("x and y coordinate arrays must have equal length")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    transform = osr.CoordinateTransformation(
        _spatial_reference(source_crs),
        _spatial_reference(destination_crs),
    )
    output_x = np.empty(len(x), dtype=np.float64)
    output_y = np.empty(len(y), dtype=np.float64)
    for start in range(0, len(x), chunk_size):
        stop = min(start + chunk_size, len(x))
        points = transform.TransformPoints(
            [(float(px), float(py)) for px, py in zip(x[start:stop], y[start:stop])]
        )
        output_x[start:stop] = [point[0] for point in points]
        output_y[start:stop] = [point[1] for point in points]
    if not np.isfinite(output_x).all() or not np.isfinite(output_y).all():
        raise ValueError("coordinate transformation produced non-finite values")
    return output_x, output_y


def join_contains(
    headers: Sequence[TileHeader],
    x: np.ndarray,
    y: np.ndarray,
    sm: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Assign each tile the mean of ESA-CCI cell centres it contains.

    Tile bounds are half-open on their right and top edges, preventing a cell
    centre on a shared seam from being counted by two neighboring tiles.

    Parameters
    ----------
    headers : sequence of TileHeader
        Tile footprints in the same CRS as ``x`` and ``y``.
    x, y : numpy.ndarray
        Projected ESA-CCI cell-centre coordinates.
    sm : numpy.ndarray
        Soil-moisture value parallel to each coordinate pair.

    Returns
    -------
    tuple of numpy.ndarray
        Float64 targets, using NaN for unmatched tiles, and int32 counts of
        contributing cells.

    Raises
    ------
    ValueError
        If the coordinate and soil-moisture arrays have different lengths.
    """
    if not (len(x) == len(y) == len(sm)):
        raise ValueError("x, y, and soil-moisture arrays must have equal length")
    order = np.argsort(x)
    sorted_x, sorted_y, sorted_sm = x[order], y[order], sm[order]
    targets = np.full(len(headers), np.nan, dtype=np.float64)
    counts = np.zeros(len(headers), dtype=np.int32)
    for index, header in enumerate(headers):
        start = np.searchsorted(sorted_x, header.left, side="left")
        stop = np.searchsorted(sorted_x, header.right, side="left")
        inside = (sorted_y[start:stop] >= header.bottom) & (
            sorted_y[start:stop] < header.top
        )
        counts[index] = int(inside.sum())
        if counts[index]:
            targets[index] = float(sorted_sm[start:stop][inside].mean())
    return targets, counts


def join_nearest(
    headers: Sequence[TileHeader],
    lon: np.ndarray,
    lat: np.ndarray,
    sm: np.ndarray,
    tile_crs: str,
    radius_m: float,
    metric_crs: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Assign the nearest ESA-CCI cell within a true metric radius.

    A radius-sized spatial hash limits each tile lookup to nine neighboring
    buckets, avoiding an all-pairs distance matrix and an additional spatial
    indexing dependency.

    Parameters
    ----------
    headers : sequence of TileHeader
        Tile records whose centres will receive targets.
    lon, lat : numpy.ndarray
        ESA-CCI cell centres in EPSG:4326.
    sm : numpy.ndarray
        Soil-moisture values parallel to ``lon`` and ``lat``.
    tile_crs : str
        CRS shared by the tile bounds.
    radius_m : float
        Inclusive maximum tile-centre-to-cell-centre distance in metres.
    metric_crs : str
        Projected CRS with metre linear units used for distance calculations.

    Returns
    -------
    tuple of numpy.ndarray
        Float64 targets with NaN outside the radius, and int32 match flags.

    Raises
    ------
    ValueError
        If arrays differ in length, the radius is non-positive, or
        ``metric_crs`` is not projected in metres.
    RuntimeError
        Propagated if OSR cannot perform either coordinate transformation.
    """
    if not (len(lon) == len(lat) == len(sm)):
        raise ValueError("longitude, latitude, and soil moisture must align")
    if radius_m <= 0:
        raise ValueError("nearest-join radius must be positive")
    metric = _spatial_reference(metric_crs)
    if not metric.IsProjected() or not np.isclose(metric.GetLinearUnits(), 1.0):
        raise ValueError(f"metric CRS must be projected in metres: {metric_crs}")

    cell_x, cell_y = transform_xy(lon, lat, "EPSG:4326", metric_crs)
    centre_x = np.array([(h.left + h.right) / 2 for h in headers])
    centre_y = np.array([(h.bottom + h.top) / 2 for h in headers])
    tile_x, tile_y = transform_xy(centre_x, centre_y, tile_crs, metric_crs)

    buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    cell_keys = np.floor(np.column_stack((cell_x, cell_y)) / radius_m).astype(np.int64)
    for index, key in enumerate(cell_keys):
        buckets[(int(key[0]), int(key[1]))].append(index)

    targets = np.full(len(headers), np.nan, dtype=np.float64)
    counts = np.zeros(len(headers), dtype=np.int32)
    distances = []
    radius_squared = radius_m * radius_m
    for index, (x_value, y_value) in enumerate(zip(tile_x, tile_y)):
        key_x, key_y = np.floor([x_value / radius_m, y_value / radius_m]).astype(int)
        candidates = [
            candidate
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            for candidate in buckets.get((key_x + dx, key_y + dy), ())
        ]
        if not candidates:
            continue
        candidate_array = np.asarray(candidates, dtype=np.int64)
        squared = np.square(cell_x[candidate_array] - x_value) + np.square(
            cell_y[candidate_array] - y_value
        )
        nearest = int(np.argmin(squared))
        if squared[nearest] <= radius_squared:
            cell_index = candidate_array[nearest]
            targets[index] = sm[cell_index]
            counts[index] = 1
            distances.append(float(np.sqrt(squared[nearest])))

    median = f", median distance {np.median(distances):.0f} m" if distances else ""
    print(
        f"Nearest join: {int(counts.sum())}/{len(headers)} tiles within "
        f"{radius_m:.0f} m{median}",
        flush=True,
    )
    return targets, counts


def load_holdout(path: Path | None) -> set[Path]:
    """Load a newline-delimited spatial holdout list.

    Parameters
    ----------
    path : pathlib.Path or None
        Text file containing one tile path per line. Blank lines and lines
        beginning with ``#`` are ignored; ``None`` disables holdouts.

    Returns
    -------
    set of pathlib.Path
        Absolute normalized paths used for manifest split assignment.

    Raises
    ------
    FileNotFoundError
        If a non-``None`` holdout path does not exist.
    OSError
        If the holdout file cannot be read.
    """
    if path is None:
        return set()
    if not path.is_file():
        raise FileNotFoundError(f"holdout file not found: {path}")
    return {
        Path(line).expanduser().resolve()
        for raw in path.read_text().splitlines()
        if (line := raw.strip()) and not line.startswith("#")
    }


def split_paths(values: Sequence[str]) -> list[Path]:
    """Normalize repeatable and comma-separated CLI path values.

    Parameters
    ----------
    values : sequence of str
        Raw option values, each optionally containing commas.

    Returns
    -------
    list of pathlib.Path
        Non-empty path fragments in user-supplied order.

    Notes
    -----
    Paths are not resolved or checked here; discovery performs validation.
    """
    return [
        Path(item.strip())
        for value in values
        for item in value.split(",")
        if item.strip()
    ]


def build_manifest(
    headers: Sequence[TileHeader],
    target: np.ndarray,
    n_points: np.ndarray,
    holdout: set[Path],
    month: str | None,
    sm_column: str,
    join: str,
) -> pd.DataFrame:
    """Build the manifest consumed by training and evaluation.

    Parameters
    ----------
    headers : sequence of TileHeader
        Tile records parallel to ``target`` and ``n_points``.
    target : numpy.ndarray
        Per-tile target, with NaN marking tiles without supervision.
    n_points : numpy.ndarray
        Number of cells contributing to each target.
    holdout : set of pathlib.Path
        Tiles assigned to the ``holdout`` split when labelled.
    month : str or None
        Requested month recorded as provenance.
    sm_column : str
        Actual source CSV column selected for targets.
    join : str
        Join policy recorded as provenance.

    Returns
    -------
    pandas.DataFrame
        One row per tile with split, target, grid metadata, and provenance.

    Raises
    ------
    ValueError
        If headers, targets, and counts have different lengths.
    """
    if not (len(headers) == len(target) == len(n_points)):
        raise ValueError("headers, targets, and point counts must have equal length")
    rows = []
    for header, value, count in zip(headers, target, n_points):
        split = (
            "unlabeled"
            if np.isnan(value)
            else "holdout" if header.path in holdout else "train"
        )
        rows.append(
            {
                "tile": str(header.path),
                "region": header.region,
                "split": split,
                "target": value,
                "n_points": int(count),
                "left": header.left,
                "right": header.right,
                "bottom": header.bottom,
                "top": header.top,
                "center_x": (header.left + header.right) / 2,
                "center_y": (header.bottom + header.top) / 2,
                "width": header.width,
                "height": header.height,
                "band_count": header.band_count,
                "month": month or "",
                "sm_column": sm_column,
                "join": join,
            }
        )
    return pd.DataFrame.from_records(rows)


def report(manifest: pd.DataFrame) -> None:
    """Print overall and per-region target coverage diagnostics.

    Parameters
    ----------
    manifest : pandas.DataFrame
        Manifest returned by :func:`build_manifest`.

    Returns
    -------
    None
        Results are written to standard output.

    Raises
    ------
    ValueError
        If the manifest is empty.
    KeyError
        If required ``split``, ``region``, or ``target`` columns are absent.
    """
    total = len(manifest)
    if not total:
        raise ValueError("cannot report an empty manifest")
    counts = manifest["split"].value_counts()
    labelled = total - int(counts.get("unlabeled", 0))
    print(
        f"\n{total} tiles: {labelled} labelled ({labelled / total:.1%}), "
        f"{int(counts.get('holdout', 0))} held out"
    )
    print(f"\n{'region':>16}  {'tiles':>7}  {'labelled':>9}  {'yield':>6}  {'mean':>10}")
    for region, group in manifest.groupby("region"):
        valid = group[group["split"] != "unlabeled"]
        mean = f"{valid['target'].mean():.4f}" if len(valid) else "-"
        print(
            f"{region:>16}  {len(group):>7}  {len(valid):>9}  "
            f"{len(valid) / len(group):>5.1%}  {mean:>10}"
        )
    if not labelled:
        print("\n[warn] No tiles were labelled; check coverage and the month column.")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse target-attachment command-line options.

    Parameters
    ----------
    argv : sequence of str or None, optional
        Explicit argument vector; ``None`` reads process arguments.

    Returns
    -------
    argparse.Namespace
        Validated option values used by :func:`main`.

    Raises
    ------
    SystemExit
        Raised by ``argparse`` for invalid options or ``--help``.
    """
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--tiles-root",
        action="append",
        required=True,
        help="prepared tile root; repeat or comma-separate additional regions",
    )
    parser.add_argument("--soil-moisture-csv", type=Path, required=True)
    parser.add_argument("--month", help="month name or number, resolved to X<n>")
    parser.add_argument("--sm-col", default="sm", help="explicit target column")
    parser.add_argument("--x-col", default="x", help="longitude column")
    parser.add_argument("--y-col", default="y", help="latitude column")
    parser.add_argument("--join", choices=("contains", "nearest"), default="contains")
    parser.add_argument(
        "--radius-m",
        type=float,
        default=13_500.0,
        help="maximum distance for a nearest join",
    )
    parser.add_argument(
        "--metric-crs",
        default=DEFAULT_METRIC_CRS,
        help="projected metre-based CRS used for nearest distances",
    )
    parser.add_argument("--holdout-tiles", type=Path)
    parser.add_argument("--workers", type=int, help="parallel tile-header readers")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true", help="replace an existing manifest")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Run target attachment and atomically publish the training manifest.

    Parameters
    ----------
    argv : sequence of str or None, optional
        Command-line arguments forwarded to :func:`parse_args`.

    Returns
    -------
    None
        The manifest is written to ``--output`` and a coverage report is
        printed. Existing output is left unchanged unless ``--force`` is set.

    Raises
    ------
    FileNotFoundError
        If tile roots, the target CSV, or the holdout list are missing.
    ValueError
        If CRS, target columns, coordinate arrays, or join settings are
        invalid.
    RuntimeError
        If GDAL/OSR cannot read tile metadata or transform coordinates.
    OSError
        If the temporary manifest cannot be written or atomically replaced.
    """
    args = parse_args(argv)
    if args.output.exists() and not args.force:
        print(f"{args.output} already exists; skipping (use --force to rebuild).")
        return

    roots = split_paths(args.tiles_root)
    headers = read_tile_headers(roots, args.workers)
    tile_crs = check_tile_crs(headers)
    frame, sm_column = load_soil_moisture(
        args.soil_moisture_csv,
        args.x_col,
        args.y_col,
        args.sm_col,
        args.month,
    )
    lon = frame["x"].to_numpy(dtype=np.float64)
    lat = frame["y"].to_numpy(dtype=np.float64)
    moisture = frame["sm"].to_numpy(dtype=np.float64)
    print(
        f"Read {len(headers)} tile headers from {len(roots)} root(s)",
        flush=True,
    )

    if args.join == "contains":
        x, y = transform_xy(lon, lat, "EPSG:4326", tile_crs)
        target, n_points = join_contains(headers, x, y, moisture)
    else:
        target, n_points = join_nearest(
            headers,
            lon,
            lat,
            moisture,
            tile_crs,
            args.radius_m,
            args.metric_crs,
        )

    manifest = build_manifest(
        headers,
        target,
        n_points,
        load_holdout(args.holdout_tiles),
        args.month,
        sm_column,
        args.join,
    )
    report(manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        manifest.to_csv(temporary, index=False)
        os.replace(temporary, args.output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    print(f"\nWrote manifest: {args.output}")


if __name__ == "__main__":
    main()
