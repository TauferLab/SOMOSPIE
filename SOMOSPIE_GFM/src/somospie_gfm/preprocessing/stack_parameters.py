"""Stack every band from HLS and terrain GeoTIFF inputs into one raster.

Known HLS channels are written first, followed by terrain parameters in their
canonical order and then any extra channels alphabetically. Each source band
is aligned to one reference grid through GDAL VRTs, keeping the operation
streaming even when inputs use different projections or resolutions.
"""

from __future__ import annotations

import argparse
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from osgeo import gdal

gdal.UseExceptions()

HLS_BAND_ORDER = (
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
MODEL_HLS_BANDS = ("B02", "B03", "B04", "B8A", "B11", "B12")
TERRAIN_BAND_ORDER = (
    "aspect",
    "channel_network_grid",
    "convergence_index",
    "drainage_basins_grid",
    "elevation",
    "filled_depressions",
    "flow_connectivity",
    "flow_direction",
    "flow_width",
    "hillshade",
    "plan_curvature",
    "profile_curvature",
    "slope",
    "total_catchment_area",
    "watershed_basins",
)
RESAMPLING = {
    "nearest": gdal.GRA_NearestNeighbour,
    "bilinear": gdal.GRA_Bilinear,
    "cubic": gdal.GRA_Cubic,
}


@dataclass(frozen=True)
class Channel:
    """Identify one source raster band in the final channel layout.

    Attributes
    ----------
    name : str
        Unique output band description used by training and statistics code.
    path : pathlib.Path
        GeoTIFF containing the channel.
    band : int
        One-based GDAL band index within ``path``.
    """

    name: str
    path: Path
    band: int


@dataclass(frozen=True)
class Grid:
    """Describe the exact spatial grid used for every output channel.

    Attributes
    ----------
    projection : str
        Output CRS as WKT.
    bounds : tuple of float
        ``(left, bottom, right, top)`` output extent.
    width, height : int
        Output dimensions in pixels.
    """

    projection: str
    bounds: tuple[float, float, float, float]
    width: int
    height: int


def canonical_name(name: str) -> str:
    """Normalize known channel aliases into stable model-facing names.

    Parameters
    ----------
    name : str
        Band description or filename stem to normalize.

    Returns
    -------
    str
        Canonical HLS spelling, canonical lowercase terrain spelling, or the
        stripped original for an unknown channel.

    Notes
    -----
    This pure string helper intentionally performs no validation or I/O.
    """
    stripped = name.strip()
    upper = stripped.upper()
    if upper == "B08A":
        return "B8A"
    if upper in HLS_BAND_ORDER:
        return upper
    lower = stripped.lower()
    return lower if lower in TERRAIN_BAND_ORDER else stripped


def find_inputs(
    input_dirs: Sequence[Path],
    output_path: Path,
    recursive: bool,
) -> list[Path]:
    """Discover GeoTIFF inputs without accidentally restacking the output.

    Parameters
    ----------
    input_dirs : sequence of pathlib.Path
        Directories containing HLS composites, terrain parameters, or other
        raster predictors.
    output_path : pathlib.Path
        Destination excluded from discovery when it is inside an input root.
    recursive : bool
        Search nested directories when true; otherwise inspect direct children.

    Returns
    -------
    list of pathlib.Path
        Sorted, absolute, deduplicated ``.tif`` and ``.tiff`` paths.

    Raises
    ------
    FileNotFoundError
        If an input directory is missing or no input rasters are found.
    OSError
        If a directory cannot be enumerated.
    """
    output = output_path.resolve()
    paths: set[Path] = set()
    for directory in input_dirs:
        if not directory.is_dir():
            raise FileNotFoundError(f"input directory not found: {directory}")
        iterator = directory.rglob("*") if recursive else directory.iterdir()
        paths.update(
            path.resolve()
            for path in iterator
            if path.is_file()
            and path.suffix.lower() in {".tif", ".tiff"}
            and path.resolve() != output
        )
    if not paths:
        raise FileNotFoundError(
            f"no GeoTIFF inputs found in {[str(path) for path in input_dirs]}"
        )
    return sorted(paths)


def _unnamed_band_names(path: Path, count: int) -> list[str]:
    """Infer safe names for bands that have no GDAL description.

    Parameters
    ----------
    path : pathlib.Path
        Source file whose stem supplies fallback context.
    count : int
        Number of bands in the source dataset.

    Returns
    -------
    list of str
        One name per source band. Recognized six- and thirteen-band HLS files
        receive canonical HLS names; ambiguous layouts receive positional
        names scoped by filename.

    Notes
    -----
    The caller guarantees ``count`` is positive.
    """
    if count == 1:
        return [canonical_name(path.stem)]
    if "hls" in path.stem.lower() and count == len(MODEL_HLS_BANDS):
        return list(MODEL_HLS_BANDS)
    if "hls" in path.stem.lower() and count == len(HLS_BAND_ORDER):
        return list(HLS_BAND_ORDER)
    return [f"{path.stem}_band_{index:02d}" for index in range(1, count + 1)]


def inspect_channels(paths: Sequence[Path]) -> list[Channel]:
    """Inventory every source band and establish deterministic model order.

    Parameters
    ----------
    paths : sequence of pathlib.Path
        Raster files to inspect. Multi-band files contribute every band.

    Returns
    -------
    list of Channel
        HLS channels in canonical spectral order, then terrain channels in
        canonical parameter order, then unknown channels alphabetically.

    Raises
    ------
    RuntimeError
        If GDAL cannot open an input raster.
    ValueError
        If a raster has no bands or two inputs resolve to the same channel
        name, which would make checkpoint layout ambiguous.
    """
    channels = []
    for path in paths:
        dataset = gdal.Open(str(path))
        if dataset is None:
            raise RuntimeError(f"could not open input raster: {path}")
        try:
            if dataset.RasterCount < 1:
                raise ValueError(f"input raster has no bands: {path}")
            inferred = _unnamed_band_names(path, dataset.RasterCount)
            for index in range(1, dataset.RasterCount + 1):
                description = dataset.GetRasterBand(index).GetDescription().strip()
                name = canonical_name(description) if description else inferred[index - 1]
                channels.append(Channel(name, path, index))
        finally:
            dataset = None

    duplicates: dict[str, list[Channel]] = {}
    for channel in channels:
        duplicates.setdefault(channel.name.lower(), []).append(channel)
    repeated = {name: values for name, values in duplicates.items() if len(values) > 1}
    if repeated:
        details = ", ".join(
            f"{name}: {[f'{item.path.name}:{item.band}' for item in values]}"
            for name, values in sorted(repeated.items())
        )
        raise ValueError(f"duplicate channel names are ambiguous: {details}")

    hls_rank = {name.lower(): index for index, name in enumerate(HLS_BAND_ORDER)}
    terrain_rank = {
        name.lower(): index for index, name in enumerate(TERRAIN_BAND_ORDER)
    }

    def order(channel: Channel) -> tuple[int, int, str, str, int]:
        """Build a stable sort key for one discovered channel.

        Parameters
        ----------
        channel : Channel
            Channel to rank against known HLS and terrain orders.

        Returns
        -------
        tuple
            Group rank, canonical rank, fallback name, path, and band index.

        Notes
        -----
        This nested helper only reads precomputed ranking dictionaries.
        """
        key = channel.name.lower()
        if key in hls_rank:
            return 0, hls_rank[key], "", str(channel.path), channel.band
        if key in terrain_rank:
            return 1, terrain_rank[key], "", str(channel.path), channel.band
        return 2, 0, key, str(channel.path), channel.band

    return sorted(channels, key=order)


def select_channels(
    channels: Sequence[Channel],
    requested: Sequence[str] | None,
) -> list[Channel]:
    """Apply an optional explicit channel subset and output order.

    Parameters
    ----------
    channels : sequence of Channel
        Available unique channels from :func:`inspect_channels`.
    requested : sequence of str or None
        User-requested channel names. ``None`` or an empty sequence keeps the
        canonical discovered order.

    Returns
    -------
    list of Channel
        Selected channels, following explicit request order when provided.

    Raises
    ------
    ValueError
        If a requested channel is absent or requested more than once.
    """
    if not requested:
        return list(channels)
    by_name = {channel.name.lower(): channel for channel in channels}
    normalized = [canonical_name(name).lower() for name in requested]
    missing = [name for name, key in zip(requested, normalized) if key not in by_name]
    if missing:
        raise ValueError(
            f"requested channels not found: {missing}; available channels are "
            f"{[channel.name for channel in channels]}"
        )
    if len(set(normalized)) != len(normalized):
        raise ValueError("--select-bands contains duplicate channel names")
    return [by_name[key] for key in normalized]


def reference_grid(path: Path) -> Grid:
    """Read the reference raster's exact CRS, extent, and dimensions.

    Parameters
    ----------
    path : pathlib.Path
        Raster whose grid every input band will be warped onto.

    Returns
    -------
    Grid
        Validated north-up output-grid definition.

    Raises
    ------
    FileNotFoundError
        If the reference path does not exist.
    RuntimeError
        If GDAL cannot open the reference raster.
    ValueError
        If it lacks a CRS, is rotated, or is not north-up.
    """
    if not path.is_file():
        raise FileNotFoundError(f"reference raster not found: {path}")
    dataset = gdal.Open(str(path))
    if dataset is None:
        raise RuntimeError(f"could not open reference raster: {path}")
    try:
        projection = dataset.GetProjection()
        transform = dataset.GetGeoTransform()
        if not projection:
            raise ValueError(f"reference raster has no CRS: {path}")
        if transform[2] != 0 or transform[4] != 0:
            raise ValueError("rotated reference grids are not supported")
        if transform[1] <= 0 or transform[5] >= 0:
            raise ValueError("reference raster must be a north-up grid")
        left = transform[0]
        top = transform[3]
        right = left + dataset.RasterXSize * transform[1]
        bottom = top + dataset.RasterYSize * transform[5]
        return Grid(
            projection,
            (left, bottom, right, top),
            dataset.RasterXSize,
            dataset.RasterYSize,
        )
    finally:
        dataset = None


def stack_parameters(
    input_dirs: Sequence[Path],
    output_path: Path,
    select_bands: Sequence[str] | None = None,
    reference: Path | None = None,
    nodata: float = -9999.0,
    resampling: str = "nearest",
    recursive: bool = False,
    overwrite: bool = False,
) -> Path:
    """Align and stack all selected predictor bands into one GeoTIFF.

    The function creates one lightweight VRT per source band, warps those VRTs
    to an exact reference grid, combines them as separate channels, and then
    atomically publishes a compressed Float32 GeoTIFF. Source arrays are never
    loaded together in Python memory.

    Parameters
    ----------
    input_dirs : sequence of pathlib.Path
        Directories containing all predictor GeoTIFFs to include.
    output_path : pathlib.Path
        Destination multi-band GeoTIFF.
    select_bands : sequence of str or None, optional
        Optional subset; supplied order becomes output band order.
    reference : pathlib.Path or None, optional
        Raster defining the exact output grid. The first canonically ordered
        channel is used when omitted.
    nodata : float, optional
        Common Float32 destination nodata value.
    resampling : {"nearest", "bilinear", "cubic"}, optional
        GDAL algorithm used while aligning each band.
    recursive : bool, optional
        Search nested input directories.
    overwrite : bool, optional
        Permit atomic replacement of an existing destination.

    Returns
    -------
    pathlib.Path
        ``output_path`` after the completed stack has been published.

    Raises
    ------
    FileExistsError
        If the output exists and ``overwrite`` is false.
    FileNotFoundError
        If inputs or the reference raster are missing.
    ValueError
        If channel names are ambiguous, selection is invalid, resampling is
        unknown, or the reference grid is unsuitable.
    RuntimeError
        If GDAL cannot open, align, combine, or write a raster.
    OSError
        If output directories/files cannot be created or atomically replaced.
    """
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"output already exists: {output_path}; use --overwrite")
    if resampling not in RESAMPLING:
        raise ValueError(
            f"unknown resampling method {resampling!r}; choose from {tuple(RESAMPLING)}"
        )
    paths = find_inputs(input_dirs, output_path, recursive)
    channels = select_channels(inspect_channels(paths), select_bands)
    grid = reference_grid(reference or channels[0].path)

    print(f"Stacking {len(channels)} channels on the grid from {reference or channels[0].path}")
    for index, channel in enumerate(channels, start=1):
        print(f"  Band {index:2d}: {channel.name} ({channel.path.name}:{channel.band})")

    token = f"stack_parameters_{os.getpid()}_{uuid.uuid4().hex}"
    virtual_paths: list[str] = []
    datasets: list[gdal.Dataset] = []
    aligned: list[gdal.Dataset] = []
    selected = warped = None
    combined = output = None
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    try:
        for index, channel in enumerate(channels):
            selected_path = f"/vsimem/{token}_selected_{index}.vrt"
            aligned_path = f"/vsimem/{token}_aligned_{index}.vrt"
            virtual_paths.extend((selected_path, aligned_path))

            selected = gdal.Translate(
                selected_path,
                str(channel.path),
                options=gdal.TranslateOptions(format="VRT", bandList=[channel.band]),
            )
            if selected is None:
                raise RuntimeError(
                    f"GDAL could not select {channel.path} band {channel.band}"
                )
            datasets.append(selected)
            warped = gdal.Warp(
                aligned_path,
                selected,
                options=gdal.WarpOptions(
                    format="VRT",
                    outputBounds=grid.bounds,
                    width=grid.width,
                    height=grid.height,
                    dstSRS=grid.projection,
                    outputType=gdal.GDT_Float32,
                    dstNodata=nodata,
                    resampleAlg=RESAMPLING[resampling],
                    multithread=True,
                    warpOptions=["NUM_THREADS=ALL_CPUS"],
                ),
            )
            if warped is None:
                raise RuntimeError(f"GDAL could not align channel {channel.name}")
            warped.GetRasterBand(1).SetDescription(channel.name)
            datasets.append(warped)
            aligned.append(warped)

        stack_path = f"/vsimem/{token}_stack.vrt"
        virtual_paths.append(stack_path)
        combined = gdal.BuildVRT(
            stack_path,
            aligned,
            options=gdal.BuildVRTOptions(separate=True),
        )
        if combined is None:
            raise RuntimeError("GDAL could not build the multi-band VRT")
        for index, channel in enumerate(channels, start=1):
            combined.GetRasterBand(index).SetDescription(channel.name)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary.unlink(missing_ok=True)
        output = gdal.Translate(
            str(temporary),
            combined,
            options=gdal.TranslateOptions(
                format="GTiff",
                outputType=gdal.GDT_Float32,
                noData=nodata,
                creationOptions=[
                    "TILED=YES",
                    "COMPRESS=ZSTD",
                    "ZSTD_LEVEL=9",
                    "PREDICTOR=3",
                    "BIGTIFF=IF_SAFER",
                    "NUM_THREADS=ALL_CPUS",
                ],
            ),
        )
        if output is None:
            raise RuntimeError(f"GDAL could not write stack: {output_path}")
        for index, channel in enumerate(channels, start=1):
            output.GetRasterBand(index).SetDescription(channel.name)
        output.FlushCache()
        output = None
        os.replace(temporary, output_path)
    except Exception:
        output = None
        temporary.unlink(missing_ok=True)
        raise
    finally:
        selected = warped = None
        combined = None
        aligned.clear()
        datasets.clear()
        for path in reversed(virtual_paths):
            try:
                gdal.Unlink(path)
            except RuntimeError:
                pass

    print(f"Wrote {len(channels)}-band parameter stack: {output_path}")
    return output_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse parameter-stacking command-line options.

    Parameters
    ----------
    argv : sequence of str or None, optional
        Explicit arguments; ``None`` reads process arguments.

    Returns
    -------
    argparse.Namespace
        Parsed input roots, grid, selection, encoding, and overwrite options.

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
        "--input-dir",
        type=Path,
        action="append",
        required=True,
        help="input directory; repeat to combine HLS and terrain directories",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--select-bands",
        help="comma-separated channel names; their order becomes output order",
    )
    parser.add_argument(
        "--reference",
        type=Path,
        help="raster whose exact grid is used (default: first ordered channel)",
    )
    parser.add_argument("--nodata", type=float, default=-9999.0)
    parser.add_argument("--resampling", choices=tuple(RESAMPLING), default="nearest")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Resolve CLI selections and build one complete parameter stack.

    Parameters
    ----------
    argv : sequence of str or None, optional
        Command-line arguments forwarded to :func:`parse_args`.

    Returns
    -------
    None
        The stacked GeoTIFF is written to ``--output``.

    Raises
    ------
    FileExistsError
        If the destination exists without ``--overwrite``.
    FileNotFoundError
        If inputs or the reference raster are missing.
    ValueError
        If channel discovery, selection, or grid validation fails.
    RuntimeError
        If GDAL cannot produce the stack.
    """
    args = parse_args(argv)
    selected = (
        [name.strip() for name in args.select_bands.split(",") if name.strip()]
        if args.select_bands
        else None
    )
    stack_parameters(
        args.input_dir,
        args.output,
        select_bands=selected,
        reference=args.reference,
        nodata=args.nodata,
        resampling=args.resampling,
        recursive=args.recursive,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    main()
