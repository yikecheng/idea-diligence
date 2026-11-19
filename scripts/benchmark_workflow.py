"""Replay scripted provider inputs through the production diligence engine offline."""

from __future__ import annotations

import argparse
import json
import sqlite3
from copy import deepcopy
from dataclasses import dataclass, replace
from html import escape
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from idea_diligence import engine, providers, storage
from idea_diligence.report import render_html

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "workflow_benchmark.json"


@dataclass(frozen=True)
class Scenario:
    name: str
    sources: tuple[str, ...]
    proposals: list[dict]
    experiment: dict
    expected_links: dict[str, str]
    expected_statuses: dict[str, str]
    expected_target: str | None
    warning: str = ""


def scenarios(fixture: dict) -> list[Scenario]:
    ground = fixture["ground_truth"]
    links, plans = fixture["proposal_links"], fixture["experiments"]
    base = Scenario(
        "exact citations and conservative evidence",
        tuple(ground["baseline_links"]), links, plans["repeat_use"], ground["baseline_links"],
        ground["baseline_statuses"], ground["baseline_target"],
    )
    conflict_name = "partner_limits"
    conflict = {"assumption_id": "A1", "source": conflict_name, "stance": "challenges",
                "reason": "The release notes describe a delay that would make a close-to-class alert stale."}
    vendor_overreach = [
        {**row, "stance": "challenges", "reason": "Some members will prefer the vendor and never use our service."}
        if row["source"] == "repeat_blog" else row
        for row in links
    ]
    return [
        base,
        replace(base, name="unknown citations, assumptions, and duplicate links",
                proposals=[*links, {**links[0], "source": "S999"}, {**links[0], "assumption_id": "A999"},
                           {**links[0], "stance": "supports"}], warning="Discarded 3"),
        replace(base, name="a matched vendor excerpt cannot settle demand in either direction",
                proposals=vendor_overreach),
        replace(base, name="contradictory passages move the experiment target",
                sources=(*base.sources, conflict_name), proposals=[*links, conflict],
                expected_links={**base.expected_links, conflict_name: "challenges"},
                expected_statuses={**base.expected_statuses, "A1": "mixed"},
                experiment=plans["delivery"], expected_target=ground["conflicting_target"]),
        replace(base, name="wrong-target experiment is rejected",
                experiment=plans["alternatives"], expected_target=None, warning="experiment for A2"),
        replace(base, name="nonnumeric threshold is rejected",
                experiment={**plans["repeat_use"], "threshold": "Continue if promising."},
                expected_target=None, warning="experiment for A2"),
        replace(base, name="empty research keeps every assumption open",
                sources=(), proposals=[], experiment=plans["alternatives"], expected_links={},
                expected_statuses=dict.fromkeys(ground["rank"], "open"),
                expected_target=ground["no_evidence_target"], warning="No usable public source records"),
    ]


def run_case(fixture: dict, case: Scenario) -> dict:
    source_rows = fixture["sources"]
    search_rows = {row["query"]: [] for row in fixture["assumptions"]}
    for key in case.sources:
        row = source_rows[key]
        position = int(row["search_for"][1:]) - 1
        query = fixture["assumptions"][position]["query"]
        search_rows[query].append({field: value for field, value in row.items() if field != "search_for"})

    def model_response(_config, *, name, inputs, usage, **_kwargs):
        usage["model_calls"] += 1
        if name == "assumption_plan":
            return {"assumptions": deepcopy(fixture["assumptions"])}
        if name == "evidence_assessment":
            ids = {row["title"]: row["id"] for row in inputs["sources"]}
            links = []
            for row in case.proposals:
                link = {field: value for field, value in row.items() if field != "source"}
                source = row["source"]
                title = source_rows.get(source, {}).get("title")
                links.append({**link, "source_id": ids.get(title, source)})
            return {"links": links, "experiment": deepcopy(case.experiment)}
        raise AssertionError(f"Unexpected model request {name!r}")

    config = providers.ProviderConfig("simulated", "simulated", "benchmark", providers.OPENAI_BASE)
    with (
        patch.object(providers.ProviderConfig, "from_env", return_value=config),
        patch.object(providers, "_post", side_effect=AssertionError("Network call during offline benchmark")),
        patch.object(engine, "model_json", side_effect=model_response),
        patch.object(engine, "search_web", side_effect=lambda _config, query, _timeout: search_rows[query]),
    ):
        return engine.run_analysis(fixture["brief"], "live", allow_external=True)


