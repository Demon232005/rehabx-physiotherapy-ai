"""Upper-limb platform: exercise library coverage, metadata and filters."""
from __future__ import annotations

from sqlalchemy import func, select

from app.models import Exercise
from app.db.session import SessionLocal


def _library() -> list[dict]:
    from rehabilitation.exercises import get_exercise_library

    return get_exercise_library()


class TestLibraryCoverage:
    def test_library_spans_all_upper_limb_regions(self):
        regions = {ex["target_region"] for ex in _library()}
        expected = {"hand", "thumb", "palm", "grip", "wrist", "forearm", "elbow", "shoulder"}
        assert expected <= regions

    def test_every_new_exercise_declares_tracking_mode(self):
        for ex in _library():
            if ex["slug"] in {
                # legacy hand exercises pre-date explicit tracking modes
                "finger-flexion", "finger-extension", "finger-spreading",
                "finger-walking", "fist-open-close", "thumb-opposition",
                "thumb-flexion", "thumb-extension", "thumb-abduction",
                "wrist-flexion", "wrist-extension", "wrist-rotation",
                "wrist-ulnar-radial-deviation", "gentle-grip-release",
                "towel-wring", "individual-finger-flexion", "tendon-gliding",
                "wrist-ulnar-deviation", "wrist-radial-deviation",
                "forearm-pronation", "forearm-supination", "elbow-flexion-extension",
            }:
                continue
            assert ex.get("tracking_mode") in {"hand", "pose", "hand+pose"}, ex["slug"]
            assert ex.get("category") in {"mobility", "stretching", "strengthening", "recovery"}, ex["slug"]

    def test_pose_tracking_for_elbow_and_shoulder(self):
        by_slug = {ex["slug"]: ex for ex in _library()}
        for slug in ["elbow-flexion", "shoulder-flexion", "shoulder-abduction"]:
            assert by_slug[slug]["tracking_mode"] == "pose"

    def test_advanced_shoulder_strengthening_is_intermediate(self):
        """Safety rule: no auto-prescribable advanced strengthening."""
        by_slug = {ex["slug"]: ex for ex in _library()}
        for slug in ["front-raises", "side-raises", "wall-slides"]:
            assert by_slug[slug]["difficulty"] == "intermediate"


class TestSeededMetadata:
    def test_seed_fills_upper_limb_fields(self, client):
        session = SessionLocal()
        try:
            total = session.scalar(select(func.count()).select_from(Exercise))
            shoulder = session.scalar(
                select(Exercise).where(Exercise.slug == "shoulder-flexion")
            )
            wrist = session.scalar(select(Exercise).where(Exercise.slug == "wrist-circumduction"))
            legacy = session.scalar(select(Exercise).where(Exercise.slug == "finger-flexion"))
            assert total and total >= 70
            assert shoulder.tracking_mode == "pose"
            assert shoulder.category == "mobility"
            assert wrist.tracking_mode == "hand+pose"
            assert legacy.tracking_mode in (None, "hand")  # legacy row tolerated
        finally:
            session.close()


class TestExerciseFilters:
    def test_region_filter(self, client, auth_headers):
        resp = client.get("/api/v1/exercises?region=shoulder", headers=auth_headers)
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) >= 15
        assert all(r["target_region"] == "shoulder" for r in rows)

    def test_category_filter(self, client, auth_headers):
        resp = client.get("/api/v1/exercises?category=stretching&region=shoulder", headers=auth_headers)
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) >= 5
        assert all(r["category"] == "stretching" for r in rows)

    def test_search_filter(self, client, auth_headers):
        resp = client.get("/api/v1/exercises?search=pendulum", headers=auth_headers)
        assert resp.status_code == 200
        slugs = [r["slug"] for r in resp.json()]
        assert "pendulum-exercise" in slugs

    def test_payload_includes_platform_fields(self, client, auth_headers):
        resp = client.get("/api/v1/exercises/shoulder-flexion", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["tracking_mode"] == "pose"
        assert body["movement_type"] == "shoulder_elev"
        assert body["duration_minutes"] == 5
