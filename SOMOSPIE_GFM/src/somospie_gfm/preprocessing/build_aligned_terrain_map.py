"""Pre-warp terrain stacks onto prepared-tile grids.

Each terrain stack is warped once to the common grid of the HLS tiles that use
it. Training and statistics code can then read plain windows from the aligned
mosaic instead of repeatedly resampling a large terrain raster.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
from osgeo import gdal

gdal.UseExceptions()


@dataclass(frozen=True)
class AlignedTerrain:
    """An aligned terrain mosaic and the grid needed for windowed reads."""

    path: Path
    gt: tuple[float, float, float, float, float, float]
    width: int
    height: int
    n_bands: int
    nodata: float | None


def resolve_terrain_for_tile(
    tile_path: Path,
    terrain_path: Path | None,
    terrain_map: dict[str, Path] | None = None,
) -> Path | None:
    """Resolve the terrain stack associated with a tile path."""
    if terrain_map:
        components = {
            component.lower().replace(" ", "_")
            for component in tile_path.parts
        }
        for region, stack in terrain_map.items():
            if region.lower().replace(" ", "_") in components:
                return Path(stack)
    return terrain_path


def _temporary_path(parent: Path, suffix: str) -> Path:
    """Reserve a unique path without leaving an open or existing file."""
    descriptor, name = tempfile.mkstemp(
        dir=parent,
        prefix=".terrain_",
        suffix=suffix,
    )
    os.close(descriptor)
    path = Path(name)
    path.unlink()
    return path


def _tile_grid_vrt(
    tile_paths: Sequence[Path],
) -> tuple[Path, tuple[float, ...], str, int, int]:
    """Build a temporary VRT defining the tiles' common mosaic grid."""
    if not tile_paths:
        raise ValueError("at least one tile is required to define a terrain grid")

    vrt_path = _temporary_path(Path(tempfile.gettempdir()), ".vrt")
    try:
        vrt = gdal.BuildVRT(vrt_path.as_posix(), [str(path) for path in tile_paths])
        if vrt is None:
            raise RuntimeError("GDAL could not build the tile-grid VRT")
        transform = tuple(vrt.GetGeoTransform())
        projection = vrt.GetProjection()
        width, height = vrt.RasterXSize, vrt.RasterYSize
        vrt.FlushCache()
        vrt = None
    except Exception:
        vrt_path.unlink(missing_ok=True)
        raise

    if not projection:
        vrt_path.unlink(missing_ok=True)
        raise ValueError("prepared tiles have no coordinate reference system")
    if transform[2] != 0 or transform[4] != 0:
        vrt_path.unlink(missing_ok=True)
        raise ValueError("rotated prepared-tile grids are not supported")
    if transform[1] <= 0 or transform[5] >= 0:
        vrt_path.unlink(missing_ok=True)
        raise ValueError(
            "expected a north-up tile grid with positive x and negative y resolution"
        )
    return vrt_path, transform, projection, width, height


def _source_metadata(
    terrain_path: Path,
) -> tuple[int, float | None, list[str]]:
    """Read terrain band count, common nodata, and descriptions."""
    source = gdal.Open(str(terrain_path))
    if source is None:
        raise RuntimeError(f"Could not open terrain stack: {terrain_path}")
    try:
        count = source.RasterCount
        if count < 1:
            raise ValueError(f"terrain stack has no bands: {terrain_path}")
        nodata_values = [
            source.GetRasterBand(index).GetNoDataValue()
            for index in range(1, count + 1)
        ]
        descriptions = [
            source.GetRasterBand(index).GetDescription() or ""
            for index in range(1, count + 1)
        ]
    finally:
        source = None

    declared = [value for value in nodata_values if value is not None]
    if declared and any(
        not np.isclose(value, declared[0], equal_nan=True)
        for value in declared[1:]
    ):
        raise ValueError(
            f"terrain bands in {terrain_path} use different nodata values"
        )
    if declared and len(declared) != count:
        raise ValueError(
            f"only some terrain bands in {terrain_path} declare nodata"
        )
    return count, declared[0] if declared else None, descriptions


