# Evaluation

Does the LLM label misconceptions the way a teacher does? This folder holds
the data and results that answer that, honestly.

## 0. Constructed challenge set

`challenge_set.csv` holds 23 cases written to contain one known misconception
each (or none), with labels checked by the teacher against the memo. It tests
whether the system **can detect** each misconception. It does **not** measure
agreement with real learners: that needs real scripts (below). Every row is
marked `source = constructed`.

All 23 rows can be run. To run it in Colab (costs under $1):

```python
import anthropic
from pipeline import misconceptions as mc
from pipeline.evaluate import load, run_llm, report

cat = mc.load()
rows = load("repo/evaluation/challenge_set.csv")
results = run_llm(anthropic.Anthropic(), cat, rows)
print(report(results))
for r in results:
    if r["teacher_ids"] != r["llm_ids"] or r["needs_teacher"]:
        print(r["case_id"], "| teacher:", r["teacher_ids"], "| AI:", r["llm_ids"], "|", r["problems"])
```

## 1. Collect anonymised scripts

For Question 11.2 and 11.3 (DBE Grade 11 P1, November 2018), copy each
learner's working into `teacher_labels_template.csv`, one row per learner per
item:

| Column | What to put |
|---|---|
| `learner_code` | A code such as L01. **Never a name or ID number** |
| `item_id` | `dbe_p1_2018_nov_gr11.11.2` or `...11.3` |
| `working` | The learner's working, typed as written, mistakes included |
| `final_answer` | Their final number, e.g. `0.56` |
| `earlier_answer` | For 11.3 only: their 11.2 answer (for positive marking) |
| `teacher_ids` | **Your** diagnosis, e.g. `EMI-08` or `EMI-12;EMI-13`. Empty if correct |
| `teacher_marks` | **Your** marks for the item, using the memo |

Label every row yourself **before** running the LLM, so its answers cannot
influence yours.

Privacy: get consent, remove names, ID numbers and school details. The
working is sent to the Anthropic API when the LLM runs (POPIA).

## 2. Run the LLM and the report

```python
import anthropic, csv
from pipeline import misconceptions as mc
from pipeline.evaluate import load, run_llm, report

cat = mc.load()
rows = load("evaluation/teacher_labels.csv")
results = run_llm(anthropic.Anthropic(), cat, rows[:3])   # try 3 rows first
print(report(results))
```

Start with a few rows to check cost and output before running them all.

## 3. Publish the results, including failures

Save `report(...)` output and the rows the LLM got wrong in `evaluation/results/`.
Report the numbers as they are; the failure cases are the most useful part.
