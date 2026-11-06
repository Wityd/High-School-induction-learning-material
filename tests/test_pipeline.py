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


# LLM layer, tested with a fake client: no API key, no cost, no learner data.
from types import SimpleNamespace

from pipeline.llm_diagnose import Diagnosis, TickDecision, diagnose_working


class FakeClient:
    """Stands in for anthropic.Anthropic(); returns a fixed diagnosis."""

    def __init__(self, diagnosis=None, stop_reason="end_turn"):
        self.calls = []

        def parse(**kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(stop_reason=stop_reason, parsed_output=diagnosis)

        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=parse))


def ticks_for(cat, item_id, earned):
    item = next(i for i in cat["numeric_map"] if i["item_id"] == item_id)
    return [TickDecision(number=n, earned=e, reason="") for n, e in enumerate(earned, start=1)]


WORKING_EMI15 = "ΔΦ = BA cos 45°\n-0,0014 = B (0,03)² cos 45°\nB = 2,20 T"


def test_llm_and_rules_agree(cat):
    d = Diagnosis(misconception_ids=["EMI-15"], evidence="ΔΦ = BA cos 45°",
                  ticks=ticks_for(cat, Q11 + ".3", [False, True, False, False]),
                  confidence="high", feedback_for_teacher="Initial flux ignored.")
    client = FakeClient(d)
    r = diagnose_working(client, cat, Q11 + ".3", WORKING_EMI15, 2.20, earlier_answer=-0.0014)
    assert r["misconception_ids"] == ["EMI-15"] and r["marks"] == 1
    assert r["needs_teacher"] is False
    sent = client.calls[0]
    assert sent["model"] == "claude-opus-5-5" and sent["fallbacks"] == "default"
    assert WORKING_EMI15 in sent["messages"][0]["content"]
    assert "EMI-15" in sent["system"][0]["text"]  # catalogue is in the prompt


def test_invented_id_is_removed_and_flagged(cat):
    d = Diagnosis(misconception_ids=["EMI-15", "EMI-99"], evidence="...",
                  ticks=ticks_for(cat, Q11 + ".3", [False, True, False, False]),
                  confidence="high", feedback_for_teacher="")
    r = diagnose_working(FakeClient(d), cat, Q11 + ".3", WORKING_EMI15, 2.20, -0.0014)
    assert r["misconception_ids"] == ["EMI-15"]
    assert r["needs_teacher"] and "EMI-99" in r["problems"][0]


def test_disagreement_with_rules_goes_to_teacher(cat):
    """The LLM says EMI-13, but 2,20 T is an EMI-15/EMI-12 fingerprint."""
    d = Diagnosis(misconception_ids=["EMI-13"], evidence="...",
                  ticks=ticks_for(cat, Q11 + ".3", [True, True, False, False]),
                  confidence="high", feedback_for_teacher="")
    r = diagnose_working(FakeClient(d), cat, Q11 + ".3", WORKING_EMI15, 2.20, -0.0014)
    assert r["needs_teacher"] and "disagrees" in r["problems"][-1]


def test_wrong_tick_list_and_low_confidence_flagged(cat):
    d = Diagnosis(misconception_ids=[], evidence="no misconception",
                  ticks=[TickDecision(number=7, earned=True, reason="")],
                  confidence="low", feedback_for_teacher="")
    r = diagnose_working(FakeClient(d), cat, Q11 + ".2", "7 = 400 x / 0,08", -0.0014)
    assert r["needs_teacher"] and "expected ticks 1 to 3" in r["problems"][0]
    assert r["marks"] is None


def test_refusal_goes_to_teacher(cat):
    r = diagnose_working(FakeClient(None, "refusal"), cat, Q11 + ".2", "...", -0.0014)
    assert r["needs_teacher"] is True


# Evaluation report, on a tiny hand-made table (not real learner data).
from pipeline.evaluate import cohen_kappa, report


