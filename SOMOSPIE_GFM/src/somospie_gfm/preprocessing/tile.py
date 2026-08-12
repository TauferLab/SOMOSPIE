"""Reserved entry point for prepared-raster tiling.

The GFM preprocessing package currently consumes tiles produced by the
workflow outside this module, using the filename convention
``tile_r<row>_c<column>.tif``. No public tiling API is defined here because the
required edge, overlap, padding, and nodata policies have not yet been fixed by
the pipeline contract. Keeping this module explicitly documented avoids
mistaking an empty file for a working preprocessing stage.

Implement tiling here only after those policies are specified; downstream
``prune_tiles_to_ecoregion``, ``attach_targets``, ``compute_band_stats``, and
``build_aligned_terrain_map`` depend on a regular north-up lattice and stable
row/column filenames.
"""
