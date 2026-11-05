"""Load a misconception catalogue and diagnose learner answers against it.

This is the rule-based core that the LLM layer will build on. Every diagnosis
the LLM makes later can be checked against these hand-written mappings.
"""
import json
import math
from pathlib import Path

CATALOGUE_DIR = Path(__file__).resolve().parent.parent / "misconceptions"


def load(name: str = "electromagnetic_induction") -> dict:
    with open(CATALOGUE_DIR / f"{name}.json", encoding="utf-8") as f:
        cat = json.load(f)
    validate(cat)
    return cat


def validate(cat: dict) -> None:
    """Raise ValueError if the catalogue refers to unknown misconception ids."""
    ids = [m["id"] for m in cat["misconceptions"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate misconception ids")
    known = set(ids)
    refs = [m for row in cat.get("item_map", []) for m in row["misconceptions"]]
    refs += [m for item in cat.get("numeric_map", [])
             for fp in item["fingerprints"] for m in fp["misconceptions"]]
    refs += [m for rule in cat.get("text_rules", []) for m in rule["misconceptions"]]
    unknown = set(refs) - known
    if unknown:
        raise ValueError(f"Unknown misconception ids: {sorted(unknown)}")
    for row in cat.get("item_map", []):
        if row["correct"] and row["misconceptions"]:
            raise ValueError(f"{row['item_id']} {row['option']} is correct but tagged")


def _details(cat: dict, ids: list) -> list:
    by_id = {m["id"]: m for m in cat["misconceptions"]}
    return [by_id[i] for i in ids]


def diagnose_choice(cat: dict, item_id: str, option: str) -> list:
    """Misconceptions behind a multiple-choice answer (empty list if correct)."""
    for row in cat["item_map"]:
        if row["item_id"] == item_id and row["option"] == option.upper():
            return _details(cat, row["misconceptions"])
    raise KeyError(f"No option {option} for {item_id}")


def diagnose_numeric(cat: dict, item_id: str, value: float) -> dict:
    """Classify a numeric answer as correct, a known error pattern, or unknown."""
    item = next(i for i in cat["numeric_map"] if i["item_id"] == item_id)
    tol = item["tolerance"]

    def close(a, b):
        return math.isclose(a, b, rel_tol=tol)

    if close(value, item["correct_value"]):
        return {"status": "correct", "misconceptions": []}
    for fp in item["fingerprints"]:
        if close(value, fp["value"]):
            return {"status": "known_error", "working": fp["working"],
                    "misconceptions": _details(cat, fp["misconceptions"])}
    return {"status": "unknown", "misconceptions": []}


def diagnose_text(cat: dict, item_id: str, answer: str) -> list:
    """Apply simple keyword rules to a written answer (LLM will replace this)."""
    answer = answer.lower()
    found = []
    for rule in cat.get("text_rules", []):
        if rule["item_id"] == item_id and not any(k in answer for k in rule["if_missing_any"]):
            found += rule["misconceptions"]
    return _details(cat, found)
