# Validation

## Founder workspace checks

- Opened both curated cases in Chrome and checked that each arrived at a different experiment tied to its own evidence and priority assumption.
- Saved an evidence review and a simulated outcome in a separate QA database. Reopened the analysis after refreshing and confirmed both records appeared in the trace. The simulation was a software check and supplies no customer results.
- Downloaded an HTML decision memo in Chrome. Automated checks cover persistence, review status, report content and link safety, and partial-run handling.

## Midpoint checks

Run the automated tests with `python -m pytest -q` and record the demonstrated commit and browser workflow before recording. The midpoint covers a reproducible implementation check and one focused product demonstration. Confirm each check before narrating it as a result.

| Check | Evidence to capture |
| --- | --- |
| Reproduce without credentials | Load the public demo brief, run it, and open five ranked assumption cards from a fresh launch. |
| Verify the evidence chain | Follow at least one evidence ID to the displayed passage and original URL. Inspect how it supports or challenges the specific assumption. |
| Show a consequential unknown | Verify that feature overlap leaves recurring use by the target audience open. Locate the experiment for the highest-priority open risk. |
| Check the experiment | Verify that the recommendation has a linked assumption, an observable outcome, a threshold, and an actionable interpretation. |
| Check persistence and export | Reopen a saved run after refresh or restart and compare the report with the displayed result. |
| Check live provider behavior when credentials are available | Log the observed model calls, search calls, latency, and any incomplete results. Compare one returned passage with its original source. |

Source presence and correct IDs are engineering checks. Relevance, interpretation, and experiment usefulness require human review. The curated demo is a development case and cannot estimate how often the agent improves decisions for new ideas.

### Observed at the midpoint · November 18, 2026

- Ran the app on Python 3.12.14 and Streamlit 1.50.0. In Chrome, the public example rendered five assumptions, a source card with the AnyPod passage and original URL, and the repeat-use pilot with its 4-of-8 threshold.
- Reproduced the curated run with zero model and search calls. The tests reopened a persisted run in a new Streamlit session and checked the Markdown report for the original evidence URL and decision threshold.
- All six automated tests passed. Tests with simulated providers covered the call budget, invalid references, snippet handling, public-brief consent, provider failure, and selection of the next experiment after evidence changed which assumption was open. Provider access, live output quality, and actual latency and cost still need a credentialed run.
- The five excerpts were checked against public source pages for the demo. Product descriptions substantiate advertised capabilities. There are no observed pilot results or measured customer demand.

## Final evaluation

Recruit five to ten volunteers with ideas they are comfortable sharing. Before any generated outputs, record each participant’s known alternatives, critical beliefs, and planned next test. Freeze the briefs and use the same research budget and available information across three conditions:

1. A normal AI prompt for market research and next steps.
2. A static competitor report.
3. Idea Diligence.

Remove product names from the outputs where practical and present them in randomized order. The idea owner marks whether a competitor or belief was new to them and scores overall preference separately. An independent reviewer with product or research experience uses the same rubric for each output; a second reviewer can double-score a subset and record disagreements. Use the frozen pre-output brief to judge whether a risk was overlooked and plausible enough to affect the decision. Score unsupported or unverifiable claims and missing experiment recommendations explicitly.

| Experiment criterion | Score 0–2 |
| --- | --- |
| Targets the decision | The experiment tests a named high-risk assumption and would inform a concrete decision. |
| Observable outcome | Another person can tell what to measure and how to measure it. |
| Threshold | The result maps to a stated pass, fail, or inconclusive action. |
| Feasibility | Participants, time, and materials fit a small, realistic test. |
| Interpretation | The design addresses the most obvious alternative explanations and explains what remains open. |

Use 0 for missing, 1 for partial, and 2 for specific and defensible. Report grounded competitor discoveries, new high-impact risks, source support, and rubric scores by condition. Report preference separately. A high rubric score estimates whether a proposed test is decision-relevant. Actual resolution requires carrying out the test and observing its results.

For the final video, use outcomes observed by the final cutoff and identify planned evaluation work in the next steps. Cite competitor feature claims directly in any slides or PDFs so the comparison is inspectable without speaker notes.
