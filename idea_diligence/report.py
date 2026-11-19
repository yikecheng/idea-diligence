"""Render a portable diligence memo from a run and its optional human decisions."""

from html import escape
import re
from urllib.parse import quote, urlsplit


BRIEF_FIELDS = (
    ("customer", "Target customer"),
    ("problem", "Problem"),
    ("solution", "Proposed solution"),
    ("known", "Starting evidence"),
)
EXPERIMENT_FIELDS = (
    ("assumption_id", "Assumption"),
    ("procedure", "Procedure"),
    ("metric", "Measure"),
    ("threshold", "Decision threshold"),
    ("time", "Time"),
    ("cost", "Estimated cost"),
)
REVIEW_LABELS = {"accept": "Accepted", "question": "Questioned", "exclude": "Excluded"}


def escape_markdown(value: str) -> str:
    return re.sub(r"([\\\x60*_{}\[\]<>#+\-.!|:$])", r"\\\1", str(value))


def _html(value: object) -> str:
    return escape(str(value), quote=True)


def _web_url(value: object) -> str:
    url = str(value).strip()
    if re.search(r"[\s\\\x00-\x1f\x7f]", url):
        return ""
    try:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname or parts.username is not None:
            return ""
        _ = parts.port
    except ValueError:
        return ""
    return quote(url, safe=":/?#[]@!$&'()*+,;=%-._~")


def _source_rows(report: dict, workspace: dict) -> tuple[dict, list]:
    sources = {source["id"]: source for source in report.get("sources", [])}
    reviews = {
        (item["assumption_id"], item["source_id"]): item
        for item in workspace.get("reviews", [])
    }
    grouped = {}
    linked_ids = set()
    for link in report.get("links", []):
        source_id = link["source_id"]
        if source_id in sources:
            assumption_id = link["assumption_id"]
            review = reviews.get((assumption_id, source_id))
            grouped.setdefault(assumption_id, []).append((link, sources[source_id], review))
            linked_ids.add(source_id)
    return grouped, [source for sid, source in sources.items() if sid not in linked_ids]


def _mode(report: dict) -> str:
    return {"demo": "Curated evidence replay", "live": "Live model and search",
            "local": "Local evidence review"}.get(report["mode"], "Research")


def _observed_metric(outcome: dict) -> str:
    participants = outcome.get("participants")
    qualifying = outcome.get("qualifying")
    if participants is None:
        return "Awaiting participant counts"
    if qualifying is None:
        return f"{participants} participants recorded"
    return f"{qualifying} of {participants} met the metric"


def _review_label(review: dict) -> str:
    return REVIEW_LABELS.get(review.get("verdict"), "Reviewed")


def _markdown_source(source: dict) -> str:
    title = escape_markdown(source["title"])
    if url := _web_url(source.get("url")):
        title = f"[{title}](<{url}>)"
    kind = escape_markdown(source["kind"].replace("_", " "))
    date = escape_markdown(source["retrieved_at"])
    return f"{title} · {kind} · {date}"


def _revision_rows(report: dict, workspace: dict):
    scores = {row["id"]: row["risk"] for row in report.get("assumptions", [])}
    for update in workspace.get("priority_updates", []):
        aid = update["assumption_id"]
        before = scores[aid]
        after = update["impact"] * update["uncertainty"]
        scores[aid] = after
        yield f"{aid} · {before}/25 → {after}/25 · {update['created_at']}", update["reason"]


def _followups(workspace: dict) -> list[dict]:
    return list(reversed(workspace.get("followups", [])))


