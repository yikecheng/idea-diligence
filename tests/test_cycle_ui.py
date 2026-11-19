"""Exercise a founder's second visit through the Streamlit entry point."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from idea_diligence.storage import list_followup_experiments, load_research, load_run, load_workspace, recent_runs


APP = Path(__file__).resolve().parents[1] / "app.py"


def widget(elements, label):
    return next(element for element in elements if element.label == label)


def run(app):
    # AppTest serializes a segmented control's single value as a list of choices.
    if app.button_group and isinstance((control := app.button_group[0]).value, str):
        control.set_value([control.value])
    app.run()
    assert not app.exception and not app.error


def click(app, label):
    widget(app.button, label).click()
    run(app)


def section(app, run_id, name):
    app.button_group(key=f"section-{run_id}").set_value([name])
    run(app)


def current_priority(app):
    return next(item.proto.body for item in app.get("html") if "CURRENT RESEARCH PRIORITY" in item.proto.body)


def test_founder_revisits_a_saved_run_after_new_evidence(monkeypatch, tmp_path):
    database = tmp_path / "idea-diligence.sqlite3"
    monkeypatch.setenv("IDEA_DILIGENCE_DB", str(database))
    query = "audio briefings for founders"
    observed_queries = []

    def search(terms):
        observed_queries.append(terms)
        return [{"title": "Audio briefing discussion", "url": "https://news.ycombinator.com/item?id=115500",
                 "passage": "Hacker News discussion · 2 comments", "retrieved_at": "2026-11-18"}]

    monkeypatch.setattr("idea_diligence.research_ui.search_discussions", search)
    first_visit = AppTest.from_file(str(APP)).run()
    click(first_visit, "Open Catch Me Up on Anything demo")
    [(run_id, _, _, _)] = recent_runs(database)
    original = load_run(run_id, database)

    app = AppTest.from_file(str(APP)).run()
    app.selectbox[0].select(run_id).run()
    click(app, "Open saved analysis")
    assert "A1 · 25/25 risk" in current_priority(app)
    section(app, run_id, "Research")
    widget(app.text_input, "Public search terms").set_value(query)
    click(app, "Search and save round")
    assert observed_queries == [query]
    assert any(query in expander.label and "1 new" in expander.label for expander in app.expander)

    excerpt = "Five of six participants already requested another briefing."
    widget(app.selectbox, "Assumption").select("A1")
    widget(app.text_input, "Source title").set_value("Pilot interview notes")
    widget(app.text_input, "Source URL").set_value("https://example.org/briefing-pilot")
    widget(app.text_area, "Exact excerpt").set_value(excerpt)
    widget(app.selectbox, "Proposed relationship").select("supports")
    click(app, "Attach excerpt")

    section(app, run_id, "Evidence")
    assert widget(app.radio, "Choose an assumption").value == "A1"
    assert any(excerpt in item.proto.body for item in app.get("html"))
    widget(app.selectbox, "Your judgment").select("accept")
    widget(app.text_area, "Review note (optional)").set_value("Useful pilot context for repeat demand.")
    click(app, "Save evidence review")
    [review] = load_workspace(run_id, database)["reviews"]
    assert (review["assumption_id"], review["source_id"], review["verdict"]) == ("A1", "FS1", "accept")
    assert load_research(run_id, database)["links"][0]["stance"] == "context"

    section(app, run_id, "Overview")
    widget(app.selectbox, "Assumption to update").select("A1")
    run(app)
    widget(app.selectbox, "Uncertainty").select(2)
    widget(app.text_area, "What changed?").set_value("FS1 reduced uncertainty enough to test payment next.")
    click(app, "Save risk update")
    assert "A5 · 16/25 risk" in current_priority(app)

    section(app, run_id, "Experiment")
    assert widget(app.selectbox, "Assumption to test").value == "A5"
    widget(app.text_input, "Test name").set_value("Paid repeat briefing")
    widget(app.text_area, "Procedure").set_value("Offer a paid briefing to six recent repeat listeners.")
    widget(app.text_input, "Measure").set_value("Listeners who pay")
    widget(app.text_area, "Decision threshold").set_value("At least three of six listeners pay.")
    widget(app.text_input, "Time").set_value("One week")
    widget(app.text_input, "Estimated cost").set_value("$15")
    click(app, "Save follow-up test")
    [test] = list_followup_experiments(run_id, database)
    assert widget(app.selectbox, "View test plan").value == test["id"]
    widget(app.selectbox, "Test status").select("completed")
    widget(app.number_input, "Total observed").set_value(6)
    widget(app.number_input, "Met criterion").set_value(2)
    widget(app.selectbox, "Founder decision").select("revise")
    click(app, "Save experiment outcome")
    [test] = list_followup_experiments(run_id, database)
    assert test["outcome"]["decision"] == "revise" and test["outcome"]["qualifying"] == 2
    assert test["plan"]["threshold"] == "At least three of six listeners pay."
    assert load_workspace(run_id, database)["outcome"] is None
    assert load_run(run_id, database) == original

    section(app, run_id, "Run trace")
    assert any("A1 · 25/25 → 10/25" in caption.value for caption in app.caption)
    assert any("Follow-up outcome · A5" in caption.value for caption in app.caption)
