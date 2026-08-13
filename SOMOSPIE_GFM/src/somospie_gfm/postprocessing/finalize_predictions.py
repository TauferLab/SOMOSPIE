"""Crop and mask a prediction raster to its configured EPA ecoregion.

The command turns the raw, seam-blended inference mosaic into the authoritative
final GeoTIFF. Pixels outside the selected ecoregion become NaN nodata, and the
raster extent is reduced to the polygon's bounding box.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from osgeo import gdal

from somospie_gfm.preprocessing.produce_ecoregion_terrain import (
    find_shapefile,
    infer_code_field,
    infer_level,
    load_region,
)

gdal.UseExceptions()

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SHAPEFILES_ROOT = PROJECT_ROOT / "resources" / "shapefiles"


def crop_prediction(
    source: Path,
    output: Path,
    shapefile: Path,
    code_field: str,
    ecoregion: str,
    *,
    force: bool = False,
) -> Path:
    """Mask a prediction mosaic to one ecoregion and publish it atomically.

    Parameters
    ----------
    source : pathlib.Path
        Raw blended prediction GeoTIFF.
    output : pathlib.Path
        Final cropped GeoTIFF destination.
    shapefile : pathlib.Path
        EPA/CEC ecoregion vector dataset.
    code_field : str
        Attribute field containing ``ecoregion``.
    ecoregion : str
        Region code selected from ``code_field``.
    force : bool, optional
        Replace ``output`` when it already exists.

    Returns
    -------
    pathlib.Path
        Published final GeoTIFF.

    Raises
    ------
    FileNotFoundError
        If the source raster or shapefile components are missing.
    FileExistsError
        If the output exists and ``force`` is false.
    ValueError
        If the ecoregion selection, raster CRS, or source bands are invalid.
    RuntimeError
        If GDAL cannot open or crop the raster.
    OSError
        If output directories, temporary files, or atomic publication fail.
    """
    if not source.is_file():
        raise FileNotFoundError(f"prediction raster not found: {source}")
    if output.exists() and not force:
        raise FileExistsError(f"final raster exists; use --force to replace: {output}")
    selection = load_region(shapefile, code_field, ecoregion)

    dataset = gdal.Open(str(source))
    if dataset is None:
        raise RuntimeError(f"could not open prediction raster: {source}")
    try:
        if not dataset.GetProjection():
            raise ValueError(f"prediction raster has no CRS: {source}")
        if dataset.RasterCount < 1:
            raise ValueError(f"prediction raster has no bands: {source}")
        descriptions = [
            dataset.GetRasterBand(index).GetDescription()
            for index in range(1, dataset.RasterCount + 1)
        ]
    finally:
        dataset = None

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.stem}.{os.getpid()}.tmp.tif")
    temporary.unlink(missing_ok=True)
    options = gdal.WarpOptions(
        format="GTiff",
        cutlineDSName=str(selection.shapefile),
        cutlineLayer=selection.layer_name,
        cutlineWhere=selection.where,
        cropToCutline=True,
        dstNodata=float("nan"),
        outputType=gdal.GDT_Float32,
        multithread=True,
        creationOptions=(
            "TILED=YES",
            "COMPRESS=ZSTD",
            "ZSTD_LEVEL=9",
            "PREDICTOR=3",
            "BIGTIFF=IF_SAFER",
            "NUM_THREADS=ALL_CPUS",
        ),
        warpOptions=("NUM_THREADS=ALL_CPUS",),
    )
    result = None
    try:
        result = gdal.Warp(str(temporary), str(source), options=options)
        if result is None:
            raise RuntimeError(f"GDAL could not crop {source} to {ecoregion}")
        for index, description in enumerate(descriptions, start=1):
            if description:
                result.GetRasterBand(index).SetDescription(description)
        result.FlushCache()
        result = None
        os.replace(temporary, output)
    except Exception:
        result = None
        temporary.unlink(missing_ok=True)
        raise
    return output


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse final prediction-cropping options.

    Parameters
    ----------
    argv : list of str or None, optional
        Explicit arguments; ``None`` reads process arguments.

    Returns
    -------
    argparse.Namespace
        Parsed paths, ecoregion selection, and overwrite policy.

    Raises
    ------
    SystemExit
        Raised by ``argparse`` for invalid options or ``--help``.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ecoregion", required=True)
    parser.add_argument("--level", type=int, choices=(1, 2, 3))
    parser.add_argument("--shapefile", type=Path)
    parser.add_argument(
        "--shapefiles-root",
        type=Path,
        default=DEFAULT_SHAPEFILES_ROOT,
    )
    parser.add_argument("--code-field")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Resolve the ecoregion vector and produce the final masked GeoTIFF.

    Parameters
    ----------
    argv : list of str or None, optional
        Arguments forwarded to :func:`parse_args`.

    Returns
    -------
    None
        The final path is printed after successful publication.

    Raises
    ------
    FileNotFoundError, FileExistsError, ValueError, RuntimeError, OSError
        Propagated from vector discovery and :func:`crop_prediction`.
    """
    args = parse_args(argv)
    level = args.level or infer_level(args.ecoregion)
    shapefile = args.shapefile or find_shapefile(args.shapefiles_root, level)
    code_field = args.code_field or infer_code_field(shapefile, level)
    output = crop_prediction(
        args.input,
        args.output,
        shapefile,
        code_field,
        args.ecoregion,
        force=args.force,
    )
    print(f"Wrote final ecoregion-cropped prediction: {output}", flush=True)


if __name__ == "__main__":
    main()
