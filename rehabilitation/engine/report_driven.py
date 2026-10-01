"""Report-driven rehabilitation scoping (engine v2).

The medical report controls the rehabilitation scope. Given the structured
extraction produced by ``app.services.report_parser`` (affected side, body
region on the upper-limb hierarchy, specific structure, condition, stated
restrictions), this engine selects exercises ONLY for the affected area,
filters them through condition/restriction safety rules, and emits one
recommendation section per injury when several are reported.

It never invents findings: unknown values stay None, and when safety cannot
be determined from the report the section is returned empty with a
"consult your physiotherapist" message instead of guessed exercises.
"""
from __future__ import annotations

import re
from typing import Any

from rehabilitation.exercises import get_exercise_library

ENGINE_VERSION = "2.0.0"

CONSULT_MESSAGE = (
    "Your report does not provide enough information to safely recommend "
    "this exercise. Please consult your physiotherapist."
)

# Finding region (parser vocabulary) -> library target_regions in scope.
_REGION_SCOPE: dict[str, list[str]] = {
    "fingers": ["hand"],
    "hand": ["hand"],
    "thumb": ["thumb", "hand"],
    "palm": ["palm", "hand"],
    "grip": ["grip", "hand"],
    "wrist": ["wrist", "forearm"],  # forearm rotation is standard wrist rehab
    "forearm": ["forearm"],
    "elbow": ["elbow", "forearm"],
    "upper_arm": ["elbow", "shoulder"],
    "shoulder": ["shoulder"],
}

# Structure/sub-region overrides for finer targeting inside the hand.
_SUBREGION_SCOPE: dict[str, list[str]] = {
    "thumb": ["thumb", "hand"],
    "palm": ["palm", "hand"],
}

_FRACTURE_FAMILY = {
    "fracture",
    "comminuted_fracture",
    "displaced_fracture",
    "hairline_fracture",
    "dislocation",
}
_DEGENERATIVE = {"osteoarthritis", "rheumatoid_arthritis", "osteoporosis"}
_SOFT_TISSUE = {"sprain", "soft_tissue_swelling", "tendonitis"}
_UNSAFE_WITHOUT_CLEARANCE = {"tendon_injury", "nerve_compression", "infection", "foreign_body"}

_BLOCKING_RESTRICTIONS = {"immobilization", "post_operative", "non_weight_bearing"}

_CATEGORY_ORDER = ["mobility", "stretching", "recovery", "strengthening"]

_AREA_LABELS = {
    "fingers": "finger",
    "hand": "hand",
    "thumb": "thumb",
    "palm": "palm",
    "grip": "grip",
    "wrist": "wrist",
    "forearm": "forearm",
    "elbow": "elbow",
    "upper_arm": "upper arm",
    "shoulder": "shoulder",
}


def area_label(finding: dict[str, Any]) -> str:
    """Human label for the most specific affected area available."""
    structure = finding.get("specific_structure")
    if structure:
        return structure.replace("_", " ")
    sub = finding.get("sub_region")
    if sub:
        return sub.replace("_", " ")
    region = finding.get("region") or ""
    return _AREA_LABELS.get(region, region)


def section_key(finding: dict[str, Any]) -> str | None:
    side = finding.get("side")
    area = finding.get("region")
    return "_".join(p for p in (side, area) if p) or None


def _scope_for(finding: dict[str, Any]) -> list[str]:
    sub = finding.get("sub_region")
    if sub in _SUBREGION_SCOPE:
        return list(_SUBREGION_SCOPE[sub])
    return list(_REGION_SCOPE.get(finding.get("region") or "", []))


def condition_family(condition: str | None) -> str | None:
    if condition in _FRACTURE_FAMILY:
        return "fracture"
    if condition in _DEGENERATIVE:
        return "degenerative"
    if condition in _SOFT_TISSUE:
        return "soft_tissue"
    if condition in _UNSAFE_WITHOUT_CLEARANCE:
        return "unsafe_without_clearance"
    return None


