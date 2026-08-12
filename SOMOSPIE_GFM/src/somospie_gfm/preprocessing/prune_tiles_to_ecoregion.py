"""Remove prepared tiles that lie entirely outside an ecoregion.

Tile footprints are derived from the regular row/column lattice and checked
against sampled rasters before use. Tiles that touch or overlap the ecoregion
are kept whole. The command is a dry run unless --apply is supplied.
"""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
from osgeo import gdal
from shapely.geometry import box
from shapely.strtree import STRtree

try:
    from .produce_ecoregion_terrain import find_shapefile
except ImportError:
    from produce_ecoregion_terrain import find_shapefile

gdal.UseExceptions()

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SHAPEFILES_ROOT = PROJECT_ROOT / "resources" / "shapefiles"
TILE_RE = re.compile(r"tile_r(\d+)_c(\d+)\.tif$", re.IGNORECASE)


@dataclass(frozen=True)
class PruneReport:
    """Summarize the scope and effect of one pruning run.

    Attributes
    ----------
    total : int
        Prepared tiles examined.
    kept : int
        Tiles touching or overlapping the selected ecoregion.
    removed : int
        Tiles outside the ecoregion.
    bytes_removed : int
        Total size of outside tiles, whether deleted or only proposed.
    applied : bool
        Whether deletion actually occurred instead of a dry run.
    """

    total: int
    kept: int
    removed: int
    bytes_removed: int
    applied: bool

    def summary(self) -> str:
        """Format counts, percentage, and recoverable storage for display.

        Returns
        -------
        str
            One-line dry-run or applied summary.

        Notes
        -----
        Empty runs report a zero percentage instead of dividing by zero.
        """
        percentage = 100 * self.removed / self.total if self.total else 0
        action = "deleted" if self.applied else "would delete"
        return (
            f"{self.total} tiles: {self.kept} overlap the ecoregion; "
            f"{action} {self.removed} ({percentage:.1f}%), "
            f"freeing {self.bytes_removed / 1e9:.2f} GB"
        )


def _tile_row_col(path: Path) -> tuple[int, int]:
    """Parse lattice row and column indices from a prepared-tile filename.

    Parameters
    ----------
    path : pathlib.Path
        Tile named ``tile_r<row>_c<column>.tif``.

    Returns
    -------
    tuple of int
        Zero- or one-based row/column values exactly as encoded.

    Raises
    ------
    ValueError
        If the basename does not follow the required convention.
    """
    match = TILE_RE.fullmatch(path.name)
    if match is None:
        raise ValueError(f"invalid tile filename: {path.name}")
    return int(match.group(1)), int(match.group(2))


def _open_tile(path: Path):
    """Open one prepared tile through a consistent error boundary.

    Parameters
    ----------
    path : pathlib.Path
        Raster to open read-only.

    Returns
    -------
    osgeo.gdal.Dataset
        Open dataset owned by the caller.

    Raises
    ------
    RuntimeError
        If GDAL cannot open the tile.
    """
    dataset = gdal.Open(str(path))
    if dataset is None:
        raise RuntimeError(f"could not open tile: {path}")
    return dataset


