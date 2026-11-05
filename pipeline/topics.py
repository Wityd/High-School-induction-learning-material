"""Draft topic tags for Grade 11 Physical Sciences Paper 1 questions.

The tagger is a first draft for a teacher to correct, not a final answer.
Changes from the notebook version:

* Whole-word matching, so "charge" no longer matches "discharge" and "coil"
  no longer matches "recoil".
* Geometrical optics keywords (Snell's Law, critical angle, total internal
  reflection) are included, since they are part of Grade 11 Paper 1.
* A ``needs_review`` flag marks questions where the top two topics are close
  or nothing matched.
"""
import re

import pandas as pd

TOPIC_KEYWORDS = {
    "Vectors": [r"resultant", r"vectors?", r"head-to-tail", r"tail-to-head",
                r"components?"],
    "Newton's laws": [r"newton's (first|second|third) law", r"friction(al)?",
                      r"normal force", r"incline[ds]?", r"tension", r"net force",
                      r"pulley", r"trolley", r"blocks?", r"inertia"],
    "Gravitation": [r"gravitational force", r"universal gravitation", r"planets?",
                    r"satellites?", r"moon", r"orbits?", r"weight"],
    "Electrostatics": [r"coulomb's law", r"charges?", r"charged", r"electrostatic",
                       r"electric field", r"spheres?", r"point charges?"],
    "Electromagnetism": [r"magnetic", r"flux", r"faraday", r"induced", r"induction",
                         r"solenoid", r"lenz", r"coils?", r"galvanometer", r"emf"],
    "Electric circuits": [r"resistors?", r"resistance", r"circuits?", r"ammeter",
                          r"voltmeter", r"potential difference", r"internal resistance",
                          r"ohm's law", r"power"],
    "Waves and optics": [r"wavefronts?", r"diffraction", r"slits?", r"refraction",
                         r"refractive index", r"snell's law", r"critical angle",
                         r"total internal reflection", r"interference"],
}

_PATTERNS = {
    topic: [re.compile(rf"\b{kw}\b", re.I) for kw in kws]
    for topic, kws in TOPIC_KEYWORDS.items()
}


def score_topics(text: str) -> dict:
    """Count whole-word keyword hits per topic."""
    return {t: sum(len(p.findall(text)) for p in pats) for t, pats in _PATTERNS.items()}


def tag_text(text: str, min_margin: int = 2) -> dict:
    """Top topic, runner-up and whether a human should check the tag."""
    ranked = sorted(score_topics(text).items(), key=lambda kv: -kv[1])
    (top, hits), (runner, runner_hits) = ranked[0], ranked[1]
    return {
        "topic": top if hits else "Unknown",
        "hits": hits,
        "runner_up": runner,
        "runner_hits": runner_hits,
        "needs_review": hits == 0 or hits - runner_hits < min_margin,
    }


def tag_questions(df: pd.DataFrame, min_margin: int = 2) -> pd.DataFrame:
    """One row per main question with draft tags and total marks."""
    qtext = df.groupby("question")["text"].apply(lambda s: " ".join(s.astype(str)))
    tags = pd.DataFrame([tag_text(t, min_margin) for t in qtext], index=qtext.index)
    tags["marks"] = df.groupby("question")["marks"].sum()
    return tags


def apply_overrides(tags: pd.DataFrame, overrides: dict) -> pd.DataFrame:
    """Apply teacher corrections, e.g. ``{6: "Gravitation"}``, and clear the flag."""
    tags = tags.copy()
    if "source" not in tags:
        tags["source"] = "keywords"
    for q, topic in overrides.items():
        tags.loc[q, ["topic", "needs_review", "source"]] = [topic, False, "teacher"]
    return tags
