"""Decide how loudly each finding is shown: Issue / Suggestion / Hidden.

score = rule strength × agreement × (1 − the rule's false-alarm rate on good Xero ads)
Code findings are measured, so they are always Issues.
"""

import json
from pathlib import Path

CALIBRATION = Path(__file__).resolve().parent / "calibration.json"
ISSUE, SUGGESTION = 0.7, 0.4

# How solid the rule behind each check is.
#   1.0 = written in Xero's brand kit · 0.8 = universal design defect (anyone would call it broken)
#   0.5 = "(observed)": inferred from brand-kit images · 0.3 = our own taste call
RULE_STRENGTH = {
    "wordmark_integrity": 1.0,
    "cobrand_lockup": 1.0,
    "pill_needed": 1.0,
    "pill_misused": 1.0,
    "bloom_flat_fill": 1.0,
    "bloom_extends_past_frame": 1.0,
    "bloom_pattern_colours": 1.0,
    "photo_in_bloom_crop": 1.0,
    "card_content_broken": 0.8,
    "stray_artefact": 0.8,
    "text_rendering": 0.8,
    "asset_quality": 0.8,
    "readable_on_background": 0.8,
    "case_and_emphasis": 0.5,
    "charm_style": 0.5,
    "illustration_style": 0.5,
    "bloom_shape_style": 0.5,
    "button_looks_clickable": 0.5,
    "awkward_crop": 0.5,
    "charm_placement_feel": 0.3,
}
DEFAULT_STRENGTH = 0.5
VOTE = {("true", "high"): 1.0, ("true", "medium"): 0.8, ("true", "low"): 0.5}


def load_calibration():
    return json.loads(CALIBRATION.read_text()) if CALIBRATION.exists() else {}


def false_alarm_rate(cal, check, exclude_ad=None):
    """Share of good-ad evaluations where this check wrongly failed.

    exclude_ad: leave that ad out (leave-one-out), so an ad is never scored on its own calibration.
    Smoothed (+1 fail / +2 evaluations) so a rule seen on few ads isn't trusted blindly.
    """
    per_ad = cal.get(check, {})
    evaluated = sum(v["evaluated"] for ad, v in per_ad.items() if ad != exclude_ad)
    failed = sum(v["failed"] for ad, v in per_ad.items() if ad != exclude_ad)
    if not evaluated:
        return None
    return (failed + 1) / (evaluated + 2)


def agreement(f):
    votes = f.get("verify_votes") or [
        {"verdict": f.get("verified"), "confidence": f.get("verify_confidence")}
    ]
    return sum(
        VOTE.get((v.get("verdict"), v.get("confidence")), 0.0) for v in votes
    ) / len(votes)


def escalate(findings, cal=None, exclude_ad=None):
    cal = load_calibration() if cal is None else cal
    out = []
    for f in findings:
        if f.get("source") == "code":
            out.append({**f, "score": 1.0, "tier": "issue", "why": "measured by code"})
            continue
        strength = RULE_STRENGTH.get(f["check"], DEFAULT_STRENGTH)
        agree = agreement(f)
        rate = false_alarm_rate(cal, f["check"], exclude_ad)
        score = strength * agree * (1 - (rate or 0))
        tier = (
            "issue"
            if score >= ISSUE
            else "suggestion"
            if score >= SUGGESTION
            else "hidden"
        )
        why = f"rule {strength:.1f} × agreement {agree:.2f} × " + (
            f"(1 − {rate:.0%} false alarms on good ads)"
            if rate is not None
            else "(no calibration yet)"
        )
        out.append({**f, "score": round(score, 2), "tier": tier, "why": why})
    return out