def tile_footprints(tiles: list[Path]) -> tuple[np.ndarray, str]:
    """Return tile bounds and their shared CRS.

    Bounds are calculated from one reference tile and the row/column encoded
    in every filename. A sample is opened to verify that the tiles really do
    form the expected uniform, north-up lattice.

    Parameters
    ----------
    tiles : list of pathlib.Path
        Sorted prepared tiles following the row/column filename convention.

    Returns
    -------
    tuple
        Float64 ``[n_tiles, 4]`` bounds in left/bottom/right/top order and the
        shared CRS WKT.

    Raises
    ------
    ValueError
        If the list is empty, filenames are invalid, CRS/grid is unsuitable,
        or sampled tiles do not follow the inferred lattice.
    RuntimeError
        If GDAL cannot open a sampled tile.
    """
    if not tiles:
        raise ValueError("at least one tile is required")

    positions = np.asarray([_tile_row_col(tile) for tile in tiles], dtype=np.int64)
    reference = _open_tile(tiles[0])
    transform = reference.GetGeoTransform()
    projection = reference.GetProjection()
    width, height = reference.RasterXSize, reference.RasterYSize
    reference = None

    if not projection:
        raise ValueError(f"{tiles[0]} has no CRS")
    if transform[2] != 0 or transform[4] != 0:
        raise ValueError("rotated tile grids are not supported")
    if transform[1] <= 0 or transform[5] >= 0:
        raise ValueError("expected a north-up grid with positive x and negative y resolution")

    tile_width = width * transform[1]
    tile_height = height * abs(transform[5])
    first_row, first_col = positions[0]
    left = transform[0] + (positions[:, 1] - first_col) * tile_width
    top = transform[3] - (positions[:, 0] - first_row) * tile_height

    sample_indices = np.unique(
        np.linspace(0, len(tiles) - 1, min(5, len(tiles)), dtype=int)
    )
    tolerance = max(abs(transform[1]), abs(transform[5])) * 1e-6
    for index in sample_indices:
        dataset = _open_tile(tiles[index])
        actual_transform = dataset.GetGeoTransform()
        actual_projection = dataset.GetProjection()
        actual_size = (dataset.RasterXSize, dataset.RasterYSize)
        dataset = None

        expected_origin = (left[index], top[index])
        actual_origin = (actual_transform[0], actual_transform[3])
        uniform = (
            actual_size == (width, height)
            and actual_projection == projection
            and np.allclose(actual_transform[1:3], transform[1:3], atol=tolerance, rtol=0)
            and np.allclose(actual_transform[4:6], transform[4:6], atol=tolerance, rtol=0)
            and np.allclose(actual_origin, expected_origin, atol=tolerance, rtol=0)
        )
        if not uniform:
            raise ValueError(
                f"{tiles[index].name} does not match the regular tile lattice"
            )

    bounds = np.column_stack(
        (left, top - tile_height, left + tile_width, top)
    )
    return bounds, projection


def ecoregion_geometry(
    shapefile: Path,
    code: str,
    code_field: str,
    tile_crs: str,
):
    """Select, dissolve, and project one ecoregion polygon to tile space.

    Parameters
    ----------
    shapefile : pathlib.Path
        Ecoregion vector dataset.
    code : str
        Region code to select.
    code_field : str
        Attribute column holding the codes.
    tile_crs : str
        Destination CRS WKT shared by prepared tiles.

    Returns
    -------
    shapely geometry
        Non-empty union of all selected features in ``tile_crs``.

    Raises
    ------
    SystemExit
        If the shapefile/field/CRS/code is missing or geometry is empty.
    OSError, ValueError
        Propagated by GeoPandas for unreadable vectors or reprojection failure.
    """
    if not shapefile.is_file():
        raise SystemExit(f"ecoregion shapefile not found: {shapefile}")

    frame = gpd.read_file(shapefile)
    if code_field not in frame.columns:
        raise SystemExit(
            f"{code_field!r} is not a field in {shapefile}; "
            f"available fields: {list(frame.columns)}"
        )
    if frame.crs is None:
        raise SystemExit(f"ecoregion shapefile has no CRS: {shapefile}")

    selected = frame[frame[code_field].astype(str) == str(code)]
    if selected.empty:
        raise SystemExit(
            f"no features with {code_field} == {code!r} in {shapefile}"
        )

    projected = selected.to_crs(tile_crs).geometry
    geometry = (
        projected.union_all()
        if hasattr(projected, "union_all")
        else projected.unary_union
    )
    if geometry.is_empty:
        raise SystemExit(f"ecoregion {code!r} has empty geometry")
    return geometry


def _intersecting_indices(footprints: list, geometry) -> set[int]:
    """Query tile footprints intersecting an ecoregion across Shapely versions.

    Parameters
    ----------
    footprints : list of shapely geometry
        Tile boxes in the same CRS as ``geometry``.
    geometry : shapely geometry
        Dissolved ecoregion polygon.

    Returns
    -------
    set of int
        Indices of footprints that touch or overlap the region.

    Raises
    ------
    ValueError
        Propagated if geometries are invalid for spatial indexing/predicates.
    """
    tree = STRtree(footprints)
    try:
        return set(tree.query(geometry, predicate="intersects").tolist())
    except TypeError:
        # Shapely 1 returns geometry objects and has no predicate argument.
        indices = {id(footprint): index for index, footprint in enumerate(footprints)}
        return {
            indices[id(candidate)]
            for candidate in tree.query(geometry)
            if candidate.intersects(geometry)
        }


