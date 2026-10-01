"""Command-line entrypoint for AI inference.

Invoked by the backend as::

    python -m ai.inference.cli \
        --image <path> \
        --classifier <path> \
        --segmentation <path> \
        --side <left|right> \
        --region <hand|wrist|...> \
        --output <json>

Writes a single JSON object to --output and exits 0 on success,
non-zero with a message on stderr on failure.
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

from ai.inference.predict import predict_image


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="ai.inference.cli", description=__doc__)
    parser.add_argument("--image", required=True, help="Path to the X-ray image")
    parser.add_argument("--classifier", default=None, help="Optional fine-tuned classifier checkpoint")
    parser.add_argument("--segmentation", default=None, help="Optional trained segmentation checkpoint")
    parser.add_argument("--side", default="right", choices=["left", "right", "unknown"])
    parser.add_argument("--region", default="hand", choices=["hand", "wrist", "fingers", "unknown"])
    parser.add_argument("--output", required=True, help="Path for the JSON result file")
    parser.add_argument("--device", default="cpu", help="torch device (cpu, cuda)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = predict_image(
            image_path=args.image,
            classifier_checkpoint=args.classifier,
            segmentation_checkpoint=args.segmentation,
            side=args.side,
            region=args.region,
            device=args.device,
        )
        Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
        return 0
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc(file=sys.stderr)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
