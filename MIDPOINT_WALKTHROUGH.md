# Midpoint recording guide

The November 19 check-in uses a GitHub code link and an accessible video around four minutes, with a five-minute maximum. Post the video in the class sign-up sheet before class. In class, the video is played and followed by brief questions. [Class sign-up sheet](https://docs.google.com/spreadsheets/d/1ZewIG5udWWpk3Kdrab5yDbsWDV4gnH3liKobIAp7HG4/edit?usp=sharing)

## Rehearse

1. Start the local app from the README. Select **Load demo brief** in the sidebar so the audience, problem, and idea are visible before you click **Run demo**.
2. Point to the open repeat-listening assumption. Collapse it and expand the defensibility assumption directly below it. Scroll to the AnyPod passage and its **Open original source** link, then show the experiment in **What to test next**. The proposed threshold is four of eight participants independently requesting and listening to at least half of a second briefing within seven days.
3. Expand **Run trace and limits**, reopen the saved result from **Run history**, and confirm **Download Markdown report**. For the recording, use the same verified run or rerun the curated case with the mode visible.
4. In the editor, enlarge the font and open `idea_diligence/engine.py` at `run_analysis` and the evidence-link checks. Confirm the code in the video matches the GitHub commit.
5. Record the screen and voice. Watch the exported video, then test both links as a viewer with the expected access.

## Narration · 4:10

| Time | Segment | Screen |
| --- | --- | --- |
| 0:00–0:10 | Introduction | Project title and your name |
| 0:10–0:40 | Pitch | Idea brief or one problem slide |
| 0:40–1:10 | Technology | Architecture diagram |
| 1:10–2:10 | Code | Python pipeline and evidence-link handling |
| 2:10–3:10 | Demo | One analysis from brief to experiment |
| 3:10–3:40 | Risks | Open assumption and evidence view |
| 3:40–4:10 | Next steps | Evaluation plan or app end screen |

### Introduction · 10 seconds

“Hi everyone, I’m Yike. My project is Idea Diligence. It helps founders figure out what they need to learn before they spend weeks building an idea.”

### Pitch · 30 seconds

“I started this after I kept brainstorming ideas and then finding out that someone was already building them. That was useful, but it left me with a harder question. If someone has built part of my idea, what does that actually tell me? Is there still a gap, and what would I need to learn before pursuing it? I wanted to take a rough idea and leave with one practical test.”

### Technology · 30 seconds

“The interface is built with Streamlit, the research workflow runs in Python, and saved runs go into a local SQLite database. The live path is configured for GPT-5.4 mini and Tavily, with a limit of two model calls and five searches. For this recording I’m using a curated case, so you can open the same example and check the same public evidence yourself.”

### Code · 1 minute

“This function takes the brief and prepares five assumptions. Each one has an impact and an uncertainty rating, which gives us a consistent way to prioritize the open questions. The research step gathers evidence and assigns each passage an ID. When the engine links a finding to a source, it uses that reference. The source text you see comes from the evidence record, so you can trace it back to the page and make up your own mind. Then the workflow picks the most important open assumption and generates an experiment around it. The result includes the source links and the research trace, so I can see how the system got there when I reopen it.”

### Demo · 1 minute

“I’ll use one of my own ideas. Imagine I want a short audio briefing about whatever I’m trying to catch up on. I put in the audience, the problem, and the product. Here are the five assumptions. This one asks if starting from a topic is enough to stand out. AnyPod already describes a similar feature, and I can click into the source. Now look at this other question. Would my target audience actually listen more than once? That’s still open. The app proposes a one-week pilot. I’d make a first briefing by hand and see whether four out of eight people come back on their own and listen to at least half of a second one.”

### Risks · 30 seconds

“The main risk is that the system can point to a real passage and still draw too strong a conclusion from it. Product pages can tell me that a feature exists. For repeat usage or willingness to pay, I still need to observe people. I also still need to check whether the workflow finds useful evidence when the idea is outside this demo case.”

### Next steps · 30 seconds

“Next I want to try five to ten ideas and compare this with a regular AI prompt and a static competitor report. I’ll shuffle the outputs and ask reviewers to score whether the proposed test would answer an important question. I’ll ask the idea owners what they liked separately. I want to learn how often this helps someone choose a better test.”

## Questions to be ready for

- **How is this different from a normal competitor search?** It starts with what has to be true. A competitor finding becomes useful when it changes a specific belief or helps choose the next experiment.
- **What does the model do?** In live mode it proposes assumptions and searches, then connects evidence to assumptions and proposes an experiment. Python ranks risks and checks evidence references. The recorded case supplies the fixed inputs for those checks without a live call.
- **Does a source link verify a claim?** It verifies the cited text is inspectable. Whether the passage warrants the claim is part of the review.
- **How do you know the highest-ranked assumption is the right one?** Impact and uncertainty are prioritization inputs. They make the ranking explainable and provide something the founder or reviewer can challenge.
- **Why the curated run?** It shows the workflow with a reproducible example and lets reviewers inspect evidence regardless of API access. The validated state of live research belongs in the recording and validation record.
- **Does a user liking the experiment show it works?** Preference and decision usefulness are different measures. The human reviewer scores whether the method, metric, and threshold address the assumption, and the experiment has to be run to establish the outcome.

## Before class

1. Verify the instructor can open the project repository and that the recorded revision includes the run instructions.
2. Upload the screen recording to a location where the video plays for anyone with the link. Open that link in a signed-out browser to check playback.
3. Put the midpoint video URL in your row on the class sheet as instructed. Include the code repository link with your project details and double-check both links. [Class sign-up sheet](https://docs.google.com/spreadsheets/d/1ZewIG5udWWpk3Kdrab5yDbsWDV4gnH3liKobIAp7HG4/edit?usp=sharing)
