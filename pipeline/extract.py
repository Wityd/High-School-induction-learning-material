"""Turn a DBE question paper PDF into a checked list of questions with marks.

Moved from the Colab notebook that extracted the November 2018 Paper 1
(64 rows, 150 marks, every question total matching the printed total).

Steps:

1. Read the text of every page (pdfplumber) and remove page headers.
2. Cut the text at "TOTAL: n", so the data sheet after it is ignored.
3. Split it into questions on numbers like 4.2 or 10.2.1, and read the marks
   printed in brackets at the end, e.g. "(3)".
4. Where exactly one sub-question in a main question has no marks, work them
   out from the printed total, e.g. "[20]", and label them "inferred".
   (In the 2018 paper this recovers 1.3, which was fixed by hand before.)
5. Check every main question against its printed total.

Command line:
    python -m pipeline.extract paper.pdf --paper-id physci_p1_2018_nov_gr11
"""
import re

import pandas as pd

from pipeline.verify import check_totals, parent_questions

# Lines to drop from every page. Add patterns here for other papers' headers.
HEADER_PATTERNS = [
    r"^Physical Sciences/P\d",
    r"^Copyright reserved",
    r"^CAPS\s*[–-]\s*Grade",
]

QUESTION_NUMBER = re.compile(r"^(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\s+(?=\S)", re.M)
MARKS_AT_END = re.compile(r"\((\d{1,2})\)\s*$", re.M)
PRINTED_TOTAL = re.compile(r"\n\[\d+\]\s*$")
PAPER_TOTAL = re.compile(r"^TOTAL(?:\s*/\s*TOTAAL)?:\s*(\d+)", re.M)  # memos say "TOTAL/TOTAAL: 150"


def clean_page(text: str, header_patterns=HEADER_PATTERNS) -> str:
    """Remove header and footer lines from one page of text."""
    drop = [re.compile(p) for p in header_patterns]
    keep = [line.strip() for line in text.split("\n")]
    return "\n".join(s for s in keep if not any(d.match(s) for d in drop))


def read_pdf(pdf_path: str, start_page: int = 2, header_patterns=HEADER_PATTERNS) -> str:
    """Text of the paper from ``start_page`` (0-based; 2 skips the cover and instructions)."""
    import pdfplumber  # only needed when reading a real PDF

    with pdfplumber.open(pdf_path) as pdf:
        pages = [(p.extract_text() or "") for p in pdf.pages]
    return "\n".join(clean_page(t, header_patterns) for t in pages[start_page:])


def paper_body(full_text: str):
    """Text before "TOTAL: n" (the data sheet follows it), and the paper total."""
    m = PAPER_TOTAL.search(full_text)
    if not m:
        return full_text, None
    return full_text[:m.start()], int(m.group(1))


QUESTION_HEADER = re.compile(r"^QUESTION (\d+)[^\n]*\n", re.M)


def question_stems(body: str) -> dict:
    """The introduction of each main question: the text between "QUESTION n"
    and its first numbered item (e.g. the coil, 400 windings and 7 V of Question 11).
    Without it, sub-questions like "Calculate the change in flux" lose their data."""
    stems = {}
    for h in QUESTION_HEADER.finditer(body):
        first_item = QUESTION_NUMBER.search(body, h.end())
        end = first_item.start() if first_item else len(body)
        stems[int(h.group(1))] = body[h.end():end].strip()
    return stems


def split_questions(body: str, paper_id: str) -> pd.DataFrame:
    """One row per numbered question or sub-question, with its printed marks."""
    matches = list(QUESTION_NUMBER.finditer(body))
    stems = question_stems(body)
    rows = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        block = body[m.start():end].strip()
        block = re.split(r"\nQUESTION \d+", block)[0]      # drop the next question's header
        block = PRINTED_TOTAL.sub("", block).strip()         # drop totals like [14]
        found = MARKS_AT_END.findall(block)
        rows.append({
            "paper_id": paper_id,
            "q_id": m.group(1),
            "question": int(m.group(1).split(".")[0]),
            "marks": int(found[-1]) if found else None,
            "marks_source": "printed" if found else "",
            "text": block,
            "stem": stems.get(int(m.group(1).split(".")[0]), ""),
        })
    return pd.DataFrame(rows)


def infer_missing_marks(df: pd.DataFrame, body: str) -> pd.DataFrame:
    """Fill a sub-question's missing marks from the printed question total.

    Only when exactly one sub-question in the main question is missing its
    marks and is not a parent question (like "10.2 Calculate:"), because only
    then is the gap certain.
    """
    df = df.copy()
    check = check_totals(df, body).set_index("question")
    parents = set(parent_questions(df)["q_id"])
    for q, row in check.iterrows():
        if pd.isna(row["stated"]) or row["match"]:
            continue
        missing = df[(df["question"] == q) & df["marks"].isna() & ~df["q_id"].isin(parents)]
        gap = row["stated"] - row["extracted"]
        if len(missing) == 1 and gap > 0:
            df.loc[missing.index, ["marks", "marks_source"]] = [gap, "inferred"]
    return df


def extract_text(full_text: str, paper_id: str):
    """Run every step on already-extracted text. Returns (questions, check, paper_total)."""
    body, total = paper_body(full_text)
    df = infer_missing_marks(split_questions(body, paper_id), body)
    df["marks"] = df["marks"].astype("Int64")   # whole numbers; empty for parent questions
    return df, check_totals(df, body), total


def extract_paper(pdf_path: str, paper_id: str, start_page: int = 2):
    """Run every step on a PDF. Returns (questions, check, paper_total)."""
    return extract_text(read_pdf(pdf_path, start_page), paper_id)


def summary(df: pd.DataFrame, check: pd.DataFrame, total) -> str:
    """A short report a teacher can read before trusting the extraction."""
    lines = [
        f"{len(df)} questions and sub-questions",
        f"Marks found: {int(df['marks'].sum())}" + (f" (paper total: {total})" if total else ""),
    ]
    inferred = df.loc[df["marks_source"] == "inferred", "q_id"].tolist()
    if inferred:
        lines.append(f"Marks worked out from the printed totals: {inferred} (please check)")
    parents = parent_questions(df)["q_id"].tolist()
    if parents:
        lines.append(f"Parent questions (marks are on their parts): {parents}")
    bad = check.loc[~check["match"], "question"].tolist()
    lines.append("Every question matches its printed total" if not bad
                 else f"These questions do NOT match their printed totals: {bad}")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Extract questions and marks from a DBE paper PDF.")
    ap.add_argument("pdf")
    ap.add_argument("--paper-id", required=True, help="e.g. physci_p1_2018_nov_gr11")
    ap.add_argument("--start-page", type=int, default=2, help="0-based page where questions start")
    ap.add_argument("--out", help="CSV file to write (without the question text)")
    a = ap.parse_args()

    questions, checked, paper_total = extract_paper(a.pdf, a.paper_id, a.start_page)
    print(summary(questions, checked, paper_total))
    print()
    print(checked.to_string(index=False))
    if a.out:
        questions.drop(columns=["text", "stem"]).to_csv(a.out, index=False)
        print(f"\nSaved {a.out}")
