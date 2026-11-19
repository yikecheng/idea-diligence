import json

import pytest
from streamlit.testing.v1 import AppTest

from idea_diligence.evaluation import (
    LABELS,
    RUBRIC,
    attach_outputs,
    create_case,
    feedback_status,
    get_blind_packet,
    get_case,
    list_cases,
    record_founder_feedback,
    record_review,
    reveal_review,
    submitted_reviews,
)
from idea_diligence.storage import recent_runs


FIELDS = {
    "title": "Library Room Alerts",
    "brief": "Let students opt in to alerts for an open group study room.",
    "known_alternatives": "Campus library booking website",
    "known_assumptions": "Students need shorter waits. Planned test: interview six regular library visitors.",
    "budget": "Ten minutes and up to four public pages per condition",
    "source_scope": "Public library websites and campus discussion pages available on the same date",
}
OUTPUTS = {
    "direct_ai": "Ask students whether they struggle to get a slot.",
    "competitor_report": "The library website already shows a calendar of room availability.",
    "idea_diligence": "Check how often an available room turns into a booking and who can access that data.",
}


def _ratings(score):
    return {label: dict.fromkeys(RUBRIC, score) for label in LABELS}


def _novelty():
    return {label: {"competitor": "", "risk": ""} for label in LABELS}


def test_freezes_context_and_distinct_condition_outputs_on_existing_database(tmp_path):
    path = tmp_path / "runs.sqlite3"
    assert recent_runs(path) == []
    with pytest.raises(ValueError, match="research budget"):
        create_case({**FIELDS, "budget": " "}, path)
    assert list_cases(path) == []

    case_id = create_case(FIELDS, path)
    assert get_case(case_id, path)["known_assumptions"] == FIELDS["known_assumptions"]
    assert get_blind_packet(case_id, path) == {}
    with pytest.raises(ValueError, match="three frozen outputs"):
        record_review(case_id, "Reviewer", _ratings(1), {}, path)
    with pytest.raises(ValueError, match="each comparison condition"):
        attach_outputs(case_id, {"direct_ai": "Only one output"}, path)
    with pytest.raises(ValueError, match="distinct"):
        attach_outputs(case_id, dict.fromkeys(OUTPUTS, "Repeated output"), path)
    assert get_case(case_id, path)["packet_ready_at"] is None

    attach_outputs(case_id, OUTPUTS, path)
    packet = get_blind_packet(case_id, path)
    assert tuple(packet) == LABELS
    assert set(packet.values()) == set(OUTPUTS.values())
    with pytest.raises(ValueError, match="still awaiting outputs"):
        attach_outputs(case_id, {key: value + " Updated." for key, value in OUTPUTS.items()}, path)
    assert get_blind_packet(case_id, path) == packet
    assert recent_runs(path) == []


def test_condition_reveal_waits_for_all_human_inputs(tmp_path):
    path = tmp_path / "study.sqlite3"
    case_id = create_case(FIELDS, path, required_reviews=2)
    attach_outputs(case_id, OUTPUTS, path)
    ratings = _ratings(1)
    del ratings["B"]["new_risk"]
    with pytest.raises(ValueError, match="every rubric item"):
        record_review(case_id, "Reader 1", ratings, {}, path)
    with pytest.raises(ValueError, match="0, 1, or 2"):
        record_review(case_id, "Reader 1", _ratings(True), {}, path)
    assert submitted_reviews(case_id, path) == []

    first_review = record_review(case_id, "Reader 1", _ratings(1), {"A": "Verify booking conversion."}, path)
    assert reveal_review(case_id, first_review, path) is None
    with pytest.raises(ValueError, match="already submitted"):
        record_review(case_id, "reader 1", _ratings(0), {}, path)
    with pytest.raises(ValueError, match="naming the overlooked risk"):
        record_review(case_id, "Reader 2", _ratings(2), {}, path)
    notes = dict.fromkeys(LABELS, "Verify the booking conversion mentioned in the public library reports.")
    second_review = record_review(case_id, "Reader 2", _ratings(2), notes, path)
    assert reveal_review(case_id, second_review, path) is None
    assert feedback_status(case_id, path) == {
        "required_reviews": 2, "review_count": 2, "founder_recorded": 0, "can_reveal": False,
    }

    novelty = _novelty()
    novelty["A"]["risk"] = "Calendar data access was outside my original plan."
    record_founder_feedback(case_id, "C", novelty, path)
    assert feedback_status(case_id, path)["can_reveal"]
    first = reveal_review(case_id, first_review, path)
    second = reveal_review(case_id, second_review, path)
    assert first["case"]["budget"] == FIELDS["budget"]
    assert first["review"]["rubric_version"] == 1
    assert first["outputs"][0]["reviewer_note"] == "Verify booking conversion."
    assert {o["condition"]: o["content"] for o in first["outputs"]} == OUTPUTS
    assert [o["experiment_design_score"] for o in first["outputs"]] == [5, 5, 5]
    assert [o["experiment_design_score"] for o in second["outputs"]] == [10, 10, 10]
    assert first["founder_feedback"]["preference"] == "C"
    assert first["founder_feedback"]["novelty"][0]["risk"] == novelty["A"]["risk"]
    assert "Observed outcomes require" in json.dumps(first)
    other_case = create_case(FIELDS, path)
    assert reveal_review(other_case, first_review, path) is None
    with pytest.raises(ValueError, match="already recorded"):
        record_founder_feedback(case_id, "tie", _novelty(), path)
    with pytest.raises(ValueError, match="registered number"):
        record_review(case_id, "Reader 3", _ratings(0), {}, path)


def test_streamlit_setup_scoring_and_founder_feedback(monkeypatch, tmp_path):
    monkeypatch.setenv("IDEA_DILIGENCE_DB", str(tmp_path / "evaluation.sqlite3"))
    entry_point = "from idea_diligence.evaluation_ui import show_evaluation\nshow_evaluation()"
    app = AppTest.from_string(entry_point, default_timeout=20)
    app.run()
    assert not app.exception
    app.text_input[0].set_value(FIELDS["title"])
    for field, value in zip(app.text_area, (FIELDS[key] for key in list(FIELDS)[1:])):
        field.set_value(value)
    app.button[0].click().run()
    assert not app.exception
    assert app.subheader[0].value == "Prepare the review packet"

    outputs = [field for field in app.text_area if field.key and field.key.startswith("evaluation_output_")]
    for field, value in zip(outputs, OUTPUTS.values()):
        field.set_value(value)
    next(button for button in app.button if button.label == "Freeze and shuffle outputs").click().run()
    assert not app.exception
    assert "condition labels unlock" in app.info[0].value
    assert not app.table

    app = AppTest.from_string(entry_point, default_timeout=20).run()
    next(field for field in app.text_input if field.label == "Reviewer alias").set_value("Independent reviewer")
    next(button for button in app.button if button.label == "Submit all three ratings").click().run()
    assert "0, 1, or 2" in app.error[0].value
    for field in app.selectbox:
        if field.key and field.key.startswith("evaluation_score_"):
            field.set_value(1)
    next(button for button in app.button if button.label == "Submit all three ratings").click().run()
    assert not app.exception
    assert not app.table

    app = AppTest.from_string(entry_point, default_timeout=20).run()
    app.radio[0].set_value("A")
    next(button for button in app.button if button.label == "Submit founder feedback").click().run()
    assert not app.exception
    assert len(app.table) == 4
    assert set(app.table[0].value["Condition"]) == {"Standard AI prompt", "Static competitor report", "Idea Diligence"}
    assert "Founder preference" in [item.value.replace("**", "") for item in app.markdown]