def test_report_numbers():
    rows = [
        {"teacher_ids": "EMI-08", "llm_ids": "EMI-08", "teacher_marks": "1", "llm_marks": "1", "needs_teacher": "False"},
        {"teacher_ids": "", "llm_ids": "", "teacher_marks": "3", "llm_marks": "3", "needs_teacher": "False"},
        {"teacher_ids": "EMI-15", "llm_ids": "EMI-12", "teacher_marks": "1", "llm_marks": "2", "needs_teacher": "True"},
        {"teacher_ids": "", "llm_ids": "EMI-13", "teacher_marks": "4", "llm_marks": "3", "needs_teacher": "True"},
    ]
    r = report(rows)
    assert r["exact_id_agreement"] == 0.5
    assert r["per_id"]["EMI-08"] == {"precision": 1.0, "recall": 1.0, "teacher_count": 1}
    assert r["per_id"]["EMI-15"]["recall"] == 0.0
    assert r["marks_exact_agreement"] == 0.5 and r["marks_mean_abs_diff"] == 0.5
    assert r["sent_to_teacher"] == 2
    assert r["silent_errors"] == 0  # both wrong rows were flagged


def test_kappa():
    assert cohen_kappa([True, False, True, False], [True, False, True, False]) == 1.0
    assert cohen_kappa([True, True, False, False], [True, False, True, False]) == 0.0


# Constructed challenge set (teacher-checked labels, not learner data).
import csv as _csv
from pathlib import Path

from pipeline.marking import mark_numeric as _mark

CHALLENGE = Path(__file__).resolve().parent.parent / "evaluation" / "challenge_set.csv"


def _challenge_rows():
    with open(CHALLENGE, encoding="utf-8", newline="") as f:
        return list(_csv.DictReader(f))


def test_challenge_set_uses_known_ids(cat):
    known = {m["id"] for m in cat["misconceptions"]}
    for r in _challenge_rows():
        assert r["source"] == "constructed"
        for i in filter(None, r["teacher_ids"].split(";")):
            assert i in known, (r["case_id"], i)


def test_rules_agree_with_teacher_on_numeric_cases(cat):
    """The final-answer rules reach the teacher's label on every 11.2 and 11.3 case."""
    for r in _challenge_rows():
        if not r["item_id"].endswith(("11.2", "11.3")):
            continue
        earlier = float(r["earlier_answer"]) if r["earlier_answer"] else None
        res = _mark(cat, r["item_id"], float(r["final_answer"]), 4, source_value=earlier)
        teacher = set(filter(None, r["teacher_ids"].split(";")))
        if teacher:
            assert teacher & {m["id"] for m in res["misconceptions"]}, r["case_id"]
        else:
            assert res["status"] in ("correct", "carried_forward"), r["case_id"]


# Text items (11.1, 11.4 to 11.7), with the fake client.
from pipeline.llm_diagnose import find_item


def text_ticks(cat, item_id, earned):
    return [TickDecision(number=n, earned=e, reason="") for n, e in enumerate(earned, start=1)]


def test_one_word_wrong_answer_agrees_with_options(cat):
    d = Diagnosis(misconception_ids=["EMI-04"], evidence="The coil attracts the magnet",
                  ticks=text_ticks(cat, Q11 + ".6", [False]), confidence="high",
                  feedback_for_teacher="")
    r = diagnose_working(FakeClient(d), cat, Q11 + ".6", "The coil attracts the magnet.", "SOUTH")
    assert r["rule_ids"] == ["EMI-04"] and r["needs_teacher"] is False and r["marks"] == 0


def test_right_answer_wrong_reasoning_goes_to_teacher(cat):
    """CASE_11.7_03: FROM A TO B reached from a wrong South pole."""
    d = Diagnosis(misconception_ids=["EMI-04"], evidence="Since end X is a South pole",
                  ticks=text_ticks(cat, Q11 + ".7", [True]), confidence="high",
                  feedback_for_teacher="")
    client = FakeClient(d)
    r = diagnose_working(client, cat, Q11 + ".7", "Since end X is a South pole, A to B.",
                         "FROM A TO B", earlier_answer="SOUTH")
    assert r["marks"] == 1 and r["needs_teacher"] is True
    assert "right answer" in r["problems"][0]
    assert "answer to 11.6 was SOUTH" in client.calls[0]["messages"][0]["content"]


def test_two_or_nothing_is_enforced(cat):
    d = Diagnosis(misconception_ids=["EMI-02"], evidence="change in magnetic flux",
                  ticks=text_ticks(cat, Q11 + ".1", [True, False]), confidence="high",
                  feedback_for_teacher="")
    r = diagnose_working(FakeClient(d), cat, Q11 + ".1",
                         "The induced emf is directly proportional to the change in magnetic flux.",
                         "Faraday's Law")
    assert r["marks"] == 0  # 1 of 2 ticks is not allowed: 2 or 0


