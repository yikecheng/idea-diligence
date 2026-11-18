# Idea Diligence

Idea Diligence helps early-stage founders and product teams decide what to test before building. Describe an idea, inspect and review the evidence behind its assumptions, then record the experiment outcome and the decision it informs.

MIT 1.125 Agentic Engineering · Fall 2026 · EK (Yike) Cheng · Founder workspace

## Try it

Use Python 3.12. From this repository:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

Open the local URL printed by Streamlit. From **Workspace home**, choose **Catch Me Up on Anything** or **Return Deadline Assistant**. These examples replay curated public excerpts with zero provider requests.

1. **Overview** ranks the assumptions and summarizes the most consequential unresolved question.
2. **Evidence** shows exact source excerpts and lets you accept, question, or exclude each link. Your judgments are preserved alongside the original AI classification.
3. **Experiment** gives you a procedure, measure, and decision threshold. Record real observations and choose whether to continue, revise, or stop.
4. **Run trace** shows research calls, source coverage, warnings, and recorded founder activity. The HTML memo and Markdown exports live in **Overview**. Open the HTML memo in a browser to print or save it as PDF.

Runs, evidence reviews, and outcomes are stored in SQLite on this device. Earlier midpoint databases open in the new workspace and receive the additional tables automatically.

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
- [Startup pitch walkthrough](PITCH_WALKTHROUGH.md)
- [Proposal submission](https://github.com/onexi/ps06/pull/33) and [Abel’s proposal feedback](https://github.com/onexi/ps06/blob/main/yikecheng/feedback_abel.md)

Yinuo Zhao’s legal research prototype was a benchmark for inspectable evidence, bounded research, and reporting the limits of verification. Idea Diligence’s workflow and implementation were developed separately with Codex assistance. [Benchmark repository](https://github.com/inorrr/agentic-legal-research)
