# Idea Diligence midpoint recording

Open the [public demo](https://idea-diligence.streamlit.app/) or [the app on this Mac](http://127.0.0.1:8501) and preload `idea_diligence/engine.py` at `_validated_links`. Start on **Workspace home**. The source and the proposed experiment are ready in **Catch Me Up on Anything**. The timings leave room to pause on the code and let people read.

## 0:00–0:40 · Introduce it

**Screen** — Workspace home.

“Hi, I’m Yike, and this is Idea Diligence. This actually came from me brainstorming startup ideas and finding out, over and over, that someone was already building them. Like, almost every time.

“Once I found those competitors, I still had the same question. What should I do with that information? Is there still a reason someone would pick my product? So I built a tool that takes a rough idea, looks at what has to be true, and helps you pick a test you can actually run.”

## 0:40–1:05 · Show the stack

**Screen** — Switch to `engine.py`.

“The app is built in Streamlit and Python, and it saves the work in SQLite. The live research path is set up to use GPT-5.4 mini and Tavily. I cap it at two model calls and five searches. Today I’m using a saved example with real public sources, so you can open it and see the same thing.”

## 1:05–2:05 · Walk through the code

**Screen** — Show `_rank_assumptions`, then `_validated_links`, then `_experiment_target` in `engine.py`.

“There are three pieces I want to show. First, we rank the assumptions. I score how much it would matter if each one was wrong and how much we still don’t know. Multiplying those gives me a risk score.

“Here’s the part that links the evidence. Every link has to match an assumption and a source we actually retrieved. If the source ID doesn’t exist, we drop the link. Search snippets stay as background. So when I see a claim in the app, I can look at the actual passage and decide whether I agree with it.

“Then we pick an unresolved assumption to test. When I learn something new, I can change the risk score and save a follow-up test. I can always go back and see what I thought the first time.”

## 2:05–3:10 · Demo the case

**Clicks** — **Open Catch Me Up on Anything demo** → show the priority → **Evidence** → **A2 · Defensibility** → point to the **AnyPod** quote and **Open original source** → **Experiment** → point to **Decision threshold**.

“Okay, here’s one of those ideas. I wanted to type in a topic and get a short audio briefing. I thought that might be what made it different. But when I click into Evidence, here’s AnyPod describing a very similar flow. And I can go straight to the source.

“So the question I’d test first is whether my audience would actually come back for a second briefing. Here’s the pilot. I’d make the first briefing by hand for eight people, leave the link open for a week, and see if at least four come back on their own and listen to half of a second one. I could learn that before building the whole thing.”

## 3:10–3:45 · Risks and next steps

**Clicks** — Stay on the threshold for the first paragraph, then open **Evaluation lab**.

“A product page can tell me what a competitor offers. To find out if my users would come back, I still have to run the pilot.

“For the final, I want to try this on five to ten class ideas. I’ve built a comparison where people score outputs without seeing which tool produced them. I want to see whether this actually helps founders pick a better next test.”

## Submit

Put the accessible video link on the [class sign-up sheet](https://docs.google.com/spreadsheets/d/1ZewIG5udWWpk3Kdrab5yDbsWDV4gnH3liKobIAp7HG4/edit?usp=sharing) and use the [current GitHub project branch](https://github.com/yikecheng/idea-diligence/tree/pitch-workspace) as your code link. Open the video link signed out once to confirm playback.