def test_explanation_has_no_rule_so_llm_stands(cat):
    d = Diagnosis(misconception_ids=["EMI-17"], evidence="magnetic field becomes stronger",
                  ticks=text_ticks(cat, Q11 + ".5", [False]), confidence="high",
                  feedback_for_teacher="")
    r = diagnose_working(FakeClient(d), cat, Q11 + ".5", "Because the field becomes stronger.",
                         "Magnetic field increases", earlier_answer="INCREASE")
    assert r["rule_status"] == "unknown" and r["needs_teacher"] is False


def test_whole_challenge_set_runs(cat):
    """Every one of the 23 cases goes through the pipeline. The fake client
    answers with the teacher's own labels, so this tests the wiring, not Claude."""
    from pipeline.evaluate import load, report, run_llm

    rows = load(str(CHALLENGE))
    by_working = {r["working"]: r for r in rows}

    class EchoClient(FakeClient):
        def __init__(self):
            super().__init__()

            def parse(**kwargs):
                content = kwargs["messages"][0]["content"]
                row = next(r for w, r in by_working.items() if w in content)
                _, item = find_item(cat, row["item_id"])
                n = int(row["teacher_marks"] or 0)
                earned = [i < n for i in range(len(item["memo_ticks"]))]
                return SimpleNamespace(stop_reason="end_turn", parsed_output=Diagnosis(
                    misconception_ids=[i for i in row["teacher_ids"].split(";") if i],
                    evidence="", ticks=text_ticks(cat, row["item_id"], earned),
                    confidence="high", feedback_for_teacher=""))

            self.beta = SimpleNamespace(messages=SimpleNamespace(parse=parse))

    results = run_llm(EchoClient(), cat, rows)
    assert len(results) == 23
    r = report(results)
    assert r["exact_id_agreement"] == 1.0 and r["marks_exact_agreement"] == 1.0
    flagged = [x["case_id"] for x in results if x["needs_teacher"]]
    # Only CASE_11.7_03 is flagged: right answer, wrong reasoning, which a
    # teacher should always see. Every other label agrees with the rules.
    assert flagged == ["CASE_11.7_03"], flagged
    assert r["silent_errors"] == 0


# Open-source backend (Llama through Ollama), with a fake chat function.
from pipeline.llm_diagnose import OllamaBackend


