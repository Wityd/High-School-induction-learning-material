"""Read a learner's written working with Claude and name the misconception.

Final answers alone are not always enough: in Question 11.3, B = 2,20 T can
come from EMI-15 (initial flux ignored) or EMI-12 (angle taken from the plane).
Only the working tells them apart. This module asks Claude to:

1. decide which memo ticks the working earns, and
2. name misconceptions, choosing ONLY from the catalogue, with a quote from
   the learner's working as evidence.

The result is then checked by code, never trusted blindly:

* ids not in the catalogue are removed and the result is flagged;
* the tick list must match the memo;
* the final answer is also diagnosed by the rule-based fingerprints, and if
  the two disagree the result goes to the teacher.

PRIVACY: learner working is sent to the Anthropic API. Send only anonymised
working (no names, no ID numbers, no school), with consent, in line with POPIA.
"""
from typing import List, Optional

from pydantic import BaseModel

from pipeline import misconceptions as mc
from pipeline.marking import mark_numeric

MODEL = "claude-opus-5-5"


class TickDecision(BaseModel):
    tick: str
    earned: bool
    reason: str


class Diagnosis(BaseModel):
    misconception_ids: List[str]
    evidence: str
    ticks: List[TickDecision]
    confidence: str  # "high", "medium" or "low"
    feedback_for_teacher: str


def system_prompt(cat: dict) -> str:
    """Stable across every learner, so it can be cached."""
    lines = [
        "You are an experienced South African Grade 11 Physical Sciences marker (CAPS).",
        "You mark one learner's written working for one question against the official",
        "memorandum ticks, and you diagnose misconceptions.",
        "",
        "Rules:",
        "- Choose misconception ids ONLY from the catalogue below. If none fits, return",
        "  an empty list. Never invent an id.",
        "- 'evidence' must quote the learner's own working that shows the misconception,",
        "  or say 'no misconception' when the list is empty.",
        "- Return one tick decision for each memo tick, in the order given, using the",
        "  tick text exactly as given.",
        "- Apply positive marking when the memo says so: a wrong earlier answer used",
        "  correctly later earns the later ticks.",
        "- Use confidence 'low' when the working is unclear, incomplete or ambiguous.",
        "- feedback_for_teacher: one or two plain sentences a teacher can act on.",
        "",
        "Misconception catalogue:",
    ]
    for m in cat["misconceptions"]:
        lines.append(f"- {m['id']} ({m['type']}): {m['label']}. Learners say: {m['learner_says']} "
                     f"Correct idea: {m['correct_idea']}")
    return "\n".join(lines)


def user_prompt(item: dict, working: str, earlier_answer: Optional[float]) -> str:
    ticks = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(item["memo_ticks"]))
    earlier = ("" if earlier_answer is None else
               f"\nThe learner's own answer to {item['positive_marking_from'].rsplit('.', 2)[-2]}."
               f"{item['positive_marking_from'].rsplit('.', 1)[-1]} was {earlier_answer}.\n")
    return (f"Question:\n{item['question']}\n\nMemo ticks:\n{ticks}\n{earlier}\n"
            f"Learner's working (anonymised):\n<working>\n{working}\n</working>")


def check(cat: dict, item: dict, d: Diagnosis) -> dict:
    """Validate the model's answer against the catalogue and the memo."""
    known = {m["id"] for m in cat["misconceptions"]}
    problems = []
    ids = [i for i in d.misconception_ids if i in known]
    if len(ids) != len(d.misconception_ids):
        problems.append(f"unknown ids removed: {sorted(set(d.misconception_ids) - known)}")
    if [t.tick for t in d.ticks] != item["memo_ticks"]:
        problems.append("tick list does not match the memo")
    return {
        "misconception_ids": ids,
        "evidence": d.evidence,
        "ticks": [t.model_dump() for t in d.ticks],
        "marks": sum(t.earned for t in d.ticks),
        "max": len(item["memo_ticks"]),
        "confidence": d.confidence,
        "feedback_for_teacher": d.feedback_for_teacher,
        "problems": problems,
    }


def diagnose_working(client, cat: dict, item_id: str, working: str, final_answer: float,
                     earlier_answer: Optional[float] = None) -> dict:
    """Diagnose one learner's working for one item.

    ``client`` is an ``anthropic.Anthropic()``; tests pass a fake one.
    ``final_answer`` is the learner's final number, used for the rule-based
    cross-check. ``earlier_answer`` is their answer to the item this one is
    positively marked from (e.g. 11.2 when diagnosing 11.3).
    """
    item = next(i for i in cat["numeric_map"] if i["item_id"] == item_id)
    response = client.beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        output_config={"effort": "medium"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=[{"type": "text", "text": system_prompt(cat),
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_prompt(item, working, earlier_answer)}],
        output_format=Diagnosis,
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        return {"item_id": item_id, "needs_teacher": True,
                "problems": [f"no diagnosis (stop_reason={response.stop_reason})"]}

    result = check(cat, item, response.parsed_output)
    rule = mark_numeric(cat, item_id, final_answer, len(item["memo_ticks"]),
                        source_value=earlier_answer)
    rule_ids = {m["id"] for m in rule["misconceptions"]}
    llm_ids = set(result["misconception_ids"])
    # Agreement: the rules found nothing to compare against ("unknown"), or the
    # two share at least one id, or both say the answer is right.
    agrees = (rule["status"] == "unknown" or bool(rule_ids & llm_ids)
              or (rule["status"] in ("correct", "carried_forward") and not llm_ids))
    if not agrees:
        result["problems"].append(
            f"disagrees with final-answer rules ({rule['status']}: {sorted(rule_ids)})")
    result.update({
        "item_id": item_id,
        "rule_status": rule["status"],
        "rule_ids": sorted(rule_ids),
        "needs_teacher": bool(result["problems"]) or result["confidence"] == "low",
    })
    return result
