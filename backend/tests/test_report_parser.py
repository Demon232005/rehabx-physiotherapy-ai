"""Tests for the X-ray report parser."""
from __future__ import annotations

from app.services import report_parser


def test_parse_left_wrist_fracture():
    parsed = report_parser.parse_report(
        "Fracture of the left distal radius. Mild comminution noted. No dislocation."
    )
    assert parsed["affected_side"] == "left"
    assert parsed["affected_region"] == "wrist"
    assert parsed["severity"] == "mild"
    assert parsed["condition"] == "fracture"


def test_parse_severe_comminuted_right_wrist():
    parsed = report_parser.parse_report(
        "Severely displaced comminuted fracture of the right wrist, carpal bones involved."
    )
    assert parsed["affected_side"] == "right"
    assert parsed["affected_region"] == "wrist"
    assert parsed["severity"] == "severe"
    assert parsed["condition"] == "comminuted_fracture"


def test_parse_osteoarthritis():
    parsed = report_parser.parse_report(
        "Osteoarthritis of the right hand, moderate degenerative changes."
    )
    assert parsed["affected_side"] == "right"
    assert parsed["affected_region"] == "hand"
    assert parsed["severity"] == "moderate"
    assert parsed["condition"] == "osteoarthritis"


def test_negated_fracture_is_not_detected():
    parsed = report_parser.parse_report("No fracture. Normal study of the right wrist.")
    assert parsed["condition"] is None
    assert parsed["affected_side"] == "right"
    assert parsed["affected_region"] == "wrist"
    assert "No abnormality identified" in parsed["summary"]


def test_empty_report_returns_empty_dict():
    assert report_parser.parse_report("") == {}
    assert report_parser.parse_report(None) == {}
