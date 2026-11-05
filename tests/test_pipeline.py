import math

import pandas as pd
import pytest

from pipeline import misconceptions as mc
from pipeline.topics import apply_overrides, tag_questions, tag_text
from pipeline.verify import check_totals, missing_marks, parent_questions

BODY = """QUESTION 1
1.1 Define a vector. (2)
1.2 Calculate the resultant. (3)
[5]
QUESTION 2
2.1 Calculate: 
2.1.1 the EMF (2)
2.1.2 the current (2)
2.2 State Lenz's law.
[6]
"""

DF = pd.DataFrame({
    "q_id": ["1.1", "1.2", "2.1", "2.1.1", "2.1.2", "2.2"],
    "question": [1, 1, 2, 2, 2, 2],
    "marks": [2, 3, None, 2, 2, None],
    "text": ["Define a vector.", "Calculate the resultant of the two vectors.",
             "A coil is in a magnetic field. Calculate:",
             "the induced emf", "the current in the circuit", "State Lenz's law."],
})


def test_check_totals_flags_lost_marks():
    check = check_totals(DF, BODY)
    assert check.set_index("question")["match"].to_dict() == {1: True, 2: False}


def test_parent_vs_missing():
    assert parent_questions(DF)["q_id"].tolist() == ["2.1"]
    assert missing_marks(DF)["q_id"].tolist() == ["2.2"]


def test_whole_word_matching():
    assert tag_text("The capacitor will discharge")["hits"] == 0
    assert tag_text("The gun recoils")["topic"] == "Unknown"


def test_tagging_and_overrides():
    tags = tag_questions(DF)
    assert tags.loc[1, "topic"] == "Vectors"
    assert tags.loc[2, "topic"] == "Electromagnetism"
    fixed = apply_overrides(tags, {1: "Newton's laws"})
    assert fixed.loc[1, "source"] == "teacher" and fixed.loc[2, "source"] == "keywords"


@pytest.fixture(scope="module")
def cat():
    return mc.load()


def test_catalogue_is_consistent(cat):
    assert len(cat["misconceptions"]) >= 10


def test_every_wrong_option_is_mapped(cat):
    for row in cat["item_map"]:
        assert row["correct"] or row["misconceptions"], row


def test_diagnose_choice(cat):
    assert [m["id"] for m in mc.diagnose_choice(cat, "lesson.predict1", "a")] == ["EMI-01"]
    assert mc.diagnose_choice(cat, "lesson.predict2", "C") == []


def test_numeric_fingerprints_match_the_physics(cat):
    item = cat["numeric_map"][0]
    N, dphi, dt = (item["given"][k] for k in ("N", "delta_phi", "delta_t"))
    assert math.isclose(item["correct_value"], N * dphi / dt)
    expected = {"EMI-08": dphi / dt, "EMI-09": N * dphi * dt}
    for mid, value in expected.items():
        result = mc.diagnose_numeric(cat, "lesson.check3", value)
        assert result["status"] == "known_error"
        assert mid in [m["id"] for m in result["misconceptions"]]
    assert mc.diagnose_numeric(cat, "lesson.check3", 6.0)["status"] == "correct"
    assert mc.diagnose_numeric(cat, "lesson.check3", 42)["status"] == "unknown"


def test_text_rule(cat):
    good = "The EMF is proportional to the rate of change of flux linkage."
    bad = "The EMF depends on the magnetic flux."
    assert mc.diagnose_text(cat, "lesson.check1", good) == []
    assert [m["id"] for m in mc.diagnose_text(cat, "lesson.check1", bad)] == ["EMI-02"]


def test_validate_rejects_unknown_ids(cat):
    broken = {**cat, "item_map": cat["item_map"] + [
        {"item_id": "x", "option": "A", "correct": False, "misconceptions": ["EMI-99"]}]}
    with pytest.raises(ValueError):
        mc.validate(broken)


# Real items from the November 2018 Paper 1, with the topic the teacher assigned.
# The v0.1 tagger got 1.4, 1.5 and 1.6 wrong; these tests stop that coming back.
TEACHER_CHECKED = {
    "1.4": ("1.4 A man in a lift is moving upwards at a CONSTANT SPEED. The weight of the\n"
            "man is W. According to Newton's Third Law, the reaction force of the\n"
            "weight W is the force of ... A the floor on the man. B Earth on the man.\n"
            "C the man on the floor. D the man on Earth. (2)", "Newton's laws"),
    "1.5": ("1.5 The optical density of a medium ... A will be high if the refraction of light\n"
            "is less. B is a measure of the refracting power of the medium. C is less when\n"
            "light bends towards the normal when entering the medium. D will be high if light\n"
            "moves faster through the medium. (2)", "Waves and optics"),
    "1.6": ("1.6 In which ONE of the graphs below will the gradient represent the refractive\n"
            "index of a material when light passes from the air through the material? (2)",
            "Waves and optics"),
    "5": ("5.1 Draw a free-body diagram of ALL the forces acting on the crate while it moves\n"
          "from B to C. (3) 5.2 Calculate the magnitude of the acceleration of the crate while\n"
          "it moves from A to B. (4) 5.3 Write down the direction of the acceleration of the\n"
          "crate while it slows down from B to C. Write only UP THE SLOPE or DOWN THE SLOPE. (1)\n"
          "5.4 The magnitude of the net acceleration from B to C is 1,2 m·s-2. Calculate the\n"
          "magnitude of the frictional force acting on the crate. (4)", "Newton's laws"),
}


@pytest.mark.parametrize("q_id", TEACHER_CHECKED)
def test_matches_teacher_tags(q_id):
    text, topic = TEACHER_CHECKED[q_id]
    assert tag_text(text)["topic"] == topic


def test_keywords_match_across_line_breaks():
    assert tag_text("the refractive\nindex of glass")["topic"] == "Waves and optics"


def test_paper_links_use_known_ids(cat):
    rows = mc.load_paper_links(cat)
    q11 = [r for r in rows if r["q_id"].startswith("11.")]
    assert sum(int(r["marks"]) for r in q11) == 13  # matches the printed [13]
    assert all(r["misconception_ids"] for r in rows)
