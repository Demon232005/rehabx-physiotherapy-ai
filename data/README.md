# data/

Downloaded/processed X-ray datasets live here (gitignored). See
`docs/DATASET.md` for sources (MURA v1.1, GRAZPEDWRI-DX), licensing, and the
full download → preprocess → split → train → evaluate pipeline.

> Named `data/` (not `datasets/`) so the top-level folder never shadows the
> Hugging Face `datasets` Python package used by `ai/data/setup_dataset.py`.

Structure produced by the pipeline:

```
data/
  MURA-v1.1/        raw MURA images (hand/wrist studies)
  processed/        CLAHE + 512x512 normalized images + index.csv
  splits*.csv       stratified train/val/test indices
  seg_*.csv         segmentation indices (image_path, mask_path, split)
```