def fake_ollama_chat(content):
    calls = []

    def chat(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(message=SimpleNamespace(content=content))

    return chat, calls


def test_ollama_backend_valid_json(cat):
    d = Diagnosis(misconception_ids=["EMI-04"], evidence="attracts",
                  ticks=text_ticks(cat, Q11 + ".6", [False]), confidence="high",
                  feedback_for_teacher="")
    chat, calls = fake_ollama_chat(
        '{"misconception_ids": ["EMI-04"], "evidence": "attracts", "tick_1": false, '
        '"tick_reasons": "", "confidence": "high", "feedback_for_teacher": ""}')
    r = diagnose_working(OllamaBackend("llama3.1:8b", chat=chat), cat, Q11 + ".6",
                         "The coil attracts the magnet.", "SOUTH")
    assert r["misconception_ids"] == ["EMI-04"] and r["model"] == "llama3.1:8b"
    assert r["marks"] == 0 and not r["problems"]
    assert "tick_1" in calls[0]["format"]["required"]  # schema sent to the model
    assert calls[0]["messages"][0]["role"] == "system"


def test_ollama_backend_invalid_json_goes_to_teacher(cat):
    chat, _ = fake_ollama_chat("Sure! The learner thinks the coil attracts.")
    r = diagnose_working(OllamaBackend("llama3.1:8b", chat=chat), cat, Q11 + ".6",
                         "The coil attracts the magnet.", "SOUTH")
    assert r["needs_teacher"] and "invalid JSON" in r["problems"][0]


# Bugs found by the first Llama run (evaluation/results/llama3.1-8b_v1.csv).
def test_extra_ticks_never_give_more_marks_than_the_item_has(cat):
    """CASE_11.5_03 v1: Llama returned 2 ticks for a 1-mark item and scored 2/1."""
    d = Diagnosis(misconception_ids=["EMI-17"], evidence="field becomes stronger",
                  ticks=text_ticks(cat, Q11 + ".5", [True, True]), confidence="high",
                  feedback_for_teacher="")
    r = diagnose_working(FakeClient(d), cat, Q11 + ".5", "Because the field becomes stronger.",
                         "Magnetic field increases", earlier_answer="INCREASE")
    assert r["marks"] is None and r["needs_teacher"]


def test_confidence_outside_the_three_levels_is_rejected(cat):
    """v1: Llama put 'low' in the id list. Confidence is now limited to three values."""
    bad = ('{"misconception_ids": [], "evidence": "", "tick_1": true, "tick_reasons": "", '
           '"confidence": "very sure", "feedback_for_teacher": ""}')
    chat, _ = fake_ollama_chat(bad)
    r = diagnose_working(OllamaBackend("llama3.1:8b", chat=chat), cat, Q11 + ".6",
                         "North pole repels.", "NORTH")
    assert r["needs_teacher"] and "invalid JSON" in r["problems"][0]


def test_numbered_ticks_are_shown_with_the_memo_text(cat):
    d = Diagnosis(misconception_ids=[], evidence="no misconception",
                  ticks=text_ticks(cat, Q11 + ".6", [True]), confidence="high",
                  feedback_for_teacher="")
    r = diagnose_working(FakeClient(d), cat, Q11 + ".6", "North repels north.", "NORTH")
    assert r["ticks"][0]["tick"] == "NORTH" and r["marks"] == 1


def test_schema_makes_every_tick_required():
    """Run 2: with a list, Llama returned no ticks. Now each tick is a required field."""
    from pipeline.llm_diagnose import answer_schema

    schema = answer_schema(4).model_json_schema()
    assert {"tick_1", "tick_2", "tick_3", "tick_4"} <= set(schema["required"])
    assert "tick_5" not in schema["properties"]


def test_missing_tick_field_is_invalid(cat):
    chat, _ = fake_ollama_chat(
        '{"misconception_ids": [], "evidence": "", "tick_1": true, "tick_reasons": "", '
        '"confidence": "high", "feedback_for_teacher": ""}')  # 11.2 needs tick_1 to tick_3
    r = diagnose_working(OllamaBackend("llama3.1:8b", chat=chat), cat, Q11 + ".2",
                         "emf = -N dPhi/dt ...", -0.0014)
    assert r["needs_teacher"] and "invalid JSON" in r["problems"][0]


# Found in Run 3: the LLM's marks on one-word answers are replaced by the rules'.
@pytest.mark.parametrize("item, answer, llm_tick, expected", [
    (".4", "DECREASE", True, 0),       # Run 3, 11.4_02: LLM gave 1
    (".6", "SOUTH", True, 0),          # Run 3, 11.6_02: LLM gave 1
    (".7", "FROM B TO A", True, 0),    # Run 3, 11.7_01: LLM gave 1
    (".6", "NORTH", False, 1),         # right answer the LLM failed to credit
])
def test_rules_set_marks_on_one_word_answers(cat, item, answer, llm_tick, expected):
    d = Diagnosis(misconception_ids=[], evidence="", ticks=text_ticks(cat, Q11 + item, [llm_tick]),
                  confidence="high", feedback_for_teacher="")
    r = diagnose_working(FakeClient(d), cat, Q11 + item, "...", answer)
    assert r["marks"] == expected


def test_false_alarm_on_right_one_word_answer_is_flagged(cat):
    """Run 3, 11.6_01: NORTH is right, but the LLM reported EMI-04."""
    d = Diagnosis(misconception_ids=["EMI-04"], evidence="", ticks=text_ticks(cat, Q11 + ".6", [True]),
                  confidence="high", feedback_for_teacher="")
    r = diagnose_working(FakeClient(d), cat, Q11 + ".6", "North pole repels north pole.", "NORTH")
    assert r["needs_teacher"] is True


def test_silent_errors_counted():
    rows = [
        {"teacher_ids": "EMI-04", "llm_ids": "", "teacher_marks": "0", "llm_marks": "1", "needs_teacher": "False"},
        {"teacher_ids": "EMI-04", "llm_ids": "", "teacher_marks": "0", "llm_marks": "1", "needs_teacher": "True"},
        {"teacher_ids": "", "llm_ids": "", "teacher_marks": "1", "llm_marks": "1", "needs_teacher": "False"},
    ]
    assert report(rows)["silent_errors"] == 1
