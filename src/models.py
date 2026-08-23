"""Small, dependency-free data models used throughout the application."""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Review:
    review_id: str
    app_id: str
    score: float
    content: str
    review_date: Optional[str] = None
    country: Optional[str] = None
    language: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Evidence:
    review_id: str
    score: float
    quote: str
    review_date: Optional[str] = None
    why_relevant: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TopicInsight:
    name: str
    summary: str
    review_count: int
    share: float
    average_score: float
    severity: float
    recency: float
    priority_score: float
    impact: str
    recommendation: str
    evidence: List[Evidence] = field(default_factory=list)
    facts: List[str] = field(default_factory=list)
    inferences: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["evidence"] = [item.to_dict() for item in self.evidence]
        return payload


@dataclass
class ToolTrace:
    name: str
    arguments: Dict[str, Any]
    result_summary: str
    success: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InsightReport:
    app_id: str
    country: Optional[str]
    language: Optional[str]
    review_count: int
    average_score: float
    low_score_rate: float
    date_range: Dict[str, Optional[str]]
    overview: str
    topics: List[TopicInsight]
    recommendations: List[str]
    limitations: List[str]
    language_output: str = "en"
    demo_mode: bool = False
    trace: List[ToolTrace] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "app": {
                "app_id": self.app_id,
                "country": self.country,
                "language": self.language,
            },
            "dataset": {
                "review_count": self.review_count,
                "average_score": self.average_score,
                "low_score_rate": self.low_score_rate,
                "date_range": self.date_range,
            },
            "overview": self.overview,
            "topics": [topic.to_dict() for topic in self.topics],
            "recommendations": self.recommendations,
            "limitations": self.limitations,
            "language_output": self.language_output,
            "demo_mode": self.demo_mode,
            "trace": [item.to_dict() for item in self.trace],
        }


def report_from_dict(payload: Dict[str, Any], default_app_id: str,
                     default_country: Optional[str],
                     default_language: Optional[str],
                     output_language: str,
                     trace: Optional[List[ToolTrace]] = None,
                     demo_mode: bool = False) -> InsightReport:
    """Convert model JSON into a validated report with safe defaults."""

    app = payload.get("app") or {}
    dataset = payload.get("dataset") or {}
    topics: List[TopicInsight] = []

    for raw_topic in payload.get("topics") or []:
        if not isinstance(raw_topic, dict):
            continue
        evidence: List[Evidence] = []
        for raw_evidence in raw_topic.get("evidence") or []:
            if not isinstance(raw_evidence, dict):
                continue
            evidence.append(Evidence(
                review_id=str(raw_evidence.get("review_id", "")),
                score=_as_float(raw_evidence.get("score"), 0.0),
                quote=str(raw_evidence.get("quote", "")),
                review_date=raw_evidence.get("review_date"),
                why_relevant=str(raw_evidence.get("why_relevant", "")),
            ))
        topics.append(TopicInsight(
            name=str(raw_topic.get("name", "Untitled topic")),
            summary=str(raw_topic.get("summary", "")),
            review_count=max(0, _as_int(raw_topic.get("review_count"), 0)),
            share=max(0.0, _as_float(raw_topic.get("share"), 0.0)),
            average_score=_as_float(raw_topic.get("average_score"), 0.0),
            severity=max(0.0, min(1.0, _as_float(raw_topic.get("severity"), 0.0))),
            recency=max(0.0, min(1.0, _as_float(raw_topic.get("recency"), 0.0))),
            priority_score=max(0.0, min(1.0, _as_float(raw_topic.get("priority_score"), 0.0))),
            impact=str(raw_topic.get("impact", "")),
            recommendation=str(raw_topic.get("recommendation", "")),
            evidence=evidence,
            facts=[str(item) for item in raw_topic.get("facts", []) if item is not None],
            inferences=[str(item) for item in raw_topic.get("inferences", []) if item is not None],
        ))

    date_range = dataset.get("date_range") or {"start": None, "end": None}
    return InsightReport(
        app_id=str(app.get("app_id") or default_app_id),
        country=app.get("country") or default_country,
        language=app.get("language") or default_language,
        review_count=max(0, _as_int(dataset.get("review_count"), 0)),
        average_score=_as_float(dataset.get("average_score"), 0.0),
        low_score_rate=max(0.0, min(1.0, _as_float(dataset.get("low_score_rate"), 0.0))),
        date_range={"start": date_range.get("start"), "end": date_range.get("end")},
        overview=str(payload.get("overview", "")),
        topics=topics[:7],
        recommendations=[str(item) for item in payload.get("recommendations", []) if item is not None],
        limitations=[str(item) for item in payload.get("limitations", []) if item is not None],
        language_output=output_language,
        demo_mode=demo_mode,
        trace=trace or [],
    )


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
