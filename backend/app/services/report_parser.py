"""Parse a free-text X-ray report into structured facts.

Extracts the affected side (left/right/bilateral), the affected body region on
an upper-limb hierarchy (shoulder → upper arm → elbow → forearm → wrist →
hand → palm/thumb/fingers), the most specific anatomical structure named
(e.g. index finger, distal radius), an estimated severity, a matching
condition, and any movement restrictions stated in the report. The result
drives report-scoped rehabilitation recommendations. This is a keyword/
heuristic layer, not a diagnosis.
"""
from __future__ import annotations

import re
from typing import Any

# --- Body-part hierarchy ----------------------------------------------------
#
# Upper Limb
# ├── Shoulder            region="shoulder"
# ├── Upper Arm           region="upper_arm"
# ├── Elbow               region="elbow"
# ├── Forearm             region="forearm"
# ├── Wrist               region="wrist"
# └── Hand                region="hand"
#     ├── Palm            sub_region="palm"
#     ├── Thumb           sub_region="thumb"
#     └── Fingers         sub_region="finger" (+ specific_structure)

_REGION_TERMS = {
    "hand": ("hand",),
    "wrist": ("wrist", "carpal", "carpus", "carpi"),
    "fingers": ("fingers", "finger", "phalanges", "phalangeal", "phalanx", "interphalangeal"),
    "forearm": ("forearm", "radius", "radial", "ulna", "ulnar"),
    "elbow": ("elbow",),
    "upper_arm": ("upper arm", "arm", "humerus", "humeral"),
    "shoulder": ("shoulder", "clavicle", "scapula", "scapular", "acromion", "acromioclavicular", "glenohumeral", "rotator cuff"),
}

# Specific anatomical structures, ordered most-specific-first. Each entry maps
# structure key -> (region, sub_region, search terms).
_STRUCTURE_TERMS: dict[str, tuple[str, str | None, tuple[str, ...]]] = {
    "index_finger": ("hand", "finger", ("index finger", "index digit", "second digit", "2nd digit")),
    "middle_finger": ("hand", "finger", ("middle finger", "middle digit", "third digit", "3rd digit")),
    "ring_finger": ("hand", "finger", ("ring finger", "ring digit", "fourth digit", "4th digit")),
    "little_finger": ("hand", "finger", ("little finger", "little digit", "pinky", "small finger", "fifth digit", "5th digit")),
    "thumb": ("hand", "thumb", ("thumb",)),
    "palm": ("hand", "palm", ("palm", "metacarpal")),
    "distal_radius": ("wrist", "wrist", ("distal radius", "distal radiu")),
    "distal_ulna": ("wrist", "wrist", ("distal ulna", "distal uln")),
    "radiocarpal": ("wrist", "wrist", ("radiocarpal",)),
    "scaphoid": ("wrist", "wrist", ("scaphoid",)),
    "lunate": ("wrist", "wrist", ("lunate",)),
    "triquetrum": ("wrist", "wrist", ("triquetrum",)),
    "pisiform": ("wrist", "wrist", ("pisiform",)),
    "trapezium": ("wrist", "wrist", ("trapezium",)),
    "capitate": ("wrist", "wrist", ("capitate",)),
    "hamate": ("wrist", "wrist", ("hamate",)),
    "olecranon": ("elbow", "elbow", ("olecranon",)),
    "radial_head": ("elbow", "elbow", ("radial head", "head of radius")),
    "coronoid": ("elbow", "elbow", ("coronoid",)),
    "proximal_humerus": ("shoulder", "shoulder", ("proximal humerus", "humeral head", "surgical neck")),
}

_NEGATION_MARKERS = (
    "no ",
    "without",
    "no evidence of",
    "no evidence",
    "not seen",
    "not identified",
    "absent",
    "no acute",
    "normal",
    "intact",
    "unremarkable",
)

_SIDE_SYNONYMS = {
    "left": {"left", "lhs", "baaya", "baya", "bayan", "left hand", "left wrist", "left hand wrist"},
    "right": {"right", "rhs", "dahina", "dayan", "dahine", "right hand", "right wrist", "right hand wrist"},
    "bilateral": {"bilateral", "both hands", "both wrists", "both sides", "both upper limbs"},
}

