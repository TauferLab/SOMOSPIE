"""Prithvi backbone wrapper and stable checkpoint configuration.

The wrapper keeps TerraTorch-specific feature handling out of the training and
inference programs. It maps prepared HLS band codes to Prithvi's semantic band
names, leaves terrain channels as new learnable inputs, reshapes patch tokens
to feature maps, and applies a decoder from :mod:`somospie_gfm.nn.decoders`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterator

import torch
import torch.nn as nn

from .decoders import SUPPORTED_DECODER_TYPES, build_pixel_decoder

DEFAULT_BACKBONE = "prithvi_eo_v2_300"
HLS_TO_PRITHVI = {
    "B01": "COASTAL_AEROSOL",
    "B02": "BLUE",
    "B03": "GREEN",
    "B04": "RED",
    "B05": "RED_EDGE_1",
    "B06": "RED_EDGE_2",
    "B07": "RED_EDGE_3",
    "B08": "NIR_BROAD",
    "B8A": "NIR_NARROW",
    "B09": "WATER_VAPOR",
    "B10": "CIRRUS",
    "B11": "SWIR_1",
    "B12": "SWIR_2",
}


@dataclass(frozen=True)
class ModelConfig:
    """Serializable architecture settings stored with every checkpoint.

    Attributes
    ----------
    channel_names : tuple of str
        Fused HLS-plus-terrain channels in dataset order.
    backbone_name : str
        TerraTorch registry key for the Prithvi encoder.
    tile_size, patch_size : int
        Square input dimension and Prithvi spatial patch dimension.
    decoder_type : str
        Dense decoder architecture.
    decoder_channels : int
        Hidden feature width for convolutional decoders.
    decoder_dropout : float
        Decoder dropout probability.
    output_size : int
        Dense output dimension; zero means ``tile_size``.
    drop_path_rate : float
        Stochastic-depth probability inside Prithvi.
    """

    channel_names: tuple[str, ...]
    backbone_name: str = DEFAULT_BACKBONE
    tile_size: int = 256
    patch_size: int = 16
    decoder_type: str = "conv_upsample_4stage"
    decoder_channels: int = 128
    decoder_dropout: float = 0.1
    output_size: int = 0
    drop_path_rate: float = 0.0

    def __post_init__(self) -> None:
        """Validate settings before any large backbone is allocated.

        Returns
        -------
        None
            Validation mutates no fields; successful return confirms that the
            configuration is internally consistent.

        Raises
        ------
        ValueError
            If channel/dimension, decoder, dropout, or patch settings are
            incompatible.
        """
        if not self.channel_names:
            raise ValueError("channel_names must not be empty")
        if len(set(self.channel_names)) != len(self.channel_names):
            raise ValueError("channel_names must be unique")
        if min(self.tile_size, self.patch_size, self.decoder_channels) <= 0:
            raise ValueError("tile_size, patch_size, and decoder_channels must be positive")
        if self.tile_size % self.patch_size:
            raise ValueError("tile_size must be divisible by patch_size")
        if self.output_size < 0:
            raise ValueError("output_size cannot be negative")
        if self.decoder_type not in SUPPORTED_DECODER_TYPES:
            raise ValueError(
                f"unsupported decoder_type {self.decoder_type!r}; "
                f"choose one of {SUPPORTED_DECODER_TYPES}"
            )
        if not 0 <= self.decoder_dropout < 1:
            raise ValueError("decoder_dropout must be in [0, 1)")
        if not 0 <= self.drop_path_rate < 1:
            raise ValueError("drop_path_rate must be in [0, 1)")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON- and torch-checkpoint-friendly configuration mapping.

        Returns
        -------
        dict
            All architecture fields, with ``channel_names`` converted to a list.
        """
        values = asdict(self)
        values["channel_names"] = list(self.channel_names)
        return values

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> "ModelConfig":
        """Rebuild a validated configuration from checkpoint metadata.

        Parameters
        ----------
        values : dict
            Serialized architecture mapping produced by :meth:`to_dict`.

        Returns
        -------
        ModelConfig
            Immutable, validated architecture settings.

        Raises
        ------
        KeyError, TypeError, ValueError
            If required metadata is missing or invalid.
        """
        copied = dict(values)
        copied["channel_names"] = tuple(copied["channel_names"])
        return cls(**copied)


