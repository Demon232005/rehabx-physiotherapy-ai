"""CPU-friendly baseline fine-tune for the X-ray abnormality classifier.

Produces an initial ``best.pt`` so the backend runs end-to-end with a
fine-tuned model before a full GPU training pass is done. It differs
from :mod:`ai.training.train_classifier` in three ways:

1. Balanced subsampling (--per-class) instead of the full split.
2. Reduced input resolution (default 224) — the checkpoint stays fully
   compatible with 512px inference because the backbone pools adaptively.
3. Optional frozen backbone (--freeze-head-only) so only the head is
   trained, which is several times faster on CPU.

Usage::

    python -m ai.training.train_baseline \
        --train-csv data/splits_train.csv --val-csv data/splits_val.csv \
        --out models/checkpoints/classifier --epochs 4 --per-class 600

For the production-quality model use ``train_classifier`` on a GPU with
the full splits and 512px inputs.
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

import cv2
import pandas as pd
import torch
from torch import nn, optim
from torch.utils.data import DataLoader, Dataset

from ai.models.classifier import XrayClassifier
from ai.preprocessing.transforms import apply_clahe, make_train_transforms, make_valid_transforms, read_grayscale
from ai.utils.common import MODEL_ROOT, model_version

LABELS = {"normal": 0, "abnormal": 1}


class SubsampledXrayDataset(Dataset):
    """Balanced-subset dataset with configurable input resolution."""

    def __init__(self, csv_path: Path, per_class: int, size: int, train: bool, seed: int = 42):
        df = pd.read_csv(csv_path)
        rng = random.Random(seed)
        parts = []
        for label in LABELS:
            sub = df[df["label"] == label]
            if per_class > 0 and len(sub) > per_class:
                sub = sub.sample(n=per_class, random_state=rng.randint(0, 2**31))
            parts.append(sub)
        self.df = pd.concat(parts).reset_index(drop=True)
        self.transform = make_train_transforms(size=size) if train else make_valid_transforms(size=size)

    def __len__(self) -> int:
        return len(self.df)

    def __getitem__(self, idx: int):
        row = self.df.iloc[idx]
        img = apply_clahe(read_grayscale(row["image_path"]))
        rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        tensor = self.transform(rgb)
        return tensor, LABELS[row["label"]]


def _evaluate(model: nn.Module, loader: DataLoader, device: torch.device) -> tuple[float, float]:
    from sklearn.metrics import roc_auc_score

    model.eval()
    probs, targets = [], []
    with torch.no_grad():
        for images, labels in loader:
            p = torch.softmax(model(images.to(device)), dim=1)[:, 1].cpu().numpy()
            probs.extend(p.tolist())
            targets.extend(labels.tolist())
    preds = [1 if p >= 0.5 else 0 for p in probs]
    acc = sum(1 for p, t in zip(preds, targets) if p == t) / max(1, len(targets))
    auc = roc_auc_score(targets, probs) if len(set(targets)) > 1 else 0.5
    return acc, float(auc)


def _save(model: nn.Module, path: Path, epoch: int, val_acc: float, val_auc: float, args) -> None:
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "backbone": model.backbone_name,
            "epoch": epoch,
            "val_acc": val_acc,
            "val_auc": val_auc,
            "model_version": model_version(),
            "metadata": {
                "kind": "cpu_baseline",
                "input_size": args.size,
                "frozen_backbone": args.freeze_backbone,
                "train_per_class": args.per_class,
                "note": "Baseline produced by train_baseline.py; retrain with train_classifier.py on GPU for production quality.",
            },
        },
        path,
    )


def train(args: argparse.Namespace) -> None:
    torch.manual_seed(args.seed)
    torch.set_num_threads(max(1, args.threads or 0) or (torch.get_num_threads()))
    device = torch.device("cpu")

    print(f"[baseline] train subset: {args.per_class}/class @ {args.size}px")
    train_ds = SubsampledXrayDataset(Path(args.train_csv), args.per_class, args.size, train=True, seed=args.seed)
    val_ds = SubsampledXrayDataset(Path(args.val_csv), args.per_class_val, args.size, train=False, seed=args.seed)
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=0)
    print(f"[baseline] train={len(train_ds)} val={len(val_ds)}")

    model = XrayClassifier(backbone=args.backbone, num_classes=2).to(device)
    if args.freeze_backbone:
        for p in model.model.features.parameters():
            p.requires_grad_(False)
    trainable = [p for p in model.parameters() if p.requires_grad]
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(trainable, lr=args.lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    best_auc = -1.0
    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss, correct, total = 0.0, 0, 0
        for i, (images, labels) in enumerate(train_loader):
            optimizer.zero_grad()
            logits = model(images)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * images.size(0)
            correct += (logits.argmax(1) == labels).sum().item()
            total += images.size(0)
            if i % 10 == 0:
                print(f"  epoch {epoch} batch {i}/{len(train_loader)} loss={loss.item():.4f}", flush=True)
        scheduler.step()

        val_acc, val_auc = _evaluate(model, val_loader, device)
        line = f"epoch {epoch}: loss={total_loss / total:.4f} acc={correct / total:.4f} val_acc={val_acc:.4f} val_auc={val_auc:.4f}"
        print(line, flush=True)

        if val_auc >= best_auc:
            best_auc = val_auc
            _save(model, out_dir / "best.pt", epoch, val_acc, val_auc, args)
        _save(model, out_dir / "last.pt", epoch, val_acc, val_auc, args)

    print(f"Best val ROC-AUC: {best_auc:.4f} -> {out_dir / 'best.pt'}")


def parse_args() -> argparse.Namespace:
    import os

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--train-csv", default=str(MODEL_ROOT.parent / "data" / "splits_train.csv"))
    p.add_argument("--val-csv", default=str(MODEL_ROOT.parent / "data" / "splits_val.csv"))
    p.add_argument("--out", default=str(MODEL_ROOT / "checkpoints" / "classifier"))
    p.add_argument("--backbone", default="efficientnet_b0")
    p.add_argument("--epochs", type=int, default=4)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--size", type=int, default=224)
    p.add_argument("--per-class", type=int, default=600)
    p.add_argument("--per-class-val", type=int, default=150)
    p.add_argument("--freeze-backbone", action="store_true", default=True)
    p.add_argument("--threads", type=int, default=os.cpu_count())
    return p.parse_args()


if __name__ == "__main__":
    train(parse_args())