_CONDITIONS: list[tuple[str, tuple[str, ...]]] = [
    ("comminuted_fracture", ("comminuted fracture", "comminuted fx")),
    ("displaced_fracture", ("displaced fracture", "displaced fx", "displaced")),
    ("hairline_fracture", ("hairline fracture", "hairline fx", "stress fracture", "stress fx", "avulsion", "undisplaced", "non-displaced", "nondisplaced")),
    ("fracture", ("fracture", "fractured", "fracturing", " fx", "broken")),
    ("dislocation", ("dislocation", "dislocated", "subluxation", "subluxed")),
    ("osteoarthritis", ("osteoarthritis", "degenerative joint disease", "degenerative change", "degenerative arthritis", "dj d", "osteoarthritic")),
    ("rheumatoid_arthritis", ("rheumatoid arthritis", "rheumatoid", "erosive arthritis", "juvenile idiopathic arthritis")),
    ("osteoporosis", ("osteoporosis", "osteopeni")),
    ("sprain", ("sprain", "sprained", "ligamentous", "ligament injury")),
    ("soft_tissue_swelling", ("soft tissue swelling", "soft-tissue swelling", "effusion", "swelling", "oedema", "edema")),
    ("tendonitis", ("tendonitis", "tendinitis", "tenosynovitis")),
    ("tendon_injury", ("tendon rupture", "tendon tear", "flexor tendon", "extensor tendon", "mallet", "trigger finger")),
    ("nerve_compression", ("carpal tunnel", "cubital tunnel", "neuropathy", "nerve compression")),
    ("infection", ("osteomyelitis", "infection", "infective", "septic")),
    ("foreign_body", ("foreign body", "foreign-body", "radiopaque body", "metallic density")),
    ("ganglion_cyst", ("ganglion", "cyst")),
]

_SEVERITY_ORDER = {"mild": 1, "moderate": 2, "severe": 3}

_SEVERITY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("severe", ("severe", "comminuted", "displaced", "grossly", "extensive", "advanced", "marked", "prominent", "complete", "full thickness")),
    ("moderate", ("moderate", "partially displaced", "angulated", "some", "partial")),
    ("mild", ("mild", "minimal", "hairline", "subtle", "tiny", "slight", "early", "stress", "small", "minor")),
]

# Restrictions / precautions explicitly stated in the report (never invented).
_RESTRICTION_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("non_weight_bearing", ("non weight bearing", "non-weight-bearing", "no weight bearing", "weight bearing restriction", "nwbr")),
    ("immobilization", ("immobilisation", "immobilization", "immobilised", "immobilized", "plaster", "in a cast", "back slab", "slab", "splinted", "in splint", "static brace")),
    ("post_operative", ("post-operative", "post operative", "post-op", "postop", "post surgery", "post-surgery", "status post", "open reduction", "closed reduction", "internal fixation", "external fixation", "k-wire", "k wire", "kirschner", "orif", "crif", "percutaneous pinning")),
    ("avoid_resisted", ("avoid resisted", "no resistance", "no resisted", "avoid lifting", "no heavy lifting", "avoid loading")),
    ("avoid_overhead", ("avoid overhead", "no overhead")),
]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _anchor_terms() -> list[str]:
    """All anatomical words used to localise a side mention."""
    anchors: list[str] = []
    for terms in _REGION_TERMS.values():
        anchors.extend(terms)
    for _key, (_region, _sub, terms) in _STRUCTURE_TERMS.items():
        anchors.extend(terms)
    return anchors


_ANCHORS = _anchor_terms()


