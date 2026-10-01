"""Secure image storage.

Local filesystem by default; S3-compatible object storage optionally.
X-rays are stored under random UUID keys, never under user-controlled
names, and are never exposed through public URLs.
"""
from __future__ import annotations

import io
import mimetypes
import uuid
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import XrayUpload
from app.services import audit

_STORAGE_DIR_NAME = "xray"


def _key_for(extension: str) -> str:
    return f"{uuid.uuid4().hex}{extension}"


def _local_root() -> Path:
    settings = get_settings()
    root = settings.resolved_storage_dir / _STORAGE_DIR_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def validate_image(data: bytes) -> tuple[str, tuple[int, int]]:
    """Validate that bytes are a real image and not a disguised file.

    Returns (normalized_extension, (width, height)). Raises ValueError on
    any problem. Never trusts the declared MIME type / filename.
    """
    settings = get_settings()
    if len(data) > settings.max_upload_bytes:
        raise ValueError(f"File exceeds maximum upload size of {settings.max_upload_bytes} bytes")

    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("Uploaded file is not a valid image") from exc

    fmt = (img.format or "").lower()
    mime_map = {"png": "image/png", "jpeg": "image/jpg", "jpg": "image/jpg"}
    mime = mime_map.get(fmt)
    if mime is None or mime not in settings.allowed_types:
        raise ValueError(f"Unsupported image format '{fmt or 'unknown'}'")

    width, height = img.size
    if width <= 0 or height <= 0:
        raise ValueError("Image has invalid dimensions")
    if width > settings.max_image_dimension or height > settings.max_image_dimension:
        raise ValueError(f"Image dimensions exceed the maximum of {settings.max_image_dimension}px")
    if img.mode not in ("L", "RGB", "RGBA"):
        # Convert exotic modes to a safe representation later during preprocessing.
        pass

    ext = ".png" if fmt == "png" else ".jpg"
    return ext, (width, height)


def save_upload(
    db: Session,
    user_id: str,
    original_filename: str,
    data: bytes | None,
    affected_side: str | None = None,
    affected_region: str | None = None,
    xray_report: str | None = None,
    report_parsed: dict | None = None,
) -> XrayUpload:
    """Persist an upload. ``data=None`` creates a report-only record
    (no image was supplied); such rows carry a ``report-only/`` storage key."""
    if data is None:
        settings = get_settings()
        upload = XrayUpload(
            user_id=user_id,
            original_filename=Path(original_filename).name[:255],
            storage_key=f"report-only/{uuid.uuid4().hex}",
            content_type="application/octet-stream",
            file_size_bytes=0,
            affected_side=affected_side,
            affected_region=affected_region,
            xray_report=xray_report,
            report_parsed=report_parsed,
            status="uploaded",
        )
        db.add(upload)
        db.commit()
        db.refresh(upload)
        audit.log(db, user_id=user_id, action="xray.upload", entity_type="xray_upload", entity_id=upload.id)
        return upload

    ext, (width, height) = validate_image(data)
    mime = "image/png" if ext == ".png" else "image/jpg"
    key = _key_for(ext)

    settings = get_settings()
    if settings.storage_backend == "s3":
        from app.services.s3 import upload_object

        upload_object(key, data, mime)
    else:
        target = _local_root() / key
        target.write_bytes(data)

    upload = XrayUpload(
        user_id=user_id,
        original_filename=Path(original_filename).name[:255],
        storage_key=key,
        content_type=mime,
        file_size_bytes=len(data),
        image_width=width,
        image_height=height,
        affected_side=affected_side,
        affected_region=affected_region,
        xray_report=xray_report,
        report_parsed=report_parsed,
        status="uploaded",
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)
    audit.log(db, user_id=user_id, action="xray.upload", entity_type="xray_upload", entity_id=upload.id)
    return upload


def read_bytes(upload: XrayUpload) -> bytes:
    settings = get_settings()
    if settings.storage_backend == "s3":
        from app.services.s3 import download_object

        return download_object(upload.storage_key)
    return (_local_root() / upload.storage_key).read_bytes()


REPORT_FILE_MIMES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpg",
    ".jpeg": "image/jpeg",
    ".txt": "text/plain",
    ".md": "text/markdown",
}


def save_report_file(db: Session, upload: XrayUpload, filename: str, data: bytes) -> None:
    """Persist the original uploaded report file and link it to the upload."""
    ext = Path(filename).suffix.lower()
    mime = REPORT_FILE_MIMES.get(ext, "application/octet-stream")
    key = f"report-files/{uuid.uuid4().hex}{ext}"

    settings = get_settings()
    if settings.storage_backend == "s3":
        from app.services.s3 import upload_object

        upload_object(key, data, mime)
    else:
        target = _local_root() / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    upload.report_file_key = key
    upload.report_file_name = Path(filename).name[:255]
    db.commit()
    db.refresh(upload)


def has_report_file(upload: XrayUpload) -> bool:
    return bool(upload.report_file_key)


def read_report_file(upload: XrayUpload) -> tuple[bytes, str]:
    """Return (bytes, media_type) for the stored report file."""
    ext = Path(upload.report_file_key or "").suffix.lower()
    mime = REPORT_FILE_MIMES.get(ext, "application/octet-stream")
    settings = get_settings()
    if settings.storage_backend == "s3":
        from app.services.s3 import download_object

        return download_object(upload.report_file_key), mime
    return (_local_root() / upload.report_file_key).read_bytes(), mime


def build_shortlived_preview_url(upload: XrayUpload, signed_ttl_seconds: int = 900) -> str:
    """Return a URL to a short-lived, single-user endpoint (never a public URL).

    In the local backend the preview is served by an authenticated endpoint,
    so this simply returns the API route the frontend must call with its token.
    """
    return f"/api/v1/uploads/{upload.id}/preview"
