# Datasets

RehabX AI uses **real, properly-licensed datasets only**. We do not scrape
random internet images, and we never fabricate training/evaluation numbers.

## MURA (classification)

**Stanford Musculoskeletal Radiographs (MURA) v1.1**

- 40,561 images from 7 upper-extremity study types; RehabX uses the
  **HAND** and **WRIST** studies.
- Binary labels: `normal` / `abnormal` (radiologist-verified).
- Paper: *Radiologist-Level Deep Learning for Musculoskeletal Abnormalities
  Detection* (arXiv:1712.06957).
- Data use: Stanford research agreement for the official release.

### Setup options

1. **Automatic (recommended for the prototype):** mirror published on
   Hugging Face as `KhalfounMehdi/MURA` (faithful copy of the public MURA
   v1.1 images). Download with:

   ```powershell
   python -m ai.data.setup_dataset --download
   ```

   For a quick smoke test of the whole pipeline (small subset):

   ```powershell
   python -m ai.data.setup_dataset --download --samples 200
   ```

   Verify label conventions at runtime (`label` field: 0 = normal, 1 =
   abnormal) before training — confirm against a handful of manual checks.

2. **Manual:** request MURA from Stanford via the official form, place the
    `MURA-v1.1/` folder
   under `data/`, then
   run:

   ```powershell
   python -m ai.data.setup_dataset --verify
   ```

## GRAZPEDWRI-DX (segmentation / bone localization)

**Graz Pediatric Wrist X-ray dataset**

- 20,327 pediatric wrist X-rays with bounding-box annotations for bones and
  wrist pathologies.
- License: CC BY 4.0. DOI: `10.6084/m9.figshare.14825193`.
- Use to train the U-Net. Convert bounding boxes to binary masks with a
  small script producing `data/seg_{train,val,test}.csv` with
  `image_path`, `mask_path`, `split` columns (see `ai/training/train_segmentation.py`).

## Pipeline

```powershell
# 1. Download / verify
python -m ai.data.setup_dataset --download

# 2. Preprocess (CLAHE + resize to 512x512) -> data/processed/
python -m ai.data.preprocess

# 3. Stratified split -> data/splits*.csv
python -m ai.data.split_dataset

# 4. Train classifier -> models/checkpoints/classifier/best.pt
python -m ai.training.train_classifier --train-csv data/splits_train.csv --val-csv data/splits_val.csv

# 5. Evaluate on held-out test set
python -m ai.evaluation.evaluate --test-csv data/splits_test.csv
```

> All numbers in `reports/` are produced exclusively by these scripts on
> real data. No placeholders, no fabricated metrics.
