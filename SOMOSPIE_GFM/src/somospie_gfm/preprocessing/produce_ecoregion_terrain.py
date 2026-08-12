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
    """Capture a validated ecoregion selection for repeated raster cuts.

    Attributes
    ----------
    shapefile : pathlib.Path
        Vector dataset passed to GDAL as the cutline source.
    layer_name : str
        OGR layer containing the selected features.
    where : str
        Validated OGR attribute expression selecting the ecoregion.
    source_crs : str
        Vector CRS as WKT.
    geometries : tuple of bytes
        Selected geometries serialized as WKB for bounds calculations.
    """

    shapefile: Path
    layer_name: str
    where: str
    source_crs: str
    geometries: tuple[bytes, ...]


@dataclass(frozen=True)
class ProduceReport:
    """Record outputs created and deliberately skipped by one run.

    Attributes
    ----------
    written : tuple of pathlib.Path
        New or overwritten cropped rasters.
    skipped : tuple of pathlib.Path
        Existing outputs retained because overwrite was disabled.
    """

    written: tuple[Path, ...]
    skipped: tuple[Path, ...]


def infer_level(code: str) -> int:
    """Infer the CEC hierarchy level from dotted code depth.

    Parameters
    ----------
    code : str
        Ecoregion code such as ``"6"``, ``"6.2"``, or ``"6.2.13"``.

    Returns
    -------
    int
        Hierarchy level 1, 2, or 3.

    Raises
    ------
    ValueError
        If the code has no components or more than three components.
    """
    parts = [part for part in code.split(".") if part]
    if not 1 <= len(parts) <= 3:
        raise ValueError(
            f"cannot infer an ecoregion level from {code!r}; pass --level"
        )
    return len(parts)


def find_shapefile(root: Path, level: int) -> Path:
    """Locate exactly one downloaded CEC shapefile for a hierarchy level.

    Parameters
    ----------
    root : pathlib.Path
        Shapefile root populated by the acquisition script.
    level : int
        Requested CEC level, normally 1-3.

    Returns
    -------
    pathlib.Path
        Preferred matching shapefile below ``root/level<level>``.

    Raises
    ------
    FileNotFoundError
        If no shapefile exists for the requested level.
    ValueError
        If multiple equally plausible shapefiles make selection ambiguous.
    """
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
    """Build a type-correct, injection-resistant OGR attribute filter.

    Parameters
    ----------
    field_name : str
        Valid OGR field identifier.
    field_type : int
        OGR field type constant used to choose numeric or quoted syntax.
    code : str
        Ecoregion code to compare against the field.

    Returns
    -------
    str
        OGR SQL expression selecting the requested code.

    Raises
    ------
    ValueError
        If the field identifier is unsafe or a numeric field receives a
        nonnumeric code.
    """
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
    """Validate a shapefile and materialize one ecoregion selection.

    Parameters
    ----------
    shapefile : pathlib.Path
        ESRI shapefile containing ecoregion polygons.
    code_field : str
        Attribute field holding region codes.
    code : str
        Code whose features will form the cutline.

    Returns
    -------
    RegionSelection
        Layer/filter metadata and non-empty selected geometries.

    Raises
    ------
    FileNotFoundError
        If the ``.shp``, ``.dbf``, or ``.shx`` component is missing.
    RuntimeError
        If OGR cannot open the shapefile or access its first layer.
    ValueError
        If the field/filter/CRS is invalid or no matching geometry exists.
    """
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
    """Configure a spatial reference for traditional GIS x/y axis order.

    Parameters
    ----------
    spatial_ref : osgeo.osr.SpatialReference
        Mutable CRS object to configure when the installed GDAL supports axis
        mapping strategies.

    Returns
    -------
    None
        ``spatial_ref`` is modified in place.

    Notes
    -----
    Older GDAL bindings without ``SetAxisMappingStrategy`` are left unchanged.
    """
    if hasattr(spatial_ref, "SetAxisMappingStrategy"):
        spatial_ref.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)


