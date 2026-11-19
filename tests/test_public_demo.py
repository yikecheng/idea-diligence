from pathlib import Path

from streamlit.testing.v1 import AppTest

from idea_diligence.engine import load_demo_brief, run_analysis
from idea_diligence.storage import recent_runs, save_run


ENTRYPOINT = Path(__file__).resolve().parents[1] / "streamlit_app.py"


def test_public_demo_separates_browser_sessions(monkeypatch, tmp_path):
    private_db = tmp_path / "private.sqlite3"
    monkeypatch.setenv("IDEA_DILIGENCE_DB", str(private_db))
    report = run_analysis(load_demo_brief(), "demo")
    report["brief"]["title"] = "Private research"
    save_run(report, private_db)

    first = AppTest.from_file(str(ENTRYPOINT)).run()
    assert not first.exception
    assert all("Private research" not in item.value for item in first.caption)
    next(button for button in first.button if button.label == "Open Catch Me Up on Anything demo").click().run()
    [history] = [item for item in first.selectbox if item.label == "Saved analysis"]
    assert history.value is None and history.options == ["Catch Me Up on Anything"]

    second = AppTest.from_file(str(ENTRYPOINT)).run()
    assert not second.exception
    assert not any(item.label == "Saved analysis" for item in second.selectbox)
    next(button for button in second.button if button.label == "New idea").click().run()
    assert all("AI research" not in item.options for item in second.radio)
    assert [row[2] for row in recent_runs(private_db)] == ["Private research"]
