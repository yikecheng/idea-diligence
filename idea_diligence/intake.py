"""Intake for founder-led diligence and the optional model research workflow."""

import streamlit as st

from .engine import CATEGORIES, live_available
from .local_analysis import build_local_analysis
from .public_search import PublicSearchError, search_discussions
from .report import escape_markdown

FIELDS = (
    ("title", "Idea name", "How should we refer to this idea?", 120),
    ("customer", "Target customer", "Who has the problem, and in what situation?", 450),
    ("problem", "Problem", "What are they trying to do? Where do they get stuck?", 900),
    ("solution", "Proposed solution", "What would your product do for them?", 900),
    ("known", "What you already know (optional)", "Interviews, behaviors, or competing products you’ve seen.", 1000),
)
EXPERIMENT_FIELDS = (
    ("title", "Test name", 150), ("procedure", "Procedure", 700), ("metric", "Measure", 250),
    ("threshold", "Decision threshold", 350), ("time", "Time", 100), ("cost", "Estimated cost", 180),
)


def brief_fields(prefix: str) -> dict:
    brief = {}
    for key, label, hint, limit in FIELDS:
        field = st.text_input if key in {"title", "customer"} else st.text_area
        brief[key] = field(label, placeholder=hint, max_chars=limit, key=f"{prefix}:{key}")
    return brief


def public_leads(draft: str) -> dict:
    state_key = f"{draft}:research"
    with st.expander("Find public discussion leads"):
        st.caption("Only the search words below go to Hacker News Search. Use a public topic, such as podcast discovery or room booking.")
        with st.form(f"{draft}:find-leads"):
            query = st.text_input("Public search terms", max_chars=120)
            submitted = st.form_submit_button("Search Hacker News")
        if submitted:
            with st.spinner("Searching current Hacker News results…"):
                try:
                    leads = search_discussions(query)
                except PublicSearchError as error:
                    st.warning(str(error))
                else:
                    st.session_state[state_key] = {"query": " ".join(query.split()), "leads": leads}
        result = st.session_state.get(state_key, {})
        if result:
            leads = result["leads"]
            st.caption(f'{len(leads)} results for “{result["query"]}”. The discussion titles are leads to investigate.')
            if not leads:
                st.info("Try a broader term. You can save your analysis with zero search results.")
            for lead in leads:
                st.markdown(f"**{escape_markdown(lead['title'])}**")
                st.caption(lead["passage"])
                st.link_button("Open HN discussion", lead["url"])
            if st.button("Clear these leads", key=f"{draft}:clear"):
                del st.session_state[state_key]
                st.rerun()
        return result


def assumptions_fields(draft: str) -> list[dict]:
    st.subheader("Assumptions")
    st.caption("Write what has to be true for the idea to work. A score of 5 means highest impact or uncertainty.")
    count = st.selectbox("Number of assumptions", range(1, 6), key=f"{draft}:assumption-count")
    assumptions = []
    for index in range(1, count + 1):
        prefix = f"{draft}:a{index}"
        with st.expander(f"Assumption {index}", expanded=index == 1):
            statement = st.text_input("What has to be true?", max_chars=300, key=f"{prefix}:text")
            category_col, impact_col, uncertainty_col = st.columns([1.5, 1, 1])
            with category_col:
                category = st.selectbox("Category", CATEGORIES, format_func=str.title, key=f"{prefix}:category")
            with impact_col:
                impact = st.selectbox("Impact", range(1, 6), index=3, key=f"{prefix}:impact")
            with uncertainty_col:
                uncertainty = st.selectbox("Uncertainty", range(1, 6), index=3, key=f"{prefix}:uncertainty")
            reason = st.text_input("Why it matters (optional)", max_chars=350, key=f"{prefix}:reason")
            assumptions.append({"category": category, "statement": statement, "impact": impact,
                                "uncertainty": uncertainty, "reason": reason})
    return assumptions


