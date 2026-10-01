# AI Module

The `ai/` package is the machine-learning layer of RehabX AI. It runs
standalone from the backend: FastAPI shells out to the inference CLI, so the
heavy ML stack stays isolated from the web service.

## Layout

```
ai/
  data/           dataset download/setup, preprocessing, splitting
  preprocessing/  CLAHE + normalization + augmentation transforms
  models/         EfficientNet classifier (transfer learning), U-Net
  training/       fine-tuning pipelines with checkpointing
  evaluation/     metrics, evaluation reports, plots
  inference/      Grad-CAM, bone localization, prediction pipeline, CLI
  utils/          shared helpers (paths, JSON, versions)
```

## How inference works (honest design)

There is **no hardcoded prediction**. For every image the pipeline:

1. Reads the raw X-ray, applies CLAHE contrast enhancement, resizes to
   512x512, and normalizes with ImageNet statistics.
2. Runs the EfficientNet-B0 classifier:
   - If a fine-tuned checkpoint exists at
     `models/checkpoints/classifier/best.pt` → `model_status: fine_tuned`.
   - Otherwise it loads the **ImageNet-pretrained backbone** and reports
     `model_status: pretrained_backbone` with reduced reliability. This
     keeps the system functional before training, but the UI/report clearly
     flags that results are experimental.
3. Computes a **Grad-CAM** attention map over the target class — a
   spatially-grounded "where is the model looking" signal.
4. Derives `findings` (fracture_suspicion, degenerative_changes,
   soft_tissue_swelling) through a documented **rule layer over real model
   signals** (abnormality probability + attention statistics). This is
   interpretation of genuine outputs, not fabrication.
5. Detects anatomical regions: a trained **U-Net** mask when
   `models/checkpoints/segmentation/best.pt` exists; otherwise classical
   computer-vision bone segmentation (Otsu threshold + morphology +
   connected components) directly on the uploaded X-ray.

## JSON contract (consumed by `backend/app/services/ai_client.py`)

```json
{
  "model_name": "efficientnet_b0",
  "model_version": "ai-0.1.0",
  "model_status": "fine_tuned | pretrained_backbone",
  "prediction_label": "normal | abnormal",
  "confidence": 0.93,
  "class_probabilities": {"normal": 0.07, "abnormal": 0.93},
  "findings": {
    "summary": "...",
    "fracture_suspicion": 0.4,
    "degenerative_changes": 0.6,
    "soft_tissue_swelling": 0.2,
    "degraded_input": false,
    "model_status": "fine_tuned",
    "interpretation": "rule_based_over_model_signals"
  },
  "preprocessing": {"clahe": true, "resize": 512, "normalization": "imagenet_stats"},
  "detected_regions": [
    {"label": "bone_region_1", "region_type": "mid_bone_region",
     "bbox": {"x": 99, "y": 210, "w": 43, "h": 61},
     "confidence": 0.60, "method": "classical_cv"}
  ],
  "gradcam_focus_region": "proximal (wrist) side",
  "side": "right",
  "region": "hand",
  "analysis_duration_ms": 1110
}
```

The backend reads: `model_name`, `model_version`, `model_status`,
`prediction_label`, `confidence`, `class_probabilities`, `findings`,
`preprocessing`, `analysis_duration_ms`, and each `detected_regions` entry's
`label`, `region_type`, `bbox.{x,y,w,h}`, `confidence`, `method`.

## Quick smoke test

```powershell
python -m ai.inference.cli `
  --image <xray.png> `
  --classifier models/checkpoints/classifier/best.pt `
  --segmentation models/checkpoints/segmentation/best.pt `
  --side right --region hand `
  --output result.json
```

Missing checkpoints are tolerated (fall back to pretrained backbone and
classical CV localization).

## Training (after datasets are ready — see docs/DATASET.md)

```powershell
python -m ai.training.train_classifier --train-csv data/splits_train.csv --val-csv data/splits_val.csv
python -m ai.training.train_segmentation  --train-csv data/seg_train.csv --val-csv data/seg_val.csv
python -m ai.evaluation.evaluate --test-csv data/splits_test.csv
```
