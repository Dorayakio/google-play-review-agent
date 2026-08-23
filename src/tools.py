"""Tool definitions and execution for the review analysis agent."""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .data import dataset_stats, parse_date
from .models import Review


@dataclass
class ToolContext:
    reviews: List[Review]
    app_id: str
    country: Optional[str] = None
    language: Optional[str] = None


def tool_schemas() -> List[Dict[str, Any]]:
    """Return OpenAI-compatible function tool schemas."""
    return [
        {
            "type": "function",
            "function": {
                "name": "get_dataset_stats",
                "description": "Get review count, score distribution, date range and low-score rate.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_reviews",
                "description": "Search original review text and return matching evidence reviews.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "min_score": {"type": "number", "minimum": 0, "maximum": 5},
                        "max_score": {"type": "number", "minimum": 0, "maximum": 5},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "sample_reviews",
                "description": "Return a deterministic sample of reviews, optionally focused on low scores or a query.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "min_score": {"type": "number", "minimum": 0, "maximum": 5},
                        "max_score": {"type": "number", "minimum": 0, "maximum": 5},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_reviews_by_score",
                "description": "Filter reviews by a score range and return evidence text.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "min_score": {"type": "number", "minimum": 0, "maximum": 5},
                        "max_score": {"type": "number", "minimum": 0, "maximum": 5},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_reviews_by_time_period",
                "description": "Filter reviews by inclusive ISO dates and return evidence text.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string"},
                        "end_date": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                    },
                },
            },
        },
    ]


def execute_tool(name: str, arguments: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    args = arguments or {}
    if name == "get_dataset_stats":
        return dataset_stats(context.reviews)
    if name == "search_reviews":
        return _review_result(_search(context.reviews, args.get("query", ""), args), args.get("limit", 10))
    if name == "sample_reviews":
        matches = _search(context.reviews, args.get("query", ""), args)
        if not args.get("query") and args.get("max_score") is None:
            matches = sorted(matches, key=lambda review: (review.score, review.review_date or "", review.review_id))
        return _review_result(matches, args.get("limit", 10))
    if name == "get_reviews_by_score":
        return _review_result(_filter_score(context.reviews, args), args.get("limit", 10))
    if name == "get_reviews_by_time_period":
        return _review_result(_filter_time(context.reviews, args), args.get("limit", 10))
    raise ValueError("Unknown tool: %s" % name)


def _search(reviews: List[Review], query: str, args: Dict[str, Any]) -> List[Review]:
    tokens = [token.lower() for token in str(query or "").split() if token.strip()]
    matches = []
    for review in reviews:
        if not _score_match(review, args):
            continue
        text = review.content.lower()
        if not tokens or all(token in text for token in tokens):
            matches.append(review)
    return sorted(matches, key=lambda review: (review.score, review.review_date or "", review.review_id))


def _filter_score(reviews: List[Review], args: Dict[str, Any]) -> List[Review]:
    return sorted(
        [review for review in reviews if _score_match(review, args)],
        key=lambda review: (review.score, review.review_date or "", review.review_id),
    )


def _filter_time(reviews: List[Review], args: Dict[str, Any]) -> List[Review]:
    start = parse_date(args.get("start_date"))
    end = parse_date(args.get("end_date"))
    matches = []
    for review in reviews:
        date = parse_date(review.review_date)
        if not date:
            continue
        if start and date < start:
            continue
        if end and date > end:
            continue
        matches.append(review)
    return sorted(matches, key=lambda review: (review.review_date or "", review.review_id))


def _score_match(review: Review, args: Dict[str, Any]) -> bool:
    min_score = args.get("min_score")
    max_score = args.get("max_score")
    if min_score is not None and review.score < float(min_score):
        return False
    if max_score is not None and review.score > float(max_score):
        return False
    return True


def _review_result(reviews: List[Review], limit: Any) -> Dict[str, Any]:
    try:
        safe_limit = max(1, min(20, int(limit)))
    except (TypeError, ValueError):
        safe_limit = 10
    selected = reviews[:safe_limit]
    return {
        "count": len(reviews),
        "returned": len(selected),
        "reviews": [
            {
                "review_id": review.review_id,
                "score": review.score,
                "review_date": review.review_date,
                "content": review.content,
            }
            for review in selected
        ],
    }


def compact_tool_result(result: Dict[str, Any]) -> str:
    """Keep traces readable while preserving evidence IDs and counts."""
    if "reviews" in result:
        return json.dumps({"count": result.get("count"), "returned": result.get("returned")}, ensure_ascii=False)
    return json.dumps(result, ensure_ascii=False)[:500]
