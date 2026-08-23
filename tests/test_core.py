import json
import unittest
from io import StringIO

from src.agent import ReviewAgent
from src.data import dataset_stats, load_reviews_csv
from src.heuristic import build_heuristic_report
from src.reporting import report_as_json, report_as_markdown
from src.tools import ToolContext, execute_tool


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.csv = StringIO(
            "reviewId,rating,review,date\n"
            "r1,1,The app crashes after login,2026-01-01\n"
            "r2,2,Support never replies,2026-01-02\n"
            "r3,5,Simple and useful,2026-01-03\n"
        )
        self.reviews = load_reviews_csv(self.csv, app_id="com.example.test", country="us", language="en")
        self.context = ToolContext(self.reviews, "com.example.test", "us", "en")

    def test_csv_aliases_and_normalization(self):
        self.assertEqual(len(self.reviews), 3)
        self.assertEqual(self.reviews[0].review_id, "r1")
        self.assertEqual(self.reviews[0].review_date, "2026-01-01")
        self.assertEqual(dataset_stats(self.reviews)["low_score_rate"], 0.667)

    def test_tools_return_original_evidence(self):
        result = execute_tool("search_reviews", {"query": "crashes", "limit": 5}, self.context)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["reviews"][0]["review_id"], "r1")
        score_result = execute_tool("get_reviews_by_score", {"max_score": 2}, self.context)
        self.assertEqual(score_result["count"], 2)

    def test_heuristic_report_is_grounded_and_scored(self):
        report = build_heuristic_report(self.reviews, "com.example.test", "us", "en", "en", "find issues")
        review_ids = {review.review_id for review in self.reviews}
        self.assertTrue(report.topics)
        self.assertTrue(all(0 <= topic.priority_score <= 1 for topic in report.topics))
        self.assertTrue(all(evidence.review_id in review_ids for topic in report.topics for evidence in topic.evidence))

    def test_report_renderers(self):
        report = build_heuristic_report(self.reviews, "com.example.test", "us", "en", "en", "find issues")
        payload = json.loads(report_as_json(report))
        self.assertEqual(payload["app"]["app_id"], "com.example.test")
        self.assertIn("Priority themes", report_as_markdown(report))

    def test_tool_calling_path_and_quote_grounding(self):
        class Function:
            def __init__(self, name, arguments):
                self.name = name
                self.arguments = arguments

        class Call:
            def __init__(self, name, arguments):
                self.id = "call-1"
                self.function = Function(name, arguments)

        class Message:
            def __init__(self, content="", tool_calls=None):
                self.content = content
                self.tool_calls = tool_calls or []

        class Response:
            def __init__(self, message):
                self.choices = [type("Choice", (), {"message": message})()]

        class FakeClient:
            available = True

            def __init__(self):
                self.calls = 0

            def chat(self, messages, tools, final=False):
                self.calls += 1
                if self.calls == 1:
                    return Response(Message(tool_calls=[Call("get_dataset_stats", "{}")] ))
                payload = {
                    "app": {"app_id": "com.example.test", "country": "us", "language": "en"},
                    "dataset": {"review_count": 3, "average_score": 2.67, "low_score_rate": 0.667, "date_range": {"start": "2026-01-01", "end": "2026-01-03"}},
                    "overview": "The main issue is reliability.",
                    "topics": [{
                        "name": "Reliability", "summary": "Crashes", "review_count": 1, "share": 0.33,
                        "average_score": 1, "severity": 0.8, "recency": 0.5, "priority_score": 0.7,
                        "impact": "High", "recommendation": "Improve stability.",
                        "evidence": [{"review_id": "r1", "score": 5, "quote": "fabricated quote", "review_date": "2099-01-01"}],
                    }],
                    "recommendations": ["Improve stability."], "limitations": [],
                }
                return Response(Message(content=json.dumps(payload)))

        fake = FakeClient()
        report = ReviewAgent(self.context, output_language="en", client=fake).run("find issues")
        self.assertFalse(report.demo_mode)
        self.assertEqual(report.trace[0].name, "get_dataset_stats")
        self.assertEqual(report.topics[0].evidence[0].quote, "The app crashes after login")
        self.assertEqual(report.topics[0].evidence[0].score, 1)


if __name__ == "__main__":
    unittest.main()
