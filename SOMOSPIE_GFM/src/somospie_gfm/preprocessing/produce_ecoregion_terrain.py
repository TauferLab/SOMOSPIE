"""Crop a parent region's terrain rasters to a child ecoregion.

Every GeoTIFF in the input directory is cropped to the selected ecoregion's
pixel-aligned bounding window and masked outside its polygon. Output files keep
the input names and share the parent rasters' exact pixel grid.
"""

from __future__ import annotations

import argparse
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from osgeo import gdal, ogr, osr

gdal.UseExceptions()

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SHAPEFILES_ROOT = PROJECT_ROOT / "resources" / "shapefiles"
FIELD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@dataclass(frozen=True)
class RegionSelection:
    """A validated vector-layer filter and its selected geometries."""

    shapefile: Path
    layer_name: str
    where: str
    source_crs: str
    geometries: tuple[bytes, ...]


@dataclass(frozen=True)
class ProduceReport:
    """Counts from one terrain-production run."""

    written: tuple[Path, ...]
    skipped: tuple[Path, ...]


def infer_level(code: str) -> int:
    """Infer CEC hierarchy level from a dotted ecoregion code."""
    parts = [part for part in code.split(".") if part]
    if not 1 <= len(parts) <= 3:
        raise ValueError(
            f"cannot infer an ecoregion level from {code!r}; pass --level"
        )
    return len(parts)


def find_shapefile(root: Path, level: int) -> Path:
    """Find the downloaded CEC shapefile for one hierarchy level."""
    directory = root / f"level{level}"
    candidates = (
        sorted(
            path
            for path in directory.rglob("*")
            if path.is_file() and path.suffix.lower() == ".shp"
        )
        if directory.is_dir()
        else []
    )
    if not candidates:
        raise FileNotFoundError(
            f"no Level {level} shapefile under {directory}; run "
            "retrieve_ecoregion_shapefiles.sh or pass --shapefile"
        )

    roman = {1: "i", 2: "ii", 3: "iii"}[level]
    preferred = []
    for path in candidates:
        stem = path.stem.lower().replace("_", "")
        if "ecoregion" in stem and any(
            marker in stem for marker in (f"level{level}", f"level{roman}")
        ):
            preferred.append(path)
    matches = preferred or candidates
    if len(matches) != 1:
        raise ValueError(
            f"expected one Level {level} shapefile under {directory}, "
            f"found {[str(path) for path in matches]}"
        )
    return matches[0]


def _attribute_filter(
    field_name: str,
    field_type: int,
    code: str,
) -> str:
    """Build a safe OGR attribute filter for the selected code."""
    if not FIELD_RE.fullmatch(field_name):
        raise ValueError(f"invalid shapefile field name: {field_name!r}")

    numeric_types = {ogr.OFTInteger, ogr.OFTInteger64, ogr.OFTReal}
    if field_type in numeric_types:
        try:
            value = float(code)
        except ValueError as exc:
            raise ValueError(
                f"{field_name} is numeric but {code!r} is not"
            ) from exc
        literal = str(int(value)) if value.is_integer() else repr(value)
    else:
        literal = "'" + code.replace("'", "''") + "'"
    return f'"{field_name}" = {literal}'


def load_region(
    shapefile: Path,
    code_field: str,
    code: str,
) -> RegionSelection:
    """Validate and load all geometries matching an ecoregion code."""
    if not shapefile.is_file():
        raise FileNotFoundError(f"shapefile not found: {shapefile}")
    for suffix in (".dbf", ".shx"):
        companion = shapefile.with_suffix(suffix)
        if not companion.is_file():
            raise FileNotFoundError(f"missing shapefile component: {companion}")

    dataset = ogr.Open(str(shapefile))
    if dataset is None:
        raise RuntimeError(f"could not open shapefile: {shapefile}")
    try:
        layer = dataset.GetLayer(0)
        if layer is None:
            raise RuntimeError(f"shapefile has no layers: {shapefile}")
        definition = layer.GetLayerDefn()
        field_index = definition.GetFieldIndex(code_field)
        if field_index < 0:
            fields = [
                definition.GetFieldDefn(index).GetName()
                for index in range(definition.GetFieldCount())
            ]
            raise ValueError(
                f"{code_field!r} is not in {shapefile}; available fields: {fields}"
            )

        where = _attribute_filter(
            code_field,
            definition.GetFieldDefn(field_index).GetType(),
            code,
        )
        filter_result = layer.SetAttributeFilter(where)
        if filter_result not in (None, 0):
            raise ValueError(f"invalid ecoregion filter: {where}")

        spatial_ref = layer.GetSpatialRef()
        if spatial_ref is None:
            raise ValueError(f"shapefile has no CRS: {shapefile}")
        geometries = []
        layer.ResetReading()
        for feature in layer:
            geometry = feature.GetGeometryRef()
            if geometry is not None and not geometry.IsEmpty():
                geometries.append(bytes(geometry.ExportToWkb()))
        if not geometries:
            raise ValueError(
                f"no features with {code_field} == {code!r} in {shapefile}"
            )
        return RegionSelection(
            shapefile=shapefile,
            layer_name=layer.GetName(),
            where=where,
            source_crs=spatial_ref.ExportToWkt(),
            geometries=tuple(geometries),
        )
    finally:
        dataset = None


