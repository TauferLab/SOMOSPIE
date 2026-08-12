"""Compute per-channel normalization statistics for fine-tuning inputs.

Prepared HLS tiles are sampled reproducibly and fused with their aligned
terrain rasters exactly as training sees them. Nodata pixels are excluded.
The resulting JSON contains channel means, standard deviations, validity
fractions, provenance, and warnings for degenerate channels.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from osgeo import gdal

try:
    from .build_aligned_terrain_map import (
        AlignedTerrain,
        build_aligned_terrain_map,
        read_terrain_window,
    )
except ImportError:
    from build_aligned_terrain_map import (
        AlignedTerrain,
        build_aligned_terrain_map,
        read_terrain_window,
    )

gdal.UseExceptions()

STATS_VERSION = 1
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
UNDECLARED_SENTINELS = (-9999.0, -3.4028235e38, 3.4028235e38, -32768.0)
MIN_INFORMATIVE_STD = 1e-6
MIN_VALID_FRACTION = 0.01


@dataclass
class Accumulator:
    """Accumulate shifted streaming moments for a fixed channel layout.

    Attributes
    ----------
    names : list of str
        Channel names defining required input order.
    shift : numpy.ndarray
        First valid per-channel mean used to center sums for stability.
    sums, square_sums : numpy.ndarray
        Shifted first and second moments.
    counts : numpy.ndarray
        Valid-pixel count per channel.
    initialized : numpy.ndarray
        Whether each channel has observed at least one finite value.
    total : int
        Spatial pixels examined per channel, including invalid pixels.
    """

    names: list[str]
    shift: np.ndarray = field(init=False)
    sums: np.ndarray = field(init=False)
    square_sums: np.ndarray = field(init=False)
    counts: np.ndarray = field(init=False)
    initialized: np.ndarray = field(init=False)
    total: int = 0

    def __post_init__(self) -> None:
        """Allocate zeroed float64 accumulation arrays after initialization.

        Returns
        -------
        None
            Internal arrays are initialized in place from ``names`` length.

        Notes
        -----
        Dataclass construction supplies all state; this method has no parameters
        beyond ``self`` and intentionally performs no I/O.
        """
        channels = len(self.names)
        self.shift = np.zeros(channels, dtype=np.float64)
        self.sums = np.zeros(channels, dtype=np.float64)
        self.square_sums = np.zeros(channels, dtype=np.float64)
        self.counts = np.zeros(channels, dtype=np.int64)
        self.initialized = np.zeros(channels, dtype=bool)

    def update(self, data: np.ndarray) -> None:
        """Add one channels-first tile while ignoring non-finite pixels.

        Parameters
        ----------
        data : numpy.ndarray
            Three-dimensional ``[channels, height, width]`` tile data.

        Returns
        -------
        None
            Moments, counts, and total pixels are updated in place.

        Raises
        ------
        ValueError
            If data is not three-dimensional or channel count differs from
            ``names``.
        """
        if data.ndim != 3 or data.shape[0] != len(self.names):
            raise ValueError(
                f"tile shape {data.shape} does not match "
                f"{len(self.names)} expected channels"
            )

        self.total += int(data.shape[1] * data.shape[2])
        for index, channel in enumerate(data):
            values = channel[np.isfinite(channel)].astype(np.float64, copy=False)
            if not values.size:
                continue
            if not self.initialized[index]:
                self.shift[index] = float(values.mean())
                self.initialized[index] = True
            deltas = values - self.shift[index]
            self.sums[index] += deltas.sum(dtype=np.float64)
            self.square_sums[index] += np.square(deltas).sum(dtype=np.float64)
            self.counts[index] += values.size

    def finalize(self) -> tuple[np.ndarray, np.ndarray]:
        """Finalize population moments into normalization-ready arrays.

        Returns
        -------
        tuple of numpy.ndarray
            Float32 means and population standard deviations. Empty channels
            receive mean 0/std 1; tiny standard deviations are clamped.

        Notes
        -----
        Finalization does not mutate accumulated moments and may be repeated.
        """
        divisors = np.maximum(self.counts, 1)
        means = self.shift + self.sums / divisors
        variances = (
            self.square_sums - np.square(self.sums) / divisors
        ) / divisors
        stds = np.sqrt(np.maximum(variances, 0))

        empty = self.counts == 0
        means = np.where(empty | ~np.isfinite(means), 0, means)
        stds = np.where(empty | ~np.isfinite(stds), 1, stds)
        stds = np.maximum(stds, MIN_INFORMATIVE_STD)
        return means.astype(np.float32), stds.astype(np.float32)


def split_paths(value: str) -> list[Path]:
    """Split one comma-separated path option.

    Parameters
    ----------
    value : str
        Raw comma-separated CLI value.

    Returns
    -------
    list of pathlib.Path
        Non-empty stripped path components in source order.

    Notes
    -----
    Existence is validated during tile discovery.
    """
    return [Path(item.strip()) for item in value.split(",") if item.strip()]


def find_tiles(roots: Sequence[Path]) -> list[Path]:
    """Find deterministic prepared-tile inputs below validated roots.

    Parameters
    ----------
    roots : sequence of pathlib.Path
        Directories searched recursively for ``tile_*.tif``.

    Returns
    -------
    list of pathlib.Path
        Sorted, absolute, deduplicated tile paths.

    Raises
    ------
    FileNotFoundError
        If any root is missing or no tiles are found.
    """
    missing = [root for root in roots if not root.is_dir()]
    if missing:
        raise FileNotFoundError(f"tile root(s) not found: {missing}")
    tiles = {
        tile.resolve()
        for root in roots
        for tile in root.rglob("tile_*.tif")
        if tile.is_file()
    }
    if not tiles:
        raise FileNotFoundError(
            f"No tile_*.tif files found under {[str(root) for root in roots]}"
        )
    return sorted(tiles)


def sample_tiles(
    tiles: Sequence[Path],
    max_tiles: int,
    seed: int,
) -> list[Path]:
    """Select a reproducible subset without changing filesystem order.

    Parameters
    ----------
    tiles : sequence of pathlib.Path
        Deterministically ordered population.
    max_tiles : int
        Maximum sample size; non-positive values select all tiles.
    seed : int
        NumPy random seed used when subsampling.

    Returns
    -------
    list of pathlib.Path
        All tiles or a reproducible subset in original sorted order.

    Raises
    ------
    ValueError
        Propagated by NumPy if an invalid sample request reaches the generator.
    """
    if max_tiles <= 0 or len(tiles) <= max_tiles:
        return list(tiles)
    random = np.random.default_rng(seed)
    indices = sorted(random.choice(len(tiles), size=max_tiles, replace=False))
    return [tiles[index] for index in indices]


def resolve_band_indices(
    requested: Sequence[str],
    descriptions: Sequence[str],
    source_count: int,
) -> list[int]:
    """Resolve model HLS names against descriptions or legacy band layout.

    Parameters
    ----------
    requested : sequence of str
        Canonical HLS names in desired model order.
    descriptions : sequence of str
        Per-band GDAL descriptions from the source tile.
    source_count : int
        Total source bands, used to recognize the legacy 13-band layout.

    Returns
    -------
    list of int
        Zero-based indices parallel to ``requested``.

    Raises
    ------
    ValueError
        If requested bands cannot be identified unambiguously.
    """
    named = {
        description.strip().upper(): index
        for index, description in enumerate(descriptions)
        if description.strip()
    }
    if named and all(band in named for band in requested):
        return [named[band] for band in requested]

    if not named and source_count == len(BANDS_UNION):
        unknown = [band for band in requested if band not in BANDS_UNION]
        if unknown:
            raise ValueError(
                f"unknown band(s) {unknown}; known bands are {BANDS_UNION}"
            )
        return [BANDS_UNION.index(band) for band in requested]

    present = [name for name in descriptions if name]
    raise ValueError(
        f"cannot identify {list(requested)} in a {source_count}-band tile "
        f"named {present}; expected named bands or the full "
        f"{len(BANDS_UNION)}-band layout"
    )


def resolve_terrain_for_tile(
    tile_path: Path,
    terrain_map: dict[str, Path] | None,
    terrain_stack: Path | None,
) -> Path | None:
    """Resolve a region-mapped terrain stack or shared fallback.

    Parameters
    ----------
    tile_path : pathlib.Path
        Tile whose path components encode its region.
    terrain_map : dict of str to pathlib.Path or None
        Optional region-specific stack mapping.
    terrain_stack : pathlib.Path or None
        Shared fallback stack.

    Returns
    -------
    pathlib.Path or None
        Mapped stack, fallback, or ``None`` when terrain is disabled.
    """
    if terrain_map:
        components = {
            component.lower().replace(" ", "_")
            for component in tile_path.parts
        }
        for region, stack in terrain_map.items():
            if region.lower().replace(" ", "_") in components:
                return stack
    return terrain_stack


def _tile_metadata(
    dataset: gdal.Dataset,
) -> tuple[list[str], tuple[float, ...], int, int]:
    """Extract channel descriptions and spatial dimensions from a tile.

    Parameters
    ----------
    dataset : osgeo.gdal.Dataset
        Open prepared HLS tile.

    Returns
    -------
    tuple
        Descriptions, affine geotransform, width, and height.

    Raises
    ------
    RuntimeError
        Propagated by GDAL when metadata cannot be read.
    """
    descriptions = [
        dataset.GetRasterBand(index).GetDescription() or ""
        for index in range(1, dataset.RasterCount + 1)
    ]
    return (
        descriptions,
        dataset.GetGeoTransform(),
        dataset.RasterXSize,
        dataset.RasterYSize,
    )


def read_fused_tile(
    tile_path: Path,
    band_indices: Sequence[int],
    aligned: AlignedTerrain | None,
) -> np.ndarray:
    """Read the exact channels presented to training for one tile.

    Parameters
    ----------
    tile_path : pathlib.Path
        Prepared HLS tile.
    band_indices : sequence of int
        Zero-based HLS bands in model order.
    aligned : AlignedTerrain or None
        Optional terrain cache from which the matching window is read.

    Returns
    -------
    numpy.ndarray
        Float32 channels-first HLS data, optionally followed by terrain, with
        all declared/non-finite nodata converted to NaN.

    Raises
    ------
    RuntimeError
        If GDAL cannot open/read a requested band or terrain window.
    ValueError
        If the terrain window does not match tile dimensions.
    """
    dataset = gdal.Open(str(tile_path))
    if dataset is None:
        raise RuntimeError(f"Could not open tile: {tile_path}")
    try:
        _, transform, width, height = _tile_metadata(dataset)
        channels = []
        for source_index in band_indices:
            band = dataset.GetRasterBand(source_index + 1)
            array = band.ReadAsArray()
            if array is None:
                raise RuntimeError(
                    f"Could not read band {source_index + 1} from {tile_path}"
                )
            array = array.astype(np.float32)
            invalid = ~np.isfinite(array)
            nodata = band.GetNoDataValue()
            if nodata is not None:
                invalid |= np.isnan(array) if np.isnan(nodata) else array == nodata
            array[invalid] = np.nan
            channels.append(array)
    finally:
        dataset = None

    hls = np.stack(channels)
    if aligned is None:
        return hls

    terrain = read_terrain_window(aligned, transform, width, height)
    if terrain.ndim == 2:
        terrain = terrain[np.newaxis]
    if terrain.shape[1:] != (height, width):
        raise ValueError(
            f"terrain window for {tile_path} has shape {terrain.shape[1:]}, "
            f"expected {(height, width)}"
        )
    return np.concatenate((hls, terrain.astype(np.float32)), axis=0)


def terrain_band_names(aligned: AlignedTerrain | None) -> list[str]:
    """Read stable terrain channel names from an aligned mosaic.

    Parameters
    ----------
    aligned : AlignedTerrain or None
        Terrain cache metadata; ``None`` means HLS-only inputs.

    Returns
    -------
    list of str
        GDAL descriptions or ``terrain_XX`` fallbacks; empty without terrain.

    Raises
    ------
    RuntimeError
        If the aligned terrain raster cannot be opened.
    """
    if aligned is None:
        return []
    dataset = gdal.Open(str(aligned.path))
    if dataset is None:
        raise RuntimeError(f"Could not open aligned terrain: {aligned.path}")
    try:
        names = [
            dataset.GetRasterBand(index).GetDescription()
            for index in range(1, dataset.RasterCount + 1)
        ]
    finally:
        dataset = None
    return [
        name or f"terrain_{index:02d}"
        for index, name in enumerate(names, start=1)
    ]


def find_degenerate(
    names: Sequence[str],
    means: np.ndarray,
    stds: np.ndarray,
    counts: np.ndarray,
    total: int,
) -> list[dict[str, object]]:
    """Identify channels that are unsafe or uninformative for normalization.

    Parameters
    ----------
    names : sequence of str
        Channel names parallel to all statistics arrays.
    means, stds : numpy.ndarray
        Final per-channel population moments.
    counts : numpy.ndarray
        Valid pixels per channel.
    total : int
        Pixels examined per channel.

    Returns
    -------
    list of dict
        JSON-ready issue records for empty, constant, sentinel-like, or
        mostly-invalid channels.

    Raises
    ------
    IndexError
        If supplied arrays are shorter than ``names``.
    """
    issues: list[dict[str, object]] = []
    for index, name in enumerate(names):
        valid_fraction = float(counts[index] / total) if total else 0
        reason = None
        if counts[index] == 0:
            reason = "no valid pixels; channel is entirely nodata"
        elif stds[index] <= MIN_INFORMATIVE_STD:
            reason = f"constant value {means[index]:.6g}; no variance to learn"
        elif any(
            abs(float(means[index]) - sentinel) < 1e-3
            for sentinel in UNDECLARED_SENTINELS
        ):
            reason = (
                f"mean {means[index]:.6g} matches an undeclared nodata sentinel"
            )
        elif valid_fraction < MIN_VALID_FRACTION:
            reason = f"only {valid_fraction:.2%} of pixels are valid"

        if reason:
            issues.append(
                {
                    "index": index,
                    "name": name,
                    "reason": reason,
                    "mean": float(means[index]),
                    "std": float(stds[index]),
                    "valid_fraction": valid_fraction,
                }
            )
    return issues


def provenance_key(
    bands: Sequence[str],
    channel_names: Sequence[str],
    tile_roots: Sequence[Path],
    terrain_stacks: Sequence[Path],
    sampled: int,
    seed: int,
) -> dict[str, object]:
    """Build reproducibility metadata for one statistics artifact.

    Parameters
    ----------
    bands, channel_names : sequence of str
        Requested HLS bands and complete fused channel layout.
    tile_roots : sequence of pathlib.Path
        Prepared-tile discovery roots.
    terrain_stacks : sequence of pathlib.Path
        Terrain sources whose size/mtime are fingerprinted when present.
    sampled : int
        Number of measured tiles.
    seed : int
        Sampling seed.

    Returns
    -------
    dict
        JSON-serializable provenance key.

    Raises
    ------
    OSError
        If metadata for an existing terrain stack cannot be read.
    """
    stack_records = []
    for stack in sorted({path.resolve() for path in terrain_stacks}):
        record: dict[str, object] = {"path": str(stack)}
        if stack.exists():
            stat = stack.stat()
            record.update(size=stat.st_size, mtime_ns=stat.st_mtime_ns)
        else:
            record["missing"] = True
        stack_records.append(record)

    return {
        "stats_version": STATS_VERSION,
        "bands": list(bands),
        "n_channels": len(channel_names),
        "channel_names": list(channel_names),
        "tile_roots": [str(root.resolve()) for root in tile_roots],
        "terrain_stacks": stack_records,
        "tiles_sampled": sampled,
        "seed": seed,
    }


def _aligned_for_tile(
    tile: Path,
    terrain_map: dict[str, Path] | None,
    terrain_stack: Path | None,
    aligned_by_stack: dict[Path, AlignedTerrain],
) -> AlignedTerrain | None:
    """Resolve a tile to its already-built aligned terrain record.

    Parameters
    ----------
    tile : pathlib.Path
        Prepared tile being measured.
    terrain_map, terrain_stack
        Region mapping and shared fallback used for resolution.
    aligned_by_stack : dict
        Absolute source paths mapped to built cache records.

    Returns
    -------
    AlignedTerrain or None
        Matching cache, or ``None`` for an HLS-only run.

    Raises
    ------
    ValueError
        If a configured terrain mapping does not resolve or was not built.
    """
    stack = resolve_terrain_for_tile(tile, terrain_map, terrain_stack)
    if stack is None:
        if terrain_map:
            raise ValueError(f"No terrain stack mapping matches tile {tile}")
        return None
    aligned = aligned_by_stack.get(stack.resolve())
    if aligned is None:
        raise ValueError(f"No aligned terrain was built for {stack}")
    return aligned


def _band_indices_for_tile(tile: Path, bands: Sequence[str]) -> list[int]:
    """Resolve model-band indices using one tile's actual header.

    Parameters
    ----------
    tile : pathlib.Path
        Prepared HLS tile to inspect.
    bands : sequence of str
        Canonical requested band names.

    Returns
    -------
    list of int
        Zero-based band indices in requested order.

    Raises
    ------
    RuntimeError
        If GDAL cannot open the tile.
    ValueError
        If band names cannot be resolved.
    """
    dataset = gdal.Open(str(tile))
    if dataset is None:
        raise RuntimeError(f"Could not open tile: {tile}")
    try:
        descriptions, _, _, _ = _tile_metadata(dataset)
        return resolve_band_indices(bands, descriptions, dataset.RasterCount)
    finally:
        dataset = None


def compute(
    tile_roots: list[Path],
    bands: list[str],
    terrain_map: dict[str, Path] | None,
    terrain_stack: Path | None,
    aligned_dir: Path,
    max_tiles: int,
    seed: int,
) -> dict[str, object]:
    """Compute normalization statistics over reproducibly sampled fused tiles.

    Parameters
    ----------
    tile_roots : list of pathlib.Path
        Prepared-tile roots.
    bands : list of str
        HLS channels in model order.
    terrain_map : dict of str to pathlib.Path or None
        Optional region-specific terrain mapping.
    terrain_stack : pathlib.Path or None
        Optional shared terrain stack.
    aligned_dir : pathlib.Path
        Directory used to build/reuse aligned terrain caches.
    max_tiles : int
        Maximum tiles to measure; non-positive means all.
    seed : int
        Reproducible sampling seed.

    Returns
    -------
    dict
        JSON-ready means, standard deviations, valid fractions, degeneracy
        warnings, and provenance.

    Raises
    ------
    FileNotFoundError
        If tile roots, tiles, or configured terrain stacks are missing.
    ValueError
        If band layouts, terrain mappings, or fused channel layouts differ.
    RuntimeError
        If GDAL cannot read tiles or build/read terrain caches.
    """
    tiles = find_tiles(tile_roots)
    sampled = sample_tiles(tiles, max_tiles, seed)
    print(f"Found {len(tiles)} tiles; measuring {len(sampled)}", flush=True)

    aligned_by_stack: dict[Path, AlignedTerrain] = {}
    if terrain_map or terrain_stack:
        aligned_dir.mkdir(parents=True, exist_ok=True)
        built = build_aligned_terrain_map(
            terrain_stack,
            terrain_map,
            tiles,
            aligned_dir,
        )
        aligned_by_stack = {
            Path(stack).resolve(): aligned
            for stack, aligned in built.items()
        }

    first_aligned = _aligned_for_tile(
        sampled[0],
        terrain_map,
        terrain_stack,
        aligned_by_stack,
    )
    channel_names = list(bands) + terrain_band_names(first_aligned)
    accumulator = Accumulator(channel_names)

    for number, tile in enumerate(sampled, start=1):
        aligned = _aligned_for_tile(
            tile,
            terrain_map,
            terrain_stack,
            aligned_by_stack,
        )
        names = list(bands) + terrain_band_names(aligned)
        if names != channel_names:
            raise ValueError(
                f"channel layout for {tile} is {names}, expected {channel_names}"
            )
        indices = _band_indices_for_tile(tile, bands)
        accumulator.update(read_fused_tile(tile, indices, aligned))
        if number % 50 == 0 or number == len(sampled):
            print(f"  {number}/{len(sampled)} tiles", flush=True)

    means, stds = accumulator.finalize()
    terrain_stacks = list((terrain_map or {}).values())
    if terrain_stack is not None:
        terrain_stacks.append(terrain_stack)

    return {
        "key": provenance_key(
            bands,
            channel_names,
            tile_roots,
            terrain_stacks,
            len(sampled),
            seed,
        ),
        "band_mean": [float(value) for value in means],
        "band_std": [float(value) for value in stds],
        "valid_pixel_fraction": [
            float(count / accumulator.total) if accumulator.total else 0
            for count in accumulator.counts
        ],
        "degenerate_channels": find_degenerate(
            channel_names,
            means,
            stds,
            accumulator.counts,
            accumulator.total,
        ),
    }


def report(stats: dict[str, Any]) -> None:
    """Print a human-readable statistics table and channel warnings.

    Parameters
    ----------
    stats : dict
        Artifact returned by :func:`compute`.

    Returns
    -------
    None
        The report is written to standard output.

    Raises
    ------
    KeyError, IndexError
        If ``stats`` does not follow the artifact schema.
    """
    names = stats["key"]["channel_names"]
    print(f"\n{'channel':>24}  {'mean':>14}  {'std':>14}  {'valid':>7}")
    for index, name in enumerate(names):
        print(
            f"{name:>24}  {stats['band_mean'][index]:>14.6g}  "
            f"{stats['band_std'][index]:>14.6g}  "
            f"{stats['valid_pixel_fraction'][index]:>6.1%}"
        )

    issues = stats["degenerate_channels"]
    if issues:
        print(f"\n{len(issues)} degenerate channel(s):")
        for issue in issues:
            print(f"  [{issue['index']:2d}] {issue['name']}: {issue['reason']}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse normalization-statistics command-line options.

    Parameters
    ----------
    argv : list of str or None, optional
        Explicit arguments; ``None`` reads process arguments.

    Returns
    -------
    argparse.Namespace
        Parsed bands, roots, terrain source, sampling, and output options.

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
        required=True,
        help="prepared tile directory, or several comma-separated directories",
    )
    parser.add_argument(
        "--bands",
        default=",".join(DEFAULT_BANDS),
        help="HLS bands in model order, comma-separated",
    )
    terrain = parser.add_mutually_exclusive_group()
    terrain.add_argument(
        "--terrain-stack-map",
        type=Path,
        help="JSON mapping region names to terrain stack paths",
    )
    terrain.add_argument(
        "--terrain-stack",
        type=Path,
        help="single terrain stack shared by every tile",
    )
    parser.add_argument(
        "--aligned-terrain-dir",
        type=Path,
        required=True,
        help="directory for pre-aligned terrain mosaics",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="output statistics JSON",
    )
    parser.add_argument(
        "--max-tiles",
        type=int,
        default=200,
        help="maximum sampled tiles; 0 uses every tile",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit nonzero when any channel is degenerate",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace an existing output",
    )
    return parser.parse_args(argv)


def _read_terrain_map(path: Path) -> dict[str, Path]:
    """Read and validate a region-to-terrain JSON object.

    Parameters
    ----------
    path : pathlib.Path
        JSON mapping file.

    Returns
    -------
    dict of str to pathlib.Path
        Validated region mapping.

    Raises
    ------
    SystemExit
        If the file is unreadable, invalid JSON, or not string-to-string.
    """
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot read {path}: {exc}") from exc
    if not isinstance(value, dict) or not all(
        isinstance(region, str) and isinstance(stack, str)
        for region, stack in value.items()
    ):
        raise SystemExit(
            f"{path} must contain a JSON object mapping region names to paths"
        )
    return {region: Path(stack) for region, stack in value.items()}


def main(argv: list[str] | None = None) -> None:
    """Compute, report, and atomically publish normalization statistics.

    Parameters
    ----------
    argv : list of str or None, optional
        Command-line arguments forwarded to :func:`parse_args`.

    Returns
    -------
    None
        JSON output and a terminal report are produced as side effects.

    Raises
    ------
    SystemExit
        For invalid band selection/mapping or strict degeneracy failures.
    FileNotFoundError
        If tiles or configured inputs are missing.
    ValueError, RuntimeError
        If channel/grid validation or GDAL processing fails.
    OSError
        If the JSON cannot be written or atomically replaced.
    """
    args = parse_args(argv)
    if args.output.exists() and not args.force:
        print(f"{args.output} already exists; use --force to recompute")
        return

    bands = tuple(
        "B8A" if band == "B08A" else band
        for band in (
            value.strip().upper()
            for value in args.bands.split(",")
            if value.strip()
        )
    )
    if not bands:
        raise SystemExit("--bands must contain at least one band")
    unknown = [band for band in bands if band not in BANDS_UNION]
    if unknown:
        raise SystemExit(f"unknown band(s) {unknown}; known bands are {BANDS_UNION}")
    if len(set(bands)) != len(bands):
        raise SystemExit("--bands must not contain duplicates")

    terrain_map = (
        _read_terrain_map(args.terrain_stack_map)
        if args.terrain_stack_map
        else None
    )
    stats = compute(
        tile_roots=split_paths(args.tiles_root),
        bands=list(bands),
        terrain_map=terrain_map,
        terrain_stack=args.terrain_stack,
        aligned_dir=args.aligned_terrain_dir,
        max_tiles=args.max_tiles,
        seed=args.seed,
    )
    report(stats)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    try:
        temporary.write_text(
            json.dumps(stats, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, args.output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    print(f"\nWrote band statistics: {args.output}")

    issues = stats["degenerate_channels"]
    if args.strict and issues:
        raise SystemExit(
            f"{len(issues)} degenerate channel(s); refusing under --strict"
        )


if __name__ == "__main__":
    main()
