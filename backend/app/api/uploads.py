"""X-ray upload and preview endpoints."""
from __future__ import annotations

import fastapi
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep
from app.models import XrayUpload
from app.schemas import MessageOut, ReportFileParsedOut, ReportParsedOut, UploadOut, UploadPreviewOut
from app.services import report_parser, storage
from app.services.report_file import extract_report_text as _extract_report_text

router = APIRouter(prefix="/uploads", tags=["uploads"])

SIDE_PATTERN = {"left", "right", "bilateral"}
REGION_PATTERN = {"hand", "wrist", "fingers", "thumb", "palm", "forearm", "elbow", "upper_arm", "shoulder"}


@router.post("/parse-report", response_model=ReportParsedOut)
def parse_report(text: str = Form(...)) -> dict:
    """Preview what the report parser will extract from a free-text report."""
    return report_parser.parse_report(text)


@router.post("/parse-report-file", response_model=ReportFileParsedOut)
async def parse_report_file(report_file: UploadFile = File(...)) -> dict:
    """Extract text from an uploaded report file and preview the parse."""
    data = await report_file.read()
    try:
        text = _extract_report_text(report_file.filename or "", data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return {"filename": report_file.filename, "text": text, "parsed": report_parser.parse_report(text)}


@router.post("", response_model=UploadOut, status_code=status.HTTP_201_CREATED)
async def upload_xray(
    user: CurrentUser,
    db: DbDep,
    file: UploadFile | None = File(default=None),
    affected_side: str = Form("right"),
    affected_region: str = Form("wrist"),
    xray_report: str = Form(""),
    report_file: UploadFile | None = File(default=None),
) -> XrayUpload:
    if affected_side not in SIDE_PATTERN:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="affected_side must be left, right or bilateral")
    if affected_region not in REGION_PATTERN:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="affected_region must be one of: " + ", ".join(sorted(REGION_PATTERN)))

    # The X-ray image is optional; the report file is what drives the analysis.
    data: bytes | None = None
    filename = "report-only"
    if file is not None:
        # Read fully in memory so we can validate the actual bytes.
        data = await file.read()
        if len(data) > 10 * 1024 * 1024:  # read cap; real limit enforced in validate_image
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Uploaded file too large",
            )
        filename = file.filename or "xray"

    report_bytes = b""
    if report_file is not None:
        report_bytes = await report_file.read()
        if len(report_bytes) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Report file too large",
            )

    try:
        report_text = (
            xray_report.strip() or None
        )
        if report_bytes:
            try:
                file_text = _extract_report_text(report_file.filename or "", report_bytes)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
                ) from exc
            report_text = "\n".join(part for part in (report_text, file_text) if part)
    except HTTPException:
        raise
    parsed_report = report_parser.parse_report(report_text)
    if not report_text and data is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Please upload the X-ray report file (PDF, image or text).",
        )

    # If a report is supplied, the report wins for side/region/severity/condition.
    if parsed_report.get("affected_side"):
        affected_side = parsed_report["affected_side"]
    if parsed_report.get("affected_region"):
        affected_region = parsed_report["affected_region"]

    try:
        upload = storage.save_upload(
            db,
            user_id=user.id,
            original_filename=filename,
            data=data,
            affected_side=affected_side,
            affected_region=affected_region,
            xray_report=report_text,
            report_parsed=parsed_report or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    if report_bytes and report_file is not None:
        try:
            storage.save_report_file(db, upload, report_file.filename or "report.txt", report_bytes)
        except OSError as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not store report file") from exc
    return upload


def _get_own_upload(db: DbDep, user: CurrentUser, upload_id: str) -> XrayUpload:
    upload = db.scalar(select(XrayUpload).where(XrayUpload.id == upload_id, XrayUpload.user_id == user.id))
    if not upload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found")
    return upload


@router.get("/{upload_id}", response_model=UploadOut)
def get_upload(upload_id: str, user: CurrentUser, db: DbDep) -> XrayUpload:
    return _get_own_upload(db, user, upload_id)


def _require_image(upload: XrayUpload) -> None:
    if upload.storage_key.startswith("report-only/"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No X-ray image was uploaded")


@router.get("/{upload_id}/preview", response_model=UploadPreviewOut)
def get_upload_preview(upload_id: str, user: CurrentUser, db: DbDep) -> UploadPreviewOut:
    upload = _get_own_upload(db, user, upload_id)
    _require_image(upload)
    return UploadPreviewOut(id=upload.id, image_url=storage.build_shortlived_preview_url(upload))


@router.get("/{upload_id}/image", response_class=fastapi.responses.Response)
def get_upload_image(upload_id: str, user: CurrentUser, db: DbDep) -> fastapi.responses.Response:
    """Stream the actual X-ray bytes to the authenticated owner only.

    X-rays are never served from a public URL; access requires a valid
    bearer token and ownership of the record.
    """
    upload = _get_own_upload(db, user, upload_id)
    _require_image(upload)
    data = storage.read_bytes(upload)
    media_type = upload.content_type or "image/jpeg"
    return fastapi.responses.Response(content=data, media_type=media_type)


@router.get("/{upload_id}/report-file", response_class=fastapi.responses.Response)
def get_report_file(upload_id: str, user: CurrentUser, db: DbDep) -> fastapi.responses.Response:
    """Stream the original uploaded report file (image/PDF/text) to its owner."""
    upload = _get_own_upload(db, user, upload_id)
    if not storage.has_report_file(upload):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No report file stored")
    data, media_type = storage.read_report_file(upload)
    return fastapi.responses.Response(
        content=data,
        media_type=media_type,
        headers={
            "Content-Disposition": f'inline; filename="{upload.report_file_name or "report"}"',
            "Cache-Control": "private, max-age=300",
        },
    )


@router.delete("/{upload_id}", response_model=MessageOut)
def delete_upload(upload_id: str, user: CurrentUser, db: DbDep) -> MessageOut:
    upload = _get_own_upload(db, user, upload_id)
    db.delete(upload)
    db.commit()
    return MessageOut(message="Upload deleted")
