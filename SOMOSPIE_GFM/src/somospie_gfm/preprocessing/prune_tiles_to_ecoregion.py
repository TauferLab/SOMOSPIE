"""Remove prepared tiles that lie entirely outside an ecoregion.

Tile footprints are derived from the regular row/column lattice and checked
against sampled rasters before use. Tiles that touch or overlap the ecoregion
are kept whole. The command is a dry run unless --apply is supplied.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
from osgeo import gdal
from shapely.geometry import box
from shapely.strtree import STRtree

gdal.UseExceptions()

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SHAPEFILE = (
    PACKAGE_ROOT
    / "data"
    / "EPA_ecoregions"
    / "na_cec_eco_l3"
    / "NA_CEC_Eco_Level3.shp"
)
TILE_RE = re.compile(r"tile_r(\d+)_c(\d+)\.tif$", re.IGNORECASE)


@dataclass(frozen=True)
class PruneReport:
    """Summary of a pruning run."""

    total: int
    kept: int
    removed: int
    bytes_removed: int
    applied: bool

    def summary(self) -> str:
        """Return a concise human-readable summary."""
        percentage = 100 * self.removed / self.total if self.total else 0
        action = "deleted" if self.applied else "would delete"
        return (
            f"{self.total} tiles: {self.kept} overlap the ecoregion; "
            f"{action} {self.removed} ({percentage:.1f}%), "
            f"freeing {self.bytes_removed / 1e9:.2f} GB"
        )


def _tile_row_col(path: Path) -> tuple[int, int]:
    """Read a tile's row and column from its filename."""
    match = TILE_RE.fullmatch(path.name)
    if match is None:
        raise ValueError(f"invalid tile filename: {path.name}")
    return int(match.group(1)), int(match.group(2))


def _open_tile(path: Path):
    """Open a tile or raise a useful error."""
    dataset = gdal.Open(str(path))
    if dataset is None:
        raise RuntimeError(f"could not open tile: {path}")
    return dataset


def tile_footprints(tiles: list[Path]) -> tuple[np.ndarray, str]:
    """Return tile bounds and their shared CRS.

    Bounds are calculated from one reference tile and the row/column encoded
    in every filename. A sample is opened to verify that the tiles really do
    form the expected uniform, north-up lattice.
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
    """Load one ecoregion, union its features, and project it to the tile CRS."""
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
    """Return footprint indices that intersect geometry."""
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
    """Find and optionally delete tiles that do not touch the ecoregion."""
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
    manifest.write_text(
        "".join(f"{tile}\n" for tile in remove),
        encoding="utf-8",
    )

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
    """Parse command-line arguments."""
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
        default=DEFAULT_SHAPEFILE,
        help=f"ecoregion shapefile (default: {DEFAULT_SHAPEFILE})",
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
    """Prune one prepared-tile directory."""
    args = parse_args(argv)
    manifest = args.manifest or Path(f"prune_{args.ecoregion}.txt")
    report = prune(
        args.tiles_root,
        args.ecoregion,
        args.shapefile,
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
