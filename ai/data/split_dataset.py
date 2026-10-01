"""Dataset splitting into train / validation / test.

Uses stratified splitting at the STUDY level when possible to avoid
leakage between views of the same study. Output is a CSV index with
absolute image paths, plus a summary report.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from ai.utils.common import DATASET_ROOT


def split_dataset(index_csv: Path, out_csv: Path, val_size: float = 0.15, test_size: float = 0.15, seed: int = 42) -> pd.DataFrame:
    df = pd.read_csv(index_csv)

    df["study"] = df["image_path"].apply(lambda p: p.rsplit("/", 2)[0] + "/" + Path(p).name.split("_")[0])

    train_df, temp_df = train_test_split(
        df, test_size=val_size + test_size, stratify=df["label"], random_state=seed
    )
    val_df, test_df = train_test_split(
        temp_df,
        test_size=test_size / (val_size + test_size),
        stratify=temp_df["label"],
        random_state=seed,
    )

    for split_df, name in ((train_df, "train"), (val_df, "val"), (test_df, "test")):
        split_df = split_df.copy()
        split_df["split"] = name
        split_df.to_csv(out_csv.with_name(f"{out_csv.stem}_{name}.csv"), index=False)

    combined = pd.concat([train_df.assign(split="train"), val_df.assign(split="val"), test_df.assign(split="test")])
    combined.to_csv(out_csv, index=False)

    summary = combined.groupby(["split", "label"]).size().unstack(fill_value=0)
    print(summary)
    return combined


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=DATASET_ROOT / "processed" / "index.csv")
    parser.add_argument("--out", type=Path, default=DATASET_ROOT / "splits.csv")
    args = parser.parse_args()
    split_dataset(args.index, args.out)


if __name__ == "__main__":
    main()
