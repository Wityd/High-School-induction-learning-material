"""Read a learner's written working with Claude and name the misconception.

Final answers alone are not always enough: in Question 11.3, B = 2,20 T can
come from EMI-15 (initial flux ignored) or EMI-12 (angle taken from the plane),
and in 11.5 only the explanation shows EMI-17. This module asks Claude to:

1. decide which memo ticks the working earns, and
2. name misconceptions, choosing ONLY from the catalogue, with a quote from
   the learner's working as evidence.

It handles two kinds of item:

* calculations (``numeric_map`` in the catalogue, e.g. 11.2, 11.3), and
* text items (``text_items``: definitions, one-word answers, explanations,
  e.g. 11.1 and 11.4 to 11.7).

The result is then checked by code, never trusted blindly:

* ids not in the catalogue are removed and the result is flagged;
* the tick list must match the memo, and "2 or 0" items are enforced;
* the final answer is also checked by the rule-based engine where one exists
  (fingerprints for calculations, answer options for one-word items, keyword
  rules for definitions), and a clear disagreement goes to the teacher.

The model is swappable: ``ClaudeBackend`` (Anthropic API, paid) or
``OllamaBackend`` (an open-source model such as Llama, run locally, free).
The checks below are the same for both.

PRIVACY: with ClaudeBackend, learner working is sent to the Anthropic API. Send only anonymised
working (no names, no ID numbers, no school), with consent, in line with POPIA.
"""
from typing import List, Literal, Optional, Union

from pydantic import BaseModel

from pipeline import misconceptions as mc
from pipeline.marking import mark_numeric

MODEL = "claude-opus-5-5"

Answer = Union[float, str]


class TickDecision(BaseModel):
    number: int  # memo tick number: 1, 2, 3 ...
    earned: bool
    reason: str


class Diagnosis(BaseModel):
    misconception_ids: List[str]
    evidence: str
    ticks: List[TickDecision]
    confidence: Literal["high", "medium", "low"]
    feedback_for_teacher: str


class ClaudeBackend:
    """Claude through the Anthropic API (paid, needs ANTHROPIC_API_KEY)."""

    def __init__(self, client, model: str = MODEL):
        self.client, self.model = client, model
        self.name = model

    def diagnose(self, system: str, user: str):
        response = self.client.beta.messages.parse(
            model=self.model,
            max_tokens=16000,
            output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            output_format=Diagnosis,
        )
        if response.stop_reason == "refusal" or response.parsed_output is None:
            return None, f"no diagnosis (stop_reason={response.stop_reason})"
        return response.parsed_output, None


class OllamaBackend:
    """An open-source model (e.g. Llama) running locally through Ollama. Free.

    Ollama is asked for JSON matching the same Diagnosis schema. Small models
    sometimes still return invalid JSON; that is caught and sent to the teacher.
    """

    def __init__(self, model: str = "llama3.1:8b", chat=None):
        if chat is None:
            from ollama import chat  # only needed when Ollama is actually used
        self.chat, self.model = chat, model
        self.name = model

    def diagnose(self, system: str, user: str):
        from pydantic import ValidationError

        response = self.chat(
            model=self.model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            format=Diagnosis.model_json_schema(),
            options={"temperature": 0},  # same answer each run, as a marker should
        )
        try:
            return Diagnosis.model_validate_json(response.message.content), None
        except ValidationError:
            return None, "model returned invalid JSON"


def as_backend(client_or_backend):
    """Accept a backend, or a plain anthropic.Anthropic() client."""
    if hasattr(client_or_backend, "diagnose"):
        return client_or_backend
    return ClaudeBackend(client_or_backend)


def find_item(cat: dict, item_id: str):
    """Return ("numeric" or "text", item) for an item id."""
    for kind, key in (("numeric", "numeric_map"), ("text", "text_items")):
        for item in cat.get(key, []):
            if item["item_id"] == item_id:
                return kind, item
    raise KeyError(f"{item_id} is not a calculation or text item in the catalogue")


def _short(item_id: str) -> str:
    """'dbe_p1_2018_nov_gr11.11.3' -> '11.3'."""
    return ".".join(item_id.rsplit(".", 2)[-2:])


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
        "- Return exactly one tick decision for each memo tick, using the tick's number",
        "  (1, 2, 3 ...). Do not add ticks the memo does not list.",
        "- Apply positive marking when the memo says so: a wrong earlier answer used",
        "  correctly later earns the later ticks.",
        "- A learner can reach the right answer through wrong reasoning. Award the ticks",
        "  the memo gives for the answer, and still name the misconception the reasoning shows.",
        "- Answers in Afrikaans are marked the same as answers in English.",
        "- Use confidence 'low' when the working is unclear, incomplete or ambiguous.",
        "- feedback_for_teacher: one or two plain sentences a teacher can act on.",
        "",
        "Misconception catalogue:",
    ]
    for m in cat["misconceptions"]:
        lines.append(f"- {m['id']} ({m['type']}): {m['label']}. Learners say: {m['learner_says']} "
                     f"Correct idea: {m['correct_idea']}")
    return "\n".join(lines)


