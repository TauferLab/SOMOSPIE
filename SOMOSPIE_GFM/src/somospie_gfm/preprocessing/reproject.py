"""
Memory-conscious batch reprojection of individual rasters using GDAL.

Takes an input directory of GeoTIFFs, reprojects each one to a target CRS,
and writes the outputs to an output directory without mosaicking them first.
Each raster is streamed through GDAL.Warp to keep memory usage low and
avoid gaps/distortion that can happen when mixing CRSs.
"""

from __future__ import annotations

import argparse
import os
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable, Tuple

warnings.filterwarnings(
    "ignore",
    message="Neither gdal.UseExceptions\\(\\) nor gdal.DontUseExceptions\\(\\).*",
    category=FutureWarning,
)
from osgeo import gdal

gdal.UseExceptions()

# Map CLI names to GDAL resampling enums
RESAMPLING_MAP = {
    "nearest": gdal.GRA_NearestNeighbour,
    "bilinear": gdal.GRA_Bilinear,
    "cubic": gdal.GRA_Cubic,
    "cubicspline": gdal.GRA_CubicSpline,
    "lanczos": gdal.GRA_Lanczos,
    "average": gdal.GRA_Average,
    "mode": gdal.GRA_Mode,
    "max": gdal.GRA_Max,
    "min": gdal.GRA_Min,
    "med": gdal.GRA_Med,
    "q1": gdal.GRA_Q1,
    "q3": gdal.GRA_Q3,
}


def find_rasters(in_dir: Path) -> Iterable[Path]:
    """
    Yield the GeoTIFFs in a directory, in sorted order.

    Non-raster files and subdirectories are skipped; the search is not
    recursive.

    Parameters
    ----------
    in_dir : pathlib.Path
        Directory to scan.

    Yields
    ------
    pathlib.Path
        Each ``.tif`` or ``.tiff`` file found.
    """
    for path in sorted(in_dir.iterdir()):
        if path.suffix.lower() in {".tif", ".tiff"} and path.is_file():
            yield path


def build_output_path(out_dir: Path, src_path: Path, suffix: str = "_reproj") -> Path:
    """
    Derive the output path for one reprojected raster.

    Parameters
    ----------
    out_dir : pathlib.Path
        Destination directory.
    src_path : pathlib.Path
        Source raster, whose stem is reused.
    suffix : str, optional
        Marker appended to the stem, by default ``"_reproj"``.

    Returns
    -------
    pathlib.Path
        ``<out_dir>/<stem><suffix>.tif``.
    """
    stem = src_path.stem
    return out_dir / f"{stem}{suffix}.tif"


def reproject_file(
    src_path: Path,
    out_path: Path,
    dst_crs: str,
    resampling_alg=gdal.GRA_Bilinear,
) -> Tuple[Path, dict]:
    """
    Reproject a single raster to `dst_crs`, streaming through GDAL.Warp.

    The source nodata value is carried through to the destination so masked
    pixels survive resampling. Runs in a worker process when `main` is called
    with more than one worker, so it takes only picklable arguments.

    Parameters
    ----------
    src_path : pathlib.Path
        Raster to reproject.
    out_path : pathlib.Path
        Destination path; parent directories are created as needed.
    dst_crs : str
        Target CRS, e.g. ``"EPSG:4326"``.
    resampling_alg : int, optional
        A GDAL ``GRA_*`` resampling constant, by default bilinear. CLI names
        are mapped to these by `RESAMPLING_MAP`.

    Returns
    -------
    tuple of (pathlib.Path, dict)
        The output path, and a dict of ``crs``, ``width``, ``height``,
        ``count`` read back from the written file.

    Raises
    ------
    FileNotFoundError
        If `src_path` cannot be opened.
    ValueError
        If the source declares no CRS, leaving nothing to reproject from.
    """
    src = gdal.Open(str(src_path))
    if src is None:
        raise FileNotFoundError(f"Could not open {src_path}")
    if src.GetProjectionRef() in ("", None):
        raise ValueError(f"{src_path} has no CRS; cannot reproject.")

    nodata = src.GetRasterBand(1).GetNoDataValue()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    warp_opts = gdal.WarpOptions(
        dstSRS=dst_crs,
        resampleAlg=resampling_alg,
        srcNodata=nodata,
        dstNodata=nodata,
        multithread=True,
        creationOptions=["COMPRESS=ZSTD", "ZSTD_LEVEL=1", "BIGTIFF=YES"],
    )

    gdal.Warp(destNameOrDestDS=str(out_path), srcDSOrSrcDSTab=src, options=warp_opts)

    out_ds = gdal.Open(str(out_path))
    meta = {
        "crs": dst_crs,
        "width": out_ds.RasterXSize,
        "height": out_ds.RasterYSize,
        "count": out_ds.RasterCount,
    }
    out_ds = None

    return out_path, meta


