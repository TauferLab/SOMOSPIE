"""Split prepared rasters into fixed-size, georeferenced model tiles.

Every input GeoTIFF receives its own output directory containing deterministic
``tile_r<row>_c<column>.tif`` files. Tiles do not overlap. Partial tiles along
the right and bottom edges are padded with nodata so every model input has the
configured dimensions while retaining the source raster's full footprint.
"""

from __future__ import annotations

import argparse
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from osgeo import gdal

gdal.UseExceptions()


@dataclass(frozen=True)
class TileReport:
    """Summarize one tiling invocation.

    Attributes
    ----------
    written : int
        Number of new tile files published.
    skipped : int
        Number of existing tile files left unchanged.
    sources : int
        Number of input rasters processed.
    """

    written: int
    skipped: int
    sources: int


def find_rasters(input_dir: Path) -> list[Path]:
    """Return direct-child GeoTIFF inputs in deterministic order.

    Parameters
    ----------
    input_dir : pathlib.Path
        Directory containing the reprojected HLS composites.

    Returns
    -------
    list of pathlib.Path
        Sorted ``.tif`` and ``.tiff`` files.

    Raises
    ------
    FileNotFoundError
        If the input directory is missing or contains no GeoTIFFs.
    """
    if not input_dir.is_dir():
        raise FileNotFoundError(f"input directory not found: {input_dir}")
    rasters = sorted(
        path
        for path in input_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".tif", ".tiff"}
    )
    if not rasters:
        raise FileNotFoundError(f"no GeoTIFFs found under {input_dir}")
    return rasters


def source_key(path: Path) -> str:
    """Build a stable, filesystem-safe output directory name.

    Parameters
    ----------
    path : pathlib.Path
        Source raster path.

    Returns
    -------
    str
        MGRS tile identifier when present, otherwise a sanitized source stem.

    Raises
    ------
    ValueError
        If neither an MGRS identifier nor a safe non-empty stem can be derived.
    """
    match = re.search(r"(?:^|_)(T\d{2}[A-Z]{3})(?:_|$)", path.stem, re.I)
    if match:
        return match.group(1).upper()
    key = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem).strip("._")
    if not key:
        raise ValueError(f"cannot derive an output name from {path.name!r}")
    return key


def _tile_transform(
    transform: tuple[float, float, float, float, float, float],
    column_offset: int,
    row_offset: int,
) -> tuple[float, float, float, float, float, float]:
    """Translate a source affine transform to one tile-window origin.

    Parameters
    ----------
    transform : tuple of float
        Six-element source GDAL affine geotransform.
    column_offset, row_offset : int
        Zero-based source pixel offsets of the tile's upper-left corner.

    Returns
    -------
    tuple of float
        Six-element transform with the translated origin and unchanged pixel
        vectors.
    """
    x, y = gdal.ApplyGeoTransform(transform, column_offset, row_offset)
    return (x, transform[1], transform[2], y, transform[4], transform[5])


def write_tile(
    source: gdal.Dataset,
    output: Path,
    row: int,
    column: int,
    tile_size: int,
) -> None:
    """Read one source window and atomically publish a padded GeoTIFF tile.

    Parameters
    ----------
    source : osgeo.gdal.Dataset
        Open source raster with at least one band and a valid CRS.
    output : pathlib.Path
        Final ``tile_r*_c*.tif`` path.
    row, column : int
        Zero-based tile-grid indices.
    tile_size : int
        Output width and height in pixels.

    Returns
    -------
    None
        The fixed-size tile is written as a side effect.

    Raises
    ------
    RuntimeError
        If GDAL cannot create, read, write, or flush the tile.
    OSError
        If output publication fails.
    """
    x_offset, y_offset = column * tile_size, row * tile_size
    width = min(tile_size, source.RasterXSize - x_offset)
    height = min(tile_size, source.RasterYSize - y_offset)
    if width <= 0 or height <= 0:
        raise ValueError("tile window lies outside the source raster")

    first = source.GetRasterBand(1)
    data_type = first.DataType
    if any(
        source.GetRasterBand(index).DataType != data_type
        for index in range(2, source.RasterCount + 1)
    ):
        raise ValueError("source bands must share one GDAL data type")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    driver = gdal.GetDriverByName("GTiff")
    if driver is None:
        raise RuntimeError("GDAL GTiff driver is unavailable")

    destination = None
    try:
        destination = driver.Create(
            str(temporary), tile_size, tile_size, source.RasterCount, data_type,
            options=(
                "TILED=YES", "BLOCKXSIZE=224", "BLOCKYSIZE=224",
                "COMPRESS=ZSTD", "ZSTD_LEVEL=3", "BIGTIFF=IF_SAFER",
            ),
        )
        if destination is None:
            raise RuntimeError(f"could not create tile: {temporary}")
        destination.SetProjection(source.GetProjection())
        destination.SetGeoTransform(
            _tile_transform(source.GetGeoTransform(), x_offset, y_offset)
        )
        for index in range(1, source.RasterCount + 1):
            source_band = source.GetRasterBand(index)
            output_band = destination.GetRasterBand(index)
            nodata = source_band.GetNoDataValue()
            if nodata is None:
                nodata = -9999.0
            output_band.SetNoDataValue(nodata)
            output_band.Fill(nodata)
            description = source_band.GetDescription()
            if description:
                output_band.SetDescription(description)
            array = source_band.ReadAsArray(x_offset, y_offset, width, height)
            if array is None:
                raise RuntimeError(
                    f"could not read source window row={row}, column={column}"
                )
            output_band.WriteArray(array, 0, 0)
        destination.FlushCache()
        destination = None
        os.replace(temporary, output)
    except Exception:
        destination = None
        temporary.unlink(missing_ok=True)
        raise


