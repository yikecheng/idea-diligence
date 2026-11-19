"""Idea Diligence workspace. Start with python -m streamlit run app.py."""

import html
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

import streamlit as st

from idea_diligence.decision import EVIDENCE_VERDICTS, OUTCOME_DECISIONS, OUTCOME_STATUSES
from idea_diligence.engine import list_demo_cases, load_demo_brief, run_analysis
from idea_diligence.evaluation_ui import show_evaluation
from idea_diligence.intake import experiment_form_fields, idea_intake
from idea_diligence.priorities import current_assumptions, load_priority_updates, next_priority, save_priority_update
from idea_diligence.report import escape_markdown as plain, render_html, render_markdown
from idea_diligence.research_ui import show_research
from idea_diligence.storage import (
    list_followup_experiments, load_research, load_run, load_workspace, recent_runs, save_evidence_review,
    save_experiment_outcome, save_followup_experiment, save_followup_outcome, save_founder_plan, save_run,
)

st.set_page_config(page_title="Idea Diligence", page_icon="◈", layout="wide")
st.html(Path(__file__).with_name("style.css").read_text(encoding="utf-8"))

h = html.escape
STATUS = {"open": "Open", "supported": "Supported", "challenged": "Challenged",
          "context": "Context only", "mixed": "Mixed"}
STANCE = {"supports": "Supports", "challenges": "Challenges", "context": "Context only"}
REVIEW = {"accept": "Accept link", "question": "Needs review", "exclude": "Exclude from review"}
DECISION = {"undecided": "Undecided", "continue": "Continue", "revise": "Revise", "stop": "Stop"}
MODES = {"demo": "Curated demo", "live": "AI research", "local": "Local evidence review"}


def pill(label: str, tone: str = "") -> str:
    return f'<span class="id-pill {h(tone)}">{h(label)}</span>'


def count_label(count: int, noun: str) -> str:
    suffix = "" if count == 1 else "es" if noun.endswith("ch") else "s"
    return f"{count} {noun}{suffix}"


def change_page(page: str) -> None:
    st.session_state.screen = page


def open_analysis(report: dict, run_id: int | None) -> None:
    st.session_state.report = report
    st.session_state.run_id = run_id
    change_page("analysis")


def finish_run(brief: dict, mode: str, *, demo_slug: str | None = None, consent: bool = False) -> None:
    with st.spinner("Preparing your evidence and decision brief…"):
        try:
            if demo_slug:
                report = run_analysis(brief, mode, demo_slug=demo_slug)
            else:
                report = run_analysis(brief, mode, allow_external=consent)
        except (ValueError, RuntimeError) as error:
            st.error(str(error))
            return
    persist_analysis(report)


def persist_analysis(report: dict) -> None:
    try:
        run_id = save_run(report)
    except (sqlite3.Error, OSError):
        run_id = None
        st.session_state.flash = "The run is open, but local storage was unavailable. Exports still work."
    open_analysis(report, run_id)
    st.rerun()


def sidebar() -> None:
    with st.sidebar:
        st.html("""
          <div class="id-brand"><span class="id-logo" aria-hidden="true">◈</span>
            <div><strong>Idea Diligence</strong><small>Founder workspace</small></div>
          </div>""")
        st.button("Workspace home", width="stretch", on_click=change_page, args=("home",))
        st.button("New idea", width="stretch", on_click=change_page, args=("brief",))
        st.button("Evaluation lab", width="stretch", on_click=change_page, args=("evaluation",))
        st.divider()
        st.markdown("**Saved analyses**")
        try:
            history = recent_runs()
            if history:
                options = {row[0]: row[2] for row in history}
                selected = st.selectbox("Saved analysis", list(options), format_func=options.get,
                                        label_visibility="collapsed", index=None, placeholder="Choose an analysis")
                if selected is not None and st.button("Open saved analysis", width="stretch"):
                    if report := load_run(selected):
                        open_analysis(report, selected)
            else:
                st.caption("Completed and partial runs appear here.")
        except (sqlite3.Error, OSError):
            st.warning("Saved analyses are unavailable.")
        st.divider()
        st.caption("Analyses, decisions, and evaluation records are saved on this device.")


