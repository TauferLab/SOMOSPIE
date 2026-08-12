#!/usr/bin/env python3
"""
Build a monthly mean soil-moisture CSV from ESA CCI daily NetCDF files.

Input files are expected under: <input_root>/<year>/*.nc
Output CSV: <input_root>/<year>_ESA_monthly.csv with columns:
    x, y, X1, X2, ... X12   (longitude, latitude, monthly mean)

If the output already exists and --force is not set, the script is a no-op.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import List, Sequence

import numpy as np
import pandas as pd
from osgeo import gdal

try:
    import xarray as xr
except Exception:
    xr = None

gdal.UseExceptions()
USE_XARRAY_IO = xr is not None


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """
    Parse command-line arguments for the monthly aggregation.

    Parameters
    ----------
    argv : sequence of str or None, optional
        Explicit arguments; ``None`` reads process arguments.

    Returns
    -------
    argparse.Namespace
        Parsed arguments. `output` is None unless given, in which case
        `main` derives it from `input_root` and `year`.

    Raises
    ------
    SystemExit
        Raised by ``argparse`` for invalid options or ``--help``.
    """
    parser = argparse.ArgumentParser(
        description="Aggregate ESA CCI daily soil-moisture NetCDFs into monthly mean CSV."
    )
    default_root = Path(__file__).resolve().parents[1] / "data" / "ESA_CCI"
    parser.add_argument(
        "--input-root",
        type=Path,
        default=default_root,
        help="Root directory containing year folders.",
    )
    parser.add_argument("--year", type=int, required=True, help="Year to process (e.g., 2019).")
    parser.add_argument(
        "--variable",
        default="sm",
        help="NetCDF variable name for soil moisture (default: sm).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output CSV path (default: <input_root>/<year>_ESA_monthly.csv).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recompute even if the output file already exists.",
    )
    return parser.parse_args(argv)


def month_files(year_dir: Path, year: int, month: int) -> List[Path]:
    """
    List the ESA CCI daily NetCDF files belonging to one month.

    Parameters
    ----------
    year_dir : pathlib.Path
        Directory holding the daily files for `year`.
    year : int
        Four-digit year, used to build the filename glob.
    month : int
        Month number, 1-12.

    Returns
    -------
    list of pathlib.Path
        Matching files in sorted order; empty when the month has no data.

    Raises
    ------
    OSError
        If directory enumeration fails.
    """
    pattern = f"ESACCI-SOILMOISTURE-L3S-SSMV-COMBINED-{year}{month:02d}*.nc"
    return sorted(year_dir.glob(pattern))


def _nc_subdataset(path: Path, var: str) -> str:
    """
    Build the GDAL subdataset identifier for one NetCDF variable.

    Parameters
    ----------
    path : pathlib.Path
        NetCDF file to address.
    var : str
        Variable name inside the file, e.g. ``"sm"``.

    Returns
    -------
    str
        A ``NETCDF:"<path>":<var>`` string accepted by `gdal.Open`.

    Notes
    -----
    The function only formats an identifier and performs no filesystem access.
    """
    return f'NETCDF:"{path}":{var}'


def _load_grid_gdal(sample_file: Path, var: str) -> tuple[np.ndarray, np.ndarray]:
    """
    Reconstruct the lon/lat cell-centre grid from a NetCDF geotransform.

    GDAL fallback for `load_grid`, used when the xarray backend is
    unavailable. Coordinates are taken at pixel centres (the +0.5 offset).

    Parameters
    ----------
    sample_file : pathlib.Path
        Any daily file from the year; all share one grid.
    var : str
        Soil-moisture variable name.

    Returns
    -------
    tuple of numpy.ndarray
        `(lon_grid, lat_grid)`, both shaped like the raster.

    Raises
    ------
    RuntimeError
        If GDAL cannot open the file or the variable.
    """
    ds = gdal.Open(_nc_subdataset(sample_file, var))
    if ds is None:
        raise RuntimeError(
            f"Could not open {sample_file} variable '{var}' with GDAL."
        )
    gt = ds.GetGeoTransform()
    width, height = ds.RasterXSize, ds.RasterYSize
    cols = np.arange(width, dtype="float64") + 0.5
    rows = np.arange(height, dtype="float64") + 0.5
    col_grid, row_grid = np.meshgrid(cols, rows)
    lon_grid = gt[0] + col_grid * gt[1] + row_grid * gt[2]
    lat_grid = gt[3] + col_grid * gt[4] + row_grid * gt[5]
    ds = None
    return lon_grid, lat_grid


def _read_gdal_sm_array(path: Path, var: str) -> np.ndarray:
    """
    Read one daily soil-moisture raster, converting nodata to NaN.

    Parameters
    ----------
    path : pathlib.Path
        Daily NetCDF file.
    var : str
        Soil-moisture variable name.

    Returns
    -------
    numpy.ndarray
        Float32 array with the declared nodata value replaced by NaN, so
        `numpy.nanmean` can skip it downstream.

    Raises
    ------
    RuntimeError
        If GDAL cannot open the file or the variable.
    """
    ds = gdal.Open(_nc_subdataset(path, var))
    if ds is None:
        raise RuntimeError(f"Could not open {path} variable '{var}' with GDAL.")
    band = ds.GetRasterBand(1)
    arr = band.ReadAsArray().astype("float32")
    nodata = band.GetNoDataValue()
    if nodata is not None:
        arr[arr == nodata] = np.nan
    ds = None
    return arr


def load_grid(sample_file: Path, var: str) -> tuple[np.ndarray, np.ndarray]:
    """
    Return the lon/lat grid for a year of ESA CCI files.

    Prefers xarray's coordinate variables. On any failure the module-level
    `USE_XARRAY_IO` flag is cleared so the rest of the run skips xarray, and
    the call falls back to `_load_grid_gdal`.

    Parameters
    ----------
    sample_file : pathlib.Path
        Any daily file from the year; all share one grid.
    var : str
        Soil-moisture variable name, used only by the GDAL fallback.

    Returns
    -------
    tuple of numpy.ndarray
        `(lon_grid, lat_grid)`, both shaped like the raster.

    Raises
    ------
    RuntimeError
        If xarray cannot supply coordinates and GDAL cannot open/read the
        fallback variable.
    """
    global USE_XARRAY_IO
    if USE_XARRAY_IO:
        try:
            with xr.open_dataset(sample_file) as ds:
                if "lat" not in ds or "lon" not in ds:
                    raise ValueError(f"{sample_file} missing lat/lon coordinates.")
                lats = ds["lat"].values
                lons = ds["lon"].values
            lon_grid, lat_grid = np.meshgrid(lons, lats)
            return lon_grid, lat_grid
        except Exception as exc:
            USE_XARRAY_IO = False
            print(
                f"[warn] xarray backend unavailable for NetCDF read "
                f"({exc.__class__.__name__}: {exc}); "
                "falling back to GDAL."
            )
    return _load_grid_gdal(sample_file, var=var)


def monthly_mean(files: List[Path], var: str) -> np.ndarray | None:
    """
    Average a month's daily rasters into one mean field.

    Missing days are skipped rather than propagated, so a cell's mean is
    taken over whatever days observed it. Falls back to GDAL on xarray
    failure, clearing `USE_XARRAY_IO` for the remainder of the run.

    Parameters
    ----------
    files : list of pathlib.Path
        Daily files for one month, as returned by `month_files`.
    var : str
        Soil-moisture variable name.

    Returns
    -------
    numpy.ndarray or None
        Mean field shaped like the grid, or None when `files` is empty.

    Raises
    ------
    RuntimeError
        If xarray fails and GDAL cannot open/read a daily variable.
    ValueError
        If daily arrays have inconsistent shapes and cannot be stacked.
    """
    if not files:
        return None
    global USE_XARRAY_IO
    if USE_XARRAY_IO:
        try:
            with xr.open_mfdataset(files, combine="by_coords") as ds:
                if var not in ds:
                    raise ValueError(f"Variable '{var}' not found in {files[0].name}")
                da = ds[var]
                if "time" in da.dims:
                    da = da.mean(dim="time", skipna=True)
                arr = da.values
            return arr
        except Exception as exc:
            USE_XARRAY_IO = False
            print(
                f"[warn] xarray backend unavailable for NetCDF read "
                f"({exc.__class__.__name__}: {exc}); "
                "falling back to GDAL."
            )

    stacks = [_read_gdal_sm_array(path, var) for path in files]
    if not stacks:
        return None
    return np.nanmean(np.stack(stacks, axis=0), axis=0)


def build_monthly_df(year_dir: Path, year: int, var: str) -> pd.DataFrame:
    """
    Assemble the twelve monthly means into the wide CSV table.

    Months with no files become all-NaN columns; rows NaN across every month
    are dropped, which removes ocean and permanently masked cells.

    Parameters
    ----------
    year_dir : pathlib.Path
        Directory holding the year's daily NetCDF files.
    year : int
        Four-digit year to process.
    var : str
        Soil-moisture variable name.

    Returns
    -------
    pandas.DataFrame
        Columns ``x``, ``y``, ``X1`` … ``X12`` — longitude, latitude, and one
        mean per month. Downstream code selects the target month by name.

    Raises
    ------
    FileNotFoundError
        If `year_dir` contains no ESA CCI files for `year`.
    """
    # Find at least one file to define the grid
    sample_files = sorted(year_dir.glob(f"ESACCI-SOILMOISTURE-L3S-SSMV-COMBINED-{year}*.nc"))
    if not sample_files:
        raise FileNotFoundError(f"No ESA CCI NetCDF files found in {year_dir} for {year}.")

    lon_grid, lat_grid = load_grid(sample_files[0], var)
    base = pd.DataFrame({"x": lon_grid.ravel(), "y": lat_grid.ravel()})

    for month in range(1, 13):
        files = month_files(year_dir, year, month)
        arr = monthly_mean(files, var)
        col = f"X{month}"
        if arr is None:
            base[col] = np.nan
            continue
        base[col] = arr.ravel()
    # Drop rows where all monthly values are NaN
    month_cols = [f"X{m}" for m in range(1, 13)]
    base = base.dropna(subset=month_cols, how="all")
    return base


def main(argv: Sequence[str] | None = None) -> None:
    """
    Aggregate one year of ESA CCI dailies into a monthly mean CSV.

    A no-op when the output already exists and ``--force`` was not passed.

    Parameters
    ----------
    argv : sequence of str or None, optional
        Command-line arguments forwarded to :func:`parse_args`.

    Returns
    -------
    None
        A wide monthly CSV and status message are produced as side effects.

    Raises
    ------
    FileNotFoundError
        If the expected ``<input_root>/<year>`` directory is missing.
    RuntimeError, ValueError
        If NetCDF variables cannot be read or monthly grids are inconsistent.
    OSError
        If the output directory, temporary CSV, or atomic replacement fails.
    """
    args = parse_args(argv)
    output = args.output or (args.input_root / f"{args.year}_ESA_monthly.csv")
    year_dir = args.input_root / str(args.year)

    if output.exists() and not args.force:
        print(f"{output} already exists; skipping (use --force to recompute).")
        return
    if not year_dir.is_dir():
        raise FileNotFoundError(f"Expected ESA CCI files under {year_dir}")

    df = build_monthly_df(year_dir, args.year, args.variable)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        df.to_csv(temporary, index=False)
        os.replace(temporary, output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    print(f"Wrote monthly means to {output}")


if __name__ == "__main__":
    main()
