"""Bridge between the FastAPI backend and the standalone AI inference CLI.

The AI layer lives in the `ai/` package (PyTorch + OpenCV). The backend
shells out to `python -m ai.inference.cli` so the heavy ML dependencies
stay isolated from the web service.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from app.core.config import get_settings


class AiInferenceError(RuntimeError):
    pass


def _repo_root() -> Path:
    # Repo root = two levels up from app/services/ai_client.py
    return Path(__file__).resolve().parents[3]


def _ai_module_dir() -> str:
    # Parent directory that contains the `ai` package (repo root).
    return str(_repo_root())


def run_inference(
    image_path: str,
    *,
    affected_side: str,
    affected_region: str,
) -> dict[str, Any]:
    """Run the real AI pipeline on a stored image and return parsed JSON."""
    settings = get_settings()
    start = time.monotonic()

    cli = sys.executable
    if settings.ai_inference_cli and settings.ai_inference_cli != "python":
        cli = settings.ai_inference_cli

    with tempfile.TemporaryDirectory(prefix="rehabx_ai_") as tmp:
        output_file = Path(tmp) / "result.json"
        cmd = [
            cli,
            "-m",
            "ai.inference.cli",
            "--image", image_path,
            "--classifier", str(settings.resolved_model_root / "checkpoints" / "classifier" / "best.pt"),
            "--segmentation", str(settings.resolved_model_root / "checkpoints" / "segmentation" / "best.pt"),
            "--side", affected_side,
            "--region", affected_region,
            "--output", str(output_file),
        ]
        # Inherit the parent environment: a bare env dict on Windows drops
        # SystemRoot/PATH, which breaks Winsock init in the child
        # (WinError 10106 on `import asyncio`).
        env = {
            **os.environ,
            "PYTHONPATH": _ai_module_dir(),
            "PYTHONUNBUFFERED": "1",
        }

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=settings.ai_inference_timeout_seconds,
                cwd=_repo_root(),
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise AiInferenceError("AI inference timed out") from exc

        if proc.returncode != 0:
            stderr = (proc.stderr or "")[-4000:]
            raise AiInferenceError(f"AI inference failed (exit {proc.returncode}): {stderr}")

        if not output_file.exists():
            raise AiInferenceError("AI inference produced no output file")

        try:
            result = json.loads(output_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AiInferenceError("AI inference returned invalid JSON") from exc

        result["analysis_duration_ms"] = int((time.monotonic() - start) * 1000)
        return result
