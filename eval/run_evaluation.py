"""Small, repeatable offline evaluation over three app categories."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data import load_reviews_csv
from src.heuristic import build_heuristic_report


SAMPLE_DIR = ROOT / "data" / "samples"


def main() -> int:
    files = [(ROOT / "data" / "samples" / "deliveroo_reviews_fr.csv", "com.deliveroo.orderapp", "fr", "fr")]
    files.extend((path, None, None, None) for path in sorted(SAMPLE_DIR.glob("*_reviews.csv")))
    results = []
    reports = {}
    for path, app_id, country, language in files:
        reviews = load_reviews_csv(path, app_id=app_id or "uploaded-app", country=country, language=language)
        report = build_heuristic_report(reviews, reviews[0].app_id, reviews[0].country, reviews[0].language, "en", "find the main user problems")
        review_ids = {review.review_id for review in reviews}
        evidence = [evidence for topic in report.topics for evidence in topic.evidence]
        grounded = sum(1 for item in evidence if item.review_id in review_ids)
        reports[report.app_id] = report
        results.append({
            "file": path.name,
            "reviews": len(reviews),
            "topics": len(report.topics),
            "evidence_grounding": grounded / len(evidence) if evidence else 1.0,
            "schema_valid": bool(report.to_dict().get("topics") is not None),
        })
    golden_path = ROOT / "eval" / "golden_reviews.jsonl"
    golden = [json.loads(line) for line in golden_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    covered = 0
    for item in golden:
        report = reports.get(item["app_id"])
        if report and any(topic.name == item["expected_theme"] for topic in report.topics):
            covered += 1
    summary = {
        "datasets": len(results),
        "evidence_grounding": sum(item["evidence_grounding"] for item in results) / len(results) if results else 0.0,
        "schema_valid": all(item["schema_valid"] for item in results),
        "golden_theme_coverage": covered / len(golden) if golden else 0.0,
        "golden_examples": len(golden),
        "details": results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
