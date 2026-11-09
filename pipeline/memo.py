"""Read a DBE marking guideline (memo) PDF and line it up with the question paper.

What pdfplumber gives for the November 2018 Paper 1 memo (checked in Colab):

* The tick is the Wingdings character U+F0FC, which most screens show as blank.
  It appears 222 times for a 150-mark paper, because answers with OPTION 1 and
  OPTION 2 repeat their ticks.
* Each item ends with its marks, e.g. "(3)", and each question with "[13]".
* Notes such as "POSITIVE MARKING FROM QUESTION 12.1" and "[2 or 0]" are kept
  as plain text.
* Formulas come out scrambled (fractions split over lines), so the memo
  answers themselves are not parsed here. Drafting tick descriptions is left
  to an LLM, with the teacher checking every draft.

Command line:
    python -m pipeline.memo memo.pdf paper.pdf --paper-id physci_p1_2018_nov_gr11
"""
import re

import pandas as pd

from pipeline.extract import paper_body, read_pdf, split_questions

TICK = ""  # Wingdings tick as read by pdfplumber
# Other tick characters seen in some PDFs; counted too.
TICK_CHARS = (TICK, "✓", "✔")

MEMO_HEADERS = [
    r"^Physical Sciences P\d",
    r"^Copyright reserved",
    r"^CAPS/KABV",
]

FIRST_QUESTION = re.compile(r"^QUESTION 1\b", re.M)
POSITIVE_MARKING = re.compile(r"POSITIVE MARKING FROM QUESTION ([\d.]+)", re.I)
# The memo is bilingual: "[2 or/of 0]" (found on the real 2018 memo).
ALL_OR_NOTHING = re.compile(r"\[\s*\d+\s*or(?:\s*/\s*of)?\s*0\s*\]", re.I)
# Alternative answers: "OPTION 1 ... OPTION 2", answers joined by "OR/OF", or a
# line with only "OR" or "OF" (all seen on the real 2018 memo).
ALTERNATIVES = re.compile(r"OPTION\s*2|\bOR\s*/\s*OF\b|^\s*(?:OR|OF)\s*$", re.M)


def memo_items(full_text: str, paper_id: str) -> pd.DataFrame:
    """One row per memo item: marks, ticks, options, positive marking, 'n or 0'."""
    start = FIRST_QUESTION.search(full_text)
    body, _ = paper_body(full_text[start.start():] if start else full_text)
    df = split_questions(body, paper_id).drop(columns=["marks_source", "stem"])
    df["marks"] = df["marks"].astype("Int64")
    df["ticks"] = df["text"].apply(lambda t: sum(t.count(c) for c in TICK_CHARS))
    df["has_options"] = df["text"].str.contains(ALTERNATIVES)
    df["positive_marking_from"] = df["text"].apply(
        lambda t: (POSITIVE_MARKING.search(t) or [None, ""])[1])
    df["all_or_nothing"] = df["text"].str.contains(ALL_OR_NOTHING)
    df["tick_status"] = df.apply(tick_status, axis=1)
    return df


def tick_status(row) -> str:
    """Do the ticks agree with the marks? Options repeat their ticks."""
    if pd.isna(row["marks"]):
        return "parent"
    if row["ticks"] == row["marks"]:
        return "ok"
    if row["ticks"] == 0:
        return "check"   # e.g. a diagram whose ticks are drawn, not typed (5.1 in 2018)
    if row["has_options"] and row["ticks"] > row["marks"]:
        # Alternatives repeat ticks, sometimes after a shared first tick:
        # 5.2 in 2018 has 1 shared + 3 + 3 = 7 ticks for 4 marks.
        return "ok (alternative answers)"
    return "check"   # e.g. a diagram with criteria plus ticks on the drawing (7.4)


def match_paper(memo: pd.DataFrame, paper: pd.DataFrame) -> pd.DataFrame:
    """Line memo items up with paper questions and compare their marks."""
    m = paper[["q_id", "question", "marks"]].merge(
        memo[["q_id", "marks", "ticks", "tick_status", "has_options",
              "positive_marking_from", "all_or_nothing", "text"]],
        on="q_id", how="outer", suffixes=("_paper", "_memo"), indicator=True)
    m["question"] = m["q_id"].str.split(".").str[0].astype(int)
    m["ticks"] = m["ticks"].astype("Int64")
    m["in"] = m["_merge"].map({"both": "both", "left_only": "paper only", "right_only": "memo only"})
    m["marks_agree"] = (m["marks_paper"].astype("Int64") == m["marks_memo"].astype("Int64")).fillna(
        m["marks_paper"].isna() & m["marks_memo"].isna())
    order = m["q_id"].apply(lambda q: [int(x) for x in q.split(".")])
    return m.drop(columns="_merge").iloc[order.argsort()].reset_index(drop=True)


def visible(text: str) -> str:
    """Show the hidden Wingdings ticks as ✓, for a teacher reading memo text."""
    return text.replace(TICK, "✓")


def read_memo(pdf_path: str, paper_id: str) -> pd.DataFrame:
    return memo_items(read_pdf(pdf_path, start_page=0, header_patterns=MEMO_HEADERS), paper_id)


def summary(matched: pd.DataFrame) -> str:
    """A short report a teacher can read before trusting the memo."""
    lines = [f"{(matched['in'] == 'both').sum()} items in both the paper and the memo"]
    for where in ("paper only", "memo only"):
        ids = matched.loc[matched["in"] == where, "q_id"].tolist()
        if ids:
            lines.append(f"Only in the {where.split()[0]}: {ids}")
    bad = matched.loc[(matched["in"] == "both") & ~matched["marks_agree"], "q_id"].tolist()
    lines.append("Marks agree for every item" if not bad else f"Marks differ for: {bad}")
    lines.append(f"Ticks counted: {int(matched['ticks'].fillna(0).sum())}")
    check = matched.loc[matched["tick_status"] == "check", "q_id"].tolist()
    if check:
        lines.append(f"Tick count does not match the marks (check these): {check}")
    pm = matched.loc[matched["positive_marking_from"].fillna("") != "", ["q_id", "positive_marking_from"]]
    if len(pm):
        lines.append("Positive marking: " + ", ".join(f"{a} from {b}" for a, b in pm.values))
    aon = matched.loc[matched["all_or_nothing"].eq(True), "q_id"].tolist()
    if aon:
        lines.append(f"All or nothing ('2 or 0'): {aon}")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    from pipeline.extract import extract_paper

    ap = argparse.ArgumentParser(description="Read a DBE memo and line it up with its paper.")
    ap.add_argument("memo_pdf")
    ap.add_argument("paper_pdf")
    ap.add_argument("--paper-id", required=True)
    ap.add_argument("--out", help="CSV to write (without the memo text)")
    a = ap.parse_args()

    paper, _, _ = extract_paper(a.paper_pdf, a.paper_id)
    matched = match_paper(read_memo(a.memo_pdf, a.paper_id), paper)
    print(summary(matched))
    if a.out:
        matched.drop(columns="text").to_csv(a.out, index=False)
        print(f"\nSaved {a.out}")