def _traditional_axis_order(spatial_ref: osr.SpatialReference) -> None:
    """Use x/y axis order consistently across GDAL versions."""
    if hasattr(spatial_ref, "SetAxisMappingStrategy"):
        spatial_ref.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)


def region_bounds(
    selection: RegionSelection,
    destination_crs: str,
) -> tuple[float, float, float, float]:
    """Return selected geometry bounds transformed to a raster CRS."""
    source = osr.SpatialReference()
    target = osr.SpatialReference()
    if source.ImportFromWkt(selection.source_crs) not in (None, 0):
        raise ValueError("could not parse the shapefile CRS")
    if target.ImportFromWkt(destination_crs) not in (None, 0):
        raise ValueError("could not parse the terrain raster CRS")
    _traditional_axis_order(source)
    _traditional_axis_order(target)
    transform = osr.CoordinateTransformation(source, target)

    min_x = min_y = math.inf
    max_x = max_y = -math.inf
    for data in selection.geometries:
        geometry = ogr.CreateGeometryFromWkb(data)
        if geometry is None:
            raise RuntimeError("could not restore an ecoregion geometry")
        transform_result = geometry.Transform(transform)
        if transform_result not in (None, 0):
            raise RuntimeError("could not transform the ecoregion geometry")
        envelope = geometry.GetEnvelope()
        min_x, max_x = min(min_x, envelope[0]), max(max_x, envelope[1])
        min_y, max_y = min(min_y, envelope[2]), max(max_y, envelope[3])
    return min_x, min_y, max_x, max_y


def aligned_window(
    dataset: gdal.Dataset,
    bounds: tuple[float, float, float, float],
) -> tuple[tuple[float, float, float, float], int, int]:
    """Clip geometry bounds to a raster and align them to its pixel grid."""
    transform = dataset.GetGeoTransform()
    if transform[2] != 0 or transform[4] != 0:
        raise ValueError("rotated terrain grids are not supported")
    if transform[1] <= 0 or transform[5] >= 0:
        raise ValueError(
            "expected a north-up raster with positive x and negative y resolution"
        )

    min_x, min_y, max_x, max_y = bounds
    pixel_x, pixel_y = transform[1], abs(transform[5])
    epsilon = 1e-9
    column_start = max(
        0,
        math.floor((min_x - transform[0]) / pixel_x + epsilon),
    )
    column_stop = min(
        dataset.RasterXSize,
        math.ceil((max_x - transform[0]) / pixel_x - epsilon),
    )
    row_start = max(
        0,
        math.floor((transform[3] - max_y) / pixel_y + epsilon),
    )
    row_stop = min(
        dataset.RasterYSize,
        math.ceil((transform[3] - min_y) / pixel_y - epsilon),
    )
    if column_stop <= column_start or row_stop <= row_start:
        raise ValueError("ecoregion does not overlap the terrain raster")

    left = transform[0] + column_start * pixel_x
    right = transform[0] + column_stop * pixel_x
    top = transform[3] - row_start * pixel_y
    bottom = transform[3] - row_stop * pixel_y
    return (
        (left, bottom, right, top),
        column_stop - column_start,
        row_stop - row_start,
    )


def _common_nodata(dataset: gdal.Dataset) -> float | None:
    """Return a common source nodata value, rejecting inconsistent bands."""
    values = [
        dataset.GetRasterBand(index).GetNoDataValue()
        for index in range(1, dataset.RasterCount + 1)
    ]
    declared = [value for value in values if value is not None]
    if declared and len(declared) != len(values):
        raise ValueError("only some raster bands declare nodata")
    if declared and any(
        not (
            (math.isnan(value) and math.isnan(declared[0]))
            or math.isclose(value, declared[0], rel_tol=0, abs_tol=1e-12)
        )
        for value in declared[1:]
    ):
        raise ValueError("raster bands use different nodata values")
    return declared[0] if declared else None