class ReportDrivenEngine:
    """Selects report-scoped, safety-filtered exercise sections."""

    def __init__(self, disclaimer: str) -> None:
        self.disclaimer = disclaimer
        self.exercises = get_exercise_library()

    # ------------------------------------------------------------------
    # Safety filter (spec §12)
    # ------------------------------------------------------------------
    def _safety(
        self, finding: dict[str, Any], restrictions: list[dict[str, str]]
    ) -> tuple[str, str, str | None]:
        """Return (status, intensity, block_message)."""
        keys = {r["restriction"] for r in restrictions}
        if keys & _BLOCKING_RESTRICTIONS:
            return ("not_safe", "minimal", CONSULT_MESSAGE)
        family = condition_family(finding.get("condition"))
        if family == "unsafe_without_clearance":
            return ("needs_clarification", "minimal", CONSULT_MESSAGE)
        if family == "fracture":
            return ("ok", "minimal", None)
        if finding.get("severity") == "severe":
            return ("ok", "minimal", None)
        return ("ok", "low", None)

    def _allowed_categories(self, status: str, finding: dict[str, Any]) -> set[str]:
        """Exercise categories permitted under the current safety verdict."""
        if status != "ok":
            return set()
        family = condition_family(finding.get("condition"))
        if family == "fracture" or finding.get("severity") == "severe":
            return {"mobility", "stretching", "recovery"}
        if family in ("degenerative", "soft_tissue"):
            return set(_CATEGORY_ORDER)
        # No usable condition statement — stay conservative.
        return {"mobility", "stretching", "recovery"}

    def _max_progression(self, finding: dict[str, Any]) -> int:
        family = condition_family(finding.get("condition"))
        if family == "fracture":
            return 1
        return 2

    # ------------------------------------------------------------------
    # Exercise selection scoped to the affected region only
    # ------------------------------------------------------------------
    def _select_exercises(
        self, scope: list[str], allowed: set[str], max_progression: int
    ) -> list[dict[str, Any]]:
        selected = [
            ex
            for ex in self.exercises
            if ex.get("target_region") in scope
            and ex.get("category") in allowed
            and int(ex.get("progression_level") or 1) <= max_progression
        ]
        selected.sort(
            key=lambda ex: (
                _CATEGORY_ORDER.index(ex.get("category")) if ex.get("category") in _CATEGORY_ORDER else 9,
                0 if ex.get("difficulty") == "beginner" else 1,
                ex["name"],
            )
        )
        return selected[:8]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def recommend(
        self,
        *,
        extraction: dict[str, Any],
        prediction_label: str = "abnormal",
        confidence: float = 0.5,
        findings: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Build a report-scoped recommendation from structured extraction.

        Returns None when the extraction is too poor to scope rehabilitation
        (caller falls back to the v1 image-driven engine).
        """
        report_restrictions = extraction.get("restrictions") or []
        raw_findings = [f for f in (extraction.get("findings") or []) if f]
        if not raw_findings:
            primary = {
                "side": extraction.get("affected_side"),
                "region": extraction.get("affected_region"),
                "sub_region": extraction.get("sub_region"),
                "specific_structure": extraction.get("specific_structure"),
                "condition": extraction.get("condition"),
                "condition_label": extraction.get("condition_label"),
                "severity": extraction.get("severity"),
            }
            if not primary["region"]:
                return None
            raw_findings = [primary]

        sections: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        all_slugs: list[str] = []
        for finding in raw_findings[:4]:
            key = section_key(finding) or f"section_{len(sections) + 1}"
            if key in seen_keys:
                key = f"{key}_{len(sections) + 1}"
            seen_keys.add(key)
            scope = _scope_for(finding)
            status, intensity, block_message = self._safety(finding, report_restrictions)
            allowed = self._allowed_categories(status, finding)
            chosen = self._select_exercises(scope, allowed, self._max_progression(finding)) if scope else []
            message = block_message
            if status == "ok" and not chosen:
                status = "needs_clarification"
                message = CONSULT_MESSAGE
            section = {
                "key": key,
                "label": self._section_title(finding),
                "description": self._section_description(finding),
                "target_side": finding.get("side"),
                "target_region": finding.get("region"),
                "sub_region": finding.get("sub_region"),
                "specific_structure": finding.get("specific_structure"),
                "condition": finding.get("condition"),
                "condition_label": finding.get("condition_label"),
                "severity": finding.get("severity"),
                "status": status,
                "message": message,
                "exercise_slugs": [ex["slug"] for ex in chosen],
            }
            sections.append(section)
            for slug in section["exercise_slugs"]:
                if slug not in all_slugs:
                    all_slugs.append(slug)

        primary_finding = raw_findings[0]
        _, overall_intensity, _ = self._safety(primary_finding, report_restrictions)
        abnormality_category = self._abnormality_category(prediction_label, primary_finding)

        return {
            "rehab_focus": self._section_title(primary_finding),
            "affected_region": primary_finding.get("region") or extraction.get("affected_region") or "",
            "affected_side": primary_finding.get("side") or extraction.get("affected_side") or "",
            "abnormality_category": abnormality_category,
            "focus_reasoning": self._focus_reasoning(primary_finding, report_restrictions),
            "recommended_exercise_categories": sections,
            "movement_requirements": self._movement_requirements(report_restrictions),
            "repetition_guidance": self._repetition_guidance(all_slugs, overall_intensity),
            "session_structure": self._session_structure(sections, overall_intensity),
            "safety_warnings": self._safety_warnings(primary_finding, report_restrictions),
            "extraction": extraction,
            "priority": "urgent_referral" if abnormality_category == "abnormal_fracture_suspicion" else "routine",
            "disclaimer": self.disclaimer,
            "engine_version": ENGINE_VERSION,
        }

    # ------------------------------------------------------------------
    # Builders
    # ------------------------------------------------------------------
    def _section_title(self, finding: dict[str, Any]) -> str:
        side = finding.get("side")
        area = area_label(finding)
        title_bits = [b for b in ((side or "").capitalize(), area) if b]
        return (" ".join(title_bits) + " rehabilitation") if title_bits else "Rehabilitation"

    def _section_description(self, finding: dict[str, Any]) -> str:
        bits: list[str] = []
        if finding.get("condition_label"):
            bits.append(f"Reported: {finding['condition_label']}")
        elif finding.get("severity"):
            bits.append(f"Reported severity: {finding['severity']}")
        else:
            bits.append("Scoped to the area named in your report")
        if finding.get("severity") and finding.get("condition_label"):
            bits.append(f"severity: {finding['severity']}")
        return ". ".join(bits) + "."

    def _focus_reasoning(
        self, finding: dict[str, Any], restrictions: list[dict[str, str]]
    ) -> list[str]:
        out = [
            f"The report names the {area_label(finding)}"
            + (f" ({finding['side']} side)" if finding.get("side") else "")
            + ", so only exercises for that area are recommended."
        ]
        for r in restrictions:
            out.append(f"Report precaution applied: {r['restriction'].replace('_', ' ')}.")
        family = condition_family(finding.get("condition"))
        if family == "fracture":
            out.append("A fracture is reported: gentle mobility only; strengthening requires clinician clearance.")
        return out

    def _movement_requirements(self, restrictions: list[dict[str, str]]) -> list[str]:
        reqs = [
            "Move only within a pain-free range",
            "Stop immediately if sharp pain, numbness or tingling occurs",
        ]
        if any(r["restriction"] == "avoid_resisted" for r in restrictions):
            reqs.append("No resisted or loaded movements — your report advises against loading")
        if any(r["restriction"] == "avoid_overhead" for r in restrictions):
            reqs.append("No overhead movements until cleared by your clinician")
        return reqs

    def _repetition_guidance(self, slugs: list[str], intensity: str) -> dict[str, Any]:
        by_slug: dict[str, Any] = {}
        for ex in self.exercises:
            if ex["slug"] not in slugs:
                continue
            reps = ex["rep_range"]
            sets = ex["set_range"]
            hold = next((int(s.split("-")[0]) for s in re.findall(r"\d+\s*(?:-|to\s*)?\d*\s*seconds?", ex.get("required_movement", ""))), None)
            by_slug[ex["slug"]] = {
                "repetitions": [reps[0], reps[1]],
                "sets": [sets[0], sets[1]],
                "hold_seconds": hold if hold is not None else (1 if intensity == "minimal" else 2),
                "rest_between_sets_seconds": 60,
                "frequency_per_day": 1,
            }
        return {
            "general": (
                "Only perform movements explicitly cleared by a clinician; stay strictly pain-free."
                if intensity == "minimal"
                else "Perform each movement slowly and within a pain-free range."
            ),
            "per_exercise": by_slug,
        }

    def _session_structure(self, sections: list[dict[str, Any]], intensity: str) -> dict[str, Any]:
        labels = [s["label"] for s in sections]
        return {
            "warm_up": (
                "No structured warm-up beyond gentle, pain-free movement."
                if intensity == "minimal"
                else "2-3 minutes of gentle movement of the affected area."
            ),
            "main_components": labels,
            "cool_down": "Gentle pain-free movements; no forcing at end of range.",
            "frequency": "Once daily to every other day, based on tolerance.",
            "progression_rule": "Only increase repetitions when the current level is pain-free for 5-7 consecutive days.",
            "intensity": intensity,
        }

    def _safety_warnings(
        self, finding: dict[str, Any], restrictions: list[dict[str, str]]
    ) -> list[str]:
        warnings: list[str] = []
        family = condition_family(finding.get("condition"))
        if family == "fracture":
            warnings.append(
                f"A {finding.get('condition_label') or 'fracture'} is reported: do not perform strengthening "
                "or weight-bearing exercises without clinician clearance."
            )
        if finding.get("severity") == "severe":
            warnings.append(
                "The report indicates a severe presentation — do not start exercises without clinical clearance."
            )
        for r in restrictions:
            warnings.append(
                f"Report precaution — {r['restriction'].replace('_', ' ')}: follow your clinician's instructions; "
                "restricted activities are excluded from this plan."
            )
        warnings.append("Stop any exercise that causes sharp or worsening pain.")
        warnings.append("Do not exceed pain-free range of motion.")
        return warnings

    def _abnormality_category(self, prediction_label: str, finding: dict[str, Any]) -> str:
        if prediction_label != "abnormal" and not finding.get("condition"):
            return "normal"
        family = condition_family(finding.get("condition"))
        if family == "fracture":
            return "abnormal_fracture_suspicion"
        if family == "degenerative":
            return "abnormal_degenerative_changes"
        if family == "soft_tissue":
            return "abnormal_soft_tissue_swelling"
        return "abnormal_generic"
