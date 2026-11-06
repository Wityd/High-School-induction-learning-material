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


# DBE Grade 11 P1 November 2018, Question 11, checked against the marking guidelines.
Q11 = "dbe_p1_2018_nov_gr11.11"


def test_q11_answers_follow_from_the_question(cat):
    from math import cos, radians

    q2 = next(i for i in cat["numeric_map"] if i["item_id"] == Q11 + ".2")
    g = q2["given"]
    dphi = -g["emf"] * g["delta_t"] / g["N"]  # emf = -N dPhi/dt
    assert math.isclose(dphi, q2["correct_value"])

    q3 = next(i for i in cat["numeric_map"] if i["item_id"] == Q11 + ".3")
    g = q3["given"]
    area = g["side_m"] ** 2
    b = g["delta_phi"] / (area * (cos(radians(g["theta_f_deg"])) - cos(radians(g["theta_i_deg"]))))
    assert math.isclose(b, q3["correct_value"], rel_tol=0.01)


@pytest.mark.parametrize("value, expected", [
    (-0.0014, "correct"), (0.0014, "correct"),          # sign shows direction; size is what is compared
    (0.56, "EMI-08"), (0.21875, "EMI-09"), (224, "EMI-09"),
])
def test_q11_2_diagnosis(cat, value, expected):
    result = mc.diagnose_numeric(cat, Q11 + ".2", value)
    if expected == "correct":
        assert result["status"] == "correct"
    else:
        assert expected in [m["id"] for m in result["misconceptions"]]


@pytest.mark.parametrize("value, expected", [
    (5.31, "correct"), (2.20, "EMI-15"), (0.1593, "EMI-13"), (0.0531, "EMI-13"), (0.000531, "EMI-13"),
])
def test_q11_3_diagnosis(cat, value, expected):
    result = mc.diagnose_numeric(cat, Q11 + ".3", value)
    if expected == "correct":
        assert result["status"] == "correct"
    else:
        assert expected in [m["id"] for m in result["misconceptions"]]


def test_q11_3_fingerprints_follow_from_the_errors(cat):
    """Each wrong value is what the named mistake really produces."""
    from math import cos, radians

    dphi, side, k = 0.0014, 0.03, 1 - cos(radians(45))
    expected = {
        "ΔΦ = BA cos 45°": dphi / (side**2 * cos(radians(45))),
        "ΔΦ = BA (angle ignored)": dphi / side**2,
        "side not squared": dphi / (side * k),
        "0,09 m²": dphi / (0.09 * k),
        "not converted": dphi / (9 * k),
    }
    fps = next(i for i in cat["numeric_map"] if i["item_id"] == Q11 + ".3")["fingerprints"]
    for phrase, value in expected.items():
        fp = next(f for f in fps if phrase in f["working"])
        assert math.isclose(fp["value"], value, rel_tol=0.01), phrase


def test_q11_word_answers(cat):
    assert mc.diagnose_choice(cat, Q11 + ".4", "increase") == []
    assert [m["id"] for m in mc.diagnose_choice(cat, Q11 + ".4", "stay the same")] == ["EMI-06"]
    assert [m["id"] for m in mc.diagnose_choice(cat, Q11 + ".6", "south")] == ["EMI-04"]
    assert mc.diagnose_choice(cat, Q11 + ".7", "from a to b") == []


def test_verified_links_have_memo_answers(cat):
    for row in mc.load_paper_links(cat):
        if row["status"] == "verified":
            assert row["memo_answer"], row["q_id"]


# Positive marking: 11.3 is marked using the learner's own 11.2 answer.
from math import cos, radians

from pipeline.marking import feedback, mark_numeric

K = (0.03 ** 2) * (1 - cos(radians(45)))  # A(cos 0 - cos 45)


def mark_q11(cat, dphi, b):
    r2 = mark_numeric(cat, Q11 + ".2", dphi, max_marks=3)
    r3 = mark_numeric(cat, Q11 + ".3", b, max_marks=4, source_value=dphi)
    return r2, r3


def test_all_correct(cat):
    r2, r3 = mark_q11(cat, -0.0014, 5.31)
    assert (r2["status"], r3["status"]) == ("correct", "correct")
    assert r2["marks_min"] + r3["marks_min"] == 7


def test_wrong_11_2_carried_forward_correctly(cat):
    """Forgot N in 11.2 (0,56 Wb), then used 0,56 correctly in 11.3."""
    r2, r3 = mark_q11(cat, 0.56, 0.56 / K)
    assert [m["id"] for m in r2["misconceptions"]] == ["EMI-08"]
    assert r3["status"] == "carried_forward"
    assert r3["marks_min"] == r3["max"] == 4
    assert r3["misconceptions"] == []  # the 11.2 mistake is not counted twice


def test_new_mistake_in_11_3_found_after_carrying_forward(cat):
    """Wrong 11.2, and in 11.3 also forgot to square the side (EMI-13)."""
    dphi = 0.56
    r2, r3 = mark_q11(cat, dphi, dphi / (0.03 * (1 - cos(radians(45)))))
    assert r3["status"] == "known_error"
    assert "EMI-13" in [m["id"] for m in r3["misconceptions"]]


def test_correct_11_2_but_final_flux_used_in_11_3(cat):
    r2, r3 = mark_q11(cat, -0.0014, 2.20)
    assert r2["status"] == "correct"
    assert "EMI-15" in [m["id"] for m in r3["misconceptions"]]
    assert (r3["marks_min"], r3["marks_max"], r3["needs_working"]) == (0, 3, True)


def test_feedback_reads_like_a_teacher(cat):
    text = feedback(list(mark_q11(cat, 0.56, 0.56 / K)))
    assert "11.2:" in text and "EMI-08" in text
    assert "11.3: 4/4" in text and "positive marking" in text
