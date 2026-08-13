"""Small, reusable primitives for seam-free overlapping raster inference."""

from __future__ import annotations

import numpy as np


def window_starts(total: int, size: int, stride: int) -> list[int]:
    """Return sliding-window origins that cover an axis through its far edge.

    Parameters
    ----------
    total : int
        Full axis length in pixels.
    size : int
        Window length in pixels.
    stride : int
        Positive step between consecutive windows.

    Returns
    -------
    list of int
        Sorted zero-based starts. The final window is anchored to the far edge
        whenever a regular stride would otherwise leave pixels uncovered.

    Raises
    ------
    ValueError
        If any dimension is non-positive or ``stride`` exceeds ``size``.
    """
    if total <= 0 or size <= 0 or stride <= 0:
        raise ValueError("total, size, and stride must be positive")
    if stride > size:
        raise ValueError("stride cannot exceed window size")
    starts = list(range(0, max(total - size, 0) + 1, stride))
    final = max(0, total - size)
    if not starts or starts[-1] != final:
        starts.append(final)
    return starts


def feather_weights(
    height: int,
    width: int,
    edge_floor: float = 1e-3,
) -> np.ndarray:
    """Create a two-dimensional Hann feathering surface for tile blending.

    Overlapping predictions receive the most weight near their centers and
    smoothly taper toward their edges. A small non-zero edge floor preserves
    the outside border of a mosaic where only one inference window exists.

    Parameters
    ----------
    height, width : int
        Positive output-window dimensions.
    edge_floor : float, optional
        Minimum one-dimensional weight in ``[0, 1)``.

    Returns
    -------
    numpy.ndarray
        Float32 ``[height, width]`` weights.

    Raises
    ------
    ValueError
        If dimensions or ``edge_floor`` are invalid.
    """
    if height <= 0 or width <= 0:
        raise ValueError("weight dimensions must be positive")
    if not 0 <= edge_floor < 1:
        raise ValueError("edge_floor must be in [0, 1)")

    def axis_weights(length: int) -> np.ndarray:
        """Build one Hann axis with a non-zero boundary floor.

        Parameters
        ----------
        length : int
            Positive axis length validated by the outer function.

        Returns
        -------
        numpy.ndarray
            Float32 weights of shape ``[length]``.
        """
        weights = np.hanning(length) if length > 1 else np.ones(1)
        return np.maximum(weights, edge_floor).astype(np.float32)

    return np.outer(axis_weights(height), axis_weights(width)).astype(np.float32)
