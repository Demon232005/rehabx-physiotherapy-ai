"""Shared configuration and helpers for the AI module."""
from __future__ import annotations

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
# Named "data" (not "datasets") so this folder never shadows the Hugging Face
# `datasets` package that ai/data/setup_dataset.py imports.
DATASET_ROOT = REPO_ROOT / "data"
MODEL_ROOT = REPO_ROOT / "models"

CLASS_NAMES = ["normal", "abnormal"]
CLASSIFIER_INPUT_SIZE = 512
IMG_MEAN = [0.485, 0.456, 0.406]
IMG_STD = [0.229, 0.224, 0.225]


def model_version() -> str:
    """Return a reproducible version string for the current code."""
    try:
        import ai

        return f"ai-{getattr(ai, '__version__', '0.1.0')}"
    except ImportError:
        return "ai-0.1.0"


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
