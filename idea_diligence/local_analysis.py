"""Build a custom workspace from founder-authored assumptions and evidence."""

import re
from datetime import date, datetime, timezone
from time import monotonic
from urllib.parse import urlsplit

from .engine import (
    CATEGORIES,
    EXPERIMENT_FIELDS,
    MAX_ASSUMPTIONS,
    STANCES,
    _clean_brief,
    _result,
    _source_identity,
    _source_url,
    _trace,
    _update_status,
)


def _value(value, label: str, limit: int, *, required: bool = True) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text.")
    value = value.strip()
    if required and not value:
        raise ValueError(f"Enter {label.lower()}.")
    if len(value) > limit:
        raise ValueError(f"{label} can be at most {limit:,} characters.")
    return value


def _records(rows, label: str, maximum: int, *, minimum: int = 0) -> None:
    if not isinstance(rows, (list, tuple)) or not minimum <= len(rows) <= maximum:
        size = f"{minimum}–{maximum}" if minimum else f"at most {maximum}"
        raise ValueError(f"Provide {size} {label}.")
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"Each entry for {label} must be a record.")


def _rank_local_assumptions(rows) -> list[dict]:
    _records(rows, "assumptions", MAX_ASSUMPTIONS, minimum=1)
    assumptions = []
    seen = set()
    for position, row in enumerate(rows, start=1):
        category = _value(row.get("category", ""), f"Assumption {position} category", 50).lower()
        statement = _value(row.get("statement", ""), f"Assumption {position} statement", 300)
        reason = _value(row.get("reason", ""), f"Assumption {position} rationale", 350, required=False)
        if category not in CATEGORIES:
            raise ValueError(f"Choose a category for assumption {position}.")
        impact, uncertainty = row.get("impact"), row.get("uncertainty")
        if any(type(score) is not int or score not in range(1, 6) for score in (impact, uncertainty)):
            raise ValueError(f"Assumption {position} needs impact and uncertainty scores from 1 to 5.")
        key = " ".join(statement.casefold().split())
        if key in seen:
            raise ValueError(f"Assumption {position} repeats another statement.")
        seen.add(key)
        assumptions.append({
            "id": f"A{position}",
            "category": category,
            "statement": statement,
            "reason": reason or "Ranked using your impact and uncertainty ratings.",
            "impact": impact,
            "uncertainty": uncertainty,
            "risk": impact * uncertainty,
            "status": "open",
        })
    return sorted(assumptions, key=lambda row: (-row["risk"], -row["impact"], -row["uncertainty"], row["id"]))


def _founder_sources(rows, assumption_ids: set[str], recorded_at: str) -> tuple[list[dict], list[dict]]:
    _records(rows, "founder excerpts", 5)
    sources, links = [], []
    identities, linked = {}, set()
    for position, row in enumerate(rows, start=1):
        assumption = _value(row.get("assumption_id", ""), f"Excerpt {position} assumption", 10)
        if assumption not in assumption_ids:
            raise ValueError(f"Choose an existing assumption for excerpt {position}.")
        title = _value(row.get("title", ""), f"Excerpt {position} title", 160)
        passage = _value(row.get("passage", ""), f"Excerpt {position} passage", 1_200)
        url = _source_url(_value(row.get("url", ""), f"Excerpt {position} URL", 2_000))
        if not url:
            raise ValueError(f"Excerpt {position} needs a public HTTP or HTTPS source URL.")
        stance = _value(row.get("stance", "context"), f"Excerpt {position} relationship", 30).lower()
        if stance not in STANCES:
            raise ValueError(f"Choose a relationship for excerpt {position}.")
        reason = _value(row.get("reason", ""), f"Excerpt {position} note", 350, required=False)
        identity = (_source_identity(url), passage)
        if identity not in identities:
            source_id = f"S{len(sources) + 1}"
            identities[identity] = source_id
            sources.append({
                "id": source_id, "title": title, "url": url, "passage": passage,
                "kind": "founder_supplied", "retrieved_at": recorded_at,
            })
        source_id = identities[identity]
        pair = (assumption, source_id)
        if pair in linked:
            raise ValueError(f"Excerpt {position} is already linked to this assumption.")
        linked.add(pair)
        founder_view = {"supports": "possible support", "challenges": "possible challenge", "context": "context"}[stance]
        links.append({
            "assumption_id": assumption,
            "source_id": source_id,
            "stance": "context",
            "reason": f"Founder annotation: {founder_view}. {reason}".strip(),
        })
    return sources, links