def render_markdown(report: dict, workspace: dict | None = None) -> str:
    plain = escape_markdown
    workspace = workspace or {}
    brief = report["brief"]
    grouped, leads = _source_rows(report, workspace)
    lines = [f"# {plain(brief['title'])}", "", f"Idea Diligence memo · {_mode(report)} · {plain(report['status'].title())} run",
             "", "## Idea brief", ""]
    for key, label in BRIEF_FIELDS:
        if brief.get(key):
            lines.append(f"- **{label}** — {plain(brief[key])}")
    if priority := workspace.get("priority"):
        lines += ["", "## Current research priority", "",
                  f"**{plain(priority['id'])}** · {plain(priority['statement'])}",
                  f"Current risk {priority['current_risk']}/25.",
                  ""]
        if update := priority.get("priority_update"):
            lines.append(plain(update["reason"]))
    if revisions := list(_revision_rows(report, workspace)):
        lines += ["", "## Risk revisions", "",
                  *[f"- {plain(label)} · {plain(reason)}" for label, reason in revisions]]
    lines += ["", "## Assumptions and evidence", "",
              "Risk is impact × uncertainty on two 1–5 scales. Statuses reflect the recorded research run.", ""]
    for row in report.get("assumptions", []):
        aid = row["id"]
        lines += [f"### {plain(aid)} · {plain(row['statement'])}", "",
                  f"{plain(row['category'].title())} · {plain(row['status'].title())} · Risk {plain(row['risk'])}/25",
                  "", plain(row["reason"]), ""]
        for link, source, review in grouped.get(aid, []):
            lines.append(f"**{plain(link['stance'].title())}** · {plain(link['reason'])}")
            if proposed := link.get("proposed_stance"):
                lines.append(f"Founder proposal · {plain(proposed.title())}")
            lines += [*[f"> {plain(line)}" for line in source["passage"].splitlines()], _markdown_source(source)]
            if review:
                lines.append(f"**Founder review** — {_review_label(review)}"
                             + (f" · {plain(review['note'])}" if review.get("note") else ""))
            lines.append("")
    experiment = report.get("experiment") or workspace.get("plan")
    experiment_label = "Experiment plan" if workspace.get("plan") or report["mode"] == "local" else "Recommended experiment"
    lines += [f"## {experiment_label}", ""]
    if experiment:
        lines += [f"### {plain(experiment['title'])}", ""]
        for key, label in EXPERIMENT_FIELDS:
            lines.append(f"- **{label}** — {plain(experiment[key])}")
    else:
        lines.append("Awaiting an experiment recommendation.")
    if outcome := workspace.get("outcome"):
        decision = plain(outcome["decision"].title())
        lines += ["", "## Founder decision", "",
                  f"**{decision}** · {plain(outcome['status'].title())} · {plain(_observed_metric(outcome))}"]
        if outcome.get("notes"):
            lines += ["", plain(outcome["notes"])]
    if followups := _followups(workspace):
        lines += ["", "## Follow-up experiments"]
        for record in followups:
            plan = record["plan"]
            lines += ["", f"### {plain(plan['title'])}", "",
                      *[f"- **{label}** — {plain(plan[key])}" for key, label in EXPERIMENT_FIELDS]]
            if outcome := record["outcome"]:
                lines += ["", f"**{plain(outcome['decision'].title())}** · {plain(outcome['status'].title())}"
                          f" · {plain(_observed_metric(outcome))}", "", plain(outcome["notes"])]
    if rounds := workspace.get("rounds"):
        lines += ["", "## Follow-up search history", ""]
        for record in reversed(rounds):
            lines.append(f"- {plain(record['query'])} · {record['result_count']} results"
                         f" · {record['added_count']} new · {plain(record['created_at'])}")
    if leads:
        lines += ["", "## Unlinked research leads", ""]
        for source in leads:
            lines += [_markdown_source(source), *[f"> {plain(line)}" for line in source["passage"].splitlines()], ""]
    if report.get("warnings"):
        lines += ["", "## Limitations", "", *[f"- {plain(item)}" for item in report["warnings"]]]
    lines += ["", "## Run trace", ""]
    lines += [f"- **{plain(event['stage'])}** — {plain(event['detail'])}" for event in report.get("trace", [])]
    usage = report.get("usage", {})
    if usage:
        lines += ["", "Usage — " + ", ".join(f"{plain(key.replace('_', ' '))} {plain(value)}"
                                             for key, value in usage.items() if value is not None)]
    return "\n".join(lines) + "\n"