def detect_side(text: str) -> tuple[str | None, float]:
    """Return (side, confidence) based on side words near anatomy terms."""
    norm = _normalize(text)
    matches: list[tuple[str, int]] = []
    for anchor in _ANCHORS:
        for marker in re.finditer(re.escape(anchor), norm):
            start, end = marker.span()
            window = norm[max(0, start - 25) : end + 25]
            for side, synonyms in _SIDE_SYNONYMS.items():
                if side == "bilateral":
                    continue
                for syn in synonyms:
                    if syn in window:
                        matches.append((side, marker.start()))
                        break
    if matches:
        counts: dict[str, int] = {}
        for side, _pos in matches:
            counts[side] = counts.get(side, 0) + 1
        side = max(counts, key=lambda s: counts[s])
        return side, 0.9

    bilateral_hits = sum(
        len(re.findall(rf"\b{re.escape(syn)}\b", norm))
        for syn in _SIDE_SYNONYMS["bilateral"]
    )
    if bilateral_hits:
        return "bilateral", 0.75

    # Fallback: a lone side word in a short report is almost always the limb studied.
    side_hits = {
        side: sum(len(re.findall(rf"\b{re.escape(syn)}\b", norm)) for syn in synonyms - _SIDE_SYNONYMS["bilateral"])
        for side, synonyms in _SIDE_SYNONYMS.items()
        if side != "bilateral"
    }
    candidates = {s: c for s, c in side_hits.items() if c}
    if not candidates:
        return None, 0.0
    side = max(candidates, key=candidates.get)
    return side, 0.6


def detect_structures(text: str) -> list[dict[str, Any]]:
    """Return specific anatomical structures mentioned, most specific first."""
    norm = _normalize(text)
    found: list[dict[str, Any]] = []
    for key, (region, sub_region, terms) in _STRUCTURE_TERMS.items():
        for term in terms:
            idx = norm.find(term)
            if idx != -1:
                found.append(
                    {
                        "structure": key,
                        "matched_term": term,
                        "region": region,
                        "sub_region": sub_region,
                    }
                )
                break
    return found


def detect_region(text: str) -> tuple[str | None, float]:
    """Return (region, confidence); structure mentions take precedence."""
    norm = _normalize(text)
    structures = detect_structures(norm)
    if structures:
        return structures[0]["region"], 0.9

    scores = {region: 0 for region in _REGION_TERMS}
    for region, terms in _REGION_TERMS.items():
        for term in terms:
            scores[region] += len(re.findall(rf"(?<![a-z]){re.escape(term)}(?![a-z])", norm))
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return None, 0.0
    return best, 0.8


def detect_restrictions(text: str) -> list[dict[str, str]]:
    """Return precautions explicitly stated in the report."""
    norm = _normalize(text)
    found: list[dict[str, str]] = []
    for key, keywords in _RESTRICTION_RULES:
        for kw in keywords:
            if kw in norm:
                found.append({"restriction": key, "matched_term": kw})
                break
    return found


def detect_severity(text: str) -> tuple[str | None, float]:
    norm = _normalize(text)
    matched: list[tuple[str, int]] = []
    for level, keywords in _SEVERITY_RULES:
        for kw in keywords:
            count = len(re.findall(re.escape(kw), norm))
            if count:
                matched.append((level, count))
    if not matched:
        return None, 0.0
    best = max(matched, key=lambda m: (_SEVERITY_ORDER[m[0]], m[1]))
    return best[0], 0.75


def _is_negated(norm: str, start: int) -> bool:
    """Return True when a condition keyword at `start` is negated nearby."""
    window = norm[max(0, start - 45) : start]
    return any(marker in window for marker in _NEGATION_MARKERS)


def detect_condition(text: str) -> tuple[str | None, str | None, float]:
    """Return (condition_key, matched_term, confidence)."""
    norm = _normalize(text)
    for condition, keywords in _CONDITIONS:
        for kw in keywords:
            idx = norm.find(kw)
            if idx == -1:
                continue
            if _is_negated(norm, idx):
                continue
            return condition, kw.strip(), 0.85
    return None, None, 0.0


def _label(key: str | None) -> str | None:
    return key.replace("_", " ") if key else None


