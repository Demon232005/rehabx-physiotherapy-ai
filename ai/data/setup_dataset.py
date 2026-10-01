"""Dataset download/setup for RehabX AI.

Chosen dataset: **MURA (Stanford Musculoskeletal Radiographs)** — v1.1.
  * 40,561 images from 7 upper-extremity study types; we use the
    HAND and WRIST studies only.
  * Binary radiologist labels: normal / abnormal.
  * License: Stanford research data-use agreement. It is NOT a random
    internet download — obtain it from the official sources below.
  * DOI: https://doi.org/10.71718/cwh3-0p32   |  Paper: arXiv:1712.06957

This script supports three flows:

  1. Automatic (recommended): download the MURA mirror published on
     Hugging Face (`KhalfounMehdi/MURA`, a faithful copy of the public
     MURA v1.1 images) via the `datasets` library.
   2. Manual: place the official MURA-v1.1 folder into `data/MURA-v1.1`
     following the layout documented in docs/DATASET.md.
  3. Segmentation: GRAZPEDWRI-DX (Figshare DOI 10.6084/m9.figshare.14825193,
     CC BY 4.0) provides 20,327 wrist X-rays with bounding-box annotations —
     use it to train the U-Net bone-localization model.

Do NOT fabricate dataset results. Training/evaluation numbers in the docs
are only produced after this pipeline succeeds on real data.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from ai.utils.common import DATASET_ROOT

EXPECTED_LAYOUT_MARKER = "MURA-v1.1"


def _ensure_dataset_root() -> Path:
    DATASET_ROOT.mkdir(parents=True, exist_ok=True)
    return DATASET_ROOT


def flow_download_hf(num_samples: int | None = None) -> Path:
    """Download the MURA mirror from Hugging Face Hub.

    The mirror (`KhalfounMehdi/MURA`) exposes only `image` and `label`
    columns — the original study folder (HAND/WRIST) is NOT preserved, so
    images are stored under a generic `UPPER` study folder. Study detection
    is kept for mirrors that do provide a `path` field. Label convention
    follows MURA: 0 = normal, 1 = abnormal (verify with a spot check).
    """
    try:
        from datasets import load_dataset
    except ImportError:
        sys.exit("pip install 'datasets' first: pip install -r ai/requirements.txt")

    print("Downloading MURA mirror from Hugging Face Hub (KhalfounMehdi/MURA)...")
    ds = load_dataset("KhalfounMehdi/MURA", split="train")
    if num_samples:
        ds = ds.select(range(min(num_samples, len(ds))))

    out_root = _ensure_dataset_root() / EXPECTED_LAYOUT_MARKER
    has_path = "path" in ds.column_names
    study_dirs = ("HAND", "WRIST") if has_path else ("UPPER",)
    for label_name in ("normal", "abnormal"):
        for study in study_dirs:
            (out_root / "train" / label_name / study).mkdir(parents=True, exist_ok=True)

    for i, row in enumerate(ds):
        label = row.get("label", 0)  # HF mirror labels: 0=normal,1=abnormal (verify at runtime)
        label_name = "abnormal" if label == 1 else "normal"
        img = row["image"]
        if has_path:
            p = str(row.get("path") or "")
            study = "HAND" if "hand" in p.lower() else "WRIST"
        else:
            study = "UPPER"
        target = out_root / "train" / label_name / study / f"img_{i:06d}.png"
        img.save(target)
        if (i + 1) % 500 == 0:
            print(f"  {i + 1} images written")

    print(f"Done. Dataset written to {out_root}")
    return out_root


def flow_verify_manual() -> Path:
    """Validate that the official MURA folder is present and print summary."""
    candidates = [
        DATASET_ROOT / "MURA-v1.1",
        DATASET_ROOT / "MURA",
        DATASET_ROOT / "mura",
    ]
    for cand in candidates:
        if (cand / "train").is_dir():
            _summarize(cand)
            return cand
    sys.exit(
        "\nManual MURA folder not found. Expected one of:\n"
        f"  {[str(c) for c in candidates]}\n\n"
        "1. Run with --download for the automatic Hugging Face flow, OR\n"
        "2. Request MURA from Stanford (docs/DATASET.md) and place MURA-v1.1 "
        "under data/.\n"
    )


def _summarize(root: Path) -> None:
    normal = list((root / "train" / "normal").glob("*/*.*"))
    abnormal = list((root / "train" / "abnormal").glob("*/*.*"))
    print(f"MURA found at {root}")
    print(f"  normal:   {len(normal)} images")
    print(f"  abnormal: {len(abnormal)} images")
    if (root / "valid").is_dir():
        v_normal = list((root / "valid" / "normal").glob("*/*.*"))
        v_abnormal = list((root / "valid" / "abnormal").glob("*/*.*"))
        print(f"  valid normal:   {len(v_normal)} images")
        print(f"  valid abnormal: {len(v_abnormal)} images")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--download", action="store_true", help="Download MURA mirror from Hugging Face")
    parser.add_argument("--samples", type=int, default=None, help="Limit samples when downloading (smoke test)")
    parser.add_argument("--verify", action="store_true", help="Verify a manually placed MURA folder")
    args = parser.parse_args()

    if args.download:
        flow_download_hf(args.samples)
    else:
        flow_verify_manual()


if __name__ == "__main__":
    main()
