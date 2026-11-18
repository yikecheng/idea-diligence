"""Render the same analysis as a portable human-readable Markdown file."""

import re
from urllib.parse import quote


def escape_markdown(value: str) -> str:
    return re.sub(r"([\\`*_{}\[\]<>#+\-.!|:$])", r"\\\1", str(value))


def render_markdown(report: dict) -> str:
    plain = escape_markdown
    brief = report["brief"]
    mode = "Curated evidence replay" if report["mode"] == "demo" else "Live model and search"
    lines = [f"# {plain(brief['title'])}", "", f"Mode: {mode} · Run: {report['status']}", "", "## Idea brief"]
    for key, label in (("customer", "Customer"), ("problem", "Problem"),
                       ("solution", "Solution"), ("known", "What we know")):
        if brief.get(key):
            lines.append(f"- **{label}:** {plain(brief[key])}")
    lines += ["", "## Assumptions and evidence", "",
              "Risk is impact × uncertainty on two 1–5 scales. Scores prioritize research effort.", ""]
    sources = {source["id"]: source for source in report.get("sources", [])}
    for assumption in report.get("assumptions", []):
        lines += [f"### {assumption['id']} · {plain(assumption['statement'])}", "",
                  f"{assumption['category']} · {assumption['status'].title()} · Risk {assumption['risk']}/25",
                  "", plain(assumption["reason"]), ""]
        for link in report.get("links", []):
            if link["assumption_id"] != assumption["id"] or link["source_id"] not in sources:
                continue
            source = sources[link["source_id"]]
            url = quote(source["url"], safe=":/?#[]@!$&'()*+,;=%-._~")
            lines += [f"**{link['stance'].title()}** · {plain(link['reason'])}",
                      *[f"> {plain(line)}" for line in source["passage"].splitlines()],
                      f"[{plain(source['title'])}](<{url}>) · {source['kind'].replace('_', ' ')} · {source['retrieved_at']}", ""]
    experiment = report.get("experiment")
    lines += ["## Recommended experiment", ""]
    if experiment:
        lines += [f"### {plain(experiment['title'])}", ""]
        for key, label in (("assumption_id", "Assumption"), ("procedure", "Procedure"),
                           ("metric", "Measure"), ("threshold", "Decision threshold"),
                           ("time", "Time"), ("cost", "Estimated cost")):
            lines.append(f"- **{label}:** {plain(experiment[key])}")
    else:
        lines.append("No experiment was generated in this run.")
    linked_ids = {link["source_id"] for link in report.get("links", [])}
    leads = [source for source in sources.values() if source["id"] not in linked_ids]
    if leads:
        lines += ["", "## Unlinked research leads", ""]
        for source in leads:
            url = quote(source["url"], safe=":/?#[]@!$&'()*+,;=%-._~")
            lines += [f"[{plain(source['title'])}](<{url}>) · {source['kind'].replace('_', ' ')} · {source['retrieved_at']}",
                      *[f"> {plain(line)}" for line in source["passage"].splitlines()], ""]
    if report.get("warnings"):
        lines += ["", "## Limitations", "", *[f"- {plain(item)}" for item in report["warnings"]]]
    lines += ["", "## Run trace", ""]
    lines += [f"- **{plain(event['stage'])}:** {plain(event['detail'])}" for event in report.get("trace", [])]
    lines += ["", "Usage: " + ", ".join(f"{key.replace('_', ' ')} {value}" for key, value in report["usage"].items())]
    return "\n".join(lines) + "\n"
