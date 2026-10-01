"""Dataset preprocessing.

Converts raw MURA PNG/JPEG radiographs into a normalized, resized,
CLAHE-enhanced dataset ready for training. Produces a `processed/`
directory with a flat `normal/` and `abnormal/` layout plus a CSV index.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm

from ai.preprocessing.transforms import apply_clahe
from ai.utils.common import DATASET_ROOT, CLASSIFIER_INPUT_SIZE

ALLOWED_EXTS = {".png", ".jpg", ".jpeg"}


def iter_mura_images(root: Path):
    """Yield (image_path, label) for every HAND/WRIST/UPPER MURA image.

    Scans every study subfolder under `{split}/{label}` so the layout stays
    flexible (official MURA uses HAND/WRIST; the HF mirror uses UPPER).
    """
    for split in ("train", "valid"):
        split_dir = root / split
        if not split_dir.is_dir():
            continue
        for label in ("normal", "abnormal"):
            label_dir = split_dir / label
            if not label_dir.is_dir():
                continue
            for study_dir in label_dir.iterdir():
                if not study_dir.is_dir():
                    continue
                for img_path in study_dir.iterdir():
                    if img_path.suffix.lower() in ALLOWED_EXTS:
                        yield img_path, label


def preprocess_dataset(source: Path, out_root: Path, size: int) -> Path:
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "normal").mkdir(exist_ok=True)
    (out_root / "abnormal").mkdir(exist_ok=True)

    rows: list[dict] = []
    for img_path, label in tqdm(list(iter_mura_images(source)), desc="preprocessing"):
        img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        img = apply_clahe(img)
        img = cv2.resize(img, (size, size), interpolation=cv2.INTER_AREA)
        target = out_root / label / f"{img_path.parent.name}_{img_path.stem}.png"
        cv2.imwrite(str(target), img)
        rows.append({"image_path": str(target), "label": label, "split": img_path.parts[-3]})

    index = out_root / "index.csv"
    pd.DataFrame(rows).to_csv(index, index=False)
    print(f"Processed {len(rows)} images -> {out_root}")
    print(f"Index written to {index}")
    return out_root


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DATASET_ROOT / "MURA-v1.1")
    parser.add_argument("--out", type=Path, default=DATASET_ROOT / "processed")
    parser.add_argument("--size", type=int, default=CLASSIFIER_INPUT_SIZE)
    args = parser.parse_args()
    preprocess_dataset(args.source, args.out, args.size)


if __name__ == "__main__":
    main()