def _html_source(source: dict) -> str:
    title = _html(source["title"])
    if url := _web_url(source.get("url")):
        title = f'<a href="{_html(url)}" rel="noopener noreferrer">{title}</a>'
    kind = _html(source["kind"].replace("_", " ").title())
    date = _html(source["retrieved_at"])
    return f'<blockquote>{_html(source["passage"])}</blockquote><p class="source">{title} · {kind} · {date}</p>'


def _html_evidence(grouped: dict, assumptions: list) -> str:
    cards = []
    for row in assumptions:
        aid = row["id"]
        evidence = []
        for link, source, review in grouped.get(aid, []):
            stance = _html(link["stance"].title())
            review_html = ""
            if review:
                label = _review_label(review)
                note = f' · {_html(review["note"])}' if review.get("note") else ""
                review_html = f'<p class="review"><strong>Founder review</strong> · {label}{note}</p>'
            proposal = f'<p class="source">Founder proposal · {_html(link["proposed_stance"].title())}</p>' if link.get("proposed_stance") else ""
            evidence.append(
                f'<div class="evidence"><p><strong>{stance}</strong> · {_html(link["reason"])}</p>'
                f'{proposal}{_html_source(source)}{review_html}</div>'
            )
        evidence_html = "".join(evidence) or '<p class="muted">Awaiting source evidence.</p>'
        status = row["status"].lower()
        tone = status if status in {"open", "context", "supported", "challenged", "mixed"} else "context"
        cards.append(
            f'<article class="risk"><div class="risk-meta"><span>{_html(aid)} · {_html(row["category"].title())}</span>'
            f'<span class="signal {tone}">{_html(status.title())}</span>'
            f'<span class="score">Risk {_html(row["risk"])}/25</span></div>'
            f'<h3>{_html(row["statement"])}</h3><p>{_html(row["reason"])}</p>{evidence_html}</article>'
        )
    return "".join(cards) or '<p class="muted">Awaiting an assumption assessment.</p>'


def _html_workspace(report: dict, workspace: dict) -> tuple[str, str]:
    focus = ""
    if priority := workspace.get("priority"):
        update = priority.get("priority_update")
        note = f'<p>{_html(update["reason"])}</p>' if update else ""
        focus = (
            '<section class="next"><h2>Current research priority</h2>'
            f'<h3>{_html(priority["id"])} · {_html(priority["statement"])}</h3>'
            f'<p>Current risk {_html(priority["current_risk"])}/25</p>{note}</section>'
        )
    sections = []
    if revisions := list(_revision_rows(report, workspace)):
        sections.append('<section><h2>Risk revisions</h2><ul>' + "".join(
            f'<li>{_html(label)} · {_html(reason)}</li>' for label, reason in revisions) + '</ul></section>')
    if followups := _followups(workspace):
        cards = []
        for record in followups:
            plan = record["plan"]
            fields = "".join(f'<div><dt>{label}</dt><dd>{_html(plan[key])}</dd></div>'
                             for key, label in EXPERIMENT_FIELDS)
            result = ""
            if outcome := record["outcome"]:
                result = (f'<p><strong>{_html(outcome["decision"].title())}</strong> · '
                          f'{_html(outcome["status"].title())} · {_html(_observed_metric(outcome))}</p>'
                          f'<p class="notes">{_html(outcome["notes"])}</p>')
            cards.append(f'<article class="risk"><h3>{_html(plan["title"])}</h3><dl class="facts">{fields}</dl>{result}</article>')
        sections.append('<section><h2>Follow-up experiments</h2>' + "".join(cards) + '</section>')
    if rounds := workspace.get("rounds"):
        items = "".join(f'<li>{_html(row["query"])} · {row["result_count"]} results · {row["added_count"]} new'
                        f' · {_html(row["created_at"])}</li>' for row in reversed(rounds))
        sections.append(f'<section><h2>Follow-up search history</h2><ul>{items}</ul></section>')
    return focus, "".join(sections)