def _matches_grid(
    path: Path,
    transform: tuple[float, ...],
    projection: str,
    width: int,
    height: int,
    bands: int,
) -> bool:
    """Return whether an existing mosaic can be safely reused."""
    dataset = gdal.Open(str(path))
    if dataset is None:
        return False
    try:
        return (
            dataset.RasterXSize == width
            and dataset.RasterYSize == height
            and dataset.RasterCount == bands
            and tuple(dataset.GetGeoTransform()) == transform
            and dataset.GetProjection() == projection
        )
    finally:
        dataset = None


def _aligned_metadata(path: Path) -> AlignedTerrain:
    """Read an aligned terrain record from disk."""
    dataset = gdal.Open(str(path))
    if dataset is None:
        raise RuntimeError(f"Could not open aligned terrain: {path}")
    try:
        return AlignedTerrain(
            path=path,
            gt=tuple(dataset.GetGeoTransform()),
            width=dataset.RasterXSize,
            height=dataset.RasterYSize,
            n_bands=dataset.RasterCount,
            nodata=dataset.GetRasterBand(1).GetNoDataValue(),
        )
    finally:
        dataset = None


def build_aligned_terrain(
    terrain_path: Path,
    tile_paths: Sequence[Path],
    out_path: Path,
) -> AlignedTerrain:
    """Warp one terrain stack onto the common grid of its prepared tiles."""
    terrain_path = terrain_path.resolve()
    if not terrain_path.is_file():
        raise FileNotFoundError(f"terrain stack not found: {terrain_path}")

    band_count, source_nodata, descriptions = _source_metadata(terrain_path)
    vrt_path, transform, projection, width, height = _tile_grid_vrt(tile_paths)
    try:
        reusable = (
            out_path.is_file()
            and out_path.stat().st_mtime_ns >= terrain_path.stat().st_mtime_ns
            and _matches_grid(
                out_path,
                transform,
                projection,
                width,
                height,
                band_count,
            )
        )
        if reusable:
            print(f"[terrain] Reusing {out_path}", flush=True)
            return _aligned_metadata(out_path)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = _temporary_path(out_path.parent, ".tif")
        x_end = transform[0] + width * transform[1]
        y_end = transform[3] + height * transform[5]
        output_nodata = source_nodata if source_nodata is not None else np.nan

        print(
            f"[terrain] Aligning {terrain_path} -> {out_path} "
            f"({width}x{height}, {band_count} bands)",
            flush=True,
        )
        options = gdal.WarpOptions(
            format="GTiff",
            outputBounds=(
                min(transform[0], x_end),
                min(transform[3], y_end),
                max(transform[0], x_end),
                max(transform[3], y_end),
            ),
            width=width,
            height=height,
            dstSRS=projection,
            outputType=gdal.GDT_Float32,
            resampleAlg=gdal.GRA_Bilinear,
            srcNodata=source_nodata,
            dstNodata=output_nodata,
            multithread=True,
            warpMemoryLimit=512 * 1024 * 1024,
            creationOptions=[
                "TILED=YES",
                "BLOCKXSIZE=256",
                "BLOCKYSIZE=256",
                "COMPRESS=ZSTD",
                "ZSTD_LEVEL=1",
                "PREDICTOR=3",
                "BIGTIFF=IF_SAFER",
                "NUM_THREADS=ALL_CPUS",
            ],
            warpOptions=["NUM_THREADS=ALL_CPUS"],
        )

        try:
            output = gdal.Warp(str(temporary), str(terrain_path), options=options)
            if output is None:
                raise RuntimeError(f"GDAL could not build aligned terrain: {out_path}")
            for index, description in enumerate(descriptions, start=1):
                if description:
                    output.GetRasterBand(index).SetDescription(description)
            output.FlushCache()
            output = None
            os.replace(temporary, out_path)
        except Exception:
            output = None
            temporary.unlink(missing_ok=True)
            raise
        return _aligned_metadata(out_path)
    finally:
        vrt_path.unlink(missing_ok=True)


