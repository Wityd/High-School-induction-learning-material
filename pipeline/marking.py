"""Mark linked calculation questions the way an NSC marker does.

Memos often say "POSITIVE MARKING FROM QUESTION 11.2": a learner who gets
11.2 wrong but uses their own 11.2 answer correctly in 11.3 still earns the
11.3 marks. Marking 11.3 against the memo's final answer alone would punish
the same mistake twice and hide what the learner actually got wrong.

Only final answers are used here, so method marks for a wrong answer cannot
be decided. Those are reported as a range (``marks_min`` to ``marks_max``)
with ``needs_working`` set, for a teacher or the later LLM layer to settle.
"""
import math

from pipeline import misconceptions as mc


def _item(cat: dict, item_id: str) -> dict:
    return next(i for i in cat["numeric_map"] if i["item_id"] == item_id)


def _result(item_id, max_marks, status, misconceptions=(), working=None):
    full = status in ("correct", "carried_forward")
    return {
        "item_id": item_id,
        "status": status,
        "marks_min": max_marks if full else 0,
        "marks_max": max_marks if full else max_marks - 1,  # answer mark is lost
        "max": max_marks,
        "needs_working": not full,
        "misconceptions": list(misconceptions),
        "working": working,
    }


def mark_numeric(cat: dict, item_id: str, value: float, max_marks: int,
                 source_value: float = None) -> dict:
    """Mark one numeric answer, applying positive marking when it applies.

    ``source_value`` is the learner's own answer to the item named in
    ``positive_marking_from`` (e.g. their 11.2 answer when marking 11.3).
    """
    item = _item(cat, item_id)
    source_id = item.get("positive_marking_from")
    carried = False

    if source_id and source_value is not None and item.get("proportional_to_source"):
        correct_source = abs(_item(cat, source_id)["correct_value"])
        if not math.isclose(abs(source_value), correct_source, rel_tol=0.02):
            if source_value == 0:
                return _result(item_id, max_marks, "unknown")
            # Rescale to the correct source value, then diagnose as usual.
            value = value * correct_source / abs(source_value)
            carried = True

    d = mc.diagnose_numeric(cat, item_id, value)
    if d["status"] == "correct":
        return _result(item_id, max_marks, "carried_forward" if carried else "correct")
    return _result(item_id, max_marks, d["status"], d["misconceptions"], d.get("working"))


def feedback(results: list) -> str:
    """Plain-language report for the teacher (the remediation tips are teacher moves)."""
    lines = []
    for r in results:
        q = r["item_id"].rsplit(".", 2)[-2] + "." + r["item_id"].rsplit(".", 1)[-1]
        if r["status"] == "correct":
            lines.append(f"{q}: {r['max']}/{r['max']}. Correct.")
        elif r["status"] == "carried_forward":
            lines.append(f"{q}: {r['max']}/{r['max']}. Earlier answer was wrong but used "
                         f"correctly here (positive marking).")
        else:
            marks = f"{r['marks_min']}-{r['marks_max']}/{r['max']}"
            if r["misconceptions"]:
                m = r["misconceptions"][0]
                lines.append(f"{q}: {marks} (method marks need the learner's working). "
                             f"Likely: {m['label']} ({m['id']}). Teacher tip: {m['remediation']}")
            else:
                lines.append(f"{q}: {marks}. Answer does not match a known mistake. "
                             f"Check the learner's working.")
    return "\n".join(lines)
