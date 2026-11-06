# Results

All runs use the 23-case constructed challenge set (`../challenge_set.csv`),
labelled by the teacher against the DBE memo. These cases test whether a model
**can detect** each misconception. They are not real learner data.

## Run 1: Llama 3.1 8B (Ollama, Google Colab T4, temperature 0)

Files: `llama3.1-8b_v1.csv`, `llama3.1-8b_v1_report.json`

| Measure | Result |
|---|---|
| Exact misconception match | 8 of 23 (35%) |
| Cohen's kappa, "has a misconception or not" | 0.19 (slight agreement) |
| Marks exactly right | 11 of 23 (48%) |
| Mean marks difference | 0.74 |
| Sent to the teacher | 23 of 23 |

**What it did well.** All four definitions (11.1) were labelled correctly,
including EMI-16 (Faraday's and Lenz's laws confused). It also found EMI-17,
EMI-04 on the wrong pole and EMI-14 on the wrong current direction.

**Where it failed.**

- **False alarms.** It found a misconception in 9 of the 11 correct cases, for
  example the correct B = 5,31 T working (11.3_01). This is why kappa is low:
  it does not separate correct work from wrong work.
- **Calculations.** It confused EMI-08 with EMI-09 (forgot N vs. rate handled
  wrongly) and EMI-13 with EMI-15 (area vs. initial flux).
- **Format.** It paraphrased the memo tick text instead of copying it, gave a
  1-mark item two ticks (11.5_03 scored 2 out of 1), and once put its
  confidence ("low") in the misconception list.

**The safety checks worked.** The rule-based cross-check independently caught
8 of its errors on calculation and one-word items, and nothing reached a
learner unchecked.

**Changes made after this run** (update to `pipeline/llm_diagnose.py`):

1. Ticks are returned by number (1, 2, 3) instead of by copied text.
2. If the number of ticks is wrong, no marks are given and the item goes to the
   teacher. A 1-mark item can no longer score 2.
3. Confidence is limited to high, medium or low in the schema.

Only the format problems were fixed. The prompt's marking instructions were not
changed, so a second run measures the effect of the format fix alone.

## Run 2

To do: Llama 3.1 8B again with the changes above, then compare with Run 1.