class PrithviSoilMoisture(nn.Module):
    """Pair a TerraTorch Prithvi encoder with a dense regression decoder.

    Parameters
    ----------
    config : ModelConfig
        Complete reproducible architecture configuration.
    pretrained : bool, optional
        Download/load TerraTorch's pretrained Prithvi weights.
    backbone_checkpoint : str or None, optional
        Local Prithvi checkpoint passed to TerraTorch. Useful on offline
        compute nodes; it is honored only when ``pretrained`` is true.
    freeze_backbone : bool, optional
        Disable backbone gradients initially.

    Raises
    ------
    ModuleNotFoundError
        If TerraTorch is unavailable.
    RuntimeError, ValueError
        If TerraTorch cannot build the requested backbone or its feature
        contract is incompatible.
    """

    def __init__(
        self,
        config: ModelConfig,
        *,
        pretrained: bool = True,
        backbone_checkpoint: str | None = None,
        freeze_backbone: bool = False,
    ) -> None:
        """Build the Prithvi backbone and configured dense decoder.

        Parameters
        ----------
        config : ModelConfig
            Complete channel and architecture contract.
        pretrained : bool, optional
            Request TerraTorch pretrained backbone weights.
        backbone_checkpoint : str or None, optional
            Local TerraTorch checkpoint used when pretrained weights are enabled.
        freeze_backbone : bool, optional
            Disable backbone gradients after construction.

        Returns
        -------
        None
            Backbone, decoder, and feature metadata are initialized in place.

        Raises
        ------
        ModuleNotFoundError
            If TerraTorch is not installed.
        RuntimeError, ValueError, AttributeError
            If the requested backbone cannot be built or lacks required metadata.
        """
        super().__init__()
        try:
            from terratorch.registry import BACKBONE_REGISTRY
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "Prithvi training requires TerraTorch in the runtime environment"
            ) from exc

        self.config = config
        bands = [HLS_TO_PRITHVI.get(name.upper(), name) for name in config.channel_names]
        backbone_options: dict[str, Any] = {
            "pretrained": pretrained,
            "bands": bands,
            "num_frames": 1,
            "img_size": config.tile_size,
            "patch_size": (1, config.patch_size, config.patch_size),
            "drop_path": config.drop_path_rate,
        }
        if backbone_checkpoint is not None:
            backbone_options["ckpt_path"] = backbone_checkpoint
        self.backbone = BACKBONE_REGISTRY.build(
            config.backbone_name,
            **backbone_options,
        )
        self.embed_dim = int(getattr(self.backbone, "embed_dim"))
        self.decoder = build_pixel_decoder(
            config.decoder_type,
            embed_dim=self.embed_dim,
            tile_size=config.tile_size,
            patch_grid_size=config.tile_size // config.patch_size,
            channels=config.decoder_channels,
            dropout=config.decoder_dropout,
            output_size=config.output_size,
        )
        if freeze_backbone:
            self.freeze_backbone()

    def freeze_backbone(self) -> None:
        """Disable gradients for every Prithvi backbone parameter in place.

        Returns
        -------
        None
            The backbone parameters' ``requires_grad`` flags are changed as a
            side effect.
        """
        for parameter in self.backbone.parameters():
            parameter.requires_grad_(False)

    def unfreeze_backbone(self) -> None:
        """Enable gradients for every Prithvi backbone parameter in place.

        Returns
        -------
        None
            The backbone parameters' ``requires_grad`` flags are changed as a
            side effect.
        """
        for parameter in self.backbone.parameters():
            parameter.requires_grad_(True)

    def decoder_parameters(self) -> Iterator[nn.Parameter]:
        """Return the decoder parameter iterator for optimizer grouping.

        Returns
        -------
        iterator of torch.nn.Parameter
            Parameters belonging only to the dense decoder.
        """
        return self.decoder.parameters()

    def _feature_maps(self, inputs: torch.Tensor) -> list[torch.Tensor]:
        """Run Prithvi and reshape its token sequences to image grids.

        Parameters
        ----------
        inputs : torch.Tensor
            Normalized input batch in ``[B, C, H, W]`` or
            ``[B, C, T, H, W]`` form.

        Returns
        -------
        list of torch.Tensor
            Spatial feature maps produced by the configured backbone layers.

        Raises
        ------
        ValueError
            If input dimensions/channels or backbone feature output are invalid.
        """
        if inputs.ndim not in (4, 5):
            raise ValueError(f"expected [B,C,H,W] or [B,C,T,H,W], got {inputs.shape}")
        if inputs.shape[1] != len(self.config.channel_names):
            raise ValueError(
                f"model expects {len(self.config.channel_names)} channels, "
                f"received {inputs.shape[1]}"
            )
        features = self.backbone(inputs)
        if isinstance(features, torch.Tensor):
            features = [features]
        if not isinstance(features, (list, tuple)) or not features:
            raise ValueError("Prithvi backbone returned no feature tensors")
        prepare = getattr(self.backbone, "prepare_features_for_image_model", None)
        if prepare is None:
            raise ValueError("Prithvi backbone cannot reshape tokens to image features")
        maps = prepare(list(features))
        if not maps or any(feature.ndim != 4 for feature in maps):
            raise ValueError("Prithvi returned an invalid image-feature pyramid")
        return maps

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        """Predict dense soil moisture for a normalized tile batch.

        Parameters
        ----------
        inputs : torch.Tensor
            Normalized ``[B, C, H, W]`` or ``[B, C, T, H, W]`` inputs.

        Returns
        -------
        torch.Tensor
            ``[batch, output_height, output_width]`` predictions.

        Raises
        ------
        ValueError
            If input shape/channels or backbone feature output are invalid.
        RuntimeError
            If PyTorch or the decoder cannot process the resulting feature maps.
        """
        features = self._feature_maps(inputs)
        decoder_input: torch.Tensor | list[torch.Tensor]
        decoder_input = features if self.config.decoder_type == "upernet" else features[-1]
        return self.decoder(decoder_input)
