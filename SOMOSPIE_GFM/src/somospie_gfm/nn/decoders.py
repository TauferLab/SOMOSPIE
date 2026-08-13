"""Dense decoders for Prithvi soil-moisture fine-tuning.

Prithvi encodes an image as a coarse grid of patch features. The decoders in
this module turn that grid into one soil-moisture prediction per output pixel.
They depend only on PyTorch; in particular, the UPerNet-style decoder does not
require ``segmentation_models_pytorch``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import torch
import torch.nn as nn
import torch.nn.functional as F

SUPPORTED_DECODER_TYPES = (
    "patch_upsample",
    "conv_upsample_4stage",
    "upernet",
)


def _output_size(tile_size: int, output_size: int) -> int:
    """Resolve and validate a decoder's square output dimension.

    Parameters
    ----------
    tile_size : int
        Input tile width and height in pixels.
    output_size : int
        Requested output dimension; zero selects ``tile_size``.

    Returns
    -------
    int
        Positive output width and height.

    Raises
    ------
    ValueError
        If either effective dimension is not positive.
    """
    resolved = output_size or tile_size
    if tile_size <= 0 or resolved <= 0:
        raise ValueError("tile_size and output_size must be positive")
    return resolved


class PatchUpsampleDecoder(nn.Module):
    """Project each Prithvi patch to a scalar and interpolate to pixels.

    This is the smallest decoder and provides a useful baseline. It learns only
    a normalized 1x1 projection before bilinear upsampling, so most modeling
    capacity remains in the backbone.

    Parameters
    ----------
    embed_dim : int
        Feature channels emitted by the backbone.
    tile_size : int
        Input tile dimension in pixels.
    dropout : float
        Channel dropout probability before the scalar projection.
    output_size : int, optional
        Output dimension; zero preserves ``tile_size``.

    Raises
    ------
    ValueError
        If dimensions or dropout probability are invalid.
    """

    def __init__(
        self,
        embed_dim: int,
        tile_size: int,
        dropout: float,
        output_size: int = 0,
    ) -> None:
        super().__init__()
        if embed_dim <= 0:
            raise ValueError("embed_dim must be positive")
        if not 0 <= dropout < 1:
            raise ValueError("dropout must be in [0, 1)")
        self.output_size = _output_size(tile_size, output_size)
        self.projection = nn.Sequential(
            nn.BatchNorm2d(embed_dim),
            nn.Dropout2d(dropout),
            nn.Conv2d(embed_dim, 1, kernel_size=1),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        """Decode one ``[B, E, h, w]`` patch-feature map.

        Returns
        -------
        torch.Tensor
            Dense ``[B, H, W]`` predictions.

        Raises
        ------
        ValueError
            If ``features`` is not four-dimensional.
        """
        if features.ndim != 4:
            raise ValueError(
                f"expected [batch, channels, height, width], got {features.shape}"
            )
        prediction = self.projection(features)
        prediction = F.interpolate(
            prediction,
            size=(self.output_size, self.output_size),
            mode="bilinear",
            align_corners=False,
        )
        return prediction.squeeze(1)


class ConvUpsampleDecoder(nn.Module):
    """Learn a convolutional path from patch features to dense predictions.

    Parameters
    ----------
    embed_dim : int
        Feature channels emitted by the backbone.
    tile_size : int
        Input tile dimension in pixels.
    patch_grid_size : int
        Width and height of the Prithvi patch grid.
    channels : int
        Hidden decoder channels.
    dropout : float
        Spatial dropout probability after each refinement block.
    output_size : int, optional
        Output dimension; zero preserves ``tile_size``.

    Raises
    ------
    ValueError
        If a dimension is non-positive or dropout is outside ``[0, 1)``.
    """

    def __init__(
        self,
        embed_dim: int,
        tile_size: int,
        patch_grid_size: int,
        channels: int,
        dropout: float,
        output_size: int = 0,
    ) -> None:
        super().__init__()
        if min(embed_dim, patch_grid_size, channels) <= 0:
            raise ValueError("embed_dim, patch_grid_size, and channels must be positive")
        if not 0 <= dropout < 1:
            raise ValueError("dropout must be in [0, 1)")
        self.output_size = _output_size(tile_size, output_size)
        scale = max(1, math.ceil(self.output_size / patch_grid_size))
        stages = max(1, math.ceil(math.log2(scale)))

        blocks: list[nn.Module] = [
            nn.Conv2d(embed_dim, channels, kernel_size=1),
            nn.GELU(),
        ]
        for _ in range(stages):
            blocks.extend(
                (
                    nn.Upsample(scale_factor=2, mode="bilinear", align_corners=False),
                    nn.Conv2d(channels, channels, kernel_size=3, padding=1),
                    nn.GELU(),
                    nn.Dropout2d(dropout),
                    nn.Conv2d(channels, channels, kernel_size=3, padding=1),
                    nn.GELU(),
                )
            )
        blocks.append(nn.Conv2d(channels, 1, kernel_size=1))
        self.decoder = nn.Sequential(*blocks)

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        """Decode one patch-feature map to ``[batch, height, width]``.

        Raises
        ------
        ValueError
            If ``features`` is not four-dimensional.
        """
        if features.ndim != 4:
            raise ValueError(
                f"expected [batch, channels, height, width], got {features.shape}"
            )
        prediction = self.decoder(features)
        if prediction.shape[-2:] != (self.output_size, self.output_size):
            prediction = F.interpolate(
                prediction,
                size=(self.output_size, self.output_size),
                mode="bilinear",
                align_corners=False,
            )
        return prediction.squeeze(1)


class PyramidPooling(nn.Module):
    """Aggregate local and pooled context for the deepest feature map."""

    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        branch_channels = max(1, out_channels // 4)
        self.branches = nn.ModuleList(
            nn.Sequential(
                nn.AdaptiveAvgPool2d(size),
                nn.Conv2d(in_channels, branch_channels, kernel_size=1),
                nn.GELU(),
            )
            for size in (1, 2, 3, 6)
        )
        self.fuse = nn.Sequential(
            nn.Conv2d(
                in_channels + branch_channels * len(self.branches),
                out_channels,
                kernel_size=3,
                padding=1,
            ),
            nn.GELU(),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        """Return context-enriched features at the input spatial size."""
        size = features.shape[-2:]
        pooled = [
            F.interpolate(branch(features), size=size, mode="bilinear", align_corners=False)
            for branch in self.branches
        ]
        return self.fuse(torch.cat((features, *pooled), dim=1))


class UPerNetDecoder(nn.Module):
    """Fuse several Prithvi layers with a compact UPerNet-style pyramid.

    Prithvi's transformer layers share one patch resolution. This decoder
    constructs progressively scaled feature levels, applies pyramid pooling to
    the deepest level, and combines them through a top-down feature pyramid.

    Parameters
    ----------
    embed_dim, tile_size, patch_grid_size, channels, dropout
        Backbone and decoder dimensions shared with
        :func:`build_pixel_decoder`.
    output_size : int, optional
        Output dimension; zero preserves ``tile_size``.
    encoder_depth : int, optional
        Number of backbone feature maps to fuse.

    Raises
    ------
    ValueError
        If dimensions or dropout are invalid.
    """

    def __init__(
        self,
        embed_dim: int,
        tile_size: int,
        patch_grid_size: int,
        channels: int,
        dropout: float,
        output_size: int = 0,
        encoder_depth: int = 4,
    ) -> None:
        super().__init__()
        del patch_grid_size
        if min(embed_dim, channels, encoder_depth) <= 0:
            raise ValueError("embed_dim, channels, and encoder_depth must be positive")
        if not 0 <= dropout < 1:
            raise ValueError("dropout must be in [0, 1)")
        self.output_size = _output_size(tile_size, output_size)
        self.encoder_depth = encoder_depth
        self.lateral = nn.ModuleList(
            nn.Conv2d(embed_dim, channels, kernel_size=1)
            for _ in range(encoder_depth)
        )
        self.pool = PyramidPooling(embed_dim, channels)
        self.refine = nn.ModuleList(
            nn.Sequential(
                nn.Conv2d(channels, channels, kernel_size=3, padding=1),
                nn.GELU(),
            )
            for _ in range(encoder_depth - 1)
        )
        self.head = nn.Sequential(
            nn.Conv2d(channels * encoder_depth, channels, kernel_size=3, padding=1),
            nn.GELU(),
            nn.Dropout2d(dropout),
            nn.Conv2d(channels, 1, kernel_size=1),
        )

    def _select(self, features: Sequence[torch.Tensor]) -> list[torch.Tensor]:
        """Return exactly ``encoder_depth`` feature maps, repeating if needed."""
        if not features:
            raise ValueError("UPerNetDecoder requires at least one feature map")
        selected = list(features[-self.encoder_depth :])
        while len(selected) < self.encoder_depth:
            selected.insert(0, selected[0])
        return selected

    def forward(
        self,
        features: torch.Tensor | Sequence[torch.Tensor],
    ) -> torch.Tensor:
        """Fuse feature maps and return dense ``[B, H, W]`` predictions.

        Raises
        ------
        ValueError
            If no feature maps are supplied or a feature is not four-dimensional.
        """
        selected = self._select([features] if isinstance(features, torch.Tensor) else features)
        if any(feature.ndim != 4 for feature in selected):
            raise ValueError("all UPerNet feature maps must have shape [B, E, h, w]")

        base_h, base_w = selected[-1].shape[-2:]
        pyramid: list[torch.Tensor] = []
        for level, (feature, projection) in enumerate(zip(selected, self.lateral)):
            scale = 2 ** (self.encoder_depth - level - 1)
            size = (base_h * scale, base_w * scale)
            projected = projection(feature)
            if projected.shape[-2:] != size:
                projected = F.interpolate(
                    projected, size=size, mode="bilinear", align_corners=False
                )
            pyramid.append(projected)
        pyramid[-1] = self.pool(selected[-1])

        for index in range(len(pyramid) - 2, -1, -1):
            top_down = F.interpolate(
                pyramid[index + 1],
                size=pyramid[index].shape[-2:],
                mode="bilinear",
                align_corners=False,
            )
            pyramid[index] = self.refine[index](pyramid[index] + top_down)

        target_size = pyramid[0].shape[-2:]
        fused = torch.cat(
            [
                level
                if level.shape[-2:] == target_size
                else F.interpolate(
                    level, size=target_size, mode="bilinear", align_corners=False
                )
                for level in pyramid
            ],
            dim=1,
        )
        prediction = self.head(fused)
        prediction = F.interpolate(
            prediction,
            size=(self.output_size, self.output_size),
            mode="bilinear",
            align_corners=False,
        )
        return prediction.squeeze(1)


def build_pixel_decoder(
    decoder_type: str,
    embed_dim: int,
    tile_size: int,
    patch_grid_size: int,
    channels: int,
    dropout: float,
    output_size: int = 0,
) -> nn.Module:
    """Construct a dense decoder from validated architecture settings.

    Parameters
    ----------
    decoder_type : str
        One of :data:`SUPPORTED_DECODER_TYPES`.
    embed_dim, tile_size, patch_grid_size, channels : int
        Backbone feature width and spatial/hidden dimensions.
    dropout : float
        Decoder dropout probability.
    output_size : int, optional
        Square output dimension; zero preserves ``tile_size``.

    Returns
    -------
    torch.nn.Module
        Configured decoder returning ``[batch, height, width]``.

    Raises
    ------
    ValueError
        If ``decoder_type`` is unsupported or a constructor setting is invalid.
    """
    arguments = {
        "embed_dim": embed_dim,
        "tile_size": tile_size,
        "dropout": dropout,
        "output_size": output_size,
    }
    if decoder_type == "patch_upsample":
        return PatchUpsampleDecoder(**arguments)
    if decoder_type == "conv_upsample_4stage":
        return ConvUpsampleDecoder(
            patch_grid_size=patch_grid_size,
            channels=channels,
            **arguments,
        )
    if decoder_type == "upernet":
        return UPerNetDecoder(
            patch_grid_size=patch_grid_size,
            channels=channels,
            **arguments,
        )
    raise ValueError(
        f"unsupported decoder_type {decoder_type!r}; "
        f"choose one of {SUPPORTED_DECODER_TYPES}"
    )