def check_case(fixture: dict, case: Scenario, report: dict) -> list[str]:
    ground = fixture["ground_truth"]
    sources = {row["id"]: row["url"] for row in report["sources"]}
    names_by_url = {row["url"]: name for name, row in fixture["sources"].items()}
    observed_sources = {row["url"]: (row["kind"], row["passage"]) for row in report["sources"]}
    expected_sources = {
        fixture["sources"][name]["url"]: (ground["source_kinds"][name], fixture["sources"][name]["content"])
        for name in case.sources
    }
    observed_links = sorted((names_by_url.get(sources.get(row["source_id"]), row["source_id"]),
                             row["assumption_id"], row["stance"]) for row in report["links"])
    expected_links = sorted((name, fixture["sources"][name]["search_for"], stance)
                            for name, stance in case.expected_links.items())
    expected_experiment = case.experiment if case.expected_target else None
    observed_target = (report["experiment"] or {}).get("assumption_id")
    checks = [
        ("rank", [row["id"] for row in report["assumptions"]], ground["rank"]),
        ("source excerpts and provenance", observed_sources, expected_sources),
        ("accepted citation links", observed_links, expected_links),
        ("assumption states", {row["id"]: row["status"] for row in report["assumptions"]}, case.expected_statuses),
        ("experiment target", observed_target, case.expected_target),
        ("experiment text", report["experiment"], expected_experiment),
        ("report status", report["status"], "partial" if case.warning else "complete"),
        ("model call count", report["usage"]["model_calls"], 2),
        ("search call count", report["usage"]["search_calls"], 5),
    ]
    failures = [f"{label}: expected {expected!r}, observed {observed!r}"
                for label, observed, expected in checks if observed != expected]
    if case.warning and not any(case.warning in warning for warning in report["warnings"]):
        failures.append(f"Expected a warning containing {case.warning!r}; received {report['warnings']!r}")
    return failures


def check_founder_round_trip(fixture: dict, report: dict) -> list[str]:
    source = fixture["sources"]["incumbent"]
    source_id = next(row["id"] for row in report["sources"] if row["url"] == source["url"])
    note = "Simulated QA outcome for an offline benchmark."
    with TemporaryDirectory(prefix="idea-diligence-benchmark-") as directory:
        database = Path(directory) / "benchmark.sqlite3"
        run_id = storage.save_run(report, database)
        review = storage.save_evidence_review(run_id, "A3", source_id, "accept", "Advertised overlap", database)
        outcome = storage.save_experiment_outcome(run_id, "completed", 8, 3, note, "revise", database)
        reloaded = storage.load_run(run_id, database)
        workspace = storage.load_workspace(run_id, database)
        memo = render_html(reloaded, workspace)

    failures = []
    if reloaded != report or workspace["reviews"] != [review] or workspace["outcome"] != outcome:
        failures.append("Could not reopen the original report, saved review, and simulated outcome intact.")
    expected_memo = (f'href="{source["url"]}"', escape(source["content"]), "Advertised overlap",
                     note, "3 of 8 met the metric")
    for snippet in expected_memo:
        if snippet not in memo:
            failures.append(f"Expected decision memo to contain {snippet!r}.")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable results.")
    args = parser.parse_args()
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    results = []
    for index, case in enumerate(scenarios(fixture)):
        try:
            report = run_case(fixture, case)
            failures = check_case(fixture, case, report)
        except (AssertionError, KeyError, TypeError, ValueError) as error:
            failures = [f"{type(error).__name__}: {error}"]
        results.append({"case": case.name, "failures": failures})
        if index == 0:
            round_trip_failures = ["The baseline replay failed."]
            if not failures:
                try:
                    round_trip_failures = check_founder_round_trip(fixture, report)
                except (KeyError, StopIteration, TypeError, ValueError, sqlite3.Error) as error:
                    round_trip_failures = [f"{type(error).__name__}: {error}"]
            results.append({"case": "founder review, outcome, and memo survive reopening",
                            "failures": round_trip_failures})

    passed = sum(not result["failures"] for result in results)
    summary = {"mode": "scripted providers, no network", "passed": passed,
               "total": len(results), "cases": results}
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        for result in results:
            print(f"{'FAIL' if result['failures'] else 'PASS'}  {result['case']}")
            for failure in result["failures"]:
                print(f"      {failure}")
        print(f"{passed}/{len(results)} passed ({summary['mode']}).")
    return int(passed != len(results))


if __name__ == "__main__":
    raise SystemExit(main())