def home() -> None:
    st.html("""
      <div class="id-hero">
        <div class="id-hero-content">
          <h1>Know what to test<br>before you build.</h1>
          <p>Turn a startup idea into the assumptions that matter, the evidence behind them,
          and a test that can change your decision.</p>
        </div>
        <div class="id-glyph" aria-hidden="true"><i></i><i></i><i></i><b></b></div>
      </div>""")
    st.markdown("## Explore a case")
    st.caption("Use a curated brief and public source excerpts. Each sample runs locally without credentials.")
    demos = list_demo_cases()
    for index, (column, case) in enumerate(zip(st.columns(len(demos), gap="medium"), demos)):
        with column, st.container(border=True):
            st.markdown(f"### {plain(case['title'])}")
            st.markdown(plain(case["description"]))
            if st.button(f"Open {case['title']} demo", key=case["slug"], width="stretch",
                         type="primary" if index == 0 else "secondary"):
                finish_run(load_demo_brief(case["slug"]), "demo", demo_slug=case["slug"])


def edit_priority(assumptions: list[dict], run_id: int) -> None:
    by_id = {row["id"]: row for row in assumptions}
    with st.expander("Update a risk score"):
        st.caption("Impact is the consequence if an assumption is wrong. Uncertainty is how much is still unknown.")
        key = f"risk-target-{run_id}"
        st.session_state.setdefault(key, assumptions[0]["id"])
        aid = st.selectbox("Assumption to update", sorted(by_id),
                           format_func=lambda key: f'{key} · {by_id[key]["category"].title()}',
                           key=key)
        row = by_id[aid]
        st.markdown(plain(row["statement"]))
        with st.form(f"risk-score-{run_id}-{aid}"):
            col_impact, col_uncertainty = st.columns(2)
            scores = (1, 2, 3, 4, 5)
            impact = col_impact.selectbox("Impact", scores, index=row["current_impact"] - 1)
            uncertainty = col_uncertainty.selectbox("Uncertainty", scores, index=row["current_uncertainty"] - 1)
            reason = st.text_area("What changed?", max_chars=500,
                                  placeholder="Reference an excerpt, an experiment result, or a revised judgment.")
            if st.form_submit_button("Save risk update", type="primary"):
                save_and_refresh(save_priority_update, run_id, aid, impact, uncertainty, reason)


