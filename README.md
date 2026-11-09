# Induction Lab

**An AI marker that finds learner misconceptions in Grade 11 Physical Sciences exam answers, built and evaluated by a Physical Sciences teacher.**

So far it covers **one exam question**: Question 11 (electromagnetic induction, 13 marks) of the DBE Grade 11 Physical Sciences Paper 1, November 2018. It marks learners' answers against the official memo, names the specific misconception behind a wrong answer, and sends anything it is unsure about to the teacher. It started as an interactive lesson on electromagnetic induction ([live demo](https://high-school-induction-learning-mate.vercel.app)).

[![Open the demo in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Wityd/High-School-induction-learning-material/blob/main/demo/induction_lab_demo.ipynb) **Try it in your browser:** free, no API key, no GPU, runs in seconds.

> "Induction" here means **electromagnetic induction** (Faraday's and Lenz's Laws), not school orientation.

---

## Results at a glance

Two free open-source models were tested on the same 23 teacher-labelled cases covering all of Question 11 of the DBE Grade 11 Physical Sciences Paper 1 (November 2018), with the same code and prompt.

| | Llama 3.1 8B | Qwen 2.5 14B |
|---|---|---|
| Misconception labels exactly right | 11 of 23 | **14 of 23** |
| Agreement with the teacher (Cohen's kappa) | 0.37 (fair) | **0.65 (substantial)** |
| False alarms on the 11 correct answers | 7 | **3** |
| Marks exactly right | **19 of 23** | 16 of 23 |
| Wrong and not flagged (silent errors) | 5 | **4** |

**What this shows**

1. **Fix the output format before judging the marking.** The first three Llama runs were mostly about getting a small model to return the required structure. Constrained JSON with one required field per memo tick solved it.
2. **Let rules decide what rules can decide.** Having the rules, not the model, give marks for one-word answers cut silent errors from 12 to 5, as estimated before the run.
3. **A larger model diagnoses better, but neither marks calculations and explanations reliably.** So the model diagnoses, the rules mark where they can, and the teacher checks the rest.
4. **Count silent errors.** Agreement alone hides the answers that would reach a learner wrong with nobody told.

These are **constructed cases**, written to contain known misconceptions, so they show what the system can detect, not how it performs on real learners. All runs, including the failures, are in [`evaluation/results/`](evaluation/results/).

### Example teacher report

A learner forgets the number of turns in 11.2, then uses that wrong answer correctly in 11.3. This is the system's real output:

```
11.2: 0-2/3 (method marks need the learner's working). Likely: Leaves out the number of turns (EMI-08). Teacher tip: Ask the learner to say in words what each symbol stands for before substituting.
11.3: 4/4. Earlier answer was wrong but used correctly here (positive marking).
```

The memo says "positive marking from 11.2", so the same mistake is not punished twice.

---

## How it works

```
learner's working ──► rule engine ─────────────┐
        │             (memo answers, number     │
        │              fingerprints, positive   ├──► cross-check ──► marks + misconception
        │              marking)                 │         │              + teacher tip
        └──────────► LLM (Claude, Llama, Qwen) ─┘         │
                      reads the working, names            └──► unsure or conflicting?
                      misconceptions from the                   sent to the teacher
                      catalogue only
```

- **Misconception catalogue** ([`misconceptions/electromagnetic_induction.json`](misconceptions/electromagnetic_induction.json)): 17 misconceptions for electromagnetic induction, each with what learners say, the correct idea, why learners think it and a teaching fix.
- **Rule engine** ([`pipeline/marking.py`](pipeline/marking.py)): memo answers, positive marking, and "number fingerprints" that trace a wrong answer to the step that went wrong (B = 2,20 T in 11.3 means the starting flux was ignored).
- **LLM layer** ([`pipeline/llm_diagnose.py`](pipeline/llm_diagnose.py)): reads the working, decides which memo ticks it earns and names misconceptions, quoting the working as evidence.
- **Evaluation** ([`pipeline/evaluate.py`](pipeline/evaluate.py)): compares the model with the teacher.

## LLM engineering in this project

| Skill | Where |
|---|---|
| **Structured outputs and constrained decoding**: the model must fill a schema with one required field per memo tick | `answer_schema` in [`llm_diagnose.py`](pipeline/llm_diagnose.py) |
| **Grounding**: misconception ids only from the catalogue; invented ids are removed and flagged | `check` in [`llm_diagnose.py`](pipeline/llm_diagnose.py) |
| **Guardrails**: memo tick count enforced, "2 or 0" rule, refusals and invalid JSON sent to the teacher | [`llm_diagnose.py`](pipeline/llm_diagnose.py) |
| **Hybrid AI and rules**: rules set marks where they can; the LLM is cross-checked against them | `rule_check` in [`llm_diagnose.py`](pipeline/llm_diagnose.py) |
| **Model-agnostic design**: Claude (Anthropic API) or open-source models through Ollama, behind the same checks | `ClaudeBackend`, `OllamaBackend` |
| **Evaluation**: Cohen's kappa, precision and recall per label, marks agreement, silent errors | [`evaluate.py`](pipeline/evaluate.py), [`evaluation/`](evaluation/) |
| **Iterating from evidence**: each run's failures led to one targeted fix, and the effect was predicted before the next run | [`evaluation/results/README.md`](evaluation/results/README.md) |
| **Testing LLM code without an API**: 62 tests with fake clients, free and repeatable | [`tests/`](tests/) |
| **Domain expertise**: the misconception catalogue and every label were written or checked by a Physical Sciences teacher against the DBE memo | [`misconceptions/`](misconceptions/), [`evaluation/challenge_set.csv`](evaluation/challenge_set.csv) |

---

## Run it yourself

**Quickest:** open the [demo notebook](https://colab.research.google.com/github/Wityd/High-School-induction-learning-material/blob/main/demo/induction_lab_demo.ipynb) in Colab and press Run all. It marks example learners, lets you try your own answers and shows the model results, with no API key or GPU.

The tests need no API key and cost nothing:

```bash
pip install -r requirements.txt
python -m pytest -q tests
```

To run a model on the challenge set for free in Google Colab (Llama or Qwen through Ollama), follow [`evaluation/README.md`](evaluation/README.md).

---

## The lesson behind it (v1)

Most learners don't fail Physical Sciences because they never saw the content. They fail because they walk in with **wrong mental models** that the lesson never confronts, such as "no battery means no current can flow" or "a strong magnetic field must induce a large emf, even if nothing is moving".

The lesson uses the **Predict–Observe–Explain** model: the learner commits to a prediction, drags a magnet through a coil and watches the induced emf live, sees Faraday's Law in words, symbols and a graph, and answers exam-style questions. It runs offline once loaded, collects no data, and lets learners restate key terms in their home language.

---

## Repository structure

```
├── index.html            # The interactive lesson (v1)
├── demo/                 # Free Colab demo notebook
├── misconceptions/       # Misconception catalogue and past-paper links
├── pipeline/             # Rule engine, LLM layer, evaluation, past-paper tools
├── evaluation/           # Challenge set, templates and all results
├── data/                 # Question bank schema and tagged past-paper data
├── tests/                # 62 pytest tests
└── requirements.txt
```

---

## Limitations

- **Constructed cases, not learner data.** The 23 cases show what the system can detect. Real, anonymised learner scripts are needed to measure how it performs in a classroom.
- **Small and narrow.** One question (Question 11) from one paper and one topic, one run per model. The rest of the paper is tagged by topic but not marked.
- **Changes made after seeing results.** The fixes follow general rules rather than single cases, but new cases are needed to confirm them.
- **Possible language bias.** Qwen marked one Afrikaans answer down while the same answer in English got full marks. One case proves nothing, but this needs testing in Afrikaans, isiZulu and other languages before any real use.
- **Draft misconceptions.** EMI-16 and EMI-17 came from the constructed cases and still need classroom or literature evidence.

## Roadmap

- A pilot with real, anonymised learner scripts (with consent, in line with POPIA)
- Fairness testing across South African languages
- More DBE papers, especially with electromagnetism questions
- Literature references for every misconception
- Retrieval over the CAPS document and memoranda
- A teacher dashboard: "X% of this class believes a strong static field induces emf"

## Ethics and responsible use

- **Learners first.** No personal data is collected. Any learner data must be anonymised and used with consent, in line with POPIA. With the Claude backend, working is sent to the Anthropic API; with Ollama it stays on the machine that runs the model (in Colab, a Google machine).
- **Human in the loop.** The system supports the teacher. It never has the final word on marks, and anything uncertain goes to the teacher.
- **Source respect.** DBE papers and memoranda are public and credited. The repository stores labels and tags for the paper, plus the text of Question 11 and its memo ticks, which the marker needs.
- **Honest limits.** Every run is published, failures included.

---

<details>
<summary><b>Full progress log</b></summary>

### The lesson (v1)

- [x] Interactive lesson: Predict, Observe, Explain, Check
- [x] Draggable magnet and coil simulation with live EMF and flux readout
- [x] Trial table that compares predictions against observations
- [x] Three-way explanation of Faraday's Law (words, symbols, graph)
- [x] Exam-style questions with marking answers
- [x] Fully client-side, no data collected

### The engine (v2)

- [x] Past-paper extraction verified on one paper (Physical Sciences P1, November 2018): 150 marks, every question total matches the printed total
- [x] Mark verification and topic tagging moved from the notebook into tested code in [`pipeline/`](pipeline/)
- [x] First misconception catalogue: 17 electromagnetic induction misconceptions, with every wrong option in the lesson mapped to one ([`misconceptions/electromagnetic_induction.json`](misconceptions/electromagnetic_induction.json))
- [x] Numeric fingerprints: a wrong answer to the EMF calculation (e.g. 0,024 V or 0,135 V) is traced to the step that went wrong
- [x] First paper fully tagged and teacher-checked: 150 of 150 marks (Newton's laws 43, Waves and optics 32, Electrostatics 24, Electric circuits 16, Electromagnetism 15, Vectors 12, Gravitation 8)
- [x] Tagger improved from the teacher check (line-break matching, fewer misleading keywords), with the corrected items kept as tests
- [x] Past-paper questions linked to misconceptions: Question 11 (13 marks, electromagnetism) mapped item by item in [`misconceptions/paper_links.csv`](misconceptions/paper_links.csv)
- [x] Question 11 verified against the DBE marking guidelines: answers, tick allocation and positive marking recorded; wrong answers to 11.2 and 11.3 traced to specific misconceptions (e.g. B = 2,20 T means the initial flux was ignored)
- [x] Positive marking in the engine ([`pipeline/marking.py`](pipeline/marking.py)): 11.3 is marked using the learner's own 11.2 answer, so one mistake is not punished twice, and a new mistake in 11.3 is still found. Method marks for wrong answers are reported as a range until the learner's working is read
- [x] LLM layer built ([`pipeline/llm_diagnose.py`](pipeline/llm_diagnose.py)): Claude reads a learner's written working, decides which memo ticks it earns and names misconceptions from the catalogue only, quoting the working as evidence. Code then checks the result: invented ids are removed, the tick list must match the memo, and any disagreement with the final-answer rules goes to the teacher
- [x] Evaluation harness ([`pipeline/evaluate.py`](pipeline/evaluate.py), [`evaluation/`](evaluation/)): agreement with teacher labels, Cohen's kappa, precision and recall per misconception, marks agreement
- [x] Constructed challenge set ([`evaluation/challenge_set.csv`](evaluation/challenge_set.csv)): 23 teacher-checked cases covering all of Question 11, including two new misconceptions found while building it (EMI-16, EMI-17). Constructed, not learner data
- [x] LLM layer extended to the text items (definitions, one-word answers, explanations: 11.1, 11.4 to 11.7), so all of Question 11 can be marked. It applies the memo's "2 or 0" rule, gives explanations the learner's earlier answer as context, and notes a right answer reached through wrong reasoning
- [x] Model is swappable: Claude (Anthropic API) or an open-source model such as Llama 3.1 8B (Ollama, free), behind the same checks
- [x] First real run: Llama 3.1 8B matched 8 of 23 misconception labels (kappa 0.19), with many false alarms on correct work. The rule-based cross-check caught 8 of its errors. Format problems found in the run were fixed. Details: [`evaluation/results/`](evaluation/results/)
- [x] Second run: Llama returned no ticks at all under JSON mode; the checks gave no marks instead of wrong ones. Fixed by making every memo tick a required field
- [x] Third run: 11 of 23 labels right (kappa 0.37), marks right on 15 of 23, but 12 errors were not flagged. Fixed by letting the rules set marks wherever the answer is a fixed word, and by counting silent errors
- [x] Fourth run: marks right on 19 of 23 and silent errors down to 5, as estimated beforehand. The remaining errors are the model's own (labels unchanged at 11 of 23)
- [x] Same 23 cases on Qwen 2.5 14B, with no changes: kappa 0.65 (Llama 0.37), false alarms on correct work down from 7 to 3, but harsher marks. One Afrikaans answer was marked down, a possible language bias to test further
- [x] Paper extraction moved from Colab into tested code ([`pipeline/extract.py`](pipeline/extract.py)): any DBE paper PDF becomes a checked list of questions and marks with one command. A mark lost in extraction is worked out from the printed question total and labelled for the teacher to check
- [ ] Run the evaluation on real, anonymised learner scripts and publish the results, failures included
- [ ] More papers, especially ones with electromagnetism questions
- [ ] Literature references for each misconception

</details>

## Author

**Witness Lubisi**, Bachelor of Education student (Physical Sciences, Chemistry and Life Sciences), University of Johannesburg.
Training: Universal AI (MIT), Data Science (ALX).
GitHub: [@Wityd](https://github.com/Wityd)

## License

[MIT](LICENSE) for the author's own work (code, misconception catalogue, challenge set and documentation). DBE exam and memo material included for marking remains the property of the Department of Basic Education; see [LICENSE](LICENSE).
