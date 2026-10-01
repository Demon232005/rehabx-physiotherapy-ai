"""Analysis orchestration service.

Flow: upload -> preprocess (AI CLI) -> classifier -> detected regions
-> structured findings -> rehabilitation recommendation -> report.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    AiAnalysis,
    DetectedRegion,
    Exercise,
    RehabilitationRecommendation,
    XrayUpload,
)
from app.services import ai_client, audit, storage

DISCLAIMER = (
    "This is an AI-assisted research/prototype system. It does not provide a medical "
    "diagnosis and does not replace evaluation by a qualified physician or physiotherapist. "
    "Recommendations are generated from a structured, clinician-reviewed exercise knowledge "
    "base and must be confirmed with a healthcare professional before use."
)


def _write_temp_image(upload: XrayUpload) -> str:
    data = storage.read_bytes(upload)
    suffix = ".png" if upload.content_type == "image/png" else ".jpg"
    tmp = tempfile.NamedTemporaryFile(prefix="rehabx_", suffix=suffix, delete=False)
    tmp.write(data)
    tmp.close()
    return tmp.name


def run_analysis(
    db: Session,
    *,
    upload: XrayUpload,
    analysis: AiAnalysis,
    affected_side: str,
    affected_region: str,
) -> AiAnalysis:
    upload.status = "processing"
    upload.affected_side = affected_side
    upload.affected_region = affected_region
    db.commit()

    if upload.storage_key.startswith("report-only/"):
        result = _report_only_result(upload)
    else:
        temp_path: str | None = None
        try:
            temp_path = _write_temp_image(upload)
            result = ai_client.run_inference(
                temp_path, affected_side=affected_side, affected_region=affected_region
            )
        finally:
            if temp_path:
                try:
                    Path(temp_path).unlink(missing_ok=True)
                except OSError:
                    pass

    # ---- Populate the analysis row created at request time ----
    analysis.model_name = result.get("model_name", "efficientnet_b0")
    analysis.model_version = result.get("model_version", "unknown")
    analysis.model_status = result.get("model_status", "pretrained_backbone")
    analysis.prediction_label = result.get("prediction_label", "normal")
    analysis.confidence = round(float(result.get("confidence", 0.0)), 4)
    analysis.class_probabilities = result.get("class_probabilities", {})
    analysis.findings = result.get("findings", {})
    analysis.findings["report"] = _report_findings(upload)
    analysis.preprocessing = result.get("preprocessing", {})
    analysis.analysis_duration_ms = result.get("analysis_duration_ms")
    analysis.status = "completed"
    db.flush()

    for region in result.get("detected_regions", []):
        db.add(
            DetectedRegion(
                analysis_id=analysis.id,
                label=region.get("label", "region"),
                region_type=region.get("region_type", "region"),
                bbox_x=region.get("bbox", {}).get("x") if isinstance(region.get("bbox"), dict) else None,
                bbox_y=region.get("bbox", {}).get("y") if isinstance(region.get("bbox"), dict) else None,
                bbox_w=region.get("bbox", {}).get("w") if isinstance(region.get("bbox"), dict) else None,
                bbox_h=region.get("bbox", {}).get("h") if isinstance(region.get("bbox"), dict) else None,
                confidence=round(float(region.get("confidence", 0.0)), 4),
                detection_method=region.get("method", "classical_cv"),
            )
        )

    db.commit()
    db.refresh(analysis)

    upload.status = "completed"
    db.commit()

    audit.log(
        db,
        user_id=upload.user_id,
        action="analysis.completed",
        entity_type="ai_analysis",
        entity_id=analysis.id,
        details={"model_status": analysis.model_status, "prediction": analysis.prediction_label},
    )
    return analysis


def _report_only_result(upload: XrayUpload) -> dict[str, Any]:
    """Build an analysis result purely from the parsed report (no image).

    Used when the user submits only the X-ray report file. The prediction
    is derived from the report's condition/severity, not from a model.
    """
    parsed = upload.report_parsed or {}
    condition = parsed.get("condition_label")
    severity = parsed.get("severity")
    abnormal = bool(condition) or severity in ("moderate", "severe")

    label = "abnormal" if abnormal else "normal"
    confidence = 0.85 if abnormal else 0.9
    summary = (
        f"Derived from the supplied X-ray report: "
        + (f"{condition} ({severity} severity)" if condition and severity else (condition or "no specific finding reported"))
        + ". No image analysis was performed because no X-ray image was uploaded."
    )
    return {
        "model_name": "report_parser",
        "model_version": "1.0",
        "model_status": "report_only",
        "prediction_label": label,
        "confidence": confidence,
        "class_probabilities": {
            "normal": round(1.0 - confidence, 4),
            "abnormal": round(confidence, 4),
        },
        "findings": {
            "summary": summary,
            "degraded_input": False,
            "source": "report_only",
        },
        "preprocessing": {"image_analysis": False},
        "analysis_duration_ms": 0,
        "detected_regions": [],
    }


def resolve_category_exercises(db: Session, category_keys: list[str]) -> dict[str, list[Exercise]]:
    """Map recommendation category keys to concrete Exercise rows.

    The knowledge base (single source of truth) defines which exercise slugs
    belong to each category; the DB rows carry the ids needed to start
    sessions. Unknown keys/slugs are skipped so stale recommendations never
    crash the report endpoint.
    """
    from rehabilitation.knowledge_base import load_knowledge_base

    categories = load_knowledge_base().get("exercise_categories", {})
    members_by_key: dict[str, list[str]] = {}
    slugs: set[str] = set()
    for key in category_keys:
        cat = categories.get(key)
        if not cat:
            continue
        members = [s for s in cat.get("exercises", [])]
        members_by_key[key] = members
        slugs.update(members)
    if not slugs:
        return {}
    by_slug = {e.slug: e for e in db.scalars(select(Exercise).where(Exercise.slug.in_(slugs)))}
    return {
        key: [by_slug[s] for s in members if s in by_slug]
        for key, members in members_by_key.items()
    }


def resolve_section_exercises(db: Session, sections: list[dict[str, Any]]) -> dict[str, list[Exercise]]:
    """Resolve report-driven sections (engine v2) via their explicit slug lists."""
    wanted: dict[str, list[str]] = {}
    slugs: set[str] = set()
    for section in sections:
        members = [s for s in (section.get("exercise_slugs") or [])]
        if members:
            wanted[section["key"]] = members
            slugs.update(members)
    if not slugs:
        return {}
    by_slug = {e.slug: e for e in db.scalars(select(Exercise).where(Exercise.slug.in_(slugs)))}
    return {
        key: [by_slug[s] for s in members if s in by_slug]
        for key, members in wanted.items()
    }


def _extraction_scope(parsed: dict[str, Any]) -> bool:
    """True when report_parsed is rich enough to drive scoped rehabilitation."""
    if not isinstance(parsed, dict):
        return False
    if parsed.get("findings"):
        return True
    return bool(parsed.get("affected_region") or parsed.get("recommended_region"))


def run_recommendation(db: Session, analysis: AiAnalysis) -> RehabilitationRecommendation:
    from rehabilitation.engine import RecommendationEngine

    engine = RecommendationEngine()
    upload = db.get(XrayUpload, analysis.upload_id)

    regions_payload = [
        {
            "label": r.label,
            "region_type": r.region_type,
            "confidence": r.confidence,
        }
        for r in analysis.regions
    ]

    # Engine v2: when the report yields a usable structured extraction, the
    # REPORT controls the rehabilitation scope (side + region + structure +
    # restrictions). Otherwise fall back to the v1 image-driven engine.
    parsed = upload.report_parsed if isinstance(upload.report_parsed, dict) else {}
    recommendation: dict[str, Any] | None = None
    if _extraction_scope(parsed):
        from rehabilitation.engine import report_driven

        engine_v2 = report_driven.ReportDrivenEngine(disclaimer=engine.disclaimer)
        recommendation = engine_v2.recommend(
            extraction=parsed,
            prediction_label=analysis.prediction_label,
            confidence=analysis.confidence,
            findings=analysis.findings,
        )

    if recommendation is None:
        recommendation = engine.recommend(
            affected_region=upload.affected_region or "wrist",
            affected_side=upload.affected_side or "right",
            prediction_label=analysis.prediction_label,
            confidence=analysis.confidence,
            findings=analysis.findings,
            detected_regions=regions_payload,
        )
        extraction_payload: dict[str, Any] | None = None
    else:
        extraction_payload = recommendation.get("extraction")

    rec = RehabilitationRecommendation(
        analysis_id=analysis.id,
        user_id=analysis.user_id,
        upload_id=analysis.upload_id,
        rehab_focus=recommendation["rehab_focus"],
        affected_region=recommendation.get("affected_region") or upload.affected_region or "wrist",
        affected_side=recommendation.get("affected_side") or upload.affected_side or "right",
        abnormality_category=recommendation["abnormality_category"],
        focus_reasoning=recommendation["focus_reasoning"],
        recommended_exercise_categories=[
            {
                "key": c["key"],
                "label": c["label"],
                "description": c["description"],
                **{
                    k: c[k]
                    for k in (
                        "target_side",
                        "target_region",
                        "sub_region",
                        "specific_structure",
                        "condition",
                        "condition_label",
                        "severity",
                        "status",
                        "message",
                        "exercise_slugs",
                    )
                    if k in c
                },
            }
            for c in recommendation["recommended_exercise_categories"]
        ],
        movement_requirements=recommendation["movement_requirements"],
        repetition_guidance=recommendation["repetition_guidance"],
        session_structure=recommendation["session_structure"],
        safety_warnings=recommendation["safety_warnings"],
        disclaimer=recommendation["disclaimer"],
        engine_version=recommendation["engine_version"],
        extraction=extraction_payload,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    audit.log(
        db,
        user_id=analysis.user_id,
        action="recommendation.generated",
        entity_type="rehabilitation_recommendations",
        entity_id=rec.id,
    )
    return rec


def _report_findings(upload: XrayUpload) -> dict[str, Any]:
    """Surface report-derived facts inside analysis findings."""
    parsed = upload.report_parsed or {}
    if not parsed:
        return {"source": "xray_report", "provided": False}
    return {
        "source": "xray_report",
        "provided": True,
        "affected_side": parsed.get("affected_side"),
        "affected_region": parsed.get("affected_region"),
        "sub_region": parsed.get("sub_region"),
        "specific_structure": parsed.get("specific_structure"),
        "severity": parsed.get("severity"),
        "condition": parsed.get("condition"),
        "condition_label": parsed.get("condition_label"),
        "summary": parsed.get("summary"),
        "restrictions": parsed.get("restrictions") or [],
        "findings": parsed.get("findings") or [],
        "recommended_region": parsed.get("recommended_region"),
    }


def build_report_text(analysis: AiAnalysis, recommendation: RehabilitationRecommendation) -> str:
    conf_pct = f"{analysis.confidence * 100:.1f}%"
    report = analysis.findings.get("report", {}) if isinstance(analysis.findings, dict) else {}
    lines = [
        "HAND X-RAY AI REPORT",
        "=" * 40,
        "",
        f"Affected Region: {recommendation.affected_region.capitalize()}",
        f"Affected Side: {recommendation.affected_side.capitalize()}",
    ]
    if report.get("provided"):
        lines.append(f"Report Severity: {(report.get('severity') or 'unknown').capitalize()}")
        lines.append(
            f"Report Condition: {report.get('condition_label') or 'Not specified'}"
        )
        if report.get("summary"):
            lines.append(f"Report Summary: {report['summary']}")
    lines.extend(
        [
            f"AI Analysis: {analysis.findings.get('summary', analysis.prediction_label)}",
            f"Confidence: {conf_pct}",
            "Detected Region: " + (", ".join(r.label for r in analysis.regions) or "None"),
            "",
            f"Rehabilitation Focus: {recommendation.rehab_focus}",
            "",
            "Recommended Exercise Categories:",
        ]
    )
    for i, cat in enumerate(recommendation.recommended_exercise_categories, start=1):
        lines.append(f"  {i}. {cat['label']}")
    lines.extend(["", "Movement Requirements:"])
    for req in recommendation.movement_requirements:
        lines.append(f"  * {req}")
    lines.extend(
        [
            "",
            f"Model: {analysis.model_name} v{analysis.model_version} "
            f"({analysis.model_status.replace('_', ' ')})",
            f"Analysis timestamp: {analysis.created_at.isoformat()}",
            "",
            "DISCLAIMER:",
            f"{recommendation.disclaimer}",
        ]
    )
    return "\n".join(lines)
