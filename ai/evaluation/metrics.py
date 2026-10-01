"""Evaluation metrics shared by the evaluation scripts."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)


def classification_report(y_true: np.ndarray, y_prob: np.ndarray, threshold: float = 0.5) -> dict:
    """Compute standard binary-classification metrics (0 = normal, 1 = abnormal)."""
    y_pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred)), 4),
        "recall": round(float(recall_score(y_true, y_pred)), 4),
        "f1": round(float(f1_score(y_true, y_pred)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, y_prob)), 4),
        "confusion_matrix": {"tp": int(tp), "tn": int(tn), "fp": int(fp), "fn": int(fn)},
        "n_positive": int(y_true.sum()),
        "n_negative": int((1 - y_true).sum()),
    }


def dice_score(pred_mask: np.ndarray, true_mask: np.ndarray) -> float:
    inter = float(np.logical_and(pred_mask, true_mask).sum())
    union = float(pred_mask.sum()) + float(true_mask.sum())
    return 2 * inter / max(1e-9, union)


def iou_score(pred_mask: np.ndarray, true_mask: np.ndarray) -> float:
    inter = float(np.logical_and(pred_mask, true_mask).sum())
    union = float(np.logical_or(pred_mask, true_mask).sum())
    return inter / max(1e-9, union)