def region_bounds(
    selection: RegionSelection,
    destination_crs: str,
) -> tuple[float, float, float, float]:
    """Transform selected geometry and compute its combined raster-CRS bounds.

    Parameters
    ----------
    selection : RegionSelection
        WKB geometries and source CRS to transform.
    destination_crs : str
        Target raster CRS as WKT or another OSR-compatible definition.

    Returns
    -------
    tuple of float
        Combined ``(min_x, min_y, max_x, max_y)`` bounds.

    Raises
    ------
    ValueError
        If either CRS cannot be parsed.
    RuntimeError
        If WKB restoration or coordinate transformation fails.
    """
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
    """Clip ecoregion bounds and snap the crop outward to source pixels.

    Parameters
    ----------
    dataset : osgeo.gdal.Dataset
        Open parent terrain raster defining the grid and extent.
    bounds : tuple of float
        Ecoregion ``(min_x, min_y, max_x, max_y)`` in the raster CRS.

    Returns
    -------
    tuple
        GDAL output bounds plus integer output width and height.

    Raises
    ------
    ValueError
        If the raster is rotated/not north-up or the ecoregion does not
        overlap it.
    """
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
    """Resolve one safe nodata value shared by every raster band.

    Parameters
    ----------
    dataset : osgeo.gdal.Dataset
        Open potentially multi-band terrain raster.

    Returns
    -------
    float or None
        Shared declared nodata, including NaN, or ``None`` when no band
        declares nodata.

    Raises
    ------
    ValueError
        If only some bands declare nodata or declared values differ.
    """
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
    """Crop and polygon-mask one terrain raster on its original pixel grid.

    Parameters
    ----------
    source_path : pathlib.Path
        Parent-region terrain GeoTIFF.
    output_path : pathlib.Path
        Destination written through a neighboring temporary file.
    selection : RegionSelection
        Cutline layer, filter, CRS, and geometry bounds.
    nodata : float or None
        Explicit destination nodata; source nodata or ``-9999`` is used when
        omitted.

    Returns
    -------
    pathlib.Path
        Published ``output_path``.

    Raises
    ------
    RuntimeError
        If GDAL cannot open, transform, or warp the raster.
    ValueError
        If CRS, grid, overlap, or per-band nodata metadata is invalid.
    OSError
        If output directories, temporary files, or atomic replacement fail.
    """
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
    """Discover terrain GeoTIFFs in deterministic order.

    Parameters
    ----------
    input_dir : pathlib.Path
        Directory to scan.
    recursive : bool
        Include nested directories when true.

    Returns
    -------
    list of pathlib.Path
        Sorted ``.tif`` and ``.tiff`` files; possibly empty.

    Raises
    ------
    OSError
        If directory enumeration fails.
    """
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
    """Crop every terrain parameter in a directory to one sub-ecoregion.

    Parameters
    ----------
    input_dir, output_dir : pathlib.Path
        Parent-region source directory and separate destination directory.
    selection : RegionSelection
        Validated ecoregion cutline.
    nodata : float or None
        Optional destination nodata override.
    recursive : bool
        Recurse and preserve relative subdirectory layout.
    overwrite : bool
        Replace existing outputs when true; otherwise record them as skipped.

    Returns
    -------
    ProduceReport
        Immutable lists of written and skipped paths.

    Raises
    ------
    FileNotFoundError
        If the input directory or its GeoTIFFs are missing.
    ValueError
        If input/output layout is unsafe or a crop fails validation.
    RuntimeError
        If GDAL cannot process a source raster.
    """
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
    """Parse ecoregion-terrain production options.

    Parameters
    ----------
    argv : sequence of str or None, optional
        Explicit arguments; ``None`` reads process arguments.

    Returns
    -------
    argparse.Namespace
        Parsed directories, ecoregion selection, nodata, and overwrite flags.

    Raises
    ------
    SystemExit
        Raised by ``argparse`` for invalid options or ``--help``.
    """
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
    """Resolve one ecoregion and crop all requested terrain parameters.

    Parameters
    ----------
    argv : sequence of str or None, optional
        Command-line arguments forwarded to :func:`parse_args`.

    Returns
    -------
    None
        Cropped rasters and a completion summary are written as side effects.

    Raises
    ------
    FileNotFoundError
        If shapefile components, input rasters, or directories are missing.
    ValueError
        If the code, shapefile, CRS, grid, or output layout is invalid.
    RuntimeError
        If OGR/GDAL cannot read geometry or crop a raster.
    """
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
