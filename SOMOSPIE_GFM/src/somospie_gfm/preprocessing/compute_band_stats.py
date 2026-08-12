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
    """Numerically stable streaming moments for a fixed channel list."""

    names: list[str]
    shift: np.ndarray = field(init=False)
    sums: np.ndarray = field(init=False)
    square_sums: np.ndarray = field(init=False)
    counts: np.ndarray = field(init=False)
    initialized: np.ndarray = field(init=False)
    total: int = 0

    def __post_init__(self) -> None:
        channels = len(self.names)
        self.shift = np.zeros(channels, dtype=np.float64)
        self.sums = np.zeros(channels, dtype=np.float64)
        self.square_sums = np.zeros(channels, dtype=np.float64)
        self.counts = np.zeros(channels, dtype=np.int64)
        self.initialized = np.zeros(channels, dtype=bool)

    def update(self, data: np.ndarray) -> None:
        """Add one channels-first tile, ignoring non-finite pixels."""
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
        """Return float32 population means and standard deviations."""
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
    """Split a comma-separated path option."""
    return [Path(item.strip()) for item in value.split(",") if item.strip()]


def find_tiles(roots: Sequence[Path]) -> list[Path]:
    """Find sorted, deduplicated prepared tiles below one or more roots."""
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
    """Select a reproducible, sorted subset of tiles."""
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
    """Map requested HLS names to zero-based source band indices."""
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
    """Resolve the terrain stack associated with a tile path."""
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
    """Read band descriptions and grid metadata from an open tile."""
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
    """Read selected HLS bands and optional aligned terrain as float32."""
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
    """Return named terrain channels, falling back to positional labels."""
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
    """Describe empty, constant, sentinel-like, or mostly empty channels."""
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
    """Build a JSON-serializable fingerprint of the statistics inputs."""
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
    """Return a tile's aligned terrain object and reject missing mappings."""
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
    """Resolve selected bands from one tile's own metadata."""
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
    """Compute the complete statistics artifact."""
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
    """Print statistics and degenerate-channel warnings."""
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
    """Parse command-line arguments."""
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
    """Read and validate a region-to-terrain JSON mapping."""
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
    """Compute and atomically write a normalization-statistics artifact."""
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