def render_html(report: dict, workspace: dict | None = None) -> str:
    """Return a self-contained, print-friendly HTML diligence memo."""
    workspace = workspace or {}
    brief = report["brief"]
    grouped, leads = _source_rows(report, workspace)
    assumptions = report.get("assumptions", [])
    experiment = report.get("experiment") or workspace.get("plan")
    experiment_label = "Experiment plan" if workspace.get("plan") or report["mode"] == "local" else "Recommended experiment"
    outcome = workspace.get("outcome")
    brief_html = "".join(f'<div><dt>{label}</dt><dd>{_html(brief[key])}</dd></div>'
                         for key, label in BRIEF_FIELDS if brief.get(key))
    test_html = '<p class="muted">Awaiting an experiment recommendation.</p>'
    focus = ""
    if experiment:
        focus_row = next((row for row in assumptions if row["id"] == experiment["assumption_id"]), None)
        if focus_row:
            focus = f'<p class="focus"><strong>Belief being tested</strong> · {_html(focus_row["statement"])}</p>'
        fields = "".join(f'<div><dt>{label}</dt><dd>{_html(experiment[key])}</dd></div>'
                         for key, label in EXPERIMENT_FIELDS)
        test_html = f'<h3>{_html(experiment["title"])}</h3>{focus}<dl class="facts">{fields}</dl>'
    outcome_html = ""
    if outcome:
        notes = f'<p class="notes">{_html(outcome["notes"])}</p>' if outcome.get("notes") else ""
        outcome_html = (
            '<section class="decision"><h2>Founder decision</h2>'
            f'<h3>{_html(outcome["decision"].title())}</h3>'
            f'<p>{_html(outcome["status"].title())} · {_html(_observed_metric(outcome))}</p>{notes}</section>'
        )
    leads_html = ""
    if leads:
        leads_html = '<section><h2>Unlinked research leads</h2>' + "".join(
            f'<div class="evidence">{_html_source(source)}</div>' for source in leads) + '</section>'
    warnings = "".join(f'<li>{_html(item)}</li>' for item in report.get("warnings", []))
    trace = "".join(f'<li><strong>{_html(item["stage"])}</strong> · {_html(item["detail"])}</li>'
                    for item in report.get("trace", []))
    usage = report.get("usage", {})
    counts = []
    if usage.get("model_calls") is not None:
        counts.append(f'{_html(usage["model_calls"])} model calls')
    if usage.get("search_calls") is not None:
        counts.append(f'{_html(usage["search_calls"])} searches')
    if usage.get("elapsed_seconds") is not None:
        counts.append(f'{_html(usage["elapsed_seconds"])} seconds')
    usage_html = f'<p class="muted">{" · ".join(counts)}</p>' if counts else ""
    provenance_text = {
        "demo": "Curated scenario with source excerpts and a proposed experiment.",
        "local": "The founder supplied the assumptions and any linked excerpts. Public discussions are research leads.",
    }.get(report["mode"], "Research findings reflect the sources retrieved in this run. Customer behavior requires direct evidence.")
    provenance = f'<p class="muted">{_html(provenance_text)}</p>'
    current_focus, workspace_html = _html_workspace(report, workspace)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>{_html(brief['title'])} · Idea Diligence</title>