def show_overview(report: dict, assumptions: list[dict], workspace: dict, run_id: int | None) -> None:
    experiment = report.get("experiment") or workspace.get("plan")
    outcome = workspace.get("outcome") or {}
    target = workspace["priority"]
    if target:
        decision = DECISION[outcome.get("decision", "undecided")]
        focus = f'{target["id"]} · {target["current_risk"]}/25 risk · {STATUS[target["current_status"]]}'
        st.html(f"""
          <div class="id-brief"><div>
            <small>CURRENT RESEARCH PRIORITY</small>
            <h2>{h(target['statement'])}</h2>
            <p>{h(focus)}</p>
            </div><div class="id-brief-side">
            <small>ORIGINAL EXPERIMENT</small><strong>{h(decision) if experiment else "Awaiting plan"}</strong>
            <span>{h(experiment["assumption_id"] + " · " + outcome.get("status", "planned").title()) if experiment else "Plan your first test"}</span>
          </div></div>""")
    elif assumptions:
        st.info("Every assumption has directional evidence in the workspace. Check its relevance and strength before acting.")
    left, right = st.columns([1.65, 1], gap="large")
    with left:
        st.subheader("Assumption map")
        st.caption("Impact × uncertainty ranks all risks. The focus above is the highest-ranked question still open for research.")
        for row in assumptions:
            status = row["current_status"]
            subtitle = f'{row["id"]} · Impact {row["current_impact"]}/5 · Uncertainty {row["current_uncertainty"]}/5'
            if row["pending_addition"]:
                subtitle += " · New excerpt to review"
            elif row["questioned_count"]:
                subtitle += " · Evidence questioned"
            if (update := row["priority_update"]) is not None:
                subtitle += f' · Initially {row["risk"]}/25'
            note = f'<small>{h(update["reason"])}</small>' if update else ""
            focus_badge = pill("Research priority") if target and row["id"] == target["id"] else ""
            st.html(f"""
              <div class="id-assumption"><div class="id-risk"><strong>{row["current_risk"]}</strong><span>/ 25</span></div>
                <div class="id-assumption-body"><div class="id-row-meta">
                  <span>{h(row["category"].title())}</span>{pill(STATUS[status], status)}{focus_badge}
                </div><p>{h(row["statement"])}</p><small>{h(subtitle)}</small>{note}</div>
              </div>""")
        if not assumptions:
            st.info("This run stopped before producing an assumption map. See Run trace for details.")
        elif run_id is not None:
            edit_priority(assumptions, run_id)
    with right:
        st.subheader("Decision brief")
        with st.container(border=True):
            st.markdown("**Target customer**")
            st.markdown(plain(report["brief"]["customer"]))
            st.markdown("**Problem**")
            st.markdown(plain(report["brief"]["problem"]))
            st.markdown("**Proposed solution**")
            st.markdown(plain(report["brief"]["solution"]))
            if report["brief"].get("known"):
                st.markdown("**What we know**")
                st.markdown(plain(report["brief"]["known"]))
        st.download_button("Download decision memo", render_html(report, workspace),
                           "idea-diligence-memo.html", "text/html", on_click="ignore", width="stretch")
        st.download_button("Download Markdown", render_markdown(report, workspace),
                           "idea-diligence-report.md", "text/markdown", on_click="ignore", width="stretch")


def source_passage(source: dict) -> None:
    if source["kind"] == "discussion_lead":
        st.caption(source["passage"])
    else:
        st.html(f'<blockquote class="id-source-quote">{h(source["passage"])}</blockquote>')
    st.caption(f'{source["id"]} · {source["kind"].replace("_", " ").capitalize()} · {source["retrieved_at"]}')
    if urlsplit(source["url"]).scheme in ("https", "http"):
        st.link_button("Open original source", source["url"])


def save_and_refresh(operation, *args) -> None:
    try:
        operation(*args)
    except ValueError as error:
        st.error(str(error))
    except (sqlite3.Error, OSError):
        st.error("Local storage is unavailable. Try saving again.")
    else:
        st.session_state.flash = "Saved to this analysis."
        st.rerun()


