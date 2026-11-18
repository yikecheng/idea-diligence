"""Run with: python -m streamlit run app.py"""

import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

import streamlit as st

from idea_diligence.engine import live_available, load_demo_brief, run_analysis
from idea_diligence.report import escape_markdown as plain, render_markdown
from idea_diligence.storage import load_run, recent_runs, save_run

st.set_page_config(page_title="Idea Diligence", page_icon="🔎", layout="wide")
st.html((Path(__file__).parent / "style.css").read_text(encoding="utf-8"))

FIELDS = (
    ("title", "Idea name", "A short working name"),
    ("customer", "Target customer", "Who specifically has this problem?"),
    ("problem", "Problem", "What are they trying to do, and what gets in the way?"),
    ("solution", "Proposed solution", "What would your product do for them?"),
    ("known", "What you already know (optional)", "Add observations or uncertainties worth preserving."),
)


def set_brief(brief: dict) -> None:
    for name, _, _ in FIELDS:
        st.session_state[f"brief_{name}"] = brief.get(name, "")


def start_run(brief: dict, mode: str, consent: bool = False) -> None:
    progress = "Replaying the curated evidence set…" if mode == "demo" else "Researching your assumptions…"
    with st.spinner(progress):
        try:
            report = run_analysis(brief, mode=mode, allow_external=consent)
        except (ValueError, RuntimeError) as error:
            st.error(str(error))
            return
    st.session_state.report = report
    st.session_state.report_id = None
    try:
        st.session_state.report_id = save_run(report)
    except (OSError, sqlite3.Error):
        st.warning("The analysis finished, but the local history could not be saved. You can still download the report.")


def show_experiment(report: dict) -> None:
    experiment = report.get("experiment")
    st.subheader("What to test next")
    if not experiment:
        st.info("This run did not produce an experiment. Review the trace to see which step stopped.")
        return
    premise = next((a for a in report["assumptions"] if a["id"] == experiment["assumption_id"]), None)
    with st.container(border=True):
        st.markdown(f"**{plain(experiment['title'])}**")
        if premise:
            st.caption(f"Tests {premise['id']} · {premise['category'].title()}")
        st.markdown(plain(experiment["procedure"]))
        st.markdown("**Measure**")
        st.markdown(plain(experiment["metric"]))
        st.markdown("**Decision threshold**")
        st.markdown(plain(experiment["threshold"]))
        st.caption(f"Time · {experiment['time']}  |  Estimated cost · {experiment['cost']}")


def show_evidence(source: dict, link: dict) -> None:
    icon = {"supports": "🟢", "challenges": "🔴", "context": "⚪"}[link["stance"]]
    st.markdown(f"{icon} **{link['stance'].title()}** · {plain(source['title'])}")
    st.markdown(plain(link["reason"]))
    show_source_passage(source)


def show_source_passage(source: dict) -> None:
    st.markdown("> " + plain(source["passage"]).replace("\n", "\n> "))
    st.caption(f"{source['id']} · {source['kind'].replace('_', ' ').title()} · {source['retrieved_at']}")
    if urlsplit(source["url"]).scheme in {"https", "http"}:
        st.link_button("Open original source", source["url"])


def show_assumptions(report: dict) -> None:
    st.subheader("Assumption map")
    st.caption("Ranked by impact × uncertainty. Expand an assumption to inspect its evidence.")
    sources = {item["id"]: item for item in report["sources"]}
    for index, premise in enumerate(report["assumptions"]):
        label = f"{premise['category'].title()} · {premise['status'].title()} · Risk {premise['risk']}/25"
        with st.expander(label, expanded=index == 0):
            st.markdown(f"**{plain(premise['statement'])}**")
            st.caption(f"{premise['id']} · Impact {premise['impact']}/5 · Uncertainty {premise['uncertainty']}/5")
            st.markdown(plain(premise["reason"]))
            linked = [link for link in report["links"] if link["assumption_id"] == premise["id"]]
            if not linked:
                st.caption("No evidence linked to this assumption in this run.")
            for link in linked:
                source = sources.get(link["source_id"])
                if source:
                    with st.container(border=True):
                        show_evidence(source, link)


