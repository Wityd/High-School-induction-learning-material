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

## Run 2: Llama 3.1 8B, ticks by number

Files: `llama3.1-8b_v2_report.json`, `llama3.1-8b_v2_printed_output.txt`. The full per-row CSV was not saved; these files are copied from the printed Colab output.

| Measure | Run 1 | Run 2 |
|---|---|---|
| Exact misconception match | 8 of 23 | 8 of 23 |
| Cohen's kappa | 0.19 | 0.19 |
| Marks exactly right | 11 of 23 | none given |
| Sent to the teacher | 23 of 23 | 23 of 23 |

**What happened.** Llama returned an **empty list of ticks on every item**.
Under JSON mode the model must follow the schema, and the schema allowed an
empty list, so the small model took the shortest valid answer. The new check
did its job: instead of impossible marks (2 out of 1 in Run 1), no marks were
given and every item went to the teacher.

Misconception labels were almost unchanged (EMI-13 and EMI-16 slightly better),
as expected, since the marking instructions were not changed.

**Change made after this run.** Each memo tick is now its own required field
(`tick_1`, `tick_2`, ...), so under JSON mode the model has to give a decision
for every tick and cannot add extra ones.

## Run 3: Llama 3.1 8B, required tick fields

Files: `llama3.1-8b_v3_report.json`, `llama3.1-8b_v3_printed_output.txt`. The full per-row CSV was not saved; these files are copied from the printed Colab output.

| Measure | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Exact misconception match | 8 of 23 | 8 of 23 | **11 of 23** |
| Cohen's kappa | 0.19 | 0.19 | **0.37** |
| Marks exactly right | 11 of 23 | none given | **15 of 23** |
| Sent to the teacher | 23 | 23 | **5** |

**What improved.** No format errors. All four definitions (11.1) and both
correct 11.2 calculations were fully right.

**What Run 3 revealed.** With the format fixed, far fewer items were flagged,
and that exposed a gap in the safety checks: **12 of 23 cases were wrong but
not sent to the teacher** (silent errors).

- **Generous marks on wrong one-word answers.** DECREASE (11.4_02), SOUTH
  (11.6_02) and FROM B TO A (11.7_01) each got 1 mark, although the rules
  already knew these answers were wrong.
- **False alarms on right one-word answers were only noted.** For example,
  a correct NORTH (11.6_01) labelled EMI-04.
- **Generous calculation marks.** 11.3_02 and 11.3_03 got 4 of 4; the
  teacher gave 2.
- **Still confused:** EMI-08 vs EMI-09 (forgot N vs. rate handled wrongly), and
  EMI-15 was never found.

**Changes made after this run.**

1. For one-word answers, the **rules set the marks**: the right word gets the
   mark, any other word gets none. The LLM's job there is only the reasoning.
2. A right one-word answer with a reported misconception is now **sent to the
   teacher**, not just noted: either the learner got lucky (11.7_03) or the
   LLM raised a false alarm.
3. The report now counts **silent errors**: items that were wrong and not
   sent to the teacher. This is the safety number that matters most.

**Estimate before Run 4** (worked out by hand from the Run 3 output, not a
run): silent errors should fall from 12 to about 5, and the remaining ones
are in 11.3 marks and 11.5 explanations, where no rule can check the model.

A caution: these changes were made after seeing results on the same 23 cases.
They follow a general rule (let rules decide what rules can decide) rather
than fixes for single cases, but new cases are needed to confirm them.

## Run 4: Llama 3.1 8B, rules set the marks on one-word answers

Files: `llama3.1-8b_v4.csv`, `llama3.1-8b_v4_report.json`

| Measure | Run 1 | Run 2 | Run 3 | Run 4 |
|---|---|---|---|---|
| Exact misconception match | 8 of 23 | 8 of 23 | 11 of 23 | 11 of 23 |
| Cohen's kappa | 0.19 | 0.19 | 0.37 | 0.37 |
| Marks exactly right | 11 of 23 | none given | 15 of 23 | **19 of 23** |
| Mean marks difference | 0.74 | none given | 0.43 | **0.26** |
| Sent to the teacher | 23 | 23 | 5 | 9 |
| Silent errors | not counted | not counted | 12 (by hand) | **5** |

**The estimate held.** The hand estimate made before this run (silent errors
from 12 to about 5, all in 11.3 marks and 11.5 explanations) matched exactly:
the 5 silent errors are 11.3_02 and 11.3_03 (4 of 4 given where the teacher
gave 2) and 11.5_01 to 11.5_03 (explanations, which no rule can check).

Misconception labels did not change, as expected: only the marking and
flagging logic changed.

**What is left is the model, not the system.** Llama 3.1 8B still confuses
EMI-08 with EMI-09, never finds EMI-15, and raises false alarms on correct
work. Code checks cannot fix that; a stronger model or a better prompt might.
The 9 items sent to the teacher are the system working as designed.

## Run 5: Qwen 2.5 14B (Ollama, Google Colab T4, temperature 0)

Files: `qwen2.5-14b_v1.csv`, `qwen2.5-14b_v1_report.json`

Same 23 cases, same code and prompt as Llama Run 4. Nothing was changed
between the two runs.

| Measure | Llama 3.1 8B (Run 4) | Qwen 2.5 14B |
|---|---|---|
| Exact misconception match | 11 of 23 | **14 of 23** |
| Cohen's kappa | 0.37 (fair) | **0.65 (substantial)** |
| False alarms on the 11 correct cases | 7 | **3** |
| Marks exactly right | **19 of 23** | 16 of 23 |
| Mean marks difference | **0.26** | 0.48 |
| Sent to the teacher | 9 | 8 |
| Silent errors | 5 | **4** |

**The larger model diagnoses much better.** Kappa nearly doubled, false alarms
on correct work fell from 7 to 3, and it found EMI-15 (11.3_02), which Llama
never found in any run. Much of what was left after Run 4 was the model, not
the system.

**But it marks more harshly.** Llama gave too many marks; Qwen gives too few.
It gave 0 of 4 to a correct carried-forward answer (11.3_04: no positive
marking, and an EMI-15 that is not there; the rules caught this) and 1 where
the teacher gave 2 on 11.3_02 and 11.3_03. All four of its silent errors are
about marks.

**Possible language bias, one case.** The Afrikaans definition (11.1_04) got
0 of 2, while the same answer in English got full marks, although the prompt
says Afrikaans is marked the same. One case proves nothing, but fairness across
languages matters for South African learners. It needs more Afrikaans (and
isiZulu and other) cases before any real use.

**Other errors.** It used EMI-05 ("a coil cannot have poles") for 11.7 answers
it does not fit, and confused EMI-13 with EMI-15 once.

**Caveat.** Qwen is a different model family, not only a larger model, so the
difference is not due to size alone. A pure size comparison would use two
sizes of one family (for example Qwen 2.5 7B and 14B).

## What the five runs show

1. **Format before marking.** Runs 1 to 3 were mostly about getting a small
   model to return the required structure. Constrained JSON with one required
   field per memo tick solved it.
2. **Let rules decide what rules can decide.** Rule-set marks for one-word
   answers cut silent errors from 12 to 5, as estimated before the run.
3. **A larger model diagnoses better, but neither model marks calculations and
   explanations reliably.** This supports the design: the LLM diagnoses, the
   rules mark where they can, and the teacher checks the rest.
4. **Count silent errors.** Agreement numbers alone hide the cases that would
   reach a learner wrong without anyone being told.

These are 23 constructed cases, so the results show what the system can
detect, not how it performs on real learners.