def show_evidence(report: dict, assumptions: list[dict], workspace: dict, run_id: int | None) -> None:
    st.subheader("Evidence review")
    st.caption("Review each passage against the assumption it is linked to. You can revisit the original assessment in the trace.")
    if not assumptions:
        st.info("An assumption plan is required before evidence can be reviewed.")
        return
    left, right = st.columns([0.92, 1.73], gap="large")
    lookup = {row["id"]: row for row in assumptions}
    source_by_id = {source["id"]: source for source in report["sources"]}
    candidates = sorted(assumptions, key=lambda row: (not row["pending_addition"], not any(
        link["assumption_id"] == row["id"] and link["stance"] == "challenges" for link in report["links"]
    ), -row["current_risk"]))
    with left:
        key = f"evidence-choice-{run_id}"
        st.session_state.setdefault(key, candidates[0]["id"])
        selected = st.radio("Choose an assumption", sorted(lookup),
                            format_func=lambda aid: f'{aid} · {lookup[aid]["category"].title()}',
                            key=key)
        row = lookup[selected]
        st.markdown(f"**{plain(row['statement'])}**")
        st.caption(f"{STATUS[row['current_status']]} · Impact {row['current_impact']}/5 · Uncertainty {row['current_uncertainty']}/5")
        st.markdown(plain(row["reason"]))
    with right:
        links = [item for item in report["links"] if item["assumption_id"] == selected]
        links.sort(key=lambda item: "proposed_stance" not in item)
        if not links:
            st.info("No passage is linked to this assumption. It remains an open research question.")
        for link in links:
            source = source_by_id[link["source_id"]]
            source_id = source["id"]
            key = f"{run_id}-{selected}-{source_id}"
            review = next((item for item in workspace["reviews"]
                           if item["assumption_id"] == selected and item["source_id"] == source_id), None)
            with st.container(border=True):
                st.html(f'<div class="id-card-meta">{pill(STANCE[link["stance"]], link["stance"])}'
                        f'{pill(REVIEW[review["verdict"]] if review else "Awaiting review")}</div>')
                st.markdown(f"#### {plain(source['title'])}")
                if proposed := link.get("proposed_stance"):
                    st.caption(f"Founder proposal · {STANCE[proposed]}. Founder excerpts contribute context. Record any change in judgment on the assumption map.")
                if link["reason"]:
                    st.markdown(plain(link["reason"]))
                source_passage(source)
                if run_id is not None:
                    with st.expander("Review this link"):
                        with st.form(f"review-{key}"):
                            verdict = st.selectbox("Your judgment", EVIDENCE_VERDICTS,
                                                   index=EVIDENCE_VERDICTS.index(review["verdict"]) if review else None,
                                                   format_func=REVIEW.get, placeholder="Choose a judgment")
                            note = st.text_area("Review note (optional)", value=review["note"] if review else "",
                                                max_chars=2000)
                            if st.form_submit_button("Save evidence review"):
                                save_and_refresh(save_evidence_review, run_id, selected, source_id, verdict, note)
    linked_ids = {link["source_id"] for link in report["links"]}
    leads = [source for source in report["sources"] if source["id"] not in linked_ids]
    if leads:
        with st.expander(f"Unlinked research leads · {len(leads)}"):
            st.caption("Open these leads to investigate them. They do not change the assumption’s status.")
            for source in leads:
                st.markdown(f"**{plain(source['title'])}**")
                source_passage(source)


def show_test_and_outcome(exp: dict, outcome: dict, run_id: int | None, experiment_id: int | None = None) -> None:
    left, right = st.columns([1.07, 1.0], gap="large")
    with left, st.container(border=True):
        st.markdown(f"### {plain(exp['title'])}")
        st.caption(f"Tests assumption {exp['assumption_id']}")
        for label, field in (("Procedure", "procedure"), ("Measure", "metric"),
                             ("Decision threshold", "threshold")):
            st.markdown(f"**{label}**")
            st.markdown(plain(exp[field]))
        st.caption(f"Time · {exp['time']}  |  Estimated cost · {exp['cost']}")
    with right, st.container(border=True):
        st.markdown("### Record the outcome")
        st.caption("Enter real observations after running the test. Your decision is saved separately from the research.")
        if run_id is None:
            st.info("Save the analysis before recording outcomes.")
            return
        with st.form(f"outcome-{run_id}-{experiment_id}"):
            status = st.selectbox("Test status", OUTCOME_STATUSES, format_func=str.title,
                                  index=OUTCOME_STATUSES.index(outcome.get("status", "planned")))
            a, b = st.columns(2)
            with a:
                observed = st.number_input("Total observed", min_value=0, max_value=1_000_000,
                                           value=outcome.get("participants"), step=1)
            with b:
                qualifying = st.number_input("Met criterion", min_value=0, max_value=1_000_000,
                                             value=outcome.get("qualifying"), step=1)
            notes = st.text_area("Observations", value=outcome.get("notes", ""), max_chars=4000)
            decision = st.selectbox("Founder decision", OUTCOME_DECISIONS, format_func=DECISION.get,
                                    index=OUTCOME_DECISIONS.index(outcome.get("decision", "undecided")))
            if st.form_submit_button("Save experiment outcome", type="primary"):
                if experiment_id is None:
                    save_and_refresh(save_experiment_outcome, run_id, status, observed, qualifying, notes, decision)
                else:
                    save_and_refresh(save_followup_outcome, run_id, experiment_id, status, observed, qualifying, notes, decision)


