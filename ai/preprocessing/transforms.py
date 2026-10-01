"""Preprocessing and augmentation transforms shared by training and inference.

X-ray workflow:
    raw image -> (optional) CLAHE contrast enhancement
              -> resize
              -> convert to 3-channel RGB
              -> tensor + ImageNet-style normalization
"""
from __future__ import annotations

import cv2
import numpy as np
import torch
from torchvision import transforms

from ai.utils.common import IMG_MEAN, IMG_STD


def read_grayscale(path: str) -> np.ndarray:
    """Read an image as float32 grayscale (0..255)."""
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"Cannot read image: {path}")
    return img.astype(np.float32)


def apply_clahe(img: np.ndarray, clip_limit: float = 2.0, tile_grid_size: int = 8) -> np.ndarray:
    """Contrast-limited adaptive histogram equalization for X-ray contrast."""
    if img.dtype != np.uint8:
        img = np.clip(img, 0, 255).astype(np.uint8)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile_grid_size, tile_grid_size))
    return clahe.apply(img)


def preprocess_grayscale_for_model(img: np.ndarray, size: int = 512) -> torch.Tensor:
    """Standard preprocessing used at inference time (no augmentation)."""
    img = apply_clahe(img)
    img = cv2.resize(img, (size, size), interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    rgb = np.clip(rgb, 0, 255).astype(np.float32) / 255.0
    tensor = torch.from_numpy(rgb).permute(2, 0, 1)
    norm = transforms.Normalize(mean=IMG_MEAN, std=IMG_STD)
    return norm(tensor).unsqueeze(0)


def make_train_transforms(size: int = 512) -> transforms.Compose:
    """Training pipeline with augmentation (X-ray appropriate)."""
    return transforms.Compose(
        [
            transforms.ToPILImage(),
            transforms.RandomAffine(degrees=8, translate=(0.05, 0.05), scale=(0.9, 1.1)),
            transforms.ColorJitter(brightness=0.15, contrast=0.15),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.Resize((size, size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMG_MEAN, std=IMG_STD),
        ]
    )


def make_valid_transforms(size: int = 512) -> transforms.Compose:
    """Validation/test pipeline (no augmentation)."""
    return transforms.Compose(
        [
            transforms.ToPILImage(),
            transforms.Resize((size, size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMG_MEAN, std=IMG_STD),
        ]
    )
