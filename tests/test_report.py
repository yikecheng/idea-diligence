"""Tests for portable and review-aware diligence memos."""

from copy import deepcopy
from html.parser import HTMLParser

from idea_diligence.engine import load_demo_brief, run_analysis
from idea_diligence.report import render_html, render_markdown


class MemoParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        if tag == "a":
            self.links.append(dict(attrs).get("href"))


def test_memos_preserve_sources_and_show_founder_review_and_outcome():
    report = run_analysis(load_demo_brief(), "demo")
    workspace = {
        "reviews": [
            {
                "assumption_id": "A2",
                "source_id": "S1",
                "verdict": "question",
                "note": "Check whether visitors can inspect cited articles.",
            }
        ],
        "outcome": {
            "assumption_id": "A1",
            "status": "completed",
            "participants": 8,
            "qualifying": 3,
            "decision": "revise",
            "notes": "Interview the five people who did not return.",
        },
    }
    original = deepcopy(report)
    for render in (render_markdown, render_html):
        memo = render(report, workspace)
        assert "Founder decision" in memo
        assert "Revise" in memo
        assert "3 of 8 met the metric" in memo
        assert "4 of 8" in memo
        assert "https://www.anypod.fm/about" in memo
        assert "Questioned" in memo
        assert "inspect cited articles" in memo
        assert "did not return" in memo
    assert report == original


def test_document_renders_malicious_markup_as_text_and_filters_unsafe_links():
    report = run_analysis(load_demo_brief(), "demo")
    report["brief"]["title"] = '<img src=x onerror="alert(1)">'
    report["sources"][0]["url"] = "javascript:alert(1)"
    report["sources"][1]["url"] = "https://viewer:password@example.com/"
    report["sources"][2]["url"] = 'https://example.org/?a="x"&b=2'
    report["sources"][2]["passage"] = "</blockquote><script>an unwanted script</script>"
    html = render_html(report)
    parsed = MemoParser()
    parsed.feed(html)
    assert "img" not in parsed.tags
    assert "script" not in parsed.tags
    assert "javascript:alert(1)" not in html
    assert "viewer:password" not in html
    assert "https://example.org/?a=%22x%22&b=2" in parsed.links
    markdown = render_markdown(report)
    assert "javascript:alert(1)" not in markdown
    assert "viewer:password" not in markdown
    assert r"\<img" in markdown


def test_partial_report_without_experiment_renders_for_review():
    report = run_analysis(load_demo_brief(), "demo")
    report["status"] = "partial"
    report["experiment"] = None
    report["links"] = []
    report["warnings"] = ["Evidence assessment is pending."]
    for render in (render_markdown, render_html):
        memo = render(report)
        assert "Partial" in memo
        assert "Awaiting an experiment recommendation" in memo
        assert "Unlinked research leads" in memo
        assert "Evidence assessment is pending" in memo
