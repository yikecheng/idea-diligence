"""Streamlit workspace for the blinded comparison study."""

import json

import streamlit as st

from .evaluation import (
    CASE_FIELDS,
    CONDITIONS,
    LABELS,
    LIMITATIONS,
    RUBRIC,
    SCORE_LABELS,
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

FIELD_HINTS = {
    "known_alternatives": "What products, substitutes, or workarounds does the founder already know? Enter None if there are none.",
    "known_assumptions": "List the founder’s critical beliefs and the next test they would run today.",
    "budget": "Enter a common time or tool-call cap. Specify whether search, model calls, or human research are included.",
    "source_scope": "Specify the common documents, public access, geography, dates, and exclusions where applicable.",
}


def _register_case() -> None:
    with st.expander("Register a comparison case"):
        st.caption("Record what the founder already knows and match the research conditions before generating outputs.")
        with st.form("evaluation_case_setup"):
            fields = {"title": st.text_input("Case title", max_chars=CASE_FIELDS["title"][1])}
            fields["brief"] = st.text_area("Idea and target customer", max_chars=CASE_FIELDS["brief"][1], height=88)
            for column, keys in zip(st.columns(2), (("known_alternatives", "known_assumptions"), ("budget", "source_scope"))):
                with column:
                    for key in keys:
                        label, limit = CASE_FIELDS[key]
                        fields[key] = st.text_area(label, max_chars=limit, help=FIELD_HINTS[key], height=88)
            required_reviews = st.selectbox("Independent reviewers", (1, 2, 3), help="Register two to compare judgments on a subset of cases.")
            if st.form_submit_button("Freeze comparison setup", type="primary"):
                try:
                    case_id = create_case(fields, required_reviews=required_reviews)
                except ValueError as error:
                    st.error(str(error))
                else:
                    st.session_state["evaluation_active_case"] = case_id
                    st.rerun()


def _show_context(case: dict) -> None:
    with st.expander("Frozen case and research constraints", expanded=case["packet_ready_at"] is None):
        for key, (label, _) in CASE_FIELDS.items():
            if key != "title":
                st.markdown(f"**{label}**")
                st.text(case[key])
        st.caption(f"Registered at {case['created_at']} · {case['required_reviews']} independent reviewer(s)")


def _prepare_packet(case_id: int) -> None:
    st.subheader("Prepare the review packet")
    st.caption(
        "Run all three conditions from the frozen setup. Paste their complete outputs with source URLs. "
        "Remove the generating tool’s branding and headers. Keep competitor names and source URLs."
    )
    with st.form("evaluation_attach_outputs"):
        outputs = {
            key: st.text_area(label, max_chars=16_000, height=130, key=f"evaluation_output_{case_id}_{key}")
            for key, label in CONDITIONS.items()
        }
        if st.form_submit_button("Freeze and shuffle outputs", type="primary"):
            try:
                attach_outputs(case_id, outputs)
            except ValueError as error:
                st.error(str(error))
            else:
                st.rerun()


def _show_output(content: str) -> None:
    with st.container(height=300, border=True):
        st.text(content)


def _review(case_id: int, packet: dict[str, str], status: dict) -> None:
    if status["review_count"] >= status["required_reviews"]:
        st.success("All registered reviewers have submitted.")
        return
    st.caption("Score each output against the frozen brief. Verify the passages behind claims that could change the decision.")
    with st.form(f"evaluation_reviewer_{case_id}", clear_on_submit=False):
        reviewer = st.text_input("Reviewer alias", max_chars=80, help="Use a distinct alias for each independent reviewer.")
        ratings, notes = {}, {}
        for label, tab in zip(LABELS, st.tabs([f"Output {label}" for label in LABELS])):
            with tab:
                _show_output(packet[label])
                ratings[label] = {}
                columns = st.columns(2)
                for index, (key, (name, guidance)) in enumerate(RUBRIC.items()):
                    with columns[index % 2]:
                        ratings[label][key] = st.selectbox(
                            name, tuple(SCORE_LABELS), index=None, format_func=SCORE_LABELS.__getitem__,
                            help=guidance, key=f"evaluation_score_{case_id}_{label}_{key}",
                        )
                notes[label] = st.text_area(
                    "Reason for your scores", max_chars=2_000, height=88,
                    placeholder="Name the overlooked risk or claim and cite the passage behind each top score.",
                    help="Required for a score of 2 on overlooked risk or source grounding. Other notes are optional.",
                    key=f"evaluation_note_{case_id}_{label}",
                )
        if st.form_submit_button("Submit all three ratings", type="primary"):
            try:
                record_review(case_id, reviewer, ratings, notes)
            except ValueError as error:
                st.error(str(error))
            else:
                st.session_state["evaluation_reviewer_saved"] = case_id
                st.rerun()


def _founder_feedback(case_id: int, packet: dict[str, str], status: dict) -> None:
    if status["founder_recorded"]:
        st.success("Founder feedback is recorded.")
        return
    st.caption("Use this form as the idea owner. Compare the suggestions with what you knew before reading these outputs.")
    with st.form(f"evaluation_founder_{case_id}"):
        novelty = {}
        for label, tab in zip(LABELS, st.tabs([f"Output {label}" for label in LABELS])):
            with tab:
                _show_output(packet[label])
                novelty[label] = {
                    "competitor": st.text_input("New competitor or alternative (if any)", max_chars=1_000,
                                                key=f"evaluation_new_alternative_{case_id}_{label}"),
                    "risk": st.text_input("New critical belief or risk (if any)", max_chars=1_000,
                                          key=f"evaluation_new_risk_{case_id}_{label}"),
                }
        preference = st.radio(
            "Which output would you use to decide what to test next?", (*LABELS, "tie"), index=None, horizontal=True,
            format_func=lambda value: "No preference" if value == "tie" else f"Output {value}",
        )
        if st.form_submit_button("Submit founder feedback", type="primary"):
            try:
                record_founder_feedback(case_id, preference, novelty)
            except ValueError as error:
                st.error(str(error))
            else:
                st.rerun()


def _results(case_id: int, status: dict) -> None:
    if not status["can_reveal"]:
        st.info("The condition labels unlock after all registered reviewers and the founder submit feedback.")
        return
    reviews = {review["id"]: review["reviewer"] for review in submitted_reviews(case_id)}
    review_id = st.selectbox("Independent reviewer", tuple(reviews), format_func=reviews.__getitem__, key=f"evaluation_result_{case_id}")
    result = reveal_review(case_id, review_id)
    if result is None:
        st.warning("These scores are unavailable for comparison.")
        return
    st.table([
        {
            "Output": output["label"],
            "Condition": CONDITIONS[output["condition"]],
            "New critical risk / 2": output["scores"]["new_risk"],
            "Source grounding / 2": output["scores"]["grounding"],
            "Experiment design / 10": output["experiment_design_score"],
        }
        for output in result["outputs"]
    ])
    founder = result["founder_feedback"]
    preference = founder["preference"]
    st.markdown("**Founder preference**")
    if preference == "tie":
        st.text("No preference")
    else:
        preferred_condition = next(output["condition"] for output in result["outputs"] if output["label"] == preference)
        st.text(f"Output {preference} · {CONDITIONS[preferred_condition]}")
    with st.expander("Detailed scores, notes, and founder discoveries"):
        details = {item["label"]: item for item in founder["novelty"]}
        for output in result["outputs"]:
            label = output["label"]
            st.markdown(f"**Output {label} · {CONDITIONS[output['condition']]}**")
            st.table([{"Criterion": name, "Score / 2": output["scores"][key]} for key, (name, _) in RUBRIC.items()])
            if output["reviewer_note"]:
                st.text(output["reviewer_note"])
            st.text(f"New alternative: {details[label]['competitor'] or 'None recorded'}")
            st.text(f"New risk: {details[label]['risk'] or 'None recorded'}")
    all_reviews = [reveal_review(case_id, prior_id) for prior_id in reviews]
    st.download_button(
        "Download case and all scores (JSON)", data=json.dumps(all_reviews, ensure_ascii=False, indent=2),
        file_name=f"idea-diligence-evaluation-{case_id}.json", mime="application/json",
    )
    st.caption(LIMITATIONS)


def show_evaluation() -> None:
    st.title("Evaluation Lab")
    st.caption("Compare a standard AI answer, a competitor report, and Idea Diligence using the same brief and budget.")
    _register_case()
    cases = list_cases()
    if not cases:
        st.info("Register the first case to start a blinded comparison.")
        return
    choices = {case["id"]: f"{case['title']} · Case {case['id']}" for case in cases}
    active_case = st.session_state.get("evaluation_active_case")
    case_id = st.selectbox("Comparison case", tuple(choices), format_func=choices.__getitem__,
                           index=list(choices).index(active_case) if active_case in choices else 0)
    case = get_case(case_id)
    _show_context(case)
    if case["packet_ready_at"] is None:
        _prepare_packet(case_id)
        return
    packet = get_blind_packet(case_id)
    status = feedback_status(case_id)
    if st.session_state.pop("evaluation_reviewer_saved", None) == case_id:
        st.success("Independent reviewer scores saved.")
    st.caption(f"Independent reviews {status['review_count']}/{status['required_reviews']} · "
               f"Founder feedback {'recorded' if status['founder_recorded'] else 'pending'}")
    review_tab, founder_tab, result_tab = st.tabs(["Independent review", "Founder feedback", "Results"])
    with review_tab:
        _review(case_id, packet, status)
    with founder_tab:
        _founder_feedback(case_id, packet, status)
    with result_tab:
        _results(case_id, status)
