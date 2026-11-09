"""Draft memo tick descriptions with an LLM, for the teacher to review.

Input: a memo lined up with its paper (pipeline.memo.match_paper) and the
paper's questions (pipeline.extract). For every memo item the LLM writes one
description per mark, in the format chosen by the teacher:

    1. Formula: ε = −NΔΦ/Δt
    2. Substitution: 7 = −400ΔΦ/0,08
    3. Answer: ΔΦ = −1,4 × 10⁻³ Wb

Decisions made with the teacher: "Label: content" for each tick, English
only, and diagram items (flagged by the memo reader) are left for the
teacher to write.

The LLM only drafts. Code checks every draft, and nothing is used for
marking until the teacher has accepted it.
"""
import re
from typing import Literal

from pydantic import create_model

LABELS = ("Formula", "Substitution", "Answer", "Unit", "Statement", "Definition",
          "Explanation", "Direction", "Choice", "Criterion", "Method")

SYSTEM = f"""You are an experienced South African Grade 11 Physical Sciences marker (CAPS).
You turn one item of the official DBE marking guideline (memo) into a list of
tick descriptions that another marker can apply.

Rules:
- Give exactly one description per mark: tick_1 is the first mark, tick_2 the
  second, and so on. The memo shows each mark as a ✓, and each ✓ rewards the
  text just before it. So "-0,0014 ✓ = (0,03)²B(cos 45° - cos 0°) ✓" is two
  ticks: one for -0,0014 and one for (0,03)²B(cos 45° - cos 0°).
- Give the final answer only once, in the last tick.
- Write each description as "Label: content". Use one of these labels:
  {", ".join(LABELS)}.
- Take the content from the memo. Do not add steps, numbers or answers that
  are not in the memo.
- The memo text comes from a PDF, so formulas may be scrambled across lines.
  Rebuild them carefully. If you cannot be sure, say so in notes and use
  confidence "low".
- Write in English only, even though the memo is also in Afrikaans.
- If the memo gives alternative methods (OPTION 1/2), write the ticks for the
  first one and summarise the others in alternatives.
- If the memo accepts several wordings for the same mark (OR/OF), list them all
  in that tick, joined by " or ".
- If the memo says all marks or none (e.g. 2 or 0), the marks are for one
  statement: split that statement across the ticks, the first part in tick_1
  and the rest in the later ticks.
- If positive marking applies, add "(or the learner's own answer to <question>)"
  to every tick that uses the earlier answer.
- The question text includes the introduction (the data given in the
  question). Use it to rebuild scrambled substitutions.
- answer: the final answer in a few words, e.g. "ΔΦ = −1,4 × 10⁻³ Wb" or "B".
"""


def draft_schema(n_marks: int):
    """One required string per mark, so the model cannot skip or add ticks."""
    fields = {f"tick_{i}": (str, ...) for i in range(1, n_marks + 1)}
    fields.update(answer=(str, ...), alternatives=(str, ...), notes=(str, ...),
                  confidence=(Literal["high", "medium", "low"], ...))
    return create_model(f"Draft{n_marks}", **fields)


def user_prompt(item, question_text: str) -> str:
    from pipeline.memo import visible

    rules = []
    if item.get("positive_marking_from"):
        rules.append(f"The memo says: positive marking from question {item['positive_marking_from']}.")
    if item.get("all_or_nothing"):
        rules.append("The memo says: all marks or none (e.g. 2 or 0).")
    return (f"Question {item['q_id']} ({int(item['marks_memo'])} marks). Draft ticks for {item['q_id']} only.\n\n"
            f"Question paper text (the whole question, for context):\n<question>\n{question_text}\n</question>\n\n"
            f"Memo text (✓ = one mark):\n<memo>\n{visible(item['text'])}\n</memo>\n"
            + ("\n" + "\n".join(rules) + "\n" if rules else ""))


