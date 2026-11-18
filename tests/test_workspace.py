"""Offline smoke through Streamlit's normal entry point and a fresh session."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from idea_diligence.report import render_markdown
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
    assert next(button for button in app.button if button.label == "Run live analysis").disabled
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
