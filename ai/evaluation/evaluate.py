"""Evaluation script: classifier on a held-out test split.

Usage::

    python -m ai.evaluation.evaluate --test-csv data/splits_test.csv \
        --checkpoint models/checkpoints/classifier/best.pt \
        --out reports/classifier

Writes a JSON metrics report and a confusion-matrix / ROC plot.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import roc_curve
from torch.utils.data import DataLoader

from ai.evaluation.metrics import classification_report
from ai.models.classifier import load_classifier
from ai.preprocessing.transforms import apply_clahe, read_grayscale
from ai.utils.common import CLASSIFIER_INPUT_SIZE, MODEL_ROOT
from ai.utils.common import save_json


@torch.no_grad()
def evaluate(args: argparse.Namespace) -> dict:
    device = torch.device(args.device)
    df = pd.read_csv(args.test_csv)
    model, _meta = load_classifier(args.checkpoint, device=device)

    probs, targets = [], []
    for _, row in df.iterrows():
        img = read_grayscale(row["image_path"])
        img = apply_clahe(img)
        img = cv2.resize(img, (CLASSIFIER_INPUT_SIZE, CLASSIFIER_INPUT_SIZE), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        from ai.preprocessing.transforms import make_valid_transforms

        tensor = make_valid_transforms()(rgb).unsqueeze(0).to(device)
        p = torch.softmax(model(tensor), dim=1)[:, 1].item()
        probs.append(p)
        targets.append(1 if row["label"] == "abnormal" else 0)

    y_true = np.array(targets)
    y_prob = np.array(probs)
    report = classification_report(y_true, y_prob)
    save_json(Path(args.out) / "metrics.json", report)

    fpr, tpr, _ = roc_curve(y_true, y_prob)
    fig, ax = plt.subplots()
    ax.plot(fpr, tpr, label=f"AUC={report['roc_auc']:.3f}")
    ax.plot([0, 1], [0, 1], ls="--", c="gray")
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title("Classifier ROC")
    ax.legend()
    Path(args.out).mkdir(parents=True, exist_ok=True)
    fig.savefig(Path(args.out) / "roc.png", dpi=150)

    print(report)
    return report


def parse_args() -> argparse.Namespace:
    import cv2  # noqa: F401  (imported lazily to keep module import light)

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--test-csv", required=True)
    p.add_argument("--checkpoint", default=str(MODEL_ROOT / "checkpoints" / "classifier" / "best.pt"))
    p.add_argument("--out", default="reports/classifier")
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    return p.parse_args()


if __name__ == "__main__":
    evaluate(parse_args())
