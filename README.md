# Idea Diligence

Idea Diligence helps early-stage founders and product teams decide what to test before building. Describe an idea, see five assumptions that could change the decision, inspect evidence tied to each one, and leave with an experiment for the most important open question.

MIT 1.125 Agentic Engineering · Fall 2026 · EK (Yike) Cheng · Midpoint prototype

## Try it

Use Python 3.12. From this repository:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

Open the local URL printed by Streamlit. Click **Run demo** in the sidebar to load and analyze **Catch Me Up on Anything**, a proposed on-demand audio briefing for busy professionals. Expand a result to see its source passage and compare the finding with the demand assumption that stays open. The demo uses a fixed bundle of reviewed public evidence and runs without API credentials. The app records analyses locally in SQLite and can export a Markdown report.

### Live research

Live mode uses an OpenAI-compatible endpoint and Tavily search. Copy `.env.example` to `.env`, fill in your own keys locally, and run `source .env` in the shell that starts Streamlit. `OPENAI_MODEL` and `OPENAI_BASE_URL` are optional overrides. In the idea brief, consent to external processing and select **Run live analysis**. The model gets the brief and relevant retrieved evidence. Tavily gets queries derived from the brief. Use public or fictional ideas when recording and keep API keys, private briefs, and local databases outside Git.

## What to look for

- **Assumption ranking.** Each assumption expresses something that needs to be true. Impact and uncertainty determine which open question merits early attention.
- **Traceable claims.** Follow an evidence link from an assumption to a passage and its original source. A source can support, challenge, or contextualize an assumption. A missing or irrelevant source leaves the assumption open.
- **A falsifiable next step.** The experiment describes the participants or inputs, procedure, measurable threshold, and what to do if the result goes either way.

Product documentation can establish that a competing feature exists. Customer interviews and observed behavior are needed to learn whether the proposed audience has a recurring problem, switches, or pays. The experiment is a recommendation and remains for the founder to run.

## Reproduce and inspect

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

- [Architecture and engineering decisions](ARCHITECTURE.md)
- [Validation and final evaluation plan](VALIDATION.md)
- [Midpoint rehearsal and recording script](MIDPOINT_WALKTHROUGH.md)
- [Proposal submission](https://github.com/onexi/ps06/pull/33) and [Abel’s proposal feedback](https://github.com/onexi/ps06/blob/main/yikecheng/feedback_abel.md)

Yinuo Zhao’s legal research prototype was a benchmark for inspectable evidence, bounded research, and reporting the limits of verification. Idea Diligence’s workflow and implementation were developed separately with Codex assistance. [Benchmark repository](https://github.com/inorrr/agentic-legal-research)