def show_result(report: dict) -> None:
    st.markdown("#### " + plain(report["brief"]["title"]))
    mode = "Curated evidence replay" if report["mode"] == "demo" else "Live model and search"
    st.caption(f"{mode} · {report['status'].title()} run · Public sources can inform assumptions. Demand requires a customer test.")
    if report["status"] == "partial":
        st.warning("Partial run. Available results are saved. See the trace for details.")
    left, right = st.columns([1.17, 1], gap="large")
    with left:
        show_assumptions(report)
    with right:
        show_experiment(report)
        st.download_button("Download Markdown report", render_markdown(report),
                           file_name="idea-diligence-report.md", mime="text/markdown", on_click="ignore")
    linked_ids = {link["source_id"] for link in report["links"]}
    leads = [source for source in report["sources"] if source["id"] not in linked_ids]
    if leads:
        with st.expander(f"Unlinked research leads · {len(leads)}"):
            st.caption("These results have no evidence assessment for an assumption.")
            for source in leads:
                with st.container(border=True):
                    st.markdown(f"**{plain(source['title'])}**")
                    show_source_passage(source)
    with st.expander("Run trace and limits"):
        usage = report["usage"]
        a, b, c = st.columns(3)
        a.metric("Model calls", usage["model_calls"])
        b.metric("Search calls", usage["search_calls"])
        c.metric("Duration", f"{usage['elapsed_seconds']:.2f} s")
        st.caption(f"Reported tokens · {usage['input_tokens']:,} input · {usage['output_tokens']:,} output")
        if usage.get("model"):
            st.caption(f"Model · {usage['model']}")
        if (cost := usage.get("estimated_model_cost_usd")) is not None:
            st.caption(f"Estimated model cost · ${cost:.4f} USD · Search excluded")
        if report["mode"] == "live":
            st.caption("Per run · up to 2 model calls, 5 searches, and 75 seconds")
        for event in report["trace"]:
            st.markdown(f"**{plain(event['stage'])}** · {plain(event['detail'])}")
        for warning in report["warnings"]:
            st.warning(warning)


st.title("Idea Diligence")
st.markdown("Find the assumptions your idea depends on, inspect the evidence, and choose what to test next.")
st.divider()

with st.sidebar:
    st.header("Workspace")
    st.caption("MIT 1.125 · Midpoint prototype")
    st.button("Load demo brief", on_click=set_brief, args=(load_demo_brief(),), width="stretch")
    if st.button("Run demo", type="primary", width="stretch"):
        set_brief(load_demo_brief())
        start_run(load_demo_brief(), "demo")
    st.caption("The demo replays a curated brief and public source excerpts. It makes no external requests.")
    st.divider()
    st.subheader("Run history")
    try:
        history = recent_runs()
        if history:
            labels = {i: f"#{i} · {title}" for i, _, title, _ in history}
            selected = st.selectbox("Saved analysis", list(labels), format_func=labels.get,
                                    index=None, placeholder="Choose a run")
            if selected is not None and st.button("Open run", width="stretch"):
                if saved := load_run(selected):
                    st.session_state.report = saved
                    st.session_state.report_id = selected
        else:
            st.caption("Completed and partial runs appear here.")
    except (OSError, sqlite3.Error):
        st.warning("Local history is unavailable.")

current = st.session_state.get("report")
with st.expander("Idea brief", expanded=current is None):
    with st.form("idea_brief"):
        values = {}
        for name, label, placeholder in FIELDS:
            widget = st.text_input if name in {"title", "customer"} else st.text_area
            values[name] = widget(label, placeholder=placeholder, key=f"brief_{name}")
        live_enabled = live_available()
        consent = st.checkbox("I’m using a public idea and agree to send its brief and research queries to the configured providers.",
                              disabled=not live_enabled)
        if not live_enabled:
            st.caption("Set the model and search keys to analyze a custom idea. The curated demo is available in the sidebar.")
        submitted = st.form_submit_button("Run live analysis", disabled=not live_enabled)
    if submitted:
        if consent:
            start_run(values, "live", consent=True)
        else:
            st.error("Confirm public-idea provider access before running live research.")

if current := st.session_state.get("report"):
    show_result(current)
else:
    st.info("Run the Catch Me Up on Anything demo to see how competing products change what a founder should test.")