# Common Afrikaans words in memo answers (the memo gives both languages).
# Only words that are clearly Afrikaans: "is", "die", "van" etc. are left out
# because they also appear in English drafts.
AFRIKAANS_WORDS = {"noord", "suid", "toeneem", "afneem", "dieselfde", "nie",
                   "indien", "wanneer", "weerstand", "stroom", "krag", "spoed",
                   "versnelling", "groter", "kleiner", "omgekeerd", "eweredig"}

NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def _numbers(text: str) -> set:
    """Numbers in a text, with decimal commas and points treated the same."""
    return {n.replace(".", ",").lstrip("0") or "0" for n in NUMBER.findall(text)}


def check_draft(draft: dict, n_marks: int, memo_text: str, question_text: str) -> list:
    """Problems a teacher should see before accepting a draft."""
    problems = []
    ticks = [draft.get(f"tick_{i}", "") for i in range(1, n_marks + 1)]
    for i, t in enumerate(ticks, start=1):
        if not t.strip():
            problems.append(f"tick {i} is empty")
        elif t.split(":")[0].strip() not in LABELS:
            problems.append(f"tick {i} has no label from the list")
    contents = [t.split(":", 1)[-1].strip().lower() for t in ticks]
    if len(set(contents)) < len(contents):
        problems.append("two ticks say the same thing")   # even with different labels
    afrikaans = sorted({w for t in ticks for w in re.findall(r"[A-Za-zë]+", t)
                        if w.lower() in AFRIKAANS_WORDS})
    if afrikaans:
        problems.append(f"Afrikaans words in an English draft: {afrikaans}")
    # Grounding: every number the LLM wrote must appear in the memo or question.
    allowed = _numbers(memo_text) | _numbers(question_text)
    written = _numbers(" ".join(ticks + [draft.get("answer", "")]))
    invented = sorted(written - allowed)
    if invented:
        problems.append(f"numbers not in the memo or question: {invented}")
    if draft.get("confidence") == "low":
        problems.append("the model is not confident")
    return problems


def draft_item(backend, item, question_text: str) -> dict:
    """Draft the ticks for one memo item, then check them."""
    n = int(item["marks_memo"])
    answer, error = backend.diagnose(SYSTEM, user_prompt(item, question_text), draft_schema(n))
    base = {"q_id": item["q_id"], "marks": n, "model": getattr(backend, "name", "")}
    if answer is None:
        return {**base, "status": "no draft", "problems": error}
    d = answer.model_dump()
    problems = check_draft(d, n, item["text"], question_text)
    return {**base,
            "draft_ticks": "\n".join(f"{i}. {d[f'tick_{i}']}" for i in range(1, n + 1)),
            "answer": d["answer"], "alternatives": d["alternatives"], "notes": d["notes"],
            "confidence": d["confidence"],
            "positive_marking_from": item.get("positive_marking_from") or "",
            "all_or_nothing": bool(item.get("all_or_nothing")),
            "status": "check" if problems else "draft",
            "problems": "; ".join(problems)}


def draft_all(backend, matched, paper, q_ids=None):
    """Draft every memo item (or only ``q_ids``), skipping diagram items.

    Returns a review table: the teacher fills in your_decision
    (accept, fix, or reject) before any draft is used for marking.
    """
    import pandas as pd

    # Context for each main question: its introduction plus all its items.
    context = {}
    for q, part in paper.groupby("question"):
        stem = part["stem"].iloc[0] if "stem" in part else ""
        context[q] = (stem + "\n" if stem else "") + "\n".join(part["text"])
    rows = []
    for _, item in matched[matched["in"] == "both"].iterrows():
        if q_ids and item["q_id"] not in q_ids:
            continue
        if item["tick_status"] == "check":
            rows.append({"q_id": item["q_id"], "marks": int(item["marks_memo"]),
                         "status": "teacher writes",
                         "problems": "diagram or unclear ticks in the memo"})
            continue
        rows.append(draft_item(backend, item.to_dict(), context.get(int(item["question"]), "")))
    out = pd.DataFrame(rows)
    out["your_decision"] = ""
    return out