def prune(
    tiles_root: Path,
    ecoregion: str,
    shapefile: Path,
    code_field: str,
    manifest: Path,
    apply: bool,
) -> PruneReport:
    """Identify and optionally delete prepared tiles outside one ecoregion.

    Parameters
    ----------
    tiles_root : pathlib.Path
        Directory containing ``tile_r*_c*.tif`` files.
    ecoregion : str
        Code selected from the shapefile.
    shapefile : pathlib.Path
        Ecoregion polygons.
    code_field : str
        Attribute field containing ``ecoregion``.
    manifest : pathlib.Path
        Atomic newline-delimited record of tiles selected for deletion.
    apply : bool
        Delete listed files when true; otherwise perform a dry run.

    Returns
    -------
    PruneReport
        Counts, byte total, and whether deletion was applied.

    Raises
    ------
    SystemExit
        If no tiles exist, the ecoregion is invalid, or every tile would be
        deleted (a safety refusal).
    ValueError, RuntimeError
        If filenames/grid/geometry or GDAL reads are invalid.
    OSError
        If metadata, manifest publication, or deletion fails.
    """
    tiles = sorted(tiles_root.glob("tile_r*_c*.tif"))
    if not tiles:
        raise SystemExit(f"no tile_r*_c*.tif files under {tiles_root}")

    bounds, tile_crs = tile_footprints(tiles)
    geometry = ecoregion_geometry(shapefile, ecoregion, code_field, tile_crs)
    footprints = [box(*tile_bounds) for tile_bounds in bounds]
    keep = _intersecting_indices(footprints, geometry)
    remove = [tile for index, tile in enumerate(tiles) if index not in keep]

    if len(remove) == len(tiles):
        raise SystemExit(
            "every tile was marked for deletion; check the ecoregion code and "
            "coordinate reference systems. Refusing to delete."
        )

    bytes_removed = sum(tile.stat().st_size for tile in remove)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    temporary = manifest.with_suffix(manifest.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        temporary.write_text(
            "".join(f"{tile}\n" for tile in remove),
            encoding="utf-8",
        )
        os.replace(temporary, manifest)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    if apply:
        for tile in remove:
            tile.unlink()

    return PruneReport(
        total=len(tiles),
        kept=len(keep),
        removed=len(remove),
        bytes_removed=bytes_removed,
        applied=apply,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse ecoregion tile-pruning options.

    Parameters
    ----------
    argv : list of str or None, optional
        Explicit arguments; ``None`` reads process arguments.

    Returns
    -------
    argparse.Namespace
        Parsed tile root, ecoregion selection, manifest, and apply flag.

    Raises
    ------
    SystemExit
        Raised by ``argparse`` for invalid options or ``--help``.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--tiles-root",
        type=Path,
        required=True,
        help="directory containing prepared tile_r*_c*.tif files",
    )
    parser.add_argument(
        "--ecoregion",
        required=True,
        help="ecoregion code, for example 6.2.13",
    )
    parser.add_argument(
        "--shapefile",
        type=Path,
        help="ecoregion shapefile (default: downloaded CEC Level III file)",
    )
    parser.add_argument(
        "--code-field",
        default="NA_L3CODE",
        help="shapefile field containing the ecoregion code",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="delete manifest path (default: prune_<ecoregion>.txt)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="delete listed tiles; otherwise perform a dry run",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Resolve the Level III shapefile and run safe tile pruning.

    Parameters
    ----------
    argv : list of str or None, optional
        Command-line arguments forwarded to :func:`parse_args`.

    Returns
    -------
    None
        A deletion manifest and summary are always written; tiles are deleted
        only with ``--apply``.

    Raises
    ------
    FileNotFoundError
        If automatic shapefile discovery finds no downloaded Level III data.
    SystemExit
        If tile/ecoregion validation triggers a safety refusal.
    ValueError, RuntimeError, OSError
        If raster/vector processing, manifest writing, or deletion fails.
    """
    args = parse_args(argv)
    manifest = args.manifest or Path(f"prune_{args.ecoregion}.txt")
    shapefile = args.shapefile or find_shapefile(DEFAULT_SHAPEFILES_ROOT, 3)
    report = prune(
        args.tiles_root,
        args.ecoregion,
        shapefile,
        args.code_field,
        manifest,
        args.apply,
    )
    print(f"Manifest: {manifest}", flush=True)
    print(report.summary(), flush=True)
    if not args.apply:
        print(
            "Dry run: no tiles were deleted. Re-run with --apply to remove them.",
            flush=True,
        )


if __name__ == "__main__":
    main()
