"""Grad-CAM attention maps for abnormality localization.

Provides a spatially-grounded *where is the model looking* signal that is
real (derived from the trained model's gradients/activations), used to
derive the `findings` sub-scores and the anomaly emphasis region.
"""
from __future__ import annotations

import cv2
import numpy as np
import torch
from torch.nn import functional as F

from ai.models.classifier import XrayClassifier


def grad_cam_heatmap(
    model: XrayClassifier,
    input_tensor: torch.Tensor,
    target_class: int | None = None,
) -> np.ndarray:
    """Compute a Grad-CAM heatmap (float32, 0..1, model input size)."""
    model.eval()
    spatial: torch.Tensor | None = None
    activations: list[torch.Tensor] = []
    gradients: list[torch.Tensor] = []

    def forward_hook(_m, _i, output: torch.Tensor) -> None:
        activations.append(output)

    def backward_hook(_m, _i, output) -> None:
        gradients.append(output[0])

    feature_module = _find_feature_module(model)
    handle_fwd = feature_module.register_forward_hook(forward_hook)
    handle_bwd = feature_module.register_full_backward_hook(backward_hook)

    input_tensor = input_tensor.requires_grad_(True)
    logits = model(input_tensor)
    if target_class is None:
        target_class = int(logits.argmax(dim=1).item())

    model.zero_grad()
    one_hot = torch.zeros_like(logits)
    one_hot[0, target_class] = 1.0
    logits.backward(gradient=one_hot, retain_graph=True)

    act = activations[0].detach()
    grad = gradients[0].detach()
    handle_fwd.remove()
    handle_bwd.remove()

    weights = grad.mean(dim=(2, 3), keepdim=True)
    cam = F.relu(weights * act).sum(dim=1, keepdim=True).squeeze(1)[0]
    cam = F.interpolate(cam.unsqueeze(0).unsqueeze(0), size=input_tensor.shape[2:], mode="bilinear", align_corners=False)
    cam = cam[0, 0].detach().cpu().numpy()
    cam = np.maximum(cam, 0)
    if cam.max() > 0:
        cam = cam / cam.max()
    return cam


def overlay_heatmap(image: np.ndarray, heatmap: np.ndarray, alpha: float = 0.45) -> np.ndarray:
    """Blend a (0..1) heatmap onto a grayscale image, returning BGR uint8."""
    if image.ndim == 2:
        base = cv2.cvtColor(np.clip(image, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    else:
        base = np.clip(image, 0, 255).astype(np.uint8)
    heat = np.uint8(255 * np.clip(heatmap, 0, 1))
    heat_color = cv2.applyColorMap(heat, cv2.COLORMAP_JET)
    return cv2.addWeighted(heat_color, alpha, base, 1 - alpha, 0)


def _find_feature_module(model: XrayClassifier) -> torch.nn.Module:
    if model.backbone_name.startswith("efficientnet"):
        return model.model.features[-1]
    if model.backbone_name.startswith("resnet"):
        return model.model.layer4[-1]
    if model.backbone_name.startswith("densenet"):
        return model.model.features
    raise ValueError(f"Unsupported backbone for Grad-CAM: {model.backbone_name}")
