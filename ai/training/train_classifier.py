"""Fine-tuning pipeline for the X-ray abnormality classifier.

Usage::

    python -m ai.training.train_classifier \
        --train-csv data/splits_train.csv \
        --val-csv data/splits_val.csv \
        --out models/checkpoints/classifier \
        --epochs 12 --batch-size 32 --lr 1e-4

Saves best.pt (best val ROC-AUC) and last.pt checkpoints containing
model_state_dict + metadata.
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

from ai.models.classifier import XrayClassifier
from ai.preprocessing.transforms import apply_clahe, make_train_transforms, make_valid_transforms
from ai.utils.common import MODEL_ROOT, model_version


class XrayDataset(Dataset):
    def __init__(self, csv_path: Path, transform=None, train: bool = True):
        self.df = pd.read_csv(csv_path)
        self.transform = transform or (make_train_transforms() if train else make_valid_transforms())
        self.labels = {"normal": 0, "abnormal": 1}

    def __len__(self) -> int:
        return len(self.df)

    def __getitem__(self, idx: int):
        row = self.df.iloc[idx]
        from ai.preprocessing.transforms import read_grayscale

        img = read_grayscale(row["image_path"])
        img = apply_clahe(img)
        rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        if self.transform is not None:
            img = self.transform(rgb)
        else:
            img = torch.from_numpy(rgb.transpose(2, 0, 1)).float() / 255.0
        return img, self.labels[row["label"]]


def train(args: argparse.Namespace) -> None:
    torch.manual_seed(args.seed)
    device = torch.device(args.device)

    train_ds = XrayDataset(Path(args.train_csv), train=True)
    val_ds = XrayDataset(Path(args.val_csv), train=False)
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=args.num_workers)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=args.num_workers)

    model = XrayClassifier(backbone=args.backbone, num_classes=2).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    best_auc = -1.0
    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss, correct, total = 0.0, 0, 0
        for images, labels in tqdm(train_loader, desc=f"epoch {epoch}"):
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            logits = model(images)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * images.size(0)
            correct += (logits.argmax(1) == labels).sum().item()
            total += images.size(0)
        scheduler.step()

        val_acc, val_auc = _evaluate(model, val_loader, device)
        print(f"epoch {epoch}: loss={total_loss / total:.4f} acc={correct / total:.4f} "
              f"val_acc={val_acc:.4f} val_auc={val_auc:.4f}")

        if val_auc > best_auc:
            best_auc = val_auc
            _save(model, out_dir / "best.pt", epoch, val_acc, val_auc)
        _save(model, out_dir / "last.pt", epoch, val_acc, val_auc)

    print(f"Best val ROC-AUC: {best_auc:.4f} -> {out_dir / 'best.pt'}")


@torch.no_grad()
def _evaluate(model: nn.Module, loader: DataLoader, device: torch.device) -> tuple[float, float]:
    from sklearn.metrics import roc_auc_score

    model.eval()
    probs, targets = [], []
    for images, labels in loader:
        images = images.to(device)
        p = torch.softmax(model(images), dim=1)[:, 1].cpu().numpy()
        probs.extend(p.tolist())
        targets.extend(labels.tolist())
    preds = [1 if p >= 0.5 else 0 for p in probs]
    acc = sum(1 for p, t in zip(preds, targets) if p == t) / max(1, len(targets))
    auc = roc_auc_score(targets, probs) if len(set(targets)) > 1 else 0.5
    return acc, float(auc)


def _save(model: nn.Module, path: Path, epoch: int, val_acc: float, val_auc: float) -> None:
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "backbone": model.backbone_name,
            "epoch": epoch,
            "val_acc": val_acc,
            "val_auc": val_auc,
            "model_version": model_version(),
        },
        path,
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--train-csv", required=True)
    p.add_argument("--val-csv", required=True)
    p.add_argument("--out", default=str(MODEL_ROOT / "checkpoints" / "classifier"))
    p.add_argument("--backbone", default="efficientnet_b0")
    p.add_argument("--epochs", type=int, default=12)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    p.add_argument("--num-workers", type=int, default=0)
    return p.parse_args()


if __name__ == "__main__":
    train(parse_args())