def parse_args(argv=None):
    """
    Parse command-line arguments for the batch reprojection.

    Parameters
    ----------
    argv : list of str, optional
        Argument vector to parse. Defaults to `sys.argv`.

    Returns
    -------
    argparse.Namespace
        Parsed arguments. `workers` defaults to the CPU count.
    """
    parser = argparse.ArgumentParser(
        description="Reproject all GeoTIFFs in a directory to a target CRS, writing one output per input."
    )
    parser.add_argument("input_dir", help="Directory containing input rasters (.tif/.tiff).")
    parser.add_argument("output_dir", help="Directory to write reprojected rasters.")
    parser.add_argument(
        "--dst-crs", default="EPSG:4326", help="Destination CRS (e.g., EPSG:4326)."
    )
    parser.add_argument(
        "--resampling",
        default="bilinear",
        choices=sorted(RESAMPLING_MAP.keys()),
        help="Resampling method for reprojection.",
    )
    parser.add_argument(
        "--visualize",
        action="store_true",
        help="Display a quicklook of the first output raster at the end.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=os.cpu_count() or 1,
        help="Number of parallel workers (processes) to use.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    """
    Reproject every raster in a directory, optionally in parallel.

    With one worker the rasters are processed in order in this process;
    otherwise they are dispatched to a `ProcessPoolExecutor` and logged as
    they complete, so output order is nondeterministic.

    Parameters
    ----------
    argv : list of str, optional
        Argument vector to parse. Defaults to `sys.argv`.

    Raises
    ------
    FileNotFoundError
        If the input directory is missing or holds no rasters.
    """
    args = parse_args(argv)
    in_dir = Path(args.input_dir)
    out_dir = Path(args.output_dir)
    resampling_alg = RESAMPLING_MAP[args.resampling.lower()]

    if not in_dir.is_dir():
        raise FileNotFoundError(f"Input directory not found: {in_dir}")

    rasters = list(find_rasters(in_dir))
    if not rasters:
        raise FileNotFoundError(f"No .tif/.tiff files found in {in_dir}")

    workers = max(1, int(args.workers))
    print(f"Reprojecting {len(rasters)} rasters from {in_dir} -> {out_dir} ({args.dst_crs}) using {workers} worker(s)")

    outputs = []
    if workers == 1:
        for src_path in rasters:
            out_path = build_output_path(out_dir, src_path)
            print(f"- {src_path.name} -> {out_path.name}")
            reproject_file(src_path, out_path, dst_crs=args.dst_crs, resampling_alg=resampling_alg)
            outputs.append(out_path)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            future_map = {}
            for src_path in rasters:
                out_path = build_output_path(out_dir, src_path)
                print(f"[queue] {src_path.name} -> {out_path.name}")
                fut = pool.submit(reproject_file, src_path, out_path, args.dst_crs, resampling_alg)
                future_map[fut] = out_path
            for fut in as_completed(future_map):
                out_path, _ = fut.result()
                print(f"[done] {out_path.name}")
                outputs.append(out_path)

    print("Done.")

    if args.visualize and outputs:
        show_quicklook(outputs[0])


def show_quicklook(path: Path):
    """
    Show a simple RGB (or single-band) quicklook for a raster.

    Rasters with three or more bands are drawn as RGB from the first three,
    contrast-stretched to the 2nd-98th percentile; anything else is drawn as
    a single grey band.

    Parameters
    ----------
    path : pathlib.Path
        Raster to display.

    Raises
    ------
    FileNotFoundError
        If the raster cannot be opened.
    RuntimeError
        If the raster opens but no data can be read from it.
    """
    import matplotlib.pyplot as plt
    import numpy as np

    ds = gdal.Open(str(path))
    if ds is None:
        raise FileNotFoundError(f"Could not open {path}")

    arr = ds.ReadAsArray()
    if arr is None:
        raise RuntimeError(f"Failed to read data from {path}")

    if arr.ndim == 3 and arr.shape[0] >= 3:
        rgb = arr[:3, :, :].astype(float)
        rgb = np.transpose(rgb, (1, 2, 0))
        low, high = np.percentile(rgb, (2, 98))
        rgb = np.clip((rgb - low) / (high - low + 1e-9), 0, 1)
        plt.imshow(rgb)
    else:
        band = arr if arr.ndim == 2 else arr[0]
        plt.imshow(band, cmap="gray")
    plt.title(f"Quicklook: {path.name}")
    plt.axis("off")
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
