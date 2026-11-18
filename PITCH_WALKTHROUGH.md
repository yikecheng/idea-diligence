# Idea Diligence · 90-second product walkthrough

Open the local workspace and keep the Catch Me Up on Anything demo ready. Use the short version below for a pitch or as the product segment of the final course video.

| Time | Screen | What to say |
| --- | --- | --- |
| 0:00–0:15 | Workspace home | “I got the idea after brainstorming a few products and finding out that someone was already building almost all of them. Finding a competitor answered one question. It didn’t tell me if there was still something worth building.” |
| 0:15–0:35 | Open Catch Me Up on Anything, then Evidence | “Here’s one of those ideas. Give us a topic and we’ll make you a short audio briefing. Idea Diligence turns it into five assumptions. This one is about differentiation. AnyPod already advertises a researched podcast from a topic, so I can see exactly what overlaps and read the original page.” |
| 0:35–0:50 | Accept or question the source link | “I accept this link for the feature overlap. I can question a weaker link or exclude it, and my review stays attached to that specific claim.” |
| 0:50–1:12 | Experiment | “Here’s what I still don’t know. Will people come back when another topic comes up? I can make a first briefing by hand for eight product managers or founders. If four come back and listen to at least half of a second briefing, that’s enough to keep testing with this group.” |
| 1:12–1:30 | Overview and Download decision memo | “After the pilot I can log the result and choose to continue, revise, or stop. This memo carries the sources, my reviews, and the decision, so a cofounder can understand how I got there.” |

Use the proposed pilot threshold when you present. If you enter illustrative counts to show the form, say aloud that you are simulating the product interaction. Keep any simulated run out of materials presented as research findings.

## Technical walkthrough

- Both sample modes replay checked-in public source excerpts. Custom research uses a configurable model and Tavily after consent, with two model calls, five searches, and a 75-second client budget.
- The engine ranks initial risks, validates evidence IDs, and chooses the highest unresolved assumption after assessing source links.
- SQLite preserves the analysis and stores founder judgments independently. The HTML memo renders from those records. Its source links, assumptions, and decisions remain inspectable after export.

For a second example, open **Return Deadline Assistant**. Competitor pages show that reminders already exist. Retailer rules make eligibility and deadline exceptions a more focused test of whether a source-linked recommendation helps.

## Reference demo

Yinuo Zhao’s Casework demo shows how to state a narrow example, expose the reason for a result, inspect the underlying passage, and carry human judgment forward. Idea Diligence applies those product principles to the founder’s evidence review and experiment decision. [Casework midpoint video](https://www.youtube.com/watch?v=doyNzaxG2VA)