def build_aligned_terrain_map(
    terrain_path: Path | None,
    terrain_map: dict[str, Path] | None,
    tile_paths: Sequence[Path],
    out_dir: Path,
) -> dict[Path, AlignedTerrain]:
    """Build one aligned mosaic per distinct terrain stack used by the tiles."""
    groups: dict[Path, list[Path]] = {}
    unresolved = []
    for tile in tile_paths:
        stack = resolve_terrain_for_tile(tile, terrain_path, terrain_map)
        if stack is None:
            unresolved.append(tile)
            continue
        stack = stack.resolve()
        if not stack.is_file():
            raise FileNotFoundError(f"terrain stack not found for {tile}: {stack}")
        groups.setdefault(stack, []).append(tile)

    if unresolved and (terrain_path is not None or terrain_map):
        examples = ", ".join(str(tile) for tile in unresolved[:3])
        raise ValueError(
            f"{len(unresolved)} tile(s) have no terrain mapping; examples: {examples}"
        )

    names: dict[str, Path] = {}
    for stack in groups:
        output_name = f"{stack.stem}_aligned.tif"
        previous = names.get(output_name)
        if previous is not None and previous != stack:
            raise ValueError(
                f"terrain stacks {previous} and {stack} would both write {output_name}"
            )
        names[output_name] = stack

    out_dir.mkdir(parents=True, exist_ok=True)
    return {
        stack: build_aligned_terrain(
            stack,
            tiles,
            out_dir / f"{stack.stem}_aligned.tif",
        )
        for stack, tiles in groups.items()
    }


def read_terrain_window(
    aligned: AlignedTerrain,
    tile_gt: tuple[float, float, float, float, float, float],
    tile_w: int,
    tile_h: int,
) -> np.ndarray:
    """Read an aligned terrain window as [bands, height, width] float32."""
    tolerance = max(abs(aligned.gt[1]), abs(aligned.gt[5])) * 1e-6
    if (
        not np.allclose(tile_gt[1:3], aligned.gt[1:3], atol=tolerance, rtol=0)
        or not np.allclose(tile_gt[4:6], aligned.gt[4:6], atol=tolerance, rtol=0)
    ):
        raise ValueError("tile and aligned terrain have different pixel grids")

    x_position = (tile_gt[0] - aligned.gt[0]) / aligned.gt[1]
    y_position = (tile_gt[3] - aligned.gt[3]) / aligned.gt[5]
    xoff, yoff = round(x_position), round(y_position)
    if not np.isclose(x_position, xoff, atol=1e-6, rtol=0) or not np.isclose(
        y_position,
        yoff,
        atol=1e-6,
        rtol=0,
    ):
        raise ValueError("tile origin is not aligned to the terrain pixel grid")

    result = np.full(
        (aligned.n_bands, tile_h, tile_w),
        np.nan,
        dtype=np.float32,
    )
    read_x, read_y = max(0, xoff), max(0, yoff)
    read_x2 = min(aligned.width, xoff + tile_w)
    read_y2 = min(aligned.height, yoff + tile_h)
    if read_x2 <= read_x or read_y2 <= read_y:
        return result

    dataset = gdal.Open(str(aligned.path))
    if dataset is None:
        raise RuntimeError(f"Could not open aligned terrain: {aligned.path}")
    try:
        array = dataset.ReadAsArray(
            read_x,
            read_y,
            read_x2 - read_x,
            read_y2 - read_y,
        )
        if array is None:
            raise RuntimeError(f"Could not read aligned terrain: {aligned.path}")
    finally:
        dataset = None

    array = array.astype(np.float32)
    if array.ndim == 2:
        array = array[np.newaxis]
    expected = (aligned.n_bands, read_y2 - read_y, read_x2 - read_x)
    if array.shape != expected:
        raise RuntimeError(
            f"aligned terrain read returned {array.shape}, expected {expected}"
        )
    invalid = ~np.isfinite(array)
    if aligned.nodata is not None and not np.isnan(aligned.nodata):
        invalid |= array == aligned.nodata
    array[invalid] = np.nan

    destination_x, destination_y = read_x - xoff, read_y - yoff
    result[
        :,
        destination_y : destination_y + array.shape[1],
        destination_x : destination_x + array.shape[2],
    ] = array
    return result


