"""Render a finalized soil-moisture GeoTIFF as a publication-ready PNG."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from osgeo import gdal, osr

gdal.UseExceptions()


def render_prediction(
    source: Path,
    output: Path,
    title: str,
    *,
    max_pixels: int = 4000,
    smooth_sigma: float = 0.0,
) -> Path:
    """Render a decimated, nodata-aware preview without changing the GeoTIFF.

    Parameters
    ----------
    source : pathlib.Path
        Final, ecoregion-cropped single-band prediction GeoTIFF.
    output : pathlib.Path
        PNG destination.
    title : str
        Figure title.
    max_pixels : int, optional
        Maximum pixels along the preview's longest raster axis.
    smooth_sigma : float, optional
        Cosmetic Gaussian sigma on the decimated preview. This never alters
        the authoritative GeoTIFF; zero disables smoothing.

    Returns
    -------
    pathlib.Path
        Written PNG.

    Raises
    ------
    FileNotFoundError
        If ``source`` is missing.
    ValueError
        If options, raster dimensions, CRS, or finite values are invalid.
    RuntimeError
        If GDAL cannot open or read the raster.
    ImportError
        If positive smoothing is requested without SciPy being available.
    OSError
        If the PNG directory or file cannot be written.
    """
    if not source.is_file():
        raise FileNotFoundError(f"final prediction not found: {source}")
    if max_pixels <= 0 or smooth_sigma < 0:
        raise ValueError("max_pixels must be positive and smooth_sigma non-negative")
    dataset = gdal.Open(str(source))
    if dataset is None:
        raise RuntimeError(f"could not open final prediction: {source}")
    try:
        if dataset.RasterCount != 1:
            raise ValueError("PNG rendering requires a single-band prediction raster")
        if not dataset.GetProjection():
            raise ValueError(f"final prediction has no CRS: {source}")
        scale = max(1, math.ceil(max(dataset.RasterXSize, dataset.RasterYSize) / max_pixels))
        width = max(1, dataset.RasterXSize // scale)
        height = max(1, dataset.RasterYSize // scale)
        data = dataset.GetRasterBand(1).ReadAsArray(
            buf_xsize=width,
            buf_ysize=height,
            resample_alg=gdal.GRIORA_Average,
        )
        transform = dataset.GetGeoTransform()
        projection = dataset.GetProjection()
        raster_width, raster_height = dataset.RasterXSize, dataset.RasterYSize
    finally:
        dataset = None
    if data is None:
        raise RuntimeError(f"could not read final prediction: {source}")
    data = data.astype(np.float32, copy=False)
    valid = np.isfinite(data)
    if not valid.any():
        raise ValueError(f"final prediction contains no finite values: {source}")
    if smooth_sigma:
        from scipy.ndimage import gaussian_filter

        values = np.where(valid, data, 0.0)
        support = gaussian_filter(valid.astype(np.float32), smooth_sigma)
        smoothed = gaussian_filter(values, smooth_sigma)
        data = np.divide(
            smoothed,
            support,
            out=np.full_like(smoothed, np.nan),
            where=support > 1e-6,
        )
        data[~valid] = np.nan

    finite = data[np.isfinite(data)]
    vmin, vmax = np.percentile(finite, (1, 99))
    if not vmin < vmax:
        vmin, vmax = float(finite.min()), float(finite.max()) + 1e-6
    left, top = transform[0], transform[3]
    right = left + raster_width * transform[1]
    bottom = top + raster_height * transform[5]
    spatial_ref = osr.SpatialReference(wkt=projection)
    geographic = bool(spatial_ref.IsGeographic())

    figure, axis = plt.subplots(figsize=(8, 10))
    image = axis.imshow(
        np.ma.masked_invalid(data),
        cmap="viridis",
        extent=(left, right, bottom, top),
        origin="upper",
        vmin=float(vmin),
        vmax=float(vmax),
        interpolation="nearest",
    )
    axis.set_title(title)
    axis.set_xlabel("Longitude" if geographic else "X")
    axis.set_ylabel("Latitude" if geographic else "Y")
    colorbar = figure.colorbar(image, ax=axis, fraction=0.035, pad=0.03)
    colorbar.set_label("Predicted soil moisture (m³/m³)")
    figure.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=300, bbox_inches="tight")
    plt.close(figure)
    return output


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse GeoTIFF-to-PNG rendering options.

    Parameters
    ----------
    argv : list of str or None, optional
        Explicit arguments; ``None`` reads process arguments.

    Returns
    -------
    argparse.Namespace
        Parsed paths, title, resolution cap, and smoothing sigma.

    Raises
    ------
    SystemExit
        Raised by ``argparse`` for invalid options or ``--help``.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--title", default="Predicted soil moisture")
    parser.add_argument("--max-pixels", type=int, default=4000)
    parser.add_argument("--smooth-sigma", type=float, default=0.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Render the requested finalized prediction and report its output path.

    Parameters
    ----------
    argv : list of str or None, optional
        Arguments forwarded to :func:`parse_args`.

    Returns
    -------
    None
        The PNG path is printed after successful rendering.

    Raises
    ------
    FileNotFoundError, ValueError, RuntimeError, ImportError, OSError
        Propagated from :func:`render_prediction`.
    """
    args = parse_args(argv)
    output = render_prediction(
        args.input,
        args.output,
        args.title,
        max_pixels=args.max_pixels,
        smooth_sigma=args.smooth_sigma,
    )
    print(f"Wrote prediction PNG: {output}", flush=True)


if __name__ == "__main__":
    main()