def crop_raster(
    source_path: Path,
    output_path: Path,
    selection: RegionSelection,
    nodata: float | None,
) -> Path:
    """Crop and mask one terrain raster, replacing no existing files."""
    source = gdal.Open(str(source_path))
    if source is None:
        raise RuntimeError(f"could not open terrain raster: {source_path}")
    try:
        projection = source.GetProjection()
        if not projection:
            raise ValueError(f"terrain raster has no CRS: {source_path}")
        bounds = region_bounds(selection, projection)
        output_bounds, width, height = aligned_window(source, bounds)
        source_nodata = _common_nodata(source)
        output_nodata = (
            float(nodata)
            if nodata is not None
            else float(source_nodata) if source_nodata is not None else -9999.0
        )
        descriptions = [
            source.GetRasterBand(index).GetDescription()
            for index in range(1, source.RasterCount + 1)
        ]
    finally:
        source = None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    options = gdal.WarpOptions(
        format="GTiff",
        outputBounds=output_bounds,
        width=width,
        height=height,
        dstSRS=projection,
        outputType=gdal.GDT_Float32,
        resampleAlg=gdal.GRA_NearestNeighbour,
        srcNodata=source_nodata,
        dstNodata=output_nodata,
        cutlineDSName=str(selection.shapefile),
        cutlineLayer=selection.layer_name,
        cutlineWhere=selection.where,
        multithread=True,
        creationOptions=[
            "TILED=YES",
            "COMPRESS=ZSTD",
            "ZSTD_LEVEL=9",
            "PREDICTOR=3",
            "BIGTIFF=IF_SAFER",
            "NUM_THREADS=ALL_CPUS",
        ],
        warpOptions=["NUM_THREADS=ALL_CPUS"],
    )

    output = None
    try:
        output = gdal.Warp(str(temporary), str(source_path), options=options)
        if output is None:
            raise RuntimeError(f"GDAL could not crop {source_path}")
        for index, description in enumerate(descriptions, start=1):
            if description:
                output.GetRasterBand(index).SetDescription(description)
        output.FlushCache()
        output = None
        os.replace(temporary, output_path)
    except Exception:
        output = None
        temporary.unlink(missing_ok=True)
        raise
    return output_path


def find_rasters(input_dir: Path, recursive: bool) -> list[Path]:
    """Find input GeoTIFFs in deterministic order."""
    iterator = input_dir.rglob("*") if recursive else input_dir.iterdir()
    return sorted(
        path
        for path in iterator
        if path.is_file() and path.suffix.lower() in {".tif", ".tiff"}
    )


def produce(
    input_dir: Path,
    output_dir: Path,
    selection: RegionSelection,
    nodata: float | None,
    recursive: bool,
    overwrite: bool,
) -> ProduceReport:
    """Produce every terrain parameter raster for one sub-ecoregion."""
    if not input_dir.is_dir():
        raise FileNotFoundError(f"terrain input directory not found: {input_dir}")
    input_resolved = input_dir.resolve()
    output_resolved = output_dir.resolve()
    if input_resolved == output_resolved:
        raise ValueError("input and output directories must be different")
    if recursive and output_resolved.is_relative_to(input_resolved):
        raise ValueError(
            "with --recursive, the output directory must not be inside the input directory"
        )

    rasters = find_rasters(input_dir, recursive)
    if not rasters:
        raise FileNotFoundError(f"no GeoTIFFs found under {input_dir}")

    written = []
    skipped = []
    for source in rasters:
        relative = source.relative_to(input_dir)
        output = output_dir / relative
        if output.exists() and not overwrite:
            skipped.append(output)
            continue
        crop_raster(source, output, selection, nodata)
        written.append(output)
        print(f"[terrain] {source.name} -> {output}", flush=True)
    return ProduceReport(tuple(written), tuple(skipped))


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="directory containing the parent region's terrain GeoTIFFs",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="directory for cropped terrain GeoTIFFs",
    )
    parser.add_argument(
        "--ecoregion",
        required=True,
        help="child ecoregion code, for example 6.2.13",
    )
    parser.add_argument(
        "--level",
        type=int,
        choices=(1, 2, 3),
        help="ecoregion level (default: inferred from the code)",
    )
    parser.add_argument(
        "--shapefile",
        type=Path,
        help="ecoregion shapefile (default: downloaded CEC file for the level)",
    )
    parser.add_argument(
        "--shapefiles-root",
        type=Path,
        default=DEFAULT_SHAPEFILES_ROOT,
        help="root populated by retrieve_ecoregion_shapefiles.sh",
    )
    parser.add_argument(
        "--code-field",
        help="shapefile code field (default: NA_L<level>CODE)",
    )
    parser.add_argument(
        "--nodata",
        type=float,
        help="output nodata value (default: source value or -9999)",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="search input subdirectories and preserve their layout",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace existing outputs",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Produce cropped terrain parameters from the command line."""
    args = parse_args(argv)
    level = args.level or infer_level(args.ecoregion)
    shapefile = args.shapefile or find_shapefile(args.shapefiles_root, level)
    code_field = args.code_field or f"NA_L{level}CODE"
    selection = load_region(shapefile, code_field, args.ecoregion)
    report = produce(
        args.input_dir,
        args.output_dir,
        selection,
        args.nodata,
        args.recursive,
        args.overwrite,
    )
    print(
        f"Wrote {len(report.written)} terrain raster(s) to {args.output_dir}; "
        f"{len(report.skipped)} existing output(s) skipped.",
        flush=True,
    )


if __name__ == "__main__":
    main()