def user_prompt(item: dict, working: str, earlier_answer: Optional[Answer]) -> str:
    ticks = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(item["memo_ticks"]))
    rule = "\nMemo rule: all ticks or none (2 or 0).\n" if item.get("all_or_nothing") else ""
    earlier = ""
    source = item.get("positive_marking_from") or item.get("context_from")
    if earlier_answer is not None and source:
        earlier = f"\nThe learner's own answer to {_short(source)} was {earlier_answer}.\n"
    return (f"Question:\n{item['question']}\n\nMemo ticks:\n{ticks}\n{rule}{earlier}\n"
            f"Learner's working (anonymised):\n<working>\n{working}\n</working>")


def check(cat: dict, item: dict, d: Diagnosis) -> dict:
    """Validate the model's answer against the catalogue and the memo."""
    known = {m["id"] for m in cat["misconceptions"]}
    problems = []
    ids = [i for i in d.misconception_ids if i in known]
    if len(ids) != len(d.misconception_ids):
        problems.append(f"unknown ids removed: {sorted(set(d.misconception_ids) - known)}")
    memo = item["memo_ticks"]
    numbers = [t.number for t in d.ticks]
    if sorted(numbers) == list(range(1, len(memo) + 1)):
        marks = sum(t.earned for t in d.ticks)
        if item.get("all_or_nothing") and marks not in (0, len(memo)):
            marks = 0  # memo: 2 or 0
    else:
        # Wrong number of ticks: the marks cannot be trusted, so none are given.
        problems.append(f"expected ticks 1 to {len(memo)}, got {numbers}")
        marks = None
    ticks = [{"tick": memo[t.number - 1] if 1 <= t.number <= len(memo) else f"(no tick {t.number})",
              "earned": t.earned, "reason": t.reason} for t in d.ticks]
    return {
        "misconception_ids": ids,
        "evidence": d.evidence,
        "ticks": ticks,
        "marks": marks,
        "max": len(item["memo_ticks"]),
        "confidence": d.confidence,
        "feedback_for_teacher": d.feedback_for_teacher,
        "problems": problems,
        "notes": [],
    }


def rule_check(cat: dict, kind: str, item: dict, working: str, final_answer: Answer,
               earlier_answer: Optional[Answer]) -> dict:
    """What the rule-based engine says, and how much to trust it.

    strength "strong": fingerprints or answer options, a clear disagreement
    goes to the teacher. "weak": a keyword rule, reported only. "none": no rule.
    """
    item_id = item["item_id"]
    if kind == "numeric":
        earlier = float(earlier_answer) if earlier_answer not in (None, "") else None
        r = mark_numeric(cat, item_id, float(final_answer), len(item["memo_ticks"]),
                         source_value=earlier)
        return {"status": r["status"], "ids": {m["id"] for m in r["misconceptions"]},
                "strength": "strong"}
    if any(row["item_id"] == item_id for row in cat.get("item_map", [])):
        try:
            found = mc.diagnose_choice(cat, item_id, str(final_answer).strip())
        except KeyError:
            return {"status": "unknown", "ids": set(), "strength": "strong"}
        ids = {m["id"] for m in found}
        return {"status": "known_error" if ids else "correct", "ids": ids, "strength": "strong"}
    if any(rule["item_id"] == item_id for rule in cat.get("text_rules", [])):
        ids = {m["id"] for m in mc.diagnose_text(cat, item_id, working)}
        return {"status": "known_error" if ids else "unknown", "ids": ids, "strength": "weak"}
    return {"status": "unknown", "ids": set(), "strength": "none"}


def diagnose_working(client, cat: dict, item_id: str, working: str, final_answer: Answer,
                     earlier_answer: Optional[Answer] = None) -> dict:
    """Diagnose one learner's working for one item.

    ``client`` is a backend (``ClaudeBackend``, ``OllamaBackend``) or a plain
    ``anthropic.Anthropic()``; tests pass a fake one.
    ``final_answer`` is the learner's final number or word(s), used for the
    rule-based cross-check. ``earlier_answer`` is their answer to the item this
    one depends on (e.g. 11.2 for 11.3, 11.4 for 11.5, 11.6 for 11.7).
    """
    kind, item = find_item(cat, item_id)
    backend = as_backend(client)
    diagnosis, error = backend.diagnose(system_prompt(cat),
                                        user_prompt(item, working, earlier_answer))
    if diagnosis is None:
        return {"item_id": item_id, "model": backend.name, "needs_teacher": True,
                "problems": [error]}

    result = check(cat, item, diagnosis)
    result["model"] = backend.name
    rule = rule_check(cat, kind, item, working, final_answer, earlier_answer)
    llm_ids = set(result["misconception_ids"])

    if rule["strength"] == "strong" and rule["status"] != "unknown":
        rule_correct = rule["status"] in ("correct", "carried_forward")
        if rule_correct and llm_ids and kind == "text":
            # One-word answer is right, but the reasoning shows a misconception.
            result["notes"].append("right answer, but the reasoning shows a misconception")
        elif rule_correct and llm_ids:
            result["problems"].append(
                f"rules say {rule['status']}, LLM found {sorted(llm_ids)}")
        elif not rule_correct and not (rule["ids"] & llm_ids):
            result["problems"].append(
                f"disagrees with final-answer rules ({rule['status']}: {sorted(rule['ids'])})")
    elif rule["strength"] == "weak" and rule["ids"] != llm_ids:
        result["notes"].append(f"keyword rule suggested {sorted(rule['ids'])}")

    result.update({
        "item_id": item_id,
        "rule_status": rule["status"],
        "rule_ids": sorted(rule["ids"]),
        "needs_teacher": bool(result["problems"]) or result["confidence"] == "low",
    })
    return result