def warp_terrain_to_tile(
    terrain_path: Path,
    tile_path: Path,
) -> np.ndarray:
    """Warp terrain directly to one tile grid as a slower fallback."""
    tile = gdal.Open(str(tile_path))
    if tile is None:
        raise RuntimeError(f"Could not open tile: {tile_path}")
    try:
        transform = tile.GetGeoTransform()
        projection = tile.GetProjection()
        width, height = tile.RasterXSize, tile.RasterYSize
    finally:
        tile = None

    source = gdal.Open(str(terrain_path))
    if source is None:
        raise RuntimeError(f"Could not open terrain stack: {terrain_path}")
    source_nodata = source.GetRasterBand(1).GetNoDataValue()
    output_nodata = source_nodata if source_nodata is not None else np.nan
    memory_path = f"/vsimem/terrain_{os.getpid()}_{id(source)}.tif"
    try:
        x_end = transform[0] + width * transform[1]
        y_end = transform[3] + height * transform[5]
        options = gdal.WarpOptions(
            format="GTiff",
            outputBounds=(
                min(transform[0], x_end),
                min(transform[3], y_end),
                max(transform[0], x_end),
                max(transform[3], y_end),
            ),
            width=width,
            height=height,
            dstSRS=projection,
            outputType=gdal.GDT_Float32,
            resampleAlg=gdal.GRA_Bilinear,
            srcNodata=source_nodata,
            dstNodata=output_nodata,
        )
        warped = gdal.Warp(memory_path, source, options=options)
        source = None
        if warped is None:
            raise RuntimeError(f"Could not warp terrain to tile: {tile_path}")
        data = warped.ReadAsArray()
        if data is None:
            raise RuntimeError(f"Could not read warped terrain for {tile_path}")
        warped = None
    finally:
        source = None
        gdal.Unlink(memory_path)

    data = data.astype(np.float32)
    if data.ndim == 2:
        data = data[np.newaxis]
    invalid = ~np.isfinite(data)
    if source_nodata is not None and not np.isnan(source_nodata):
        invalid |= data == source_nodata
    data[invalid] = np.nan
    return data


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
    terrain = parser.add_mutually_exclusive_group(required=True)
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
        "--output-dir",
        type=Path,
        required=True,
        help="directory for aligned terrain mosaics",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Pre-warp every terrain stack used by a prepared-tile set."""
    args = parse_args(argv)
    roots = [
        Path(value.strip())
        for value in args.tiles_root.split(",")
        if value.strip()
    ]
    if not roots:
        raise SystemExit("--tiles-root must contain at least one directory")
    terrain_map = (
        _read_terrain_map(args.terrain_stack_map)
        if args.terrain_stack_map
        else None
    )
    tiles = find_tiles(roots)
    print(f"Found {len(tiles)} tiles", flush=True)

    aligned = build_aligned_terrain_map(
        args.terrain_stack,
        terrain_map,
        tiles,
        args.output_dir,
    )
    if not aligned:
        raise SystemExit("No terrain stacks were resolved; nothing was aligned")

    print(f"\n{'stack':>40}  {'bands':>5}  {'grid':>17}")
    for stack, terrain in sorted(aligned.items()):
        print(
            f"{stack.name:>40}  {terrain.n_bands:>5}  "
            f"{terrain.width:>7} x {terrain.height:<7}"
        )
    print(
        f"\nWrote {len(aligned)} aligned terrain mosaic(s) to {args.output_dir}"
    )


if __name__ == "__main__":
    main()
