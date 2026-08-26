"""Fine-tune Prithvi for dense soil-moisture prediction.

The command consumes preprocessing artifacts rather than reproducing their
work: a target manifest, normalization statistics, and optional pre-aligned
terrain mosaics. Supervision remains tile-level because ESA-CCI observations
are coarse; the loss compares each scalar target with the spatial mean of the
dense prediction instead of teaching artificial nearest-cell boundaries.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import torch
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader

if __package__:
    from .data import (
        PreparedTileDataset,
        TerrainResolver,
        load_manifest,
        load_stats,
        load_terrain_map,
        select_records,
    )
    from .decoders import SUPPORTED_DECODER_TYPES
    from .model import DEFAULT_BACKBONE, ModelConfig, PrithviSoilMoisture
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from somospie_gfm.nn.data import (
        PreparedTileDataset,
        TerrainResolver,
        load_manifest,
        load_stats,
        load_terrain_map,
        select_records,
    )
    from somospie_gfm.nn.decoders import SUPPORTED_DECODER_TYPES
    from somospie_gfm.nn.model import (
        DEFAULT_BACKBONE,
        ModelConfig,
        PrithviSoilMoisture,
    )


def set_seed(seed: int) -> None:
    """Seed Python, NumPy, and PyTorch random generators.

    Parameters
    ----------
    seed : int
        Reproducibility seed.

    Returns
    -------
    None
        Global generator states are updated in place.
    """
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def make_loader(
    dataset: PreparedTileDataset,
    batch_size: int,
    workers: int,
    *,
    shuffle: bool,
    device: torch.device,
) -> DataLoader:
    """Build a GDAL-safe PyTorch loader for a prepared-tile dataset.

    Spawned workers avoid inheriting GDAL locks and CUDA state from the parent.

    Parameters
    ----------
    dataset : PreparedTileDataset
        Prepared records exposed to the loader.
    batch_size : int
        Positive number of records per mini-batch.
    workers : int
        Non-negative spawned worker count.
    shuffle : bool
        Randomize record order for training when true.
    device : torch.device
        Target device; CUDA enables pinned host memory.

    Returns
    -------
    torch.utils.data.DataLoader
        Configured loader safe for GDAL-backed datasets.

    Raises
    ------
    ValueError
        If batch size or worker count is invalid.
    """
    if batch_size <= 0 or workers < 0:
        raise ValueError("batch_size must be positive and workers non-negative")
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=workers,
        drop_last=False,
        pin_memory=device.type == "cuda",
        persistent_workers=workers > 0,
        multiprocessing_context="spawn" if workers > 0 else None,
    )


def edge_guided_tv(
    prediction: torch.Tensor,
    inputs: torch.Tensor,
    hls_channels: int,
) -> torch.Tensor:
    """Compute total variation suppressed at strong HLS spectral edges.

    Parameters
    ----------
    prediction : torch.Tensor
        Dense ``[B, H, W]`` soil-moisture output.
    inputs : torch.Tensor
        Normalized ``[B, C, T, H, W]`` model input.
    hls_channels : int
        Number of leading optical channels used to detect edges.

    Returns
    -------
    torch.Tensor
        Scalar differentiable regularization term.

    Raises
    ------
    ValueError
        If there are no HLS channels.
    """
    if hls_channels <= 0:
        raise ValueError("hls_channels must be positive")
    hls = inputs[:, :hls_channels, 0].detach()
    edge_y = (hls[:, :, 1:] - hls[:, :, :-1]).abs().sum(1)
    edge_x = (hls[:, :, :, 1:] - hls[:, :, :, :-1]).abs().sum(1)
    max_y = edge_y.flatten(1).amax(1).view(-1, 1, 1).clamp_min(1e-8)
    max_x = edge_x.flatten(1).amax(1).view(-1, 1, 1).clamp_min(1e-8)
    weight_y = torch.exp(-5 * edge_y / max_y)
    weight_x = torch.exp(-5 * edge_x / max_x)
    return (
        weight_y * (prediction[:, 1:] - prediction[:, :-1]).abs()
    ).mean() + (
        weight_x * (prediction[:, :, 1:] - prediction[:, :, :-1]).abs()
    ).mean()


def run_epoch(
    model: PrithviSoilMoisture,
    loader: DataLoader,
    device: torch.device,
    optimizer: AdamW | None,
    *,
    amp: bool,
    accumulation_steps: int,
    tv_weight: float,
    hls_channels: int,
) -> float:
    """Run one training or validation epoch and return tile-level MSE.

    Parameters
    ----------
    model, loader, device
        Model, batches, and compute device for this pass.
    optimizer : AdamW or None
        Optimizer for training; ``None`` enables validation mode.
    amp : bool
        Use float16 autocast on CUDA.
    accumulation_steps : int
        Mini-batches accumulated before each optimizer step.
    tv_weight : float
        Non-negative edge-guided total-variation coefficient.
    hls_channels : int
        Optical channels used for TV edge detection.

    Returns
    -------
    float
        Mean squared error across finite tile targets, excluding TV.

    Raises
    ------
    ValueError
        If accumulation or TV settings are invalid, or no finite targets are
        seen.
    RuntimeError
        Propagated for model, device, or backward failures.
    """
    if accumulation_steps <= 0 or tv_weight < 0:
        raise ValueError("accumulation_steps must be positive and tv_weight non-negative")
    training = optimizer is not None
    model.train(training)
    amp_enabled = amp and device.type == "cuda"
    try:
        scaler = torch.amp.GradScaler("cuda", enabled=amp_enabled and training)
    except (AttributeError, TypeError):
        scaler = torch.cuda.amp.GradScaler(enabled=amp_enabled and training)
    if training:
        optimizer.zero_grad(set_to_none=True)

    squared_error = 0.0
    sample_count = 0
    context = torch.enable_grad() if training else torch.no_grad()
    with context:
        for step, (inputs, targets, _) in enumerate(loader):
            inputs = inputs.to(device, non_blocking=True)
            targets = targets.to(device, non_blocking=True)
            autocast = (
                torch.autocast(device_type="cuda", dtype=torch.float16)
                if amp_enabled
                else nullcontext()
            )
            with autocast:
                prediction = model(inputs)
                valid = torch.isfinite(targets)
                if not valid.any():
                    continue
                tile_prediction = prediction.flatten(1).mean(1)
                mse = ((tile_prediction[valid] - targets[valid]) ** 2).mean()
                loss = mse
                if tv_weight:
                    loss = loss + tv_weight * edge_guided_tv(
                        prediction, inputs, hls_channels
                    )
                backward_loss = loss / accumulation_steps

            if training:
                scaler.scale(backward_loss).backward()
                last = step + 1 == len(loader)
                if (step + 1) % accumulation_steps == 0 or last:
                    scaler.step(optimizer)
                    scaler.update()
                    optimizer.zero_grad(set_to_none=True)

            count = int(valid.sum().item())
            squared_error += float(mse.detach().item()) * count
            sample_count += count
    if not sample_count:
        raise ValueError("epoch contained no finite targets")
    return squared_error / sample_count


def build_optimizer(
    model: PrithviSoilMoisture,
    *,
    head_lr: float,
    backbone_lr: float,
    weight_decay: float,
) -> AdamW:
    """Create AdamW groups with separate decoder and backbone rates.

    Parameters
    ----------
    model : PrithviSoilMoisture
        Model whose trainable parameters are grouped.
    head_lr, backbone_lr : float
        Positive learning rates for decoder and unfrozen backbone parameters.
    weight_decay : float
        Non-negative AdamW decay coefficient.

    Returns
    -------
    torch.optim.AdamW
        Optimizer containing the decoder and any trainable backbone parameters.

    Raises
    ------
    ValueError
        If a learning rate is non-positive or weight decay is negative.
    """
    if head_lr <= 0 or backbone_lr <= 0 or weight_decay < 0:
        raise ValueError("learning rates must be positive and weight_decay non-negative")
    groups: list[dict[str, Any]] = [
        {"params": list(model.decoder_parameters()), "lr": head_lr}
    ]
    backbone = [parameter for parameter in model.backbone.parameters() if parameter.requires_grad]
    if backbone:
        groups.append({"params": backbone, "lr": backbone_lr})
    return AdamW(groups, weight_decay=weight_decay)


def save_checkpoint(
    path: Path,
    model: PrithviSoilMoisture,
    optimizer: AdamW,
    epoch: int,
    metric: float,
    stats_artifact: dict[str, Any],
    history: list[dict[str, Any]],
    arguments: argparse.Namespace,
) -> None:
    """Atomically write a restartable, inference-ready checkpoint.

    Parameters
    ----------
    path : pathlib.Path
        Final checkpoint destination.
    model : PrithviSoilMoisture
        Model configuration and learned state to serialize.
    optimizer : torch.optim.AdamW
        Optimizer state needed for a future restart.
    epoch : int
        Completed epoch number.
    metric : float
        Selection MSE associated with this checkpoint.
    stats_artifact : dict
        Normalization artifact embedded for inference reproducibility.
    history : list of dict
        Epoch metrics through ``epoch``.
    arguments : argparse.Namespace
        Training CLI settings recorded as provenance.

    Returns
    -------
    None
        A checkpoint is written and atomically published.

    Raises
    ------
    OSError, RuntimeError
        If PyTorch cannot serialize the checkpoint or publish it atomically.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    config = {
        name: str(value) if isinstance(value, Path) else value
        for name, value in vars(arguments).items()
    }
    payload = {
        "checkpoint_version": 1,
        "epoch": epoch,
        "metric_mse": metric,
        "model_config": model.config.to_dict(),
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "normalization_stats": stats_artifact,
        "history": history,
        "training_arguments": config,
    }
    try:
        torch.save(payload, temporary)
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _splits(value: str) -> tuple[str, ...]:
    """Parse a comma-separated, non-empty training split option.

    Parameters
    ----------
    value : str
        Raw command-line value such as ``"train,validation"``.

    Returns
    -------
    tuple of str
        Trimmed, non-empty split labels in their supplied order.

    Raises
    ------
    argparse.ArgumentTypeError
        If the value contains no usable split label.
    """
    result = tuple(item.strip() for item in value.split(",") if item.strip())
    if not result:
        raise argparse.ArgumentTypeError("split list must not be empty")
    return result


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse and validate training command-line arguments.

    Parameters
    ----------
    argv : sequence of str or None, optional
        Explicit arguments; ``None`` reads process arguments.

    Returns
    -------
    argparse.Namespace
        Validated data, architecture, optimization, and output settings.

    Raises
    ------
    SystemExit
        Raised by ``argparse`` for invalid options or ``--help``.
    """
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    data = parser.add_argument_group("prepared data")
    data.add_argument("--manifest", type=Path, required=True)
    data.add_argument("--stats", type=Path, required=True)
    terrain = data.add_mutually_exclusive_group()
    terrain.add_argument("--aligned-terrain", type=Path)
    terrain.add_argument(
        "--aligned-terrain-map",
        type=Path,
        help="JSON mapping manifest region names to aligned terrain GeoTIFFs",
    )
    data.add_argument("--train-splits", type=_splits, default=("train",))
    data.add_argument("--validation-splits", type=_splits, default=("holdout",))
    data.add_argument("--max-records", type=int, default=0)

    architecture = parser.add_argument_group("architecture")
    architecture.add_argument("--backbone", default=DEFAULT_BACKBONE)
    architecture.add_argument("--backbone-checkpoint", type=Path)
    architecture.add_argument("--no-pretrained", action="store_true")
    architecture.add_argument("--tile-size", type=int, default=256)
    architecture.add_argument("--patch-size", type=int, default=16)
    architecture.add_argument(
        "--decoder", choices=SUPPORTED_DECODER_TYPES, default="conv_upsample_4stage"
    )
    architecture.add_argument("--decoder-channels", type=int, default=128)
    architecture.add_argument("--decoder-dropout", type=float, default=0.1)
    architecture.add_argument("--output-size", type=int, default=0)
    architecture.add_argument("--drop-path-rate", type=float, default=0.0)

    optimization = parser.add_argument_group("optimization")
    optimization.add_argument("--epochs", type=int, default=20)
    optimization.add_argument("--freeze-backbone", action="store_true")
    optimization.add_argument(
        "--unfreeze-after",
        type=int,
        default=0,
        help="warm-up epochs with a frozen backbone; ignored when permanently frozen",
    )
    optimization.add_argument("--batch-size", type=int, default=4)
    optimization.add_argument("--workers", type=int, default=0)
    optimization.add_argument("--head-lr", type=float, default=5e-5)
    optimization.add_argument("--backbone-lr", type=float, default=5e-5)
    optimization.add_argument("--weight-decay", type=float, default=1e-2)
    optimization.add_argument("--tv-weight", type=float, default=0.0)
    optimization.add_argument("--accumulation-steps", type=int, default=1)
    optimization.add_argument("--amp", action="store_true")
    optimization.add_argument("--seed", type=int, default=42)
    optimization.add_argument("--device")

    output = parser.add_argument_group("output")
    output.add_argument("--output-dir", type=Path, required=True)
    output.add_argument("--best-name", default="prithvi_sm_best.pt")
    output.add_argument("--last-name", default="prithvi_sm_last.pt")
    args = parser.parse_args(argv)
    if args.epochs <= 0:
        parser.error("--epochs must be positive")
    if args.unfreeze_after < 0:
        parser.error("--unfreeze-after cannot be negative")
    if args.freeze_backbone and args.unfreeze_after:
        parser.error("--freeze-backbone and --unfreeze-after cannot be combined")
    return args


def main(argv: Sequence[str] | None = None) -> None:
    """Train the model and publish best/last checkpoints plus JSON history.

    Parameters
    ----------
    argv : sequence of str or None, optional
        Explicit command-line arguments; ``None`` reads process arguments.

    Returns
    -------
    None
        Checkpoints, history, and progress output are produced as side effects.

    Raises
    ------
    FileNotFoundError, ValueError
        If prepared artifacts or their contracts are invalid.
    ModuleNotFoundError
        If PyTorch, TerraTorch, NumPy, or GDAL is unavailable.
    RuntimeError, OSError
        If model execution or artifact writing fails.
    """
    args = parse_args(argv)
    set_seed(args.seed)
    device = torch.device(args.device or ("cuda" if torch.cuda.is_available() else "cpu"))
    if device.type == "cuda":
        torch.backends.cudnn.benchmark = True

    records = load_manifest(args.manifest)
    stats = load_stats(args.stats)
    terrain = TerrainResolver(
        stats.terrain_channels,
        shared=args.aligned_terrain,
        mapping=load_terrain_map(args.aligned_terrain_map),
    )
    train_records = select_records(
        records,
        args.train_splits,
        require_targets=True,
        max_records=args.max_records,
    )
    try:
        validation_records = select_records(
            records,
            args.validation_splits,
            require_targets=True,
            max_records=args.max_records,
        )
    except ValueError:
        validation_records = []

    train_data = PreparedTileDataset(train_records, stats, terrain, args.tile_size)
    train_loader = make_loader(
        train_data, args.batch_size, args.workers, shuffle=True, device=device
    )
    validation_loader = None
    if validation_records:
        validation_data = PreparedTileDataset(
            validation_records, stats, terrain, args.tile_size
        )
        validation_loader = make_loader(
            validation_data,
            args.batch_size,
            args.workers,
            shuffle=False,
            device=device,
        )

    config = ModelConfig(
        channel_names=stats.channel_names,
        backbone_name=args.backbone,
        tile_size=args.tile_size,
        patch_size=args.patch_size,
        decoder_type=args.decoder,
        decoder_channels=args.decoder_channels,
        decoder_dropout=args.decoder_dropout,
        output_size=args.output_size,
        drop_path_rate=args.drop_path_rate,
    )
    frozen_epochs = args.epochs if args.freeze_backbone else min(
        args.unfreeze_after, args.epochs
    )
    model = PrithviSoilMoisture(
        config,
        pretrained=not args.no_pretrained,
        backbone_checkpoint=(
            str(args.backbone_checkpoint) if args.backbone_checkpoint else None
        ),
        freeze_backbone=frozen_epochs > 0,
    ).to(device)
    optimizer = build_optimizer(
        model,
        head_lr=args.head_lr,
        backbone_lr=args.backbone_lr,
        weight_decay=args.weight_decay,
    )
    phase_epochs = frozen_epochs or args.epochs
    scheduler = CosineAnnealingLR(optimizer, T_max=max(1, phase_epochs), eta_min=1e-7)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    best_path = args.output_dir / args.best_name
    last_path = args.output_dir / args.last_name
    history_path = args.output_dir / "training_history.json"
    history: list[dict[str, Any]] = []
    best_metric = math.inf

    print(
        f"Training {len(train_records)} tile(s) on {device}; "
        f"validation={len(validation_records)}, channels={len(stats.channel_names)}",
        flush=True,
    )
    for epoch in range(1, args.epochs + 1):
        if epoch == frozen_epochs + 1 and frozen_epochs < args.epochs and frozen_epochs:
            model.unfreeze_backbone()
            optimizer = build_optimizer(
                model,
                head_lr=args.head_lr,
                backbone_lr=args.backbone_lr,
                weight_decay=args.weight_decay,
            )
            scheduler = CosineAnnealingLR(
                optimizer,
                T_max=max(1, args.epochs - frozen_epochs),
                eta_min=1e-7,
            )
        train_mse = run_epoch(
            model,
            train_loader,
            device,
            optimizer,
            amp=args.amp,
            accumulation_steps=args.accumulation_steps,
            tv_weight=args.tv_weight,
            hls_channels=len(stats.hls_bands),
        )
        validation_mse = None
        if validation_loader is not None:
            validation_mse = run_epoch(
                model,
                validation_loader,
                device,
                None,
                amp=args.amp,
                accumulation_steps=1,
                tv_weight=0,
                hls_channels=len(stats.hls_bands),
            )
        scheduler.step()
        metric = validation_mse if validation_mse is not None else train_mse
        record = {
            "epoch": epoch,
            "train_mse": train_mse,
            "validation_mse": validation_mse,
            "backbone_frozen": epoch <= frozen_epochs,
        }
        history.append(record)
        print(
            f"epoch {epoch:03d}/{args.epochs}: train_mse={train_mse:.6f}"
            + (
                f", validation_mse={validation_mse:.6f}"
                if validation_mse is not None
                else ""
            ),
            flush=True,
        )
        if metric < best_metric:
            best_metric = metric
            save_checkpoint(
                best_path,
                model,
                optimizer,
                epoch,
                metric,
                stats.artifact,
                history,
                args,
            )
        save_checkpoint(
            last_path,
            model,
            optimizer,
            epoch,
            metric,
            stats.artifact,
            history,
            args,
        )

    temporary = history_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, history_path)
    print(f"Best checkpoint: {best_path}\nLast checkpoint: {last_path}")


if __name__ == "__main__":
    main()
