"""Check that extracted question marks match the totals printed on the paper.

NSC-style papers print each main question's total in square brackets on its own
line, e.g. ``[14]``. If the marks we extracted per question add up to those
printed totals, the extraction is trustworthy.
"""
import re

import pandas as pd

STATED_TOTAL = re.compile(r"^\[(\d+)\]\s*$", re.M)


def stated_totals(body: str) -> pd.Series:
    """Return the printed ``[n]`` totals, indexed by question number (1, 2, ...)."""
    totals = [int(x) for x in STATED_TOTAL.findall(body)]
    return pd.Series(totals, index=range(1, len(totals) + 1), dtype="int64")


def check_totals(df: pd.DataFrame, body: str) -> pd.DataFrame:
    """Compare extracted marks per main question with the printed totals.

    ``df`` needs a ``question`` column (main question number as int) and a
    ``marks`` column. Parent questions such as "2.2 Calculate the:" have NaN
    marks, which ``sum`` skips, so they do not distort the totals.
    """
    check = df.groupby("question")["marks"].sum().reset_index(name="extracted")
    check["stated"] = check["question"].map(stated_totals(body))
    check["match"] = check["extracted"] == check["stated"]
    return check


def parent_questions(df: pd.DataFrame) -> pd.DataFrame:
    """Rows with no marks that have sub-questions (e.g. 10.2 with 10.2.1, 10.2.2).

    Rows with no marks and *no* sub-questions are returned separately by
    :func:`missing_marks`, because those are probably extraction errors.
    """
    no_marks = df[df["marks"].isna()]
    has_children = no_marks["q_id"].apply(
        lambda q: df["q_id"].str.startswith(q + ".").any()
    )
    return no_marks[has_children]


def missing_marks(df: pd.DataFrame) -> pd.DataFrame:
    """Rows with no marks and no sub-questions: likely lost during extraction."""
    no_marks = df[df["marks"].isna()]
    return no_marks.drop(parent_questions(df).index)
