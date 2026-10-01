"""Extract text from an uploaded X-ray report file.

Supported inputs: plain text (.txt/.md), PDF (.pdf), and report images
(.png/.jpg/.jpeg). PDFs use pypdf; report scans use EasyOCR (torch-based).
EasyOCR downloads its model weights on first use.
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, UnidentifiedImageError

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".png", ".jpg", ".jpeg"}
MAX_REPORT_FILE_BYTES = 10 * 1024 * 1024

_OCR_READER = None


def _get_ocr_reader():
    global _OCR_READER
    if _OCR_READER is None:
        import easyocr

        _OCR_READER = easyocr.Reader(["en"], gpu=False, verbose=False)
    return _OCR_READER


def _from_text(data: bytes) -> str:
    for encoding in ("utf-8", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _from_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001 — a bad page must not kill extraction
            pages.append("")
    return "\n".join(pages).strip()


def _from_image(data: bytes) -> str:
    import numpy as np

    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("Report image is not a valid image") from exc

    reader = _get_ocr_reader()
    arr = np.array(img.convert("RGB"))
    results = reader.readtext(arr, detail=0, paragraph=True)
    return "\n".join(results).strip()


def extract_report_text(filename: str, data: bytes) -> str:
    """Extract human-readable text from a report file.

    Raises ValueError for unsupported types, oversize files, or unreadable
    content.
    """
    if len(data) > MAX_REPORT_FILE_BYTES:
        raise ValueError(
            f"Report file exceeds maximum size of {MAX_REPORT_FILE_BYTES // (1024 * 1024)} MB"
        )

    ext = Path(filename or "").suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            "Unsupported report file type; use .txt, .pdf, .png or .jpg"
        )

    if ext in (".txt", ".md"):
        return _from_text(data)
    if ext == ".pdf":
        text = _from_pdf(data)
    else:
        text = _from_image(data)

    if not text.strip():
        raise ValueError(
            "No text could be read from the report file "
            "(PDF may be scanned; try a text PDF or an image of the report)"
        )
    return text.strip()
