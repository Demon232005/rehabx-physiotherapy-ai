"""Transfer-learning classifier for hand/wrist X-ray abnormality detection.

The backbone is a pretrained EfficientNet-B0 (ImageNet). The final
classification head is replaced with a task head and fine-tuned on the
MURA hand/wrist subset. The architecture is modular: swap the backbone
by changing the factory function (e.g. resnet50, densenet121,
vit_b_16) without touching the training or inference pipelines.
"""
from __future__ import annotations

from typing import Any

import torch
from torch import nn
from torchvision import models

BACKBONES = {
    "efficientnet_b0": models.efficientnet_b0,
    "efficientnet_b2": models.efficientnet_b2,
    "resnet50": models.resnet50,
    "densenet121": models.densenet121,
}


class XrayClassifier(nn.Module):
    """Binary normal/abnormal classifier built on a pretrained backbone."""

    def __init__(self, backbone: str = "efficientnet_b0", num_classes: int = 2, weights: str | None = "DEFAULT") -> None:
        super().__init__()
        if backbone not in BACKBONES:
            raise ValueError(f"Unsupported backbone '{backbone}'. Choose from {sorted(BACKBONES)}")
        self.backbone_name = backbone

        factory = BACKBONES[backbone]
        kwargs: dict[str, Any] = {}
        if weights:
            kwargs["weights"] = getattr(models, f"{backbone.replace('efficientnet_b', 'EfficientNet_B').upper()}Weights", "DEFAULT") if backbone.startswith("efficientnet") else None
        self.model = factory(weights=weights)

        in_features = self._classifier_in_features()
        self._replace_head(in_features, num_classes)

    def _classifier_in_features(self) -> int:
        model = self.model
        if self.backbone_name.startswith("efficientnet"):
            return model.classifier[1].in_features
        if self.backbone_name.startswith("resnet"):
            return model.fc.in_features
        if self.backbone_name.startswith("densenet"):
            return model.classifier.in_features
        raise ValueError(self.backbone_name)

    def _replace_head(self, in_features: int, num_classes: int) -> None:
        if self.backbone_name.startswith("efficientnet"):
            self.model.classifier = nn.Sequential(
                nn.Dropout(p=0.2, inplace=True),
                nn.Linear(in_features, num_classes),
            )
        elif self.backbone_name.startswith("resnet"):
            self.model.fc = nn.Linear(in_features, num_classes)
        elif self.backbone_name.startswith("densenet"):
            self.model.classifier = nn.Linear(in_features, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.model(x)

    def features(self, x: torch.Tensor) -> torch.Tensor:
        """Activations before the final head (used for Grad-CAM / embeddings)."""
        if self.backbone_name.startswith("efficientnet"):
            x = self.model.features(x)
            x = self.model.avgpool(x)
            return torch.flatten(x, 1)
        if self.backbone_name.startswith("resnet"):
            x = self.model.conv1(x)
            x = self.model.bn1(x)
            x = self.model.relu(x)
            x = self.model.maxpool(x)
            x = self.model.layer1(x)
            x = self.model.layer2(x)
            x = self.model.layer3(x)
            x = self.model.layer4(x)
            x = self.model.avgpool(x)
            return torch.flatten(x, 1)
        if self.backbone_name.startswith("densenet"):
            x = self.model.features(x)
            x = nn.functional.relu(x, inplace=True)
            x = nn.functional.adaptive_avg_pool2d(x, (1, 1))
            return torch.flatten(x, 1)
        raise ValueError(self.backbone_name)

    def feature_activations(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Return (features, pre-head spatial activations) for Grad-CAM."""
        if self.backbone_name.startswith("efficientnet"):
            act = self.model.features(x)
            pooled = self.model.avgpool(act)
            return torch.flatten(pooled, 1), act
        if self.backbone_name.startswith("resnet"):
            h = self.model.conv1(x)
            h = self.model.bn1(h)
            h = self.model.relu(h)
            h = self.model.maxpool(h)
            h = self.model.layer1(h)
            h = self.model.layer2(h)
            h = self.model.layer3(h)
            h = self.model.layer4(h)
            pooled = self.model.avgpool(h)
            return torch.flatten(pooled, 1), h
        if self.backbone_name.startswith("densenet"):
            act = self.model.features(x)
            pooled = nn.functional.relu(act, inplace=True)
            pooled = nn.functional.adaptive_avg_pool2d(pooled, (1, 1))
            return torch.flatten(pooled, 1), act
        raise ValueError(self.backbone_name)


def load_classifier(checkpoint_path: str, device: str = "cpu", backbone: str = "efficientnet_b0") -> tuple[XrayClassifier, dict]:
    """Load a fine-tuned classifier from checkpoint.

    Returns (model, metadata). Raises FileNotFoundError if the checkpoint
    is missing, so callers can fall back to a pretrained-backbone model.
    """
    from ai.utils.common import MODEL_ROOT

    ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model = XrayClassifier(backbone=ckpt.get("backbone", backbone), num_classes=2, weights=None)
    model.load_state_dict(ckpt["model_state_dict"])
    model.to(device).eval()
    return model, ckpt.get("metadata", {})