def evidence_fields(draft: str, count: int) -> list[dict]:
    evidence = []
    with st.expander("Add source passages"):
        st.caption("Copy the relevant excerpt from a source you inspected. The workspace labels it founder-supplied.")
        source_count = st.selectbox("Number of source passages", range(6), key=f"{draft}:source-count")
        for index in range(1, source_count + 1):
            prefix = f"{draft}:s{index}"
            with st.container(border=True):
                st.markdown(f"**Source {index}**")
                target = st.selectbox("Links to", [f"A{i}" for i in range(1, count + 1)], key=f"{prefix}:a")
                title = st.text_input("Source title", max_chars=160, key=f"{prefix}:title")
                url = st.text_input("Public source URL", max_chars=2000, key=f"{prefix}:url")
                passage = st.text_area("Exact excerpt", max_chars=450, key=f"{prefix}:quote")
                stance = st.selectbox("Your initial reading", ("context", "supports", "challenges"),
                                      format_func=str.title, key=f"{prefix}:stance")
                reason = st.text_input("Why this passage matters (optional)", max_chars=300, key=f"{prefix}:reason")
                evidence.append({"assumption_id": target, "title": title, "url": url, "passage": passage,
                                 "stance": stance, "reason": reason})
    return evidence


def experiment_fields(draft: str, count: int) -> dict | None:
    with st.expander("Plan an experiment"):
        if not st.checkbox("Include a test plan", key=f"{draft}:has-experiment"):
            return None
        return experiment_form_fields(draft, [f"A{i}" for i in range(1, count + 1)])


def experiment_form_fields(prefix: str, assumption_ids: list[str], suggested: str | None = None) -> dict:
    choices = ["Highest risk", *assumption_ids] if suggested is None else assumption_ids
    target = st.selectbox("Assumption to test", choices, index=choices.index(suggested) if suggested else 0,
                          key=f"{prefix}:test-a")
    experiment = {} if target == "Highest risk" else {"assumption_id": target}
    for field, label, limit in EXPERIMENT_FIELDS:
        widget = st.text_area if field in {"procedure", "threshold"} else st.text_input
        experiment[field] = widget(label, max_chars=limit, key=f"{prefix}:test-{field}")
    return experiment


def local_workspace(on_report) -> None:
    draft = f"draft-{st.session_state.get('draft-sequence', 0)}"
    leads = public_leads(draft)
    with st.container(border=True):
        st.subheader("Idea brief")
        brief = brief_fields(draft)
    assumptions = assumptions_fields(draft)
    evidence = evidence_fields(draft, len(assumptions))
    experiment = experiment_fields(draft, len(assumptions))
    if st.button("Save analysis", type="primary"):
        try:
            report = build_local_analysis(
                brief, assumptions, evidence, experiment, leads=leads.get("leads", ()),
                discovery_queries=(leads["query"],) if leads else (),
            )
        except ValueError as error:
            st.error(str(error))
        else:
            st.session_state.pop(f"{draft}:research", None)
            st.session_state["draft-sequence"] = st.session_state.get("draft-sequence", 0) + 1
            on_report(report)


def idea_intake(on_report, on_live, *, visitor_demo: bool = False) -> None:
    st.title("Research an idea")
    if visitor_demo:
        st.caption("Enter a public or fictional idea for this browser session.")
        local_workspace(on_report)
        return
    mode = st.radio("Research mode", ("Local evidence review", "AI research"), horizontal=True)
    if mode == "Local evidence review":
        st.markdown("Bring your own assumptions and evidence. Record a test, then revisit the analysis as you learn.")
        local_workspace(on_report)
        return
    if not live_available():
        st.info("AI research requires both model and search keys. The local evidence review works without them.")
        return
    st.caption("The model drafts assumptions and maps search findings to the idea. You can review the evidence afterward.")
    with st.form("ai-brief"):
        brief = brief_fields("ai")
        consent = st.checkbox("This idea is public or fictional. I agree to send the brief and search queries to the configured providers.")
        submitted = st.form_submit_button("Run live analysis", type="primary")
    if submitted:
        if consent:
            on_live(brief)
        else:
            st.error("Confirm that the brief can be sent to the configured providers.")