def tile_raster(
    source_path: Path,
    output_dir: Path,
    tile_size: int,
    overwrite: bool,
) -> tuple[int, int]:
    """Tile one raster and return counts of written and skipped outputs.

    Parameters
    ----------
    source_path : pathlib.Path
        Reprojected multi-band input raster.
    output_dir : pathlib.Path
        Directory receiving deterministic fixed-size tiles.
    tile_size : int
        Positive tile width and height in pixels.
    overwrite : bool
        Replace existing tile paths when true.

    Returns
    -------
    tuple of int
        Counts of newly written and deliberately skipped tiles.

    Raises
    ------
    FileNotFoundError
        If GDAL cannot open the source.
    ValueError
        If the source lacks a projection, bands, or compatible data types.
    RuntimeError, OSError
        If individual tiles cannot be created or published.
    """
    source = gdal.Open(str(source_path))
    if source is None:
        raise FileNotFoundError(f"could not open source raster: {source_path}")
    try:
        if source.RasterCount < 1:
            raise ValueError(f"source has no raster bands: {source_path}")
        if not source.GetProjection():
            raise ValueError(f"source has no coordinate reference system: {source_path}")
        rows = math.ceil(source.RasterYSize / tile_size)
        columns = math.ceil(source.RasterXSize / tile_size)
        written = skipped = 0
        for row in range(rows):
            for column in range(columns):
                output = output_dir / f"tile_r{row:05d}_c{column:05d}.tif"
                if output.exists() and not overwrite:
                    skipped += 1
                    continue
                write_tile(source, output, row, column, tile_size)
                written += 1
        return written, skipped
    finally:
        source = None


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse raster-tiling command-line options.

    Parameters
    ----------
    argv : sequence of str or None, optional
        Explicit arguments; ``None`` reads process arguments.

    Returns
    -------
    argparse.Namespace
        Validated input/output directories, tile size, and overwrite policy.

    Raises
    ------
    SystemExit
        Raised by ``argparse`` for invalid options.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--tile-size", type=int, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.tile_size <= 0:
        parser.error("--tile-size must be positive")
    return args


def main(argv: Sequence[str] | None = None) -> None:
    """Tile every direct-child GeoTIFF and print a completion summary.

    Parameters
    ----------
    argv : sequence of str or None, optional
        Command-line arguments forwarded to :func:`parse_args`.

    Returns
    -------
    None
        Tile directories and progress messages are produced as side effects.

    Raises
    ------
    FileNotFoundError, ValueError, RuntimeError, OSError
        Propagated from discovery and per-raster tiling.
    """
    args = parse_args(argv)
    rasters = find_rasters(args.input_dir)
    written = skipped = 0
    for source in rasters:
        destination = args.output_dir / source_key(source)
        new, old = tile_raster(source, destination, args.tile_size, args.overwrite)
        written += new
        skipped += old
        print(f"[tile] {source.name}: wrote {new}, skipped {old}", flush=True)
    report = TileReport(written, skipped, len(rasters))
    print(
        f"Tiled {report.sources} raster(s): wrote {report.written}, "
        f"skipped {report.skipped}",
        flush=True,
    )


if __name__ == "__main__":
    main()
