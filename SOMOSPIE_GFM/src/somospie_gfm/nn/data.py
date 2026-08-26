"""Read prepared SOMOSPIE-GFM artifacts for neural-network workflows.

This module deliberately performs no reprojection, terrain warping, target
joining, or statistics estimation. It consumes the CSV manifest produced by
``attach_targets.py``, the JSON artifact produced by ``compute_band_stats.py``,
and optional aligned terrain GeoTIFFs from ``build_aligned_terrain_map.py``.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import torch
from osgeo import gdal
from torch.utils.data import Dataset

from somospie_gfm.preprocessing.build_aligned_terrain_map import AlignedTerrain
from somospie_gfm.preprocessing.compute_band_stats import (
    read_fused_tile,
    resolve_band_indices,
)

gdal.UseExceptions()


@dataclass(frozen=True)
class TileRecord:
    """One prepared tile and its manifest metadata.

    Attributes
    ----------
    path : pathlib.Path
        Absolute prepared HLS GeoTIFF path.
    region, split : str
        Region label and manifest split assignment.
    target : float or None
        Tile-level soil moisture, or ``None`` for an unlabelled tile.
    width, height : int
        Raster dimensions recorded during target attachment.
    row : dict
        Complete original manifest row, retained for inference summaries.
    """

    path: Path
    region: str
    split: str
    target: float | None
    width: int
    height: int
    row: dict[str, str]


@dataclass(frozen=True)
class NormalizationStats:
    """Validated per-channel normalization metadata.

    Attributes
    ----------
    channel_names : tuple of str
        Complete HLS-plus-terrain channel order.
    hls_bands : tuple of str
        HLS subset read from prepared tiles before terrain is appended.
    mean, std : numpy.ndarray
        Float32 vectors parallel to ``channel_names``.
    artifact : dict
        Original JSON object stored in training checkpoints.
    """

    channel_names: tuple[str, ...]
    hls_bands: tuple[str, ...]
    mean: np.ndarray
    std: np.ndarray
    artifact: dict[str, Any]

    @property
    def terrain_channels(self) -> int:
        """Return the number of aligned-terrain channels expected per tile.

        Returns
        -------
        int
            Total channels minus the leading HLS channels.
        """
        return len(self.channel_names) - len(self.hls_bands)


def load_manifest(path: Path) -> list[TileRecord]:
    """Load and validate a target manifest without opening raster pixels.

    Parameters
    ----------
    path : pathlib.Path
        CSV produced by :mod:`somospie_gfm.preprocessing.attach_targets`.

    Returns
    -------
    list of TileRecord
        Manifest records in source order.

    Raises
    ------
    FileNotFoundError
        If the manifest or a referenced tile is missing.
    ValueError
        If required columns, numeric dimensions, target values, or rows are
        invalid.
    csv.Error, OSError
        If the manifest cannot be read.
    """
    if not path.is_file():
        raise FileNotFoundError(f"target manifest not found: {path}")
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        required = {"tile", "region", "split", "target", "width", "height"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"manifest {path} is missing columns {sorted(missing)}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"manifest is empty: {path}")

    records: list[TileRecord] = []
    for number, row in enumerate(rows, start=2):
        tile = Path(row["tile"]).expanduser().resolve()
        if not tile.is_file():
            raise FileNotFoundError(f"manifest row {number} tile not found: {tile}")
        try:
            width, height = int(row["width"]), int(row["height"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"manifest row {number} has invalid dimensions") from exc
        if width <= 0 or height <= 0:
            raise ValueError(f"manifest row {number} has non-positive dimensions")

        raw_target = (row.get("target") or "").strip()
        target: float | None
        if not raw_target:
            target = None
        else:
            try:
                parsed = float(raw_target)
            except ValueError as exc:
                raise ValueError(
                    f"manifest row {number} has invalid target {raw_target!r}"
                ) from exc
            target = parsed if math.isfinite(parsed) else None
        records.append(
            TileRecord(
                path=tile,
                region=(row.get("region") or "").strip(),
                split=(row.get("split") or "").strip(),
                target=target,
                width=width,
                height=height,
                row=dict(row),
            )
        )
    return records


def select_records(
    records: Sequence[TileRecord],
    splits: Sequence[str] | None,
    *,
    require_targets: bool,
    max_records: int = 0,
) -> list[TileRecord]:
    """Select deterministic manifest rows for training or inference.

    Parameters
    ----------
    records : sequence of TileRecord
        Full manifest contents.
    splits : sequence of str or None
        Accepted split labels; ``None`` accepts all rows.
    require_targets : bool
        Drop rows without finite supervision when true.
    max_records : int, optional
        Positive cap applied after filtering; zero keeps all rows.

    Returns
    -------
    list of TileRecord
        Filtered records in manifest order.

    Raises
    ------
    ValueError
        If no records remain or ``max_records`` is negative.
    """
    if max_records < 0:
        raise ValueError("max_records cannot be negative")
    accepted = set(splits) if splits is not None else None
    selected = [
        record
        for record in records
        if (accepted is None or record.split in accepted)
        and (not require_targets or record.target is not None)
    ]
    if max_records:
        selected = selected[:max_records]
    if not selected:
        suffix = f" for split(s) {sorted(accepted)}" if accepted is not None else ""
        raise ValueError(f"no usable manifest records{suffix}")
    return selected


def load_stats(path: Path) -> NormalizationStats:
    """Load a normalization JSON and validate its channel contract.

    Parameters
    ----------
    path : pathlib.Path
        JSON produced by ``compute_band_stats.py``.

    Returns
    -------
    NormalizationStats
        Immutable channel names and float32 mean/std vectors.

    Raises
    ------
    FileNotFoundError
        If ``path`` is missing.
    json.JSONDecodeError, OSError
        If the JSON cannot be read.
    KeyError, TypeError, ValueError
        If required fields are absent, lengths differ, values are non-finite,
        or any standard deviation is non-positive.
    """
    if not path.is_file():
        raise FileNotFoundError(f"band statistics not found: {path}")
    artifact = json.loads(path.read_text(encoding="utf-8"))
    key = artifact["key"]
    names = tuple(str(name) for name in key["channel_names"])
    bands = tuple(str(name) for name in key["bands"])
    mean = np.asarray(artifact["band_mean"], dtype=np.float32)
    std = np.asarray(artifact["band_std"], dtype=np.float32)
    if not names or not bands:
        raise ValueError("statistics channel_names and bands must not be empty")
    if not len(names) == len(mean) == len(std):
        raise ValueError("statistics channel names, means, and stds have different lengths")
    if tuple(names[: len(bands)]) != bands:
        raise ValueError("statistics channels must begin with the requested HLS bands")
    if not np.isfinite(mean).all() or not np.isfinite(std).all():
        raise ValueError("statistics means and stds must be finite")
    if (std <= 0).any():
        raise ValueError("statistics standard deviations must be positive")
    return NormalizationStats(names, bands, mean, std, artifact)


def stats_from_checkpoint(artifact: dict[str, Any]) -> NormalizationStats:
    """Validate an embedded statistics artifact without temporary files.

    Parameters
    ----------
    artifact : dict
        Checkpoint ``normalization_stats`` mapping using the same schema as
        :func:`load_stats`.

    Returns
    -------
    NormalizationStats
        Validated channel order and float32 normalization moments.

    Raises
    ------
    KeyError, TypeError, ValueError
        If the checkpoint artifact violates the normal statistics schema.
    """
    key = artifact["key"]
    names = tuple(str(name) for name in key["channel_names"])
    bands = tuple(str(name) for name in key["bands"])
    mean = np.asarray(artifact["band_mean"], dtype=np.float32)
    std = np.asarray(artifact["band_std"], dtype=np.float32)
    if not names or not bands or tuple(names[: len(bands)]) != bands:
        raise ValueError("checkpoint contains an invalid channel layout")
    if not len(names) == len(mean) == len(std):
        raise ValueError("checkpoint statistics lengths do not match")
    if not np.isfinite(mean).all() or not np.isfinite(std).all() or (std <= 0).any():
        raise ValueError("checkpoint contains invalid normalization moments")
    return NormalizationStats(names, bands, mean, std, dict(artifact))


def open_aligned_terrain(path: Path) -> AlignedTerrain:
    """Read metadata for an already-aligned terrain GeoTIFF.

    Parameters
    ----------
    path : pathlib.Path
        Output from ``build_aligned_terrain_map.py``.

    Returns
    -------
    AlignedTerrain
        Metadata used for windowed terrain reads.

    Raises
    ------
    FileNotFoundError
        If the aligned raster is missing.
    RuntimeError
        If GDAL cannot open it.
    ValueError
        If it has no bands or bands declare inconsistent nodata values.
    """
    path = path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"aligned terrain not found: {path}")
    dataset = gdal.Open(str(path))
    if dataset is None:
        raise RuntimeError(f"could not open aligned terrain: {path}")
    try:
        count = dataset.RasterCount
        if count < 1:
            raise ValueError(f"aligned terrain has no bands: {path}")
        nodata_values = [
            dataset.GetRasterBand(index).GetNoDataValue()
            for index in range(1, count + 1)
        ]
        declared = [value for value in nodata_values if value is not None]
        if declared and (
            len(declared) != count
            or any(
                not np.isclose(value, declared[0], equal_nan=True)
                for value in declared[1:]
            )
        ):
            raise ValueError(f"aligned terrain bands use inconsistent nodata: {path}")
        return AlignedTerrain(
            path=path,
            gt=tuple(dataset.GetGeoTransform()),
            width=dataset.RasterXSize,
            height=dataset.RasterYSize,
            n_bands=count,
            nodata=declared[0] if declared else None,
        )
    finally:
        dataset = None


def _region_key(value: str) -> str:
    """Normalize a region label for case-insensitive terrain-map matching.

    Parameters
    ----------
    value : str
        Ecoregion label from a manifest or configuration mapping.

    Returns
    -------
    str
        Lowercase label with surrounding whitespace removed and spaces
        replaced by underscores.
    """
    return value.strip().lower().replace(" ", "_")


class TerrainResolver:
    """Resolve manifest regions to pre-aligned terrain mosaics.

    Parameters
    ----------
    expected_channels : int
        Terrain channels required by the normalization statistics.
    shared : pathlib.Path or None
        One aligned mosaic used for every record.
    mapping : dict of str to pathlib.Path or None
        Region-specific aligned mosaics. Exact normalized region names are
        preferred, with tile path components accepted as a fallback.

    Raises
    ------
    ValueError
        If terrain is required but no source is configured, or a configured
        raster has the wrong number of bands.
    FileNotFoundError, RuntimeError
        Propagated while opening aligned rasters.
    """

    def __init__(
        self,
        expected_channels: int,
        shared: Path | None = None,
        mapping: dict[str, Path] | None = None,
    ) -> None:
        """Open and validate every configured aligned-terrain source.

        Parameters
        ----------
        expected_channels : int
            Number of terrain channels required by model statistics.
        shared : pathlib.Path or None, optional
            Single aligned terrain raster used as a fallback.
        mapping : dict of str to pathlib.Path or None, optional
            Region labels mapped to aligned terrain rasters.

        Returns
        -------
        None
            Resolver state and raster metadata are initialized in place.

        Raises
        ------
        ValueError
            If required terrain is absent or a raster has the wrong band count.
        FileNotFoundError, RuntimeError
            If a configured raster is missing or cannot be opened.
        """
        self.expected_channels = expected_channels
        self.shared = open_aligned_terrain(shared) if shared is not None else None
        self.mapping = {
            _region_key(region): open_aligned_terrain(path)
            for region, path in (mapping or {}).items()
        }
        configured = [*self.mapping.values()]
        if self.shared is not None:
            configured.append(self.shared)
        if expected_channels and not configured:
            raise ValueError(
                f"statistics require {expected_channels} terrain channels; "
                "provide --aligned-terrain or --aligned-terrain-map"
            )
        for terrain in configured:
            if terrain.n_bands != expected_channels:
                raise ValueError(
                    f"{terrain.path} has {terrain.n_bands} bands; "
                    f"statistics require {expected_channels}"
                )

    def resolve(self, record: TileRecord) -> AlignedTerrain | None:
        """Return aligned terrain for one tile or ``None`` for HLS-only data.

        Parameters
        ----------
        record : TileRecord
            Manifest record whose region and path select a terrain source.

        Returns
        -------
        AlignedTerrain or None
            Matching aligned raster metadata, or ``None`` when the statistics
            contain no terrain channels.

        Raises
        ------
        ValueError
            If terrain is required and no mapping matches the record.
        """
        if not self.expected_channels:
            return None
        terrain = self.mapping.get(_region_key(record.region))
        if terrain is not None:
            return terrain
        components = {_region_key(component) for component in record.path.parts}
        terrain = next(
            (value for region, value in self.mapping.items() if region in components),
            self.shared,
        )
        if terrain is None:
            raise ValueError(
                f"no aligned terrain mapping matches region {record.region!r} "
                f"for {record.path}"
            )
        return terrain


def load_terrain_map(path: Path | None) -> dict[str, Path] | None:
    """Load an optional JSON region-to-aligned-raster mapping.

    Parameters
    ----------
    path : pathlib.Path or None
        JSON mapping path; ``None`` disables region-specific terrain.

    Returns
    -------
    dict of str to pathlib.Path or None
        Parsed region mapping, or ``None`` when no path was supplied.

    Raises
    ------
    FileNotFoundError
        If a non-null path is missing.
    json.JSONDecodeError, OSError
        If the file cannot be parsed.
    ValueError
        If the JSON is not a string-to-string object.
    """
    if path is None:
        return None
    if not path.is_file():
        raise FileNotFoundError(f"aligned terrain map not found: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(
        isinstance(region, str) and isinstance(raster, str)
        for region, raster in value.items()
    ):
        raise ValueError(f"{path} must map region names to aligned raster paths")
    return {region: Path(raster) for region, raster in value.items()}


def _band_indices(path: Path, bands: Sequence[str]) -> list[int]:
    """Resolve requested HLS channels from one prepared tile header.

    Parameters
    ----------
    path : pathlib.Path
        Prepared multi-band HLS tile to inspect.
    bands : sequence of str
        Canonical HLS band names in the order required by the model.

    Returns
    -------
    list of int
        One-based GDAL band indices corresponding to ``bands``.

    Raises
    ------
    RuntimeError
        If GDAL cannot open the prepared tile.
    ValueError
        If the requested names cannot be matched unambiguously to the raster
        band descriptions.
    """
    dataset = gdal.Open(str(path))
    if dataset is None:
        raise RuntimeError(f"could not open prepared tile: {path}")
    try:
        descriptions = [
            dataset.GetRasterBand(index).GetDescription() or ""
            for index in range(1, dataset.RasterCount + 1)
        ]
        return resolve_band_indices(bands, descriptions, dataset.RasterCount)
    finally:
        dataset = None


class PreparedTileDataset(Dataset):
    """Load normalized HLS-plus-terrain tensors from prepared artifacts.

    Each item is ``(inputs, target, index)``. ``inputs`` has shape
    ``[channels, time=1, height, width]``; missing source pixels are replaced
    with the corresponding channel mean and therefore become zero after
    standardization. ``target`` is NaN for inference-only rows.

    Parameters
    ----------
    records : sequence of TileRecord
        Selected manifest rows.
    stats : NormalizationStats
        Exact channel order and moments used by the model.
    terrain : TerrainResolver
        Resolver for optional pre-aligned terrain windows.
    tile_size : int or None, optional
        Required square input dimension. ``None`` accepts the first row's size
        and still requires all records to match it.

    Raises
    ------
    ValueError
        If records are empty, dimensions differ, or channels do not match.
    RuntimeError
        If GDAL cannot read a tile or aligned-terrain window.
    """

    def __init__(
        self,
        records: Sequence[TileRecord],
        stats: NormalizationStats,
        terrain: TerrainResolver,
        tile_size: int | None = None,
    ) -> None:
        """Validate records and cache their normalization/read contract.

        Parameters
        ----------
        records : sequence of TileRecord
            Manifest records exposed by this dataset.
        stats : NormalizationStats
            Required channel order, means, and standard deviations.
        terrain : TerrainResolver
            Source of optional aligned terrain windows.
        tile_size : int or None, optional
            Required square raster size, inferred from the first record when
            omitted.

        Returns
        -------
        None
            Dataset metadata and band indices are initialized in place.

        Raises
        ------
        ValueError
            If records are empty, dimensions are invalid, or sizes differ.
        RuntimeError
            If the first prepared raster cannot be opened.
        """
        if not records:
            raise ValueError("PreparedTileDataset requires at least one record")
        self.records = list(records)
        self.stats = stats
        self.terrain = terrain
        expected = tile_size or self.records[0].width
        if expected <= 0:
            raise ValueError("tile_size must be positive")
        mismatched = [
            record.path
            for record in self.records
            if record.width != expected or record.height != expected
        ]
        if mismatched:
            raise ValueError(
                f"{len(mismatched)} manifest tile(s) are not {expected}x{expected}; "
                f"first is {mismatched[0]}"
            )
        self.tile_size = expected
        self.band_indices = _band_indices(self.records[0].path, stats.hls_bands)
        self.mean = stats.mean[:, None, None]
        self.std = stats.std[:, None, None]

    def __len__(self) -> int:
        """Return the number of selected manifest records.

        Returns
        -------
        int
            Dataset length used by PyTorch samplers and loaders.
        """
        return len(self.records)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor, int]:
        """Load, normalize, and tensorize one record.

        Parameters
        ----------
        index : int
            Zero-based record index.

        Returns
        -------
        tuple of torch.Tensor, torch.Tensor, int
            Normalized ``[C, 1, H, W]`` input, scalar target (NaN when
            unlabelled), and the original index.

        Raises
        ------
        IndexError
            If ``index`` is outside the selected records.
        ValueError
            If the fused tile shape does not match the statistics contract.
        RuntimeError
            If GDAL cannot read source data.
        """
        record = self.records[index]
        data = read_fused_tile(
            record.path,
            self.band_indices,
            self.terrain.resolve(record),
        )
        expected = (len(self.stats.channel_names), self.tile_size, self.tile_size)
        if data.shape != expected:
            raise ValueError(
                f"fused tile {record.path} has shape {data.shape}, "
                f"expected {expected}"
            )
        normalized = (data - self.mean) / self.std
        normalized[~np.isfinite(normalized)] = 0
        inputs = torch.from_numpy(normalized.astype(np.float32, copy=False)).unsqueeze(1)
        target = float("nan") if record.target is None else record.target
        return inputs, torch.tensor(target, dtype=torch.float32), index
