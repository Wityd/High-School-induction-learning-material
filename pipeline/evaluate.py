"""Compare the LLM's misconception labels and marks with a teacher's.

Input: a CSV with one row per learner per item (see
``evaluation/teacher_labels_template.csv``). The teacher fills in
``teacher_ids`` and ``teacher_marks``; :func:`run_llm` fills ``llm_ids`` and
``llm_marks``. :func:`report` then gives the numbers worth publishing:

* exact agreement on the set of misconceptions,
* Cohen's kappa on "has a misconception or not" (agreement beyond chance),
* precision and recall per misconception id,
* marks: exact agreement and mean absolute difference,
* how many items the system sent to the teacher.
"""
import csv
from collections import Counter

from pipeline.llm_diagnose import diagnose_working


def _ids(cell: str) -> set:
    return {i.strip() for i in (cell or "").split(";") if i.strip()}


def _number_or_text(cell):
    """'0.56' -> 0.56, 'NORTH' -> 'NORTH', '' -> None."""
    if cell is None or str(cell).strip() == "":
        return None
    try:
        return float(cell)
    except ValueError:
        return str(cell).strip()


def load(path: str) -> list:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def run_llm(client, cat: dict, rows: list) -> list:
    """Diagnose every row with the LLM. Costs money: try a few rows first."""
    out = []
    for row in rows:
        earlier = _number_or_text(row.get("earlier_answer"))
        r = diagnose_working(client, cat, row["item_id"], row["working"],
                             _number_or_text(row["final_answer"]), earlier)
        out.append({**row,
                    "llm_ids": ";".join(r.get("misconception_ids", [])),
                    "llm_marks": r.get("marks", ""),
                    "model": r.get("model", ""),
                    "needs_teacher": r["needs_teacher"],
                    "problems": " | ".join(r.get("problems", []))})
    return out


def cohen_kappa(a: list, b: list) -> float:
    """Kappa for two lists of booleans. 1 = perfect, 0 = chance level."""
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    expected = pa * pb + (1 - pa) * (1 - pb)
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def report(rows: list) -> dict:
    teacher = [_ids(r["teacher_ids"]) for r in rows]
    llm = [_ids(r["llm_ids"]) for r in rows]
    n = len(rows)

    tp, fp, fn = Counter(), Counter(), Counter()
    for t, l in zip(teacher, llm):
        for i in t & l:
            tp[i] += 1
        for i in l - t:
            fp[i] += 1
        for i in t - l:
            fn[i] += 1
    per_id = {}
    for i in sorted(set(tp) | set(fp) | set(fn)):
        p = tp[i] / (tp[i] + fp[i]) if tp[i] + fp[i] else None
        r = tp[i] / (tp[i] + fn[i]) if tp[i] + fn[i] else None
        per_id[i] = {"precision": p, "recall": r, "teacher_count": tp[i] + fn[i]}

    marked = [(int(r["teacher_marks"]), int(r["llm_marks"])) for r in rows
              if str(r.get("teacher_marks", "")).strip() and str(r.get("llm_marks", "")).strip()]
    return {
        "rows": n,
        "exact_id_agreement": sum(t == l for t, l in zip(teacher, llm)) / n,
        "kappa_has_misconception": cohen_kappa([bool(t) for t in teacher], [bool(l) for l in llm]),
        "per_id": per_id,
        "marks_exact_agreement": (sum(a == b for a, b in marked) / len(marked)) if marked else None,
        "marks_mean_abs_diff": (sum(abs(a - b) for a, b in marked) / len(marked)) if marked else None,
        "sent_to_teacher": sum(str(r.get("needs_teacher")) == "True" for r in rows),
    }