def _extract_findings(report: str) -> list[dict[str, Any]]:
    """Split the report into statements and extract one finding each.

    Supports multiple injuries (e.g. "Left wrist fracture. Right shoulder
    stiffness") by keeping every statement that names anatomy or a condition.
    """
    segments = [s.strip() for s in re.split(r"[.;\n+]|\bdemonstrates\b|\bshows\b", _normalize(report)) if s.strip()]
    findings: list[dict[str, Any]] = []
    last_side: str | None = None

    def _segment_side(seg: str) -> str | None:
        for anchor in _ANCHORS:
            for marker in re.finditer(re.escape(anchor), seg):
                start, end = marker.span()
                window = seg[max(0, start - 25) : end + 25]
                for side, synonyms in _SIDE_SYNONYMS.items():
                    if side == "bilateral":
                        continue
                    for syn in synonyms:
                        if syn in window:
                            return side
        if any(syn in seg for syn in _SIDE_SYNONYMS["bilateral"]):
            return "bilateral"
        return None

    for seg in segments:
        structures = detect_structures(seg)
        region = structures[0]["region"] if structures else None
        sub_region = structures[0]["sub_region"] if structures else None
        structure = structures[0]["structure"] if structures else None
        if not region:
            region, _conf = detect_region(seg)
        side = _segment_side(seg) or last_side
        condition, _term, _conf = detect_condition(seg)
        severity, _sconf = detect_severity(seg)

        if not (region or condition):
            continue
        if side:
            last_side = side

        finding = {
            "side": side,
            "region": region,
            "sub_region": sub_region,
            "specific_structure": structure,
            "condition": condition,
            "condition_label": _label(condition),
            "severity": severity,
        }
        dedupe_key = (
            finding["side"],
            finding["region"],
            finding["specific_structure"],
            finding["condition"],
        )
        if finding not in findings and dedupe_key not in [
            (f["side"], f["region"], f["specific_structure"], f["condition"]) for f in findings
        ]:
            findings.append(finding)
    return findings


def parse_report(report: str | None) -> dict[str, Any]:
    """Parse a free-text X-ray report into structured facts.

    Returns a dict with keys: affected_side, affected_region, sub_region,
    specific_structure, severity, condition, condition_label, summary,
    restrictions, findings, recommended_region, matched_terms, confidence,
    source. When nothing can be extracted a fully empty dict is returned.
    Unknown values stay null — nothing is invented.
    """
    if not report or not report.strip():
        return {}

    norm = _normalize(report)
    findings = _extract_findings(report)
    primary = findings[0] if findings else {}

    side, side_conf = detect_side(report)
    region, region_conf = detect_region(report)
    severity, severity_conf = detect_severity(report)
    condition_key, condition_term, condition_conf = detect_condition(report)
    restrictions = detect_restrictions(report)

    structures = detect_structures(norm)
    structure = primary.get("specific_structure") or (structures[0]["structure"] if structures else None)
    sub_region = primary.get("sub_region") or (structures[0]["sub_region"] if structures else None)
    region = primary.get("region") or region
    side = primary.get("side") or side
    severity = primary.get("severity") or severity
    condition_key = primary.get("condition") or condition_key

    condition_label = condition_key.replace("_", " ").capitalize() if condition_key else None

    recommended_region = "_".join(p for p in (side, structure or sub_region or region) if p) or None

    location = (
        _label(structure)
        or _label(sub_region)
        or region
        or ""
    )

    parts = []
    if condition_key:
        parts.append(condition_label or "")
    if severity:
        parts.append(f"{severity} severity")
    if condition_key or severity:
        if location:
            parts.append(f"in the {location}")
        if side and side != "bilateral":
            parts.append(f"on the {side} side")
        elif side == "bilateral":
            parts.append("bilaterally")
    if parts:
        summary = " ".join(p for p in parts) + "."
    elif region or side:
        loc = " ".join(p for p in (f"the {location}" if location else "", f"on the {side} side" if side and side != "bilateral" else "") if p)
        summary = f"No abnormality identified in {loc}."
    else:
        summary = ""

    confidences = [c for c in (side_conf, region_conf, severity_conf, condition_conf) if c]
    overall_conf = round(sum(confidences) / len(confidences), 2) if confidences else 0.0

    return {
        "affected_side": side,
        "affected_region": region,
        "sub_region": sub_region,
        "specific_structure": structure,
        "severity": severity,
        "condition": condition_key,
        "condition_label": condition_label,
        "summary": summary,
        "restrictions": restrictions,
        "findings": findings,
        "recommended_region": recommended_region,
        "matched_terms": {
            "side": side,
            "region": region,
            "severity": severity,
            "condition": condition_term,
        },
        "confidence": {
            "side": side_conf,
            "region": region_conf,
            "severity": severity_conf,
            "condition": condition_conf,
            "overall": overall_conf,
        },
        "source": "xray_report",
    }