def show_experiment(report: dict, workspace: dict, run_id: int | None) -> None:
    st.subheader("Experiments")
    original = report.get("experiment") or workspace.get("plan")
    priority = workspace["priority"]
    ids = [row["id"] for row in report["assumptions"]]
    suggested = priority["id"] if priority else ids[0] if ids else None
    if not original:
        if run_id is not None and ids:
            st.caption("Choose a measurable threshold before collecting observations.")
            with st.form(f"later-plan-{run_id}"):
                plan = experiment_form_fields(f"later-plan-{run_id}", ids, suggested)
                if st.form_submit_button("Save test plan", type="primary"):
                    save_and_refresh(save_founder_plan, run_id, plan)
        else:
            st.info("Save an analysis with at least one assumption to plan a test.")
        return
    followups = {row["id"]: row for row in workspace["followups"]}
    if priority:
        st.caption(f'Current research priority · {priority["id"]} · {priority["statement"]}')
    if followups:
        def plan_label(key: int) -> str:
            return (f'{followups[key]["plan"]["assumption_id"]} · {followups[key]["plan"]["title"]}'
                    if key else f'Original · {original["title"]}')

        selected = st.selectbox("View test plan", [*followups, 0], format_func=plan_label,
                                key=f"test-selection-{run_id}")
    else:
        selected = 0
    record = followups[selected] if selected else {"plan": original, "outcome": workspace.get("outcome")}
    show_test_and_outcome(record["plan"], record["outcome"] or {}, run_id, selected or None)
    if run_id is not None and ids:
        with st.expander("Plan a follow-up test"):
            st.caption("Save a new procedure and threshold. You can return to view any earlier plan and outcome.")
            with st.form(f"followup-{run_id}"):
                plan = experiment_form_fields(f"followup-{run_id}", ids, suggested)
                if st.form_submit_button("Save follow-up test", type="primary"):
                    save_and_refresh(save_followup_experiment, run_id, plan)


def show_trace(report: dict, workspace: dict) -> None:
    st.subheader("Run trace")
    usage = report["usage"]
    a, b, c, d = st.columns(4)
    a.metric("Model calls", usage["model_calls"])
    b.metric("Search submissions" if report["mode"] == "local" else "Search calls", usage["search_calls"])
    c.metric("Source records", len(report["sources"]))
    d.metric("Duration", f"{usage['elapsed_seconds']:.2f}s")
    if usage.get("model"):
        st.caption(f'{usage["model"]} · {usage["input_tokens"]:,} input tokens · {usage["output_tokens"]:,} output tokens')
    if (cost := usage.get("estimated_model_cost_usd")) is not None:
        st.caption(f"Estimated model cost · ${cost:.4f} USD, excluding search")
    for event in report["trace"]:
        st.markdown(f"**{plain(event['stage'])}** · {plain(event['detail'])}")
    for warning in report["warnings"]:
        st.warning(warning)
    if workspace["rounds"]:
        st.caption(count_label(len(workspace["rounds"]), "completed follow-up search"))
    if workspace["reviews"] or workspace["outcome"] or workspace.get("plan"):
        st.markdown("**Founder activity**")
        if plan := workspace.get("plan"):
            st.caption(f'{plan["assumption_id"]} · Test plan added · {plan["title"]}')
        for review in workspace["reviews"]:
            st.caption(f'{review["assumption_id"]} · {review["source_id"]} · {REVIEW[review["verdict"]]} · {review["updated_at"]}')
        if outcome := workspace["outcome"]:
            st.caption(f'{outcome["assumption_id"]} · {outcome["status"].title()} · {DECISION[outcome["decision"]]} · {outcome["updated_at"]}')
    if workspace["priority_updates"]:
        st.markdown("**Risk revisions**")
        previous = {row["id"]: row["risk"] for row in report["assumptions"]}
        for row in workspace["priority_updates"]:
            aid = row["assumption_id"]
            updated_risk = row["impact"] * row["uncertainty"]
            st.caption(f'{aid} · {previous[aid]}/25 → {updated_risk}/25 · {row["created_at"]}')
            st.text(row["reason"])
            previous[aid] = updated_risk
    if workspace["activity"]:
        with st.expander("Workspace change log", expanded=True):
            for event in workspace["activity"]:
                detail = event["detail"]
                label = event["kind"].replace("_", " ").replace("followup", "follow-up").capitalize()
                ref = detail.get("assumption_id") or f'Round {detail.get("round_id")}'
                suffix = ""
                if detail.get("source_id"):
                    suffix = f' · {detail["source_id"]}'
                if detail.get("verdict"):
                    suffix += f' · {REVIEW[detail["verdict"]]}'
                    if detail.get("previous_verdict") and detail["previous_verdict"] != detail["verdict"]:
                        suffix += f' (was {REVIEW[detail["previous_verdict"]]})'
                if detail.get("experiment_id"):
                    suffix += f' · Test {detail["experiment_id"]}'
                if detail.get("decision"):
                    suffix += f' · {DECISION[detail["decision"]]}'
                st.caption(f'{event["created_at"]} · {label} · {ref}{suffix}')


