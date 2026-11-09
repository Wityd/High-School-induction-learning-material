# Pipeline

Python code that turns past papers into a verified, tagged question bank and diagnoses learner answers against the misconception catalogue.

| Module | What it does |
|--------|--------------|
| `extract.py` | Turns a DBE question paper PDF into a list of questions with marks: removes page headers, ignores the data sheet, works out a lost mark from the printed total, and checks every question total |
| `verify.py` | Checks extracted marks against the `[n]` totals printed on the paper, and separates parent questions ("2.2 Calculate the:") from questions whose marks were lost |
| `topics.py` | Drafts a topic tag per main question with whole-word keyword matching, and flags close calls with `needs_review` for a teacher to check |
| `marking.py` | Marks linked calculations with positive marking (e.g. 11.3 from the learner's own 11.2) and writes a teacher report |
| `llm_diagnose.py` | Sends a learner's written working (calculations, definitions, one-word answers, explanations) to an LLM (Claude, or Llama through Ollama), then checks the answer against the catalogue, the memo ticks and the rule-based engine |
| `evaluate.py` | Compares LLM labels and marks with a teacher's (agreement, kappa, precision and recall) |
| `misconceptions.py` | Loads and validates a catalogue in `misconceptions/`, then maps multiple-choice options, numeric answers and written answers to misconceptions |

## Loading a question paper

```bash
python -m pipeline.extract paper.pdf --paper-id physci_p1_2018_nov_gr11 --out questions.csv
```

It prints a short report: how many questions, the marks found against the paper
total, any marks worked out from the printed totals (check these), parent
questions, and whether every question matches its printed total. The CSV leaves
out the question text.

## Using it from Google Colab

```python
!git clone https://github.com/Wityd/High-School-induction-learning-material.git repo
import sys; sys.path.insert(0, "repo")

from pipeline.verify import check_totals, parent_questions, missing_marks
from pipeline.topics import tag_questions, apply_overrides

# df and body come from your extraction cells
print(check_totals(df, body).to_string(index=False))
print(missing_marks(df))            # should be empty

tags = tag_questions(df)
print(tags.to_string())             # check every row where needs_review is True

tags = apply_overrides(tags, {6: "Gravitation"})   # your corrections
df["topic"] = df["question"].map(tags["topic"])
```

## Marking a learner's Question 11 answers

```python
from pipeline import misconceptions as mc
from pipeline.marking import mark_numeric, feedback

cat = mc.load()
q = "dbe_p1_2018_nov_gr11.11"
r2 = mark_numeric(cat, q + ".2", 0.56, max_marks=3)                    # forgot N
r3 = mark_numeric(cat, q + ".3", 2124, max_marks=4, source_value=0.56)  # used 0,56 correctly
print(feedback([r2, r3]))
```

## Running the tests

```bash
pip install -r requirements.txt
python -m pytest -q tests
```
