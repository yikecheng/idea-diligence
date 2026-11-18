# Validation

## Live-demo rehearsal · November 18, 2026

The browser runs used a separate local database. The search results came from the real Hacker News Search endpoint. All recorded experiment outcomes were simulated for QA.

| Trial | Observed behavior |
| --- | --- |
| Product Brief Listening Lab | Created from scratch. The live `AI podcast` query returned five discussion leads. Attached the AnyPod excerpt, reviewed the link, recorded an outcome, and reopened the analysis after refresh. The impossible result 8 of 6 was rejected before the corrected entry saved. |
| Campus Room Availability Alerts | Created with two hypotheses and a source passage from MIT Libraries. The first `room booking` query timed out and a manual retry recovered. After restarting the app, reopened the saved analysis, added a test plan, saved an outcome, and downloaded a memo containing the late plan, reviewable source, and decision. |
| Revised search behavior | Repeated three Chrome queries after the fix. `room booking` and `AI podcast` returned five each, while `hfzxuqvpmclw` returned zero. Those runs surfaced results in 0.7–1.7 seconds in this rehearsal. A public-query validation check rejected an email-shaped input. |
| Sample regression | Reopened both curated cases and confirmed the AnyPod evidence and the separate 8-of-12 test threshold for Return Deadline Assistant. |

After observing the timeout, added a single retry for eligible temporary errors within a nine-second total limit. The retry is covered by tests with simulated failures. The live reruns succeeded, and the number of internal requests in those reruns was not measured in Chrome. Added an experiment form to saved analyses that lack a plan, and separated linked sources from search leads in the case header.

The automated suite covers legacy database compatibility, query validation, retry and empty responses, report exports, and a fresh custom intake run. The credentialed model-plus-search integration was exercised with simulated HTTP responses, including rate limits and incomplete runs. It still needs a real run using configured provider credentials.

Sources for the rehearsal [MIT Libraries reservation guidelines](https://libraries.mit.edu/study/reserve/) · [AnyPod](https://www.anypod.fm/about) · [Hacker News Search API](https://hn.algolia.com/api)

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