def analysis_page(report: dict, run_id: int | None) -> None:
    workspace = {"reviews": [], "outcome": None, "plan": None, "priority_updates": [], "followups": []}
    research = {"sources": [], "links": [], "rounds": [], "activity": []}
    if run_id is not None:
        try:
            workspace.update(load_workspace(run_id))
            research = load_research(run_id)
            workspace["priority_updates"] = load_priority_updates(run_id)
            workspace["followups"] = list_followup_experiments(run_id)
        except (sqlite3.Error, OSError):
            st.warning("Some saved workspace activity is unavailable.")
    report = {**report, "sources": [*report["sources"], *research["sources"]],
              "links": [*report["links"], *research["links"]]}
    assumptions = current_assumptions(report, workspace["reviews"], workspace["priority_updates"])
    workspace.update(priority=next_priority(assumptions), rounds=research["rounds"], activity=research["activity"])
    mode = MODES.get(report["mode"], "Research")
    linked_ids = {link["source_id"] for link in report["links"]}
    counts = [count_label(len(assumptions), "assumption"), count_label(len(linked_ids), "linked source")]
    if unlinked := len(report["sources"]) - len(linked_ids):
        counts.append(count_label(unlinked, "research lead"))
    counts.append(count_label(len(workspace["reviews"]), "evidence review"))
    st.html(f'<div class="id-case-head"><div class="id-row-meta">{pill(mode)}'
            f'{pill(report["status"].title(), report["status"])}</div>'
            f'<h1>{h(report["brief"]["title"])}</h1>'
            f'<p>{h(" · ".join(counts))}</p></div>')
    if report["status"] == "partial":
        st.warning("This run stopped early. The available evidence and the reason are saved in Run trace.")
    view = st.segmented_control("Analysis section", ["Overview", "Research", "Evidence", "Experiment", "Run trace"],
                                default="Overview", key=f"section-{run_id}", label_visibility="collapsed")
    if view == "Research":
        show_research(report, research, run_id, save_and_refresh, source_passage)
    elif view == "Evidence":
        show_evidence(report, assumptions, workspace, run_id)
    elif view == "Experiment":
        show_experiment(report, workspace, run_id)
    elif view == "Run trace":
        show_trace(report, workspace)
    else:
        show_overview(report, assumptions, workspace, run_id)


sidebar()
if flash := st.session_state.pop("flash", None):
    st.toast(flash)
screen = st.session_state.get("screen", "home")
if screen == "analysis" and (report := st.session_state.get("report")):
    analysis_page(report, st.session_state.get("run_id"))
elif screen == "brief":
    idea_intake(persist_analysis, lambda brief: finish_run(brief, "live", consent=True))
elif screen == "evaluation":
    show_evaluation()
else:
    home()