def _discussion_sources(rows, existing_source_count: int, recorded_at: str) -> list[dict]:
    _records(rows, "discussion leads", 15)
    result = []
    seen = set()
    for position, row in enumerate(rows, start=1):
        title = _value(row.get("title", ""), f"Discussion {position} title", 180)
        passage = _value(row.get("passage", ""), f"Discussion {position} context", 1_200)
        url = _source_url(_value(row.get("url", ""), f"Discussion {position} URL", 2_000))
        parts = urlsplit(url)
        if not (
            parts.netloc.lower() == "news.ycombinator.com" and parts.scheme == "https"
            and parts.path == "/item" and re.fullmatch(r"id=[1-9][0-9]{0,15}", parts.query)
            and not parts.fragment
        ):
            raise ValueError(f"Discussion {position} needs a Hacker News item link.")
        if url in seen:
            continue
        lead_date = row.get("retrieved_at", recorded_at)
        try:
            lead_date = date.fromisoformat(lead_date).isoformat()
        except (TypeError, ValueError):
            raise ValueError(f"Discussion {position} needs a valid reading date.") from None
        seen.add(url)
        result.append({
            "id": f"S{existing_source_count + len(result) + 1}", "title": title,
            "url": url, "passage": passage, "kind": "discussion_lead", "retrieved_at": lead_date,
        })
    return result


def _founder_experiment(raw, ranked: list[dict]) -> dict | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("Enter experiment details as a record.")
    target = raw.get("assumption_id")
    if target is None or target == "":
        target = ranked[0]["id"]
    target = _value(target, "Experiment assumption", 10)
    if target not in {row["id"] for row in ranked}:
        raise ValueError("Choose an existing assumption for the experiment.")
    labels = {"title": "experiment title", "procedure": "procedure", "metric": "measure",
              "threshold": "decision threshold", "time": "time estimate", "cost": "cost estimate"}
    values = {key: _value(raw.get(key, ""), labels[key].capitalize(), size)
              for key, size in EXPERIMENT_FIELDS.items()}
    return {"assumption_id": target, **values}


def build_local_analysis(
    brief: dict,
    assumptions: list[dict],
    evidence: list[dict],
    experiment: dict | None,
    *,
    leads=(),
    discovery_queries=(),
) -> dict:
    """Return the shared workspace schema from inputs already on this device.

    No networks or models are contacted here. Separately obtained discussion
    metadata can be retained as unlinked leads for later reading.
    """
    started = monotonic()
    report = _result(_clean_brief(brief), "local")
    ranked = _rank_local_assumptions(assumptions)
    recorded_at = datetime.now(timezone.utc).date().isoformat()
    sources, links = _founder_sources(evidence, {row["id"] for row in ranked}, recorded_at)
    public_leads = _discussion_sources(leads, len(sources), recorded_at)
    if not isinstance(discovery_queries, (list, tuple)) or len(discovery_queries) > 3:
        raise ValueError("Record at most three public discussion searches for an analysis.")
    # Count only. The public query may contain a founder's working terms and the
    # shared memo should not reveal exactly what someone searched for.
    for index, query in enumerate(discovery_queries, start=1):
        _value(query, f"Discussion search {index}", 120)
    if public_leads and not discovery_queries:
        raise ValueError("Record the discussion search that supplied these leads.")

    _update_status(ranked, links)
    report.update(
        assumptions=ranked, sources=[*sources, *public_leads], links=links,
        experiment=_founder_experiment(experiment, ranked),
    )
    _trace(report, "Working mode", "Ranked founder-authored assumptions and saved the supplied inputs locally. No language-model calls.")
    _trace(report, "Assumptions", f"Ranked {len(ranked)} by impact × uncertainty. Unlinked assumptions remain open.")
    if sources:
        _trace(report, "Founder evidence", f"Saved {len(sources)} unverified, founder-supplied excerpts as context.")
        report["warnings"].append("Founder-supplied passages have not been verified against their original pages.")
    if discovery_queries:
        _trace(report, "Public discovery", f"Recorded {len(discovery_queries)} search calls and {len(public_leads)} unlinked Hacker News discussion leads.")
        report["warnings"].append("Hacker News results are discussion leads. They do not verify an assumption.")
    if report["experiment"]:
        _trace(report, "Experiment", f"Saved your test for {report['experiment']['assumption_id']}.")
    else:
        _trace(report, "Experiment", "Awaiting a founder-authored experiment.")
    report["usage"]["search_calls"] = len(discovery_queries)
    report["usage"]["elapsed_seconds"] = round(monotonic() - started, 3)
    return report
