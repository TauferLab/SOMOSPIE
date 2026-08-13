"""Neural-network components for SOMOSPIE-GFM soil-moisture modeling.

The package exposes the validated Prithvi model contract while its ``train``
and ``infer`` modules provide reproducible command-line workflows for fitting
and georeferenced dense prediction.
"""

from .model import ModelConfig, PrithviSoilMoisture

__all__ = ["ModelConfig", "PrithviSoilMoisture"]
