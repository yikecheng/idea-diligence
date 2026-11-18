"""Human review summaries derived independently of the original analysis."""

EVIDENCE_VERDICTS = ("accept", "question", "exclude")
OUTCOME_STATUSES = ("planned", "running", "completed")
OUTCOME_DECISIONS = ("undecided", "continue", "revise", "stop")


def _status(stances: set[str]) -> str:
    supports = "supports" in stances
    challenges = "challenges" in stances
    if supports and challenges:
        return "mixed"
    if supports:
        return "supported"
    if challenges:
        return "challenged"
    return "context" if "context" in stances else "open"


def effective_assumptions(report: dict, reviews: list[dict]) -> list[dict]:
    """Add evidence-review counts and a direction based on accepted links only."""
    lookup = {(review["assumption_id"], review["source_id"]): review["verdict"] for review in reviews}
    result = []
    for assumption in report.get("assumptions", []):
        assumption_id = assumption["id"]
        tallies = dict.fromkeys((*EVIDENCE_VERDICTS, "unreviewed"), 0)
        accepted_stances = set()
        for link in report.get("links", []):
            if link["assumption_id"] != assumption_id:
                continue
            verdict = lookup.get((assumption_id, link["source_id"]), "unreviewed")
            tallies[verdict] += 1
            if verdict == "accept":
                accepted_stances.add(link["stance"])
        reviewed = sum(tallies[key] for key in EVIDENCE_VERDICTS)
        result.append({
            **assumption,
            "reviewed_status": _status(accepted_stances) if reviewed else None,
            "reviewed_count": reviewed,
            "accepted_count": tallies["accept"],
            "questioned_count": tallies["question"],
            "excluded_count": tallies["exclude"],
            "unreviewed_count": tallies["unreviewed"],
        })
    return result
