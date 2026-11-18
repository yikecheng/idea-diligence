"""Offline smoke through Streamlit's normal entry point and a fresh session."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from idea_diligence.report import render_html, render_markdown
from idea_diligence.storage import load_run, recent_runs


APP = Path(__file__).resolve().parents[1] / "app.py"


def click(app: AppTest, label: str) -> AppTest:
    return next(button for button in app.button if button.label == label).click().run()


def test_curated_workspace_is_reproducible_and_persisted(monkeypatch, tmp_path):
    database = tmp_path / "runs.sqlite3"
    monkeypatch.setenv("IDEA_DILIGENCE_DB", str(database))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    app = AppTest.from_file(str(APP)).run()
    assert not app.exception
    click(app, "New idea")
    app.radio[0].set_value("AI research").run()
    assert any("requires both model and search keys" in note.value for note in app.info)
    click(app, "Workspace home")

    click(app, "Open Catch Me Up on Anything demo")

    assert not app.exception
    assert any("Assumption map" == header.value for header in app.subheader)
    assert len(app.get("download_button")) == 2
    [(run_id, _, title, mode)] = recent_runs(database)
    assert title == "Catch Me Up on Anything" and mode == "demo"
    report = load_run(run_id, database)
    exported = render_markdown(report)
    assert "https://www.anypod.fm/about" in exported
    assert "4 of 8" in exported

    reopened = AppTest.from_file(str(APP)).run()
    reopened.selectbox[0].select(run_id).run()
    click(reopened, "Open saved analysis")
    assert not reopened.exception
    assert any("Assumption map" == header.value for header in reopened.subheader)


def test_local_intake_research_does_not_use_demo_data(monkeypatch, tmp_path):
    database = tmp_path / "runs.sqlite3"
    monkeypatch.setenv("IDEA_DILIGENCE_DB", str(database))
    monkeypatch.setattr("idea_diligence.intake.search_discussions", lambda terms: [
        {"title": f"Public discussion about {terms}", "url": "https://news.ycombinator.com/item?id=112233",
         "passage": "Hacker News · 2 comments", "kind": "discussion_lead", "retrieved_at": "2026-11-18"}
    ])
    app = AppTest.from_file(str(APP)).run()
    click(app, "New idea")
    click(app, "Save analysis")
    assert app.error and "title" in app.error[0].value

    next(field for field in app.text_input if field.label == "Public search terms").set_value("Study room booking")
    click(app, "Search Hacker News")
    app.text_input(key="draft-0:title").set_value("Study Room Watch")
    app.text_input(key="draft-0:customer").set_value("Students booking group rooms after class")
    app.text_area(key="draft-0:problem").set_value("Group rooms fill before students find a usable time.")
    app.text_area(key="draft-0:solution").set_value("Send an alert when a room opens up.")
    app.text_input(key="draft-0:a1:text").set_value("Students act on a same-day opening alert.")
    click(app, "Save analysis")
    assert not app.exception
    [(run, _, title, mode)] = recent_runs(database)
    assert (title, mode) == ("Study Room Watch", "local")
    report = load_run(run, database)
    assert report["assumptions"][0]["status"] == "open"
    assert report["usage"]["model_calls"] == 0 and report["usage"]["search_calls"] == 1
    assert report["links"] == [] and report["sources"][0]["kind"] == "discussion_lead"
    assert "Local evidence review" in render_html(report)
