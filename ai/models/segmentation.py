"""U-Net segmentation model for bone / joint localization in X-rays.

Trained on GRAZPEDWRI-DX bounding-box annotations (converted to masks)
to produce a foreground/bone mask. When a segmentation checkpoint is not
available, the inference pipeline falls back to classical CV localization
(see ai/inference/localization.py).
"""
from __future__ import annotations

from typing import Optional

import torch
from torch import nn
from torch.nn import functional as F


class DoubleConv(nn.Module):
    def __init__(self, in_ch: int, out_ch: int) -> None:
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)


class UNet(nn.Module):
    """Lightweight U-Net with a 2-class output (background / bone)."""

    def __init__(self, in_channels: int = 1, base: int = 32, num_classes: int = 2) -> None:
        super().__init__()
        self.enc1 = DoubleConv(in_channels, base)
        self.enc2 = DoubleConv(base, base * 2)
        self.enc3 = DoubleConv(base * 2, base * 4)
        self.enc4 = DoubleConv(base * 4, base * 8)
        self.pool = nn.MaxPool2d(2)
        self.bottleneck = DoubleConv(base * 8, base * 16)

        self.up4 = nn.ConvTranspose2d(base * 16, base * 8, 2, stride=2)
        self.dec4 = DoubleConv(base * 16, base * 8)
        self.up3 = nn.ConvTranspose2d(base * 8, base * 4, 2, stride=2)
        self.dec3 = DoubleConv(base * 8, base * 4)
        self.up2 = nn.ConvTranspose2d(base * 4, base * 2, 2, stride=2)
        self.dec2 = DoubleConv(base * 4, base * 2)
        self.up1 = nn.ConvTranspose2d(base * 2, base, 2, stride=2)
        self.dec1 = DoubleConv(base * 2, base)
        self.head = nn.Conv2d(base, num_classes, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.dim() == 3:
            x = x.unsqueeze(1)
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        e4 = self.enc4(self.pool(e3))
        b = self.bottleneck(self.pool(e4))

        d4 = torch.cat([self.up4(b), e4], dim=1)
        d4 = self.dec4(d4)
        d3 = torch.cat([self.up3(d4), e3], dim=1)
        d3 = self.dec3(d3)
        d2 = torch.cat([self.up2(d3), e2], dim=1)
        d2 = self.dec2(d2)
        d1 = torch.cat([self.up1(d2), e1], dim=1)
        d1 = self.dec1(d1)
        return self.head(d1)


def load_unet(checkpoint_path: str, device: str = "cpu") -> Optional[torch.nn.Module]:
    """Load a trained U-Net, or return None if unavailable."""
    from pathlib import Path

    if not checkpoint_path or not Path(checkpoint_path).exists():
        return None
    ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model = UNet(
        in_channels=ckpt.get("in_channels", 1),
        base=ckpt.get("base", 32),
        num_classes=ckpt.get("num_classes", 2),
    )
    model.load_state_dict(ckpt["model_state_dict"])
    model.to(device).eval()
    return model
