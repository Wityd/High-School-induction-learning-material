# Question bank schema

One row per question or sub-question. Saved as CSV now and as SQLite later.

| Column | Type | Example | Notes |
|--------|------|---------|-------|
| `paper_id` | text | `physci_p1_2018_nov_gr11` | subject, paper, year, sitting, grade |
| `q_id` | text | `10.2.1` | as printed on the paper |
| `question` | int | `10` | main question number |
| `parent_id` | text | `10.2` | empty for top-level items |
| `text` | text | `Calculate the induced emf.` | extracted text |
| `marks` | int or empty | `4` | empty for parent questions |
| `topic` | text | `Electromagnetism` | CAPS topic |
| `topic_source` | text | `keywords` / `teacher` | who assigned the tag |
| `cognitive_level` | int 1–4 | `3` | CAPS exam guidelines levels (recall, comprehension, application/analysis, evaluation/synthesis) |
| `memo_answer` | text | `ε = NΔΦ/Δt = 6,0 V` | from the memorandum |
| `misconception_ids` | text | `EMI-02;EMI-08` | ids from `misconceptions/*.json` that this question can reveal |

## How misconceptions connect

```
past-paper question ──(misconception_ids)──► misconception catalogue ◄──(item_map)── lesson questions
                                                     ▲
                                learner answer ──────┘  diagnose_choice / diagnose_numeric / diagnose_text
```

The catalogue is the single source of truth. Past-paper questions, lesson questions and later the LLM all point at the same ids, so a teacher dashboard can count misconceptions across all of them.
