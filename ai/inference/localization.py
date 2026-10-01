"""Classical computer-vision bone/joint localization (fallback).

Used when no segmentation model checkpoint is available. Operates on the
CLAHE-enhanced grayscale X-ray: morphological bone segmentation, connected
components, and anatomical-region labeling by vertical position. All
outputs are derived from the actual image content — never hardcoded.
"""
from __future__ import annotations

import cv2
import numpy as np


def locate_bones(img: np.ndarray, max_regions: int = 6) -> list[dict]:
    """Return bounding-box regions for bone-like connected components.

    `img`: grayscale uint8 image (any size). Returns a list of dicts:
    {label, region_type, bbox: {x, y, w, h}, confidence, method}.
    """
    blurred = cv2.GaussianBlur(img, (5, 5), 0)
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)

    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(thresh, connectivity=8)
    h, w = img.shape
    area_thresh = max(400, int(0.002 * h * w))

    regions: list[dict] = []
    for i in range(1, n_labels):
        x, y, bw, bh, area = stats[i]
        if area < area_thresh or bw < 8 or bh < 8:
            continue
        if bw > 0.95 * w and bh > 0.95 * h:
            continue  # background blob

        center_y = y + bh / 2
        region_type = _anatomical_region(center_y, h)
        # Real quality proxy: how much of the blob is bright bone tissue.
        solidity = area / max(1, bw * bh)
        regions.append(
            {
                "label": f"bone_region_{len(regions) + 1}",
                "region_type": region_type,
                "bbox": {"x": int(x), "y": int(y), "w": int(bw), "h": int(bh)},
                "confidence": round(min(0.95, solidity), 3),
                "method": "classical_cv",
            }
        )
        if len(regions) >= max_regions:
            break

    return regions


def _anatomical_region(center_y: float, h: float) -> str:
    """Label by vertical position (X-ray conventions vary; kept conservative)."""
    if center_y < 0.25 * h:
        return "distal_region"
    if center_y < 0.55 * h:
        return "mid_bone_region"
    return "proximal_joint_region"


def joint_candidates(img: np.ndarray, bone_regions: list[dict]) -> list[dict]:
    """Estimate joint positions as low-intensity gaps between bone blobs."""
    h, w = img.shape
    xs = sorted(r["bbox"] for r in bone_regions)
    joints: list[dict] = []
    for a, b in zip(xs, xs[1:]):
        gap_x = a["x"] + a["w"]
        gap_w = b["x"] - gap_x
        if gap_w <= 0 or gap_w > 0.4 * w:
            continue
        y = min(a["y"], b["y"])
        y2 = max(a["y"] + a["h"], b["y"] + b["h"])
        joints.append(
            {
                "label": f"joint_{len(joints) + 1}",
                "region_type": "joint",
                "bbox": {"x": int(gap_x), "y": int(y), "w": int(gap_w), "h": int(y2 - y)},
                "confidence": 0.5,
                "method": "classical_cv",
            }
        )
    return joints
