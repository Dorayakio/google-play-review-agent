"""Optional Google Play review collector."""

import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .data import normalize_date, write_reviews_csv
from .models import Review


class CollectorError(RuntimeError):
    """Raised when Google Play cannot be queried or its response is invalid."""


def collect_reviews(app_id: str, country: str = "us", language: str = "en",
                    count: int = 500, sort: str = "newest",
                    start_date: Optional[str] = None,
                    end_date: Optional[str] = None) -> List[Review]:
    try:
        from google_play_scraper import Sort, reviews as fetch_reviews
    except ImportError as exc:
        raise CollectorError("google-play-scraper is not installed.") from exc

    sort_value = Sort.NEWEST if sort.lower() == "newest" else Sort.MOST_RELEVANT
    normalized_start = normalize_date(start_date)
    normalized_end = normalize_date(end_date)
    try:
        raw_reviews, _ = fetch_reviews(
            app_id,
            lang=language,
            country=country,
            sort=sort_value,
            count=max(1, min(5000, int(count))),
            # No proxy is hard-coded. The library uses HTTP(S)_PROXY if configured by the user.
        )
    except Exception as exc:
        raise CollectorError("Google Play request failed: %s" % exc) from exc

    normalized: List[Review] = []
    for item in raw_reviews:
        content = str(item.get("content", "") or "").strip()
        if not content:
            continue
        review_date = normalize_date(_date_value(item.get("at")))
        if normalized_start and review_date and review_date < normalized_start:
            continue
        if normalized_end and review_date and review_date > normalized_end:
            continue
        normalized.append(Review(
            review_id=str(item.get("reviewId") or item.get("review_id") or ""),
            app_id=app_id,
            score=float(item.get("score", 0)),
            content=content,
            review_date=review_date,
            country=country,
            language=language,
        ))
    if not normalized:
        raise CollectorError("Google Play returned no usable reviews for this app and filter.")
    # Give records without a platform ID a stable ID through the normal CSV path.
    for index, review in enumerate(normalized):
        if not review.review_id:
            review.review_id = "%s-%04d" % (app_id.replace(".", "-"), index + 1)
    return normalized


def collect_and_save(app_id: str, destination: Path, **kwargs: object) -> Path:
    reviews = collect_reviews(app_id, **kwargs)
    return write_reviews_csv(reviews, destination)


def _date_value(value: object) -> Optional[str]:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value) if value else None
