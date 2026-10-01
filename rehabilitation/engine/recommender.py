"""Rehabilitation recommendation engine.

A separate, rule-based layer that maps AI X-ray findings onto a
clinician-reviewed exercise knowledge base. It never claims to
diagnose; outputs are framed as AI-assisted rehabilitation guidance.

The engine is intentionally deterministic and testable: given the same
structured findings it produces the same recommendation.
"""
from __future__ import annotations

from typing import Any

from rehabilitation.exercises import get_exercise_library, get_exercises_by_slugs
from rehabilitation.knowledge_base import load_validated_knowledge_base

ENGINE_VERSION = "1.0.0"


class RecommendationEngine:
    def __init__(self) -> None:
        self.kb = load_validated_knowledge_base()
        self.categories = self.kb["exercise_categories"]
        self.abnormalities = self.kb["abnormality_categories"]
        self.regions = self.kb["regions"]
        self.disclaimer = self.kb["disclaimer"]
        self.exercises = get_exercise_library()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def recommend(
        self,
        *,
        affected_region: str,
        affected_side: str = "right",
        prediction_label: str = "normal",
        confidence: float = 0.5,
        findings: dict[str, Any] | None = None,
        detected_regions: list[dict[str, Any]] | None = None,
        user_provided: dict[str, Any] | None = None,
        previous_progress: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        findings = findings or {}
        user_provided = user_provided or {}
        detected_regions = detected_regions or []

        category_key = self._resolve_category_key(prediction_label, findings)
        category = self._category(category_key)
        region = self.regions.get(affected_region, self.regions["wrist"])
        exercise_category_keys = category["exercise_categories"]
        exercise_slugs = self._resolve_exercise_slugs(exercise_category_keys)

        report_severity = None
        report_condition = None
        report_info = findings.get("report") or {}
        if isinstance(report_info, dict):
            report_severity = report_info.get("severity")
            report_condition = report_info.get("condition_label")

        intensity_modifier = self._intensity_modifier(
            category_key, confidence, user_provided, previous_progress, severity=report_severity
        )
        repetition_guidance = self._build_repetition_guidance(
            exercise_slugs, intensity_modifier, user_provided
        )
        session_structure = self._build_session_structure(
            exercise_category_keys, intensity_modifier
        )
        safety_warnings = self._build_safety_warnings(
            category_key, category, findings, severity=report_severity, condition=report_condition
        )

        movement_requirements = list(region.get("movement_requirements", []))
        extra_requirements = self._extra_movement_requirements(category_key)
        movement_requirements.extend(extra_requirements)

        return {
            "rehab_focus": category["rehab_focus"],
            "affected_region": affected_region,
            "affected_side": affected_side,
            "abnormality_category": category_key,
            "abnormality_label": category["label"],
            "priority": category["priority"],
            "focus_reasoning": category["focus_reasoning"],
            "recommended_exercise_categories": [
                {"key": k, "label": self.categories[k]["label"], "description": self.categories[k]["description"]}
                for k in exercise_category_keys
            ],
            "recommended_exercises": [
                {
                    "slug": ex["slug"],
                    "name": ex["name"],
                    "description": ex["description"],
                    "target_region": ex["target_region"],
                    "movement_type": ex["movement_type"],
                    "starting_position": ex["starting_position"],
                    "required_movement": ex["required_movement"],
                    "contraindications": ex["contraindications"],
                    "difficulty": ex["difficulty"],
                    "rep_range": ex["rep_range"],
                    "set_range": ex["set_range"],
                    "animation_placeholder": ex["animation_placeholder"],
                }
                for ex in get_exercises_by_slugs(exercise_slugs)
            ],
            "movement_requirements": movement_requirements,
            "repetition_guidance": repetition_guidance,
            "session_structure": session_structure,
            "safety_warnings": safety_warnings,
            "category_notes": category["notes"],
            "detected_region_hints": self._region_hints(detected_regions),
            "disclaimer": self.disclaimer,
            "engine_version": ENGINE_VERSION,
        }

    # ------------------------------------------------------------------
    # Category resolution (heuristic interpretation of real model signals)
    # ------------------------------------------------------------------
    def _resolve_category_key(self, prediction_label: str, findings: dict[str, Any]) -> str:
        """Map prediction + structured findings to a KB category.

        This is an explicit heuristic layer over the real model outputs; it
        is documented as such and is not presented as a diagnosis.
        """
        if prediction_label != "abnormal":
            return "normal"

        fx = findings.get("fracture_suspicion", 0.0)
        degen = findings.get("degenerative_changes", 0.0)
        soft = findings.get("soft_tissue_swelling", 0.0)

        if isinstance(fx, (int, float)) and fx >= 0.55:
            return "abnormal_fracture_suspicion"
        if isinstance(soft, (int, float)) and soft >= 0.55:
            return "abnormal_soft_tissue_swelling"
        if isinstance(degen, (int, float)) and degen >= 0.55:
            return "abnormal_degenerative_changes"
        return "abnormal_generic"

    def _category(self, key: str) -> dict[str, Any]:
        return self.abnormalities.get(key, self.abnormalities["abnormal_generic"])

    # ------------------------------------------------------------------
    # Exercise resolution
    # ------------------------------------------------------------------
    def _resolve_exercise_slugs(self, category_keys: list[str]) -> list[str]:
        slugs: list[str] = []
        for key in category_keys:
            for slug in self.categories[key]["exercises"]:
                if slug not in slugs:
                    slugs.append(slug)
        return slugs

    # ------------------------------------------------------------------
    # Guidance construction
    # ------------------------------------------------------------------
    def _intensity_modifier(
        self,
        category_key: str,
        confidence: float,
        user_provided: dict[str, Any],
        previous_progress: list[dict[str, Any]] | None,
        severity: str | None = None,
    ) -> str:
        category = self._category(category_key)
        if category_key in ("abnormal_fracture_suspicion", "abnormal_soft_tissue_swelling"):
            return "minimal"

        if severity == "severe":
            return "minimal"

        if user_provided.get("pain_level") is not None and int(user_provided["pain_level"]) >= 7:
            return "minimal"

        progressed = self._has_progressed(previous_progress)
        if progressed and category["priority"] == "routine":
            return "moderate"
        return category.get("intensity", "low")

    @staticmethod
    def _has_progressed(previous_progress: list[dict[str, Any]] | None) -> bool:
        if not previous_progress:
            return False
        return any(
            (p.get("pain_level", 10) or 10) <= 2
            and (p.get("self_reported_improvement", 0) or 0) >= 30
            for p in previous_progress
        )

    def _build_repetition_guidance(
        self, slugs: list[str], intensity: str, user_provided: dict[str, Any]
    ) -> dict[str, Any]:
        multiplier = {"minimal": 0.5, "low": 1.0, "low_to_moderate": 1.0, "moderate": 1.25}.get(intensity, 1.0)

        by_exercise: dict[str, Any] = {}
        for ex in self.exercises:
            if ex["slug"] not in slugs:
                continue
            reps = [ex["rep_range"][0], max(ex["rep_range"][1], round(ex["rep_range"][1] * multiplier))]
            sets = [ex["set_range"][0], ex["set_range"][1]]
            if multiplier <= 0.5:
                sets = [1, 2]
            by_exercise[ex["slug"]] = {
                "repetitions": reps,
                "sets": sets,
                "hold_seconds": 2 if intensity != "minimal" else 1,
                "rest_between_sets_seconds": 60,
                "frequency_per_day": 1,
            }

        return {
            "general": (
                "Perform each movement slowly and within a pain-free range."
                if intensity != "minimal"
                else "Only perform movements explicitly cleared by a clinician; stay strictly pain-free."
            ),
            "per_exercise": by_exercise,
        }

    def _build_session_structure(
        self, category_keys: list[str], intensity: str
    ) -> dict[str, Any]:
        labels = [self.categories[k]["label"] for k in category_keys]
        if intensity == "minimal":
            warmup = "No structured warm-up beyond gentle, pain-free movement."
            cooldown = "Cool down with relaxed finger spreading and slow wrist circles if pain-free."
        else:
            warmup = "2-3 minutes of gentle wrist circles and finger spreading."
            cooldown = "Slow wrist and finger full-range movements and gentle stretch (no forcing)."
        return {
            "warm_up": warmup,
            "main_components": labels,
            "cool_down": cooldown,
            "frequency": "Once daily to every other day, based on tolerance.",
            "progression_rule": "Only increase repetitions when the current level is pain-free for 5-7 consecutive days.",
            "intensity": intensity,
        }

    def _build_safety_warnings(
        self,
        category_key: str,
        category: dict[str, Any],
        findings: dict[str, Any],
        severity: str | None = None,
        condition: str | None = None,
    ) -> list[str]:
        warnings: list[str] = []
        if category_key == "abnormal_fracture_suspicion":
            warnings.append(
                "STOP: A fracture has NOT been diagnosed. Seek clinical evaluation before performing any exercises."
            )
            warnings.append("Do not perform weight-bearing, gripping or strengthening exercises.")
        elif category_key == "abnormal_soft_tissue_swelling":
            warnings.append("If swelling increases during or after exercise, stop and consult a clinician.")
        if condition and condition.lower() in ("fracture", "comminuted fracture", "displaced fracture", "dislocation"):
            warnings.append(
                f"Reported finding of {condition}: only clinician-cleared movements are permitted; no strengthening yet."
            )
        if severity == "severe":
            warnings.append(
                "The supplied X-ray report indicates a severe presentation — do not start exercises without clinical clearance."
            )
        warnings.append("Stop any exercise that causes sharp or worsening pain.")
        warnings.append("Do not exceed pain-free range of motion.")
        if findings.get("degraded_input"):
            warnings.append("This analysis was performed on a low-quality image; results should be interpreted with extra caution.")
        return warnings

    def _extra_movement_requirements(self, category_key: str) -> list[str]:
        if category_key == "abnormal_fracture_suspicion":
            return [
                "Restrict movement to joints that are clinically cleared",
                "No resistance or weight-bearing of any kind",
            ]
        if category_key == "abnormal_soft_tissue_swelling":
            return [
                "Elevate the hand between exercise sessions",
                "Use cold application only if recommended by a clinician",
            ]
        if category_key == "abnormal_degenerative_changes":
            return [
                "Keep within pain-free range; avoid hard end-range stretching",
            ]
        return []

    def _region_hints(self, detected_regions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "label": r.get("label", "region"),
                "region_type": r.get("region_type", "region"),
                "confidence": round(float(r.get("confidence", 0.0)), 3),
            }
            for r in detected_regions
            if r.get("region_type") in ("joint", "bone")
        ]
