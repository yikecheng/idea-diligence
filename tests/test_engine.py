import copy
import os
import unittest
from unittest.mock import patch

from idea_diligence.engine import load_demo_brief, run_analysis
from idea_diligence.providers import ProviderError


def model_plan(demo):
    assumptions = []
    for assumption in demo["assumptions"]:
        supplied = {
            field: assumption[field]
            for field in ("category", "statement", "impact", "uncertainty", "reason")
        }
        assumptions.append({**supplied, "query": f"Research assumption {assumption['id']} for topic audio"})
    return {"assumptions": assumptions}


class DemoTests(unittest.TestCase):
    def setUp(self):
        self.brief = load_demo_brief()

    def test_fixture_runs_offline_with_ranked_traceable_evidence(self):
        with patch("idea_diligence.engine.model_json") as model, patch(
            "idea_diligence.engine.search_web"
        ) as search:
            result = run_analysis(self.brief, mode="demo")
        model.assert_not_called()
        search.assert_not_called()
        self.assertEqual(result["mode"], "demo")
        self.assertEqual(result["usage"]["model_calls"], 0)
        self.assertEqual(result["usage"]["search_calls"], 0)

        assumptions = result["assumptions"]
        self.assertEqual(len(assumptions), 5)
        self.assertEqual([item["risk"] for item in assumptions], [25, 20, 16, 12, 8])
        by_id = {item["id"]: item for item in assumptions}
        self.assertEqual(by_id["A1"]["status"], "open")
        self.assertEqual(by_id["A2"]["status"], "challenged")
        self.assertEqual(by_id["A3"]["status"], "supported")
        self.assertEqual(result["experiment"]["assumption_id"], assumptions[0]["id"])

        sources = {source["id"]: source for source in result["sources"]}
        for link in result["links"]:
            self.assertIn(link["assumption_id"], by_id)
            self.assertTrue(sources[link["source_id"]]["url"].startswith("https://"))
            self.assertTrue(sources[link["source_id"]]["passage"])
        anypod = next(source for source in sources.values() if "AnyPod" in source["title"])
        self.assertIn(
            ("A2", anypod["id"], "challenges"),
            [(item["assumption_id"], item["source_id"], item["stance"]) for item in result["links"]],
        )


class LiveGuardrailTests(unittest.TestCase):
    def setUp(self):
        self.brief = load_demo_brief()
        self.demo = run_analysis(self.brief, mode="demo")
        provider_keys = patch.dict(os.environ, {"OPENAI_API_KEY": "test-key", "TAVILY_API_KEY": "test-key"})
        provider_keys.start()
        self.addCleanup(provider_keys.stop)

    def test_model_cannot_turn_an_unverified_snippet_into_directional_evidence(self):
        verified_text = "This existing product turns research reports into an audio briefing on request."
        unverified_text = "This search result alleges an audio product already exists for any user topic."

        def fake_model(_config, *, name, inputs, usage, **_kwargs):
            usage["model_calls"] += 1
            if name == "assumption_plan":
                return model_plan(self.demo)
            return {
                "links": [
                    {
                        "assumption_id": "A1", "source_id": "S1", "stance": "supports",
                        "reason": "A provider markets this.",
                    },
                    {
                        "assumption_id": "A2", "source_id": "S2", "stance": "challenges",
                        "reason": "A search snippet describes an existing alternative.",
                    },
                    {
                        "assumption_id": "A2", "source_id": "S99", "stance": "supports",
                        "reason": "The cited source ID was never retrieved.",
                    },
                ],
                "experiment": copy.deepcopy(self.demo["experiment"]),
            }

        # Keep fixture ID order stable for these mocks; the planning adapter assigns IDs by input order.
        self.demo["assumptions"].sort(key=lambda assumption: assumption["id"])
        with patch("idea_diligence.engine.model_json", side_effect=fake_model), patch(
            "idea_diligence.engine.search_web",
            return_value=[
                {
                    "title": "Public example", "url": "https://example.com/example",
                    "content": verified_text, "raw_content": f"Product description\n\n{verified_text}",
                },
                {
                    "title": "Unconfirmed example", "url": "https://example.org/listing",
                    "content": unverified_text, "raw_content": "A different page.",
                },
            ],
        ) as search:
            result = run_analysis(self.brief, mode="live", allow_external=True)
        self.assertEqual(result["mode"], "live")
        self.assertLessEqual(search.call_count, 5)
        self.assertEqual(result["usage"]["model_calls"], 2)
        self.assertEqual(len(result["sources"]), 2)
        self.assertEqual([source["kind"] for source in result["sources"]], ["page_excerpt", "search_snippet"])
        self.assertEqual([link["stance"] for link in result["links"]], ["context", "context"])
        self.assertEqual({link["source_id"] for link in result["links"]}, {"S1", "S2"})
        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["warnings"])
        self.assertEqual(result["experiment"]["assumption_id"], "A1")

    def test_next_experiment_skips_a_higher_ranked_directional_assumption(self):
        self.demo["assumptions"].sort(key=lambda assumption: assumption["id"])
        plan = model_plan(self.demo)
        plan["assumptions"][0]["impact"] = 4  # A2 ranks first on the impact tiebreaker.
        evidence = "An existing product advertises researched audio briefings from a topic prompt."
        assessment = {
            "links": [{
                "assumption_id": "A2", "source_id": "S1", "stance": "challenges",
                "reason": "The cited product already advertises topic-to-audio research.",
            }],
            "experiment": self.demo["experiment"],
        }
        with patch("idea_diligence.engine.model_json", side_effect=[plan, assessment]), patch(
            "idea_diligence.engine.search_web", return_value=[{
                "title": "Existing audio product", "url": "https://example.com/audio",
                "content": evidence, "raw_content": evidence,
            }],
        ):
            result = run_analysis(self.brief, mode="live", allow_external=True)

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["assumptions"][0]["id"], "A2")
        self.assertEqual(result["assumptions"][0]["status"], "challenged")
        self.assertEqual(result["experiment"]["assumption_id"], "A1")

    def test_model_unavailable_yields_honest_partial_run(self):
        with patch("idea_diligence.engine.model_json", side_effect=ProviderError("Language model returned HTTP 503.")), patch(
            "idea_diligence.engine.search_web"
        ) as search:
            result = run_analysis(self.brief, mode="live", allow_external=True)
        search.assert_not_called()
        self.assertEqual(result["mode"], "live")
        self.assertEqual(result["status"], "partial")
        self.assertIsNone(result["experiment"])
        self.assertTrue(result["warnings"])

    def test_live_research_requires_explicit_provider_consent(self):
        with patch("idea_diligence.engine.model_json") as model, patch(
            "idea_diligence.engine.search_web"
        ) as search:
            with self.assertRaises(ValueError):
                run_analysis(self.brief, mode="live")
        model.assert_not_called()
        search.assert_not_called()


if __name__ == "__main__":
    unittest.main()
