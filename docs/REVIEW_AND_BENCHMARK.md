# Product review and offline benchmark

## What a professor and a founder would ask

| Perspective | Question | What the current work can show |
| --- | --- | --- |
| Professor | Does a competitor finding change the next action? | The replay includes an incumbent that already offers the proposed feature. Its product excerpt challenges novelty, so the system moves to an unresolved question about repeat use. Contradictory technical passages move the target again. |
| Professor | Can I follow a consequential claim back to its source? | The saved memo carries the excerpt, original URL, provenance, and founder review. The benchmark checks these survive reopening. The provider-backed engine checks source IDs and downgrades search snippets. Checking factual entailment still calls for reading the original page. |
| Professor | Would the recommended experiment actually inform a decision? | The engine checks the target, required fields, and the presence of a number in the threshold. An independent reviewer can judge the design against a frozen brief. Learning whether the test resolves the risk requires actual observations. |
| Founder | Will a glossy competitor page make the tool dismiss my idea? | In new provider-backed runs, demand and viability claims stay contextual in both directions. A product excerpt can challenge the novelty of an advertised feature. Repeat behavior and willingness to pay remain questions for your own tests. |
| Founder | Can I share what I learned and pick up from there? | The workspace can retain a reviewed citation, a recorded outcome, and your decision. Its HTML memo is self-contained and carries clickable source links. |

Abel asked for a named model and search provider, a request budget, references visible to the reader, and a shuffled comparison that separates preference from experiment quality. The provider-backed workflow defaults to `gpt-5.4-mini` and Tavily, with two model calls, up to five searches, and a 75-second run budget. The offline replay checks the call structure using scripted inputs. A credentialed run is needed to measure actual latency, token usage, and retrieval coverage. Source references belong in the visible body of any submitted slide or PDF. [Abel’s proposal feedback](https://github.com/onexi/ps06/blob/main/yikecheng/feedback_abel.md)

## Reproduce the engineering checks

From the project directory, run the benchmark with Python 3.10 or newer. It uses the standard library and a temporary database.

```bash
python -m scripts.benchmark_workflow
python -m scripts.benchmark_workflow --json
```

The synthetic [ClassSpot fixture](../fixtures/workflow_benchmark.json) freezes one studio waitlist idea and its model and search responses. The benchmark drives those responses through the production analysis, replaces provider calls, and disables the HTTP adapter. It expects exact citation URLs and passages, context for unsupported behavioral claims and search snippets, and a specific experiment target for each evidence state. Across seven replay variations and one save-and-reopen check, the current implementation passed **8 of 8**. The CLI exits with code `1` if a check fails.

ClassSpot’s excerpts and recorded outcome are simulated, and the published memo check covers HTML. The benchmark measures behavior on this fixed fixture. The three-condition class study is the way to compare research usefulness and experiment quality on real ideas, with separate founder preference and reviewer scores. [Evaluation protocol](../VALIDATION.md)
