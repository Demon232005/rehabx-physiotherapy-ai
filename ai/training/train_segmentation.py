"""Training pipeline for the U-Net bone-localization segmentation model.

Expects a CSV of [image_path, mask_path, split] produced from
GRAZPEDWRI-DX bounding boxes (see docs/DATASET.md for the conversion).

Usage::

    python -m ai.training.train_segmentation \
        --train-csv data/seg_train.csv \
        --val-csv data/seg_val.csv \
        --out models/checkpoints/segmentation \
        --epochs 25 --batch-size 8
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import pandas as pd
import torch
from torch import nn, optim
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm

from ai.models.segmentation import UNet
from ai.utils.common import MODEL_ROOT, model_version


class SegmentationDataset(Dataset):
    def __init__(self, csv_path: Path):
        self.df = pd.read_csv(csv_path)

    def __len__(self) -> int:
        return len(self.df)

    def __getitem__(self, idx: int):
        row = self.df.iloc[idx]
        img = cv2.imread(row["image_path"], cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255.0
        mask = cv2.imread(row["mask_path"], cv2.IMREAD_GRAYSCALE).astype(np.float32)
        mask = (mask > 0).astype(np.float32)
        return (
            torch.from_numpy(img).unsqueeze(0),
            torch.from_numpy(mask).unsqueeze(0),
        )


def dice_loss(pred: torch.Tensor, target: torch.Tensor, smooth: float = 1.0) -> torch.Tensor:
    prob = torch.softmax(pred, dim=1)[:, 1:2]
    inter = (prob * target).sum(dim=(2, 3))
    union = prob.sum(dim=(2, 3)) + target.sum(dim=(2, 3))
    return 1 - ((2 * inter + smooth) / (union + smooth)).mean()


def train(args: argparse.Namespace) -> None:
    torch.manual_seed(args.seed)
    device = torch.device(args.device)

    train_ds = SegmentationDataset(Path(args.train_csv))
    val_ds = SegmentationDataset(Path(args.val_csv))
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=args.num_workers)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=args.num_workers)

    model = UNet(in_channels=1, base=args.base, num_classes=2).to(device)
    optimizer = optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    best_dice = -1.0

    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0.0
        for images, masks in tqdm(train_loader, desc=f"epoch {epoch}"):
            images, masks = images.to(device), masks.to(device)
            optimizer.zero_grad()
            logits = model(images)
            loss = dice_loss(logits, masks)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * images.size(0)

        val_dice = _evaluate_dice(model, val_loader, device)
        print(f"epoch {epoch}: loss={total_loss / len(train_ds):.4f} val_dice={val_dice:.4f}")

        if val_dice > best_dice:
            best_dice = val_dice
            _save(model, out_dir / "best.pt", epoch, val_dice)
        _save(model, out_dir / "last.pt", epoch, val_dice)

    print(f"Best val Dice: {best_dice:.4f} -> {out_dir / 'best.pt'}")


@torch.no_grad()
def _evaluate_dice(model: nn.Module, loader: DataLoader, device: torch.device) -> float:
    model.eval()
    total, n = 0.0, 0
    for images, masks in loader:
        images = images.to(device)
        pred = torch.softmax(model(images), dim=1)[:, 1:2].cpu()
        inter = (pred * masks).sum(dim=(2, 3))
        union = pred.sum(dim=(2, 3)) + masks.sum(dim=(2, 3))
        total += (2 * inter / (union + 1e-6)).sum().item()
        n += masks.size(0)
    return total / max(1, n)


def _save(model: nn.Module, path: Path, epoch: int, val_dice: float) -> None:
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "in_channels": 1,
            "base": model.base if hasattr(model, "base") else 32,
            "num_classes": 2,
            "epoch": epoch,
            "val_dice": val_dice,
            "model_version": model_version(),
        },
        path,
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--train-csv", required=True)
    p.add_argument("--val-csv", required=True)
    p.add_argument("--out", default=str(MODEL_ROOT / "checkpoints" / "segmentation"))
    p.add_argument("--base", type=int, default=32)
    p.add_argument("--epochs", type=int, default=25)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    p.add_argument("--num-workers", type=int, default=0)
    return p.parse_args()


if __name__ == "__main__":
    import numpy as np

    train(parse_args())
