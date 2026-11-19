# Idea Diligence

Idea Diligence helps early-stage founders and product teams decide what to test before building. Describe an idea, inspect and review the evidence behind its assumptions, then record the experiment outcome and the decision it informs.

MIT 1.125 Agentic Engineering · Fall 2026 · EK (Yike) Cheng · Founder workspace

[Open the live website](https://idea-diligence.streamlit.app/) · [Midpoint video walkthrough](MIDPOINT_WALKTHROUGH.md)

## Try it

Use Python 3.12. From this repository:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py --server.address 127.0.0.1
```

Open the local URL printed by Streamlit. From **Workspace home**, choose **Catch Me Up on Anything** or **Return Deadline Assistant**. These examples replay curated public excerpts with zero provider requests.

The public deployment entry point is `streamlit_app.py`. It keeps analyses and evaluation records in a separate temporary SQLite workspace for each browser session. Visitors can use the curated cases and public discussion search without API credentials. Download a memo or comparison result before leaving the session. The local entry point, `app.py`, supports persistent saved analyses and optional credentialed research.

1. **Overview** ranks the assumptions and highlights the current unresolved priority. Record a score change and why it matters.
2. **Research** saves public discussion searches and lets you attach a source excerpt to a specific assumption.
3. **Evidence** shows source passages and lets you accept, question, or exclude a link. A founder-supplied excerpt contributes context, and your proposed interpretation stays visible.
4. **Experiment** records a measurable test, observations, and a decision to continue, revise, or stop. Plan a follow-up test when your priority changes and revisit earlier tests at any time.
5. **Run trace** records the initial analysis and subsequent changes. **Overview** exports a decision memo with the risk revisions, sources, and test history. Open the HTML memo in a browser to print or save it as PDF.

Analyses and study records are stored in SQLite on this device. Earlier midpoint databases gain the additional tables when they open.

### Start a new idea without credentials

Select **New idea → Local evidence review**. Enter one to five assumptions and optionally attach your own source excerpts. The workspace ranks your scores and keeps the founder-supplied excerpts as context. You can save a test plan in the intake or add one later from **Experiment**. The initial analysis and test threshold remain inspectable after results are entered.

**Find public discussion leads** sends only the query you enter to Hacker News Search. Results are live links for investigation and remain separate from linked evidence. Search is optional and the workspace can save a new analysis if a query returns nothing or the provider is unavailable. [Hacker News Search API](https://hn.algolia.com/api)

### Live AI research

Live mode uses an OpenAI-compatible endpoint and Tavily search. Copy `.env.example` to `.env`, fill in your own keys locally, and run `source .env` in the shell that starts Streamlit. `OPENAI_MODEL` and `OPENAI_BASE_URL` are optional overrides. In the idea brief, consent to external processing and select **Run live analysis**. The model gets the brief and relevant retrieved evidence. Tavily gets queries derived from the brief. Use public or fictional ideas when recording and keep API keys, private briefs, and local databases outside Git.

## What to look for

- **Assumption ranking.** Each assumption expresses something that needs to be true. Impact and uncertainty determine which open question merits early attention.
- **Traceable claims.** Follow an evidence link from an assumption to a passage and its original source. A source can support, challenge, or contextualize an assumption. A missing or irrelevant source leaves the assumption open.
- **A falsifiable next step.** The experiment describes the participants or inputs, procedure, measurable threshold, and what to do if the result goes either way.

Product documentation can establish that a competing feature exists. Customer interviews and observed behavior are needed to learn whether the proposed audience has a recurring problem, switches, or pays. The experiment is a recommendation and remains for the founder to run.

## Evaluate a class idea

Open **Evaluation Lab** from the sidebar. Register an idea and freeze the founder’s known alternatives, beliefs, planned test, and matched research conditions. Run the three methods outside the lab, remove identifying tool names, and paste the outputs. Each reviewer scores the shuffled outputs against the same rubric. The founder records novelty and preference separately. Once all registered reviews and founder feedback are in, the lab reveals the methods and exports the complete case as JSON.

To collect independent judgments, share only the shuffled packet with the reviewer and collect it before revealing the method labels. The lab is a local study organizer. It relies on the organizer for matched research effort, masking, and reviewer independence.

## Reproduce and inspect

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m scripts.benchmark_workflow
```

- [Architecture and engineering decisions](ARCHITECTURE.md)
- [Validation and final evaluation plan](VALIDATION.md)
- [Professor and founder review with engineering benchmark](docs/REVIEW_AND_BENCHMARK.md)
- [Midpoint rehearsal and recording script](MIDPOINT_WALKTHROUGH.md)
- [Startup pitch walkthrough](PITCH_WALKTHROUGH.md)
- [Live demo steps and fallback](LIVE_DEMO_RUNBOOK.md)
- [Proposal submission](https://github.com/onexi/ps06/pull/33) and [Abel’s proposal feedback](https://github.com/onexi/ps06/blob/main/yikecheng/feedback_abel.md)

Yinuo Zhao’s legal research prototype was a benchmark for inspectable evidence, bounded research, and reporting the limits of verification. Idea Diligence’s workflow and implementation were developed separately with Codex assistance. [Benchmark repository](https://github.com/inorrr/agentic-legal-research)
