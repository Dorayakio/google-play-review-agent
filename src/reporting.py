"""Human-readable report renderers."""

import json
from typing import List

from .models import InsightReport


def report_as_json(report: InsightReport) -> str:
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=2)


def report_as_markdown(report: InsightReport) -> str:
    lines: List[str] = [
        "# Google Play App Review Intelligence Report",
        "",
        "- App: `%s`" % report.app_id,
        "- Reviews: %d" % report.review_count,
        "- Average score: %.2f/5" % report.average_score,
        "- Low-score rate: %.1f%%" % (report.low_score_rate * 100),
        "",
        "## Overview",
        "",
        report.overview,
        "",
        "## Priority themes",
        "",
    ]
    for index, topic in enumerate(report.topics, 1):
        lines.extend([
            "### %d. %s" % (index, topic.name),
            "",
            topic.summary,
            "",
            "- Reviews: %d (%.1f%%)" % (topic.review_count, topic.share * 100),
            "- Average score: %.2f/5" % topic.average_score,
            "- Priority: %.3f" % topic.priority_score,
            "- Impact: %s" % topic.impact,
            "- Recommendation: %s" % topic.recommendation,
            "",
            "Evidence:",
        ])
        for evidence in topic.evidence:
            lines.append("- [%s, %.1f/5] %s" % (evidence.review_id, evidence.score, evidence.quote))
        lines.append("")
    lines.extend(["## Limitations", ""])
    lines.extend(["- " + item for item in report.limitations])
    lines.extend(["", "## Tool trace", ""])
    for item in report.trace:
        status = "ok" if item.success else "failed"
        lines.append("- `%s` (%s): %s" % (item.name, status, item.result_summary))
    return "\n".join(lines).strip() + "\n"
