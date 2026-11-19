"""Continue evidence collection on a saved analysis."""

import streamlit as st

from .public_search import PublicSearchError, search_discussions
from .report import escape_markdown as plain
from .storage import MAX_RESEARCH_ROUNDS, add_founder_evidence, append_research_round


def show_research(
    report: dict, research: dict, run_id: int | None, save, show_source,
) -> None:
    st.subheader("Research rounds")
    st.caption("Return with a public search or an excerpt you want to review against an assumption.")
    if run_id is None:
        st.info("Save an analysis to keep a research history.")
        return

    rounds = research["rounds"]
    left, right = st.columns(2, gap="large")
    with left, st.container(border=True):
        st.markdown("### Find public leads")
        st.caption("Search Hacker News for alternatives or discussions. Search sends the query you enter to Algolia.")
        if len(rounds) >= MAX_RESEARCH_ROUNDS:
            st.info("This analysis has reached its limit of public search rounds.")
        else:
            with st.form(f"research-search-{run_id}", clear_on_submit=False):
                query = st.text_input("Public search terms", max_chars=120,
                                      placeholder="e.g. AI research podcast")
                search = st.form_submit_button("Search and save round", type="primary")
            if search:
                try:
                    with st.spinner("Searching Hacker News…"):
                        leads = search_discussions(query)
                except PublicSearchError as error:
                    st.error(str(error))
                else:
                    save(append_research_round, run_id, query, leads)
    with right, st.container(border=True):
        st.markdown("### Attach an excerpt")
        st.caption("Paste the relevant passage and its URL. Review it in Evidence before making a judgment.")
        assumptions = {row["id"]: row for row in report["assumptions"]}
        if assumptions:
            with st.form(f"research-source-{run_id}-{len(research['links'])}"):
                assumption = st.selectbox(
                    "Assumption", list(assumptions),
                    format_func=lambda aid: f'{aid} · {assumptions[aid]["category"].title()}',
                )
                title = st.text_input("Source title", max_chars=160)
                url = st.text_input("Source URL", max_chars=2000, placeholder="https://…")
                passage = st.text_area("Exact excerpt", max_chars=1200)
                relationship = st.selectbox("Proposed relationship", ("context", "supports", "challenges"),
                                            format_func={"context": "Adds context", "supports": "Supports",
                                                         "challenges": "Challenges"}.get)
                reason = st.text_input("Why it matters (optional)", max_chars=350)
                if st.form_submit_button("Attach excerpt"):
                    save(add_founder_evidence, run_id, assumption, title, url, passage, relationship, reason)
        else:
            st.info("An assumption map is required to attach excerpts.")

    st.subheader("Search history")
    if not rounds:
        st.caption("Your new searches will appear here, including searches with zero results.")
    for index, round_ in enumerate(rounds):
        summary = f'{round_["query"]} · {round_["result_count"]} results · {round_["added_count"]} new'
        with st.expander(summary, expanded=index == 0):
            st.caption(f'{round_["created_at"]} · Hacker News Search')
            if not round_["results"]:
                st.info("No links were returned for this search. Try a different phrase.")
            for source in round_["results"]:
                st.markdown(f"**{plain(source['title'])}**")
                show_source(source)
