# Induction Lab

**A Predict–Observe–Explain–Check learning tool for Grade 11 Physical Sciences (CAPS), built to find and fix learner misconceptions, not just deliver content.**

🔗 **Live demo:** https://high-school-induction-learning-mate.vercel.app

> Note on naming: "induction" here means **electromagnetic induction** (Faraday's and Lenz's Laws), not school induction or orientation.

---

## The problem

Most learners don't fail Physical Sciences because they never saw the content. They fail because they walk in with **wrong mental models** that the lesson never confronts. For electromagnetic induction, the classic ones are:

- "No battery means no current can flow."
- "A strong magnetic field inside the coil must induce a large EMF, even if nothing is moving."
- "The induced current helps the magnet along, instead of opposing the change."

Textbooks and slide decks explain the correct idea but rarely expose the wrong one. Teachers in large, under-resourced classrooms rarely have time to diagnose each learner's misconception individually.

## The approach

Induction Lab uses the **Predict–Observe–Explain (POE)** model, which has strong support in science education research for confronting misconceptions:

| Step | What the learner does |
|------|------------------------|
| **Predict** | Commits to a prediction *before* touching the apparatus |
| **Observe** | Drags a magnet through a coil and watches the induced EMF live |
| **Explain** | Sees the same law in words, in symbols and in a picture, with key terms they can rewrite in their own language |
| **Check** | Answers exam-style questions with CAPS-style mark allocations |

**Design principles**

- **Misconception first.** The learner is marked on explaining the gap between prediction and observation, not on being right.
- **Multiple representations.** Words, symbols and graphs for the same law.
- **Home-language support.** Learners restate key terms in the language they think in.
- **Low-data friendly.** Runs offline once loaded. No account, no tracking.
- **CAPS-aligned.** Built for the electromagnetism section of the Grade 11 Physical Sciences curriculum.

---

## Current status (v1)

- [x] Interactive lesson: Predict, Observe, Explain, Check
- [x] Draggable magnet and coil simulation with live EMF and flux readout
- [x] Trial table that compares predictions against observations
- [x] Three-way explanation of Faraday's Law (words, symbols, graph)
- [x] Exam-style questions with marking answers
- [x] Fully client-side, no data collected

## Progress on v2

- [x] Past-paper extraction verified on one paper (Physical Sciences P1, November 2018): 150 marks, every question total matches the printed total
- [x] Mark verification and topic tagging moved from the notebook into tested code in [`pipeline/`](pipeline/)
- [x] First misconception catalogue: 11 electromagnetic induction misconceptions, with every wrong option in the lesson mapped to one ([`misconceptions/electromagnetic_induction.json`](misconceptions/electromagnetic_induction.json))
- [x] Numeric fingerprints: a wrong answer to the EMF calculation (e.g. 0,024 V or 0,135 V) is traced to the step that went wrong
- [ ] Teacher-checked topic tags for the first paper
- [ ] More papers, especially ones with electromagnetism questions
- [ ] Literature references for each misconception

## Roadmap (v2): an LLM-powered misconception engine

v2 turns Induction Lab from a single lesson into a **misconception diagnosis and feedback system** for Physical Sciences and Life Sciences.

### 1. Past-paper pipeline

Collect publicly available past exam papers and memoranda and convert them into structured data.

- Download papers and memos (e.g. NSC and provincial papers) respecting each source's terms of use and `robots.txt`
- Extract text, questions, mark allocations and memo answers from PDFs
- Tag every question by **topic, sub-topic, cognitive level and marks**
- Store as a structured dataset (questions, memo answers, tags)

### 2. Misconception map

- Build a catalogue of known misconceptions per topic, drawn from science-education literature and from wrong answers seen in practice
- Link each wrong answer option and common wrong working to a specific misconception
- Use the tagged past-paper data to see which topics and question types carry the most marks and so matter most

### 3. LLM feedback layer

- Retrieval-augmented generation over the CAPS document, the tagged question bank and the memoranda, so answers stay grounded in the curriculum
- Given a learner's prediction or answer, the model identifies the likely misconception and responds with a targeted explanation and a follow-up question, not just the answer
- Explanations offered in English and, where possible, in learners' home languages
- Guardrails: stay inside the CAPS curriculum, never invent marking rules, and flag low-confidence answers for teacher review

### 4. Evaluation (what makes this credible)

- Compare the model's misconception labels against labels from a human teacher on a held-out set of answers
- Report accuracy, agreement and failure cases openly
- Compare learner performance before and after using the tool in a pilot class

### 5. Teacher dashboard (opt-in, anonymised)

- Class-level view such as: "X% of this class believes a strong static field induces EMF"
- Learners opt in. No names are stored. Designed with POPIA (South Africa's data protection law) in mind

---

## Proposed tech stack (v2)

| Layer | Tools |
|-------|-------|
| Frontend | HTML, CSS and JavaScript (current), later a PWA for offline use |
| Data pipeline | Python, `requests` / `BeautifulSoup`, `pdfplumber`, `pandas` |
| Question bank | JSON / SQLite |
| LLM layer | LLM API with retrieval over CAPS and the tagged questions (embeddings plus a vector store) |
| Evaluation | Python notebooks, scikit-learn metrics, human-labelled test set |
| Dashboard | Lightweight web dashboard on anonymised, opt-in data |

---

## Repository structure

```
induction-lab/
├── index.html            # Lesson (v1)
├── css/                  # Styles
├── js/                   # Simulation and lesson logic
├── data/
│   ├── SCHEMA.md         # Question bank columns  (done)
│   └── papers/           # Raw past papers and memos (planned)
├── pipeline/             # Verification, tagging, misconception lookup  (done)
├── misconceptions/       # Misconception catalogue and mappings  (done)
├── tests/                # pytest tests for the pipeline  (done)
├── evaluation/           # Notebooks and results (planned)
└── README.md
```

---

## Ethics and responsible use

- **Learners first.** No personal data is collected in v1. Any v2 analytics are opt-in and anonymised.
- **Source respect.** Past papers are collected from public sources in line with their terms of use. This project links to and builds on them for education, and does not claim ownership.
- **Human in the loop.** The LLM supports teachers and learners. It does not replace the teacher's judgement, and it is never the final authority on marks.
- **Honest limits.** Model errors and limitations are documented in `evaluation/`.

---

## Contributing

Teachers, developers and learners are welcome to open an issue or pull request. Especially useful: documented misconceptions from your own classroom, and corrections to the physics.

## Author

**Witness Lubisi**, Bachelor of Education student (Physical Sciences, Chemistry and Life Sciences), University of Johannesburg.
Training: Universal AI (MIT), Data Science (ALX).
GitHub: [@Wityd](https://github.com/Wityd)

## License

To be added (MIT is a good default for open educational tools).