<style>{MEMO_CSS}</style></head>
<body><main>
<header><p class="brand">Idea Diligence <span>Founder memo</span></p>
<h1>{_html(brief['title'])}</h1>
<p class="run">{_mode(report)} · {_html(report['status'].title())} research run</p></header>
<section><h2>Idea brief</h2><dl class="facts">{brief_html}</dl></section>
{current_focus}
{outcome_html}
<section class="next"><h2>{experiment_label}</h2>{test_html}</section>
<section><h2>Assumptions and evidence</h2>
<p class="muted">Risk is impact × uncertainty. Statuses reflect the recorded research run.</p>
{_html_evidence(grouped, assumptions)}</section>
{workspace_html}
{leads_html}
<section class="provenance"><h2>Run notes</h2>{provenance}{usage_html}
{'<ul>' + warnings + '</ul>' if warnings else ''}
{'<ol>' + trace + '</ol>' if trace else ''}</section>
</main></body></html>
"""


MEMO_CSS = """
:root{color-scheme:light;--ink:#19251f;--forest:#1e473a;--moss:#e9efe9;
--surface:#f5f6f3;--line:#d9e0d9;--muted:#4f645b}
*{box-sizing:border-box}
body{margin:0;background:var(--surface);color:var(--ink);font:16px/1.55 system-ui,sans-serif}
main{max-width:970px;margin:32px auto 48px;padding:0 42px 38px;background:white;border:1px solid var(--line)}
header{padding:30px 0 26px;border-bottom:2px solid var(--forest);margin-bottom:26px}
.brand{font-size:14px;font-weight:760;color:var(--forest);letter-spacing:.02em;margin:0 0 24px}
.brand span{margin-left:10px;padding-left:10px;border-left:1px solid #a8bcb2;color:var(--muted);font-weight:570}
h1,h2,h3{line-height:1.18;margin:0;overflow-wrap:anywhere}
h1{font:700 clamp(2.1rem,5.1vw,3.55rem)/1.05 Georgia,serif;letter-spacing:-.035em}
h2{font:700 1.45rem/1.2 Georgia,serif;color:var(--forest);margin-bottom:12px}
h3{font-size:1.02rem;margin:8px 0}
p,dd{margin:0 0 10px;overflow-wrap:anywhere}
.run,.muted,.source,.risk-meta{color:var(--muted)}
.run{margin:12px 0 0}
section{margin:24px 0}
.facts{display:grid;grid-template-columns:1fr 1fr;gap:12px 24px;margin:0}
dt{font-weight:700;font-size:.88rem;color:var(--forest)}
dd{margin:4px 0 0;white-space:pre-line}
.decision,.next{padding:20px 22px;background:var(--moss);border-left:3px solid var(--forest)}
.decision{background:#f3f4e9}
.focus{margin:0 0 14px}
.notes{white-space:pre-line}
.risk{margin:12px 0;padding:15px 17px;border:1px solid var(--line)}
.risk-meta{display:flex;align-items:center;flex-wrap:wrap;gap:8px;font-size:.88rem}
.score{margin-left:auto}
.signal{background:#e9efe9;color:#254536;padding:1px 7px;font-weight:680;border-radius:3px}
.signal.open,.signal.mixed{background:#f0ecdc;color:#644617}
.signal.challenged{background:#f5e5e1;color:#7f3328}
.signal.context{background:#eeefed;color:#3c5147}
.evidence{border-top:1px solid var(--line);margin-top:12px;padding-top:10px}
.evidence p,.review{margin:0 0 5px}
blockquote{margin:5px 0 6px;padding:0 10px;border-left:2px solid #a1b9ad;color:#364d42;
white-space:pre-line;overflow-wrap:anywhere}
a{color:#225844;text-underline-offset:2px}
.source,.review,.provenance{font-size:.88rem}
.provenance ol,.provenance ul{padding-left:20px;margin:6px 0}
@media(max-width:620px){main{margin:0;border:0;padding:0 20px 24px}.facts{grid-template-columns:1fr}
.decision,.next{padding:14px}.score{margin-left:0}}
@media print{@page{margin:14mm}body{background:white;color:#111;font-size:10pt}
main{border:0;margin:0;padding:0;max-width:none}header{padding:0 0 12px;margin-bottom:14px}
h1{font-size:29pt}h2,h3{break-after:avoid-page}section{margin:14px 0}
.decision,.next,.evidence,.facts>div{break-inside:avoid-page}
.signal,.decision,.next{print-color-adjust:exact;-webkit-print-color-adjust:exact}}
"""
