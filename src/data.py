"""CSV loading, normalization and dataset statistics."""

import csv
import hashlib
import io
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from .models import Review


FIELD_ALIASES = {
    "review_id": ("review_id", "reviewId", "id"),
    "app_id": ("app_id", "appId", "package_name", "packageName"),
    "score": ("score", "rating", "stars"),
    "content": ("content", "review", "text", "comment"),
    "review_date": ("review_date", "date", "at", "published_at", "publishedAt"),
    "country": ("country", "region"),
    "language": ("language", "lang"),
}


Source = Union[str, Path, io.TextIOBase, io.BytesIO, Any]


def load_reviews_csv(source: Source, app_id: str = "uploaded-app",
                     country: Optional[str] = None,
                     language: Optional[str] = None) -> List[Review]:
    """Load and normalize a CSV from disk or a file-like/Streamlit object."""

    rows = _read_rows(source)
    if not rows:
        return []
    headers = {str(key).strip(): key for key in rows[0].keys() if key is not None}
    resolved = {field: _find_column(headers, aliases) for field, aliases in FIELD_ALIASES.items()}
    if not resolved["score"] or not resolved["content"]:
        raise ValueError("CSV must include a score/rating column and a content/review column.")

    reviews: List[Review] = []
    seen = set()
    for row in rows:
        content = str(row.get(resolved["content"], "") or "").strip()
        if not content:
            continue
        score = _parse_score(row.get(resolved["score"]))
        if score is None:
            continue
        row_app_id = _clean_optional(row.get(resolved["app_id"])) or app_id
        row_country = _clean_optional(row.get(resolved["country"])) or country
        row_language = _clean_optional(row.get(resolved["language"])) or language
        raw_date = _clean_optional(row.get(resolved["review_date"]))
        review_date = normalize_date(raw_date)
        supplied_id = _clean_optional(row.get(resolved["review_id"]))
        review_id = supplied_id or stable_review_id(row_app_id, score, content, review_date)
        if review_id in seen:
            continue
        seen.add(review_id)
        reviews.append(Review(
            review_id=review_id,
            app_id=row_app_id,
            score=score,
            content=content,
            review_date=review_date,
            country=row_country,
            language=row_language,
        ))
    return reviews


def write_reviews_csv(reviews: Sequence[Review], destination: Union[str, Path]) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "review_id", "app_id", "score", "content", "review_date", "country", "language"
        ])
        writer.writeheader()
        for review in reviews:
            writer.writerow(review.to_dict())
    return path


def stable_review_id(app_id: str, score: float, content: str,
                     review_date: Optional[str]) -> str:
    raw = "|".join([app_id, str(score), review_date or "", content])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def dataset_stats(reviews: Sequence[Review]) -> Dict[str, Any]:
    scores = [review.score for review in reviews]
    dates = sorted(review.review_date for review in reviews if review.review_date)
    score_distribution: Dict[str, int] = {}
    for score in scores:
        key = str(int(score)) if float(score).is_integer() else str(score)
        score_distribution[key] = score_distribution.get(key, 0) + 1
    low_count = sum(1 for score in scores if score <= 3)
    return {
        "review_count": len(reviews),
        "average_score": round(sum(scores) / len(scores), 3) if scores else 0.0,
        "low_score_rate": round(low_count / len(scores), 3) if scores else 0.0,
        "score_distribution": score_distribution,
        "date_range": {"start": dates[0] if dates else None, "end": dates[-1] if dates else None},
        "languages": sorted({review.language for review in reviews if review.language}),
        "countries": sorted({review.country for review in reviews if review.country}),
    }


def normalize_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = str(value).strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d",
        "%Y/%m/%d %H:%M", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return text[:10]


def parse_date(value: Optional[str]) -> Optional[datetime]:
    normalized = normalize_date(value)
    if not normalized:
        return None
    try:
        return datetime.strptime(normalized, "%Y-%m-%d")
    except ValueError:
        return None


def _read_rows(source: Source) -> List[Dict[str, str]]:
    if isinstance(source, (str, Path)):
        with Path(source).open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    if hasattr(source, "getvalue"):
        raw = source.getvalue()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8-sig")
        return list(csv.DictReader(io.StringIO(raw)))
    if isinstance(source, io.BytesIO):
        return list(csv.DictReader(io.StringIO(source.getvalue().decode("utf-8-sig"))))
    if hasattr(source, "read"):
        raw = source.read()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8-sig")
        return list(csv.DictReader(io.StringIO(raw)))
    raise TypeError("Unsupported CSV source.")


def _find_column(headers: Dict[str, str], aliases: Iterable[str]) -> Optional[str]:
    normalized = {key.lower().replace("-", "_"): value for key, value in headers.items()}
    for alias in aliases:
        if alias in headers:
            return headers[alias]
        if alias.lower() in normalized:
            return normalized[alias.lower()]
    return None


def _clean_optional(value: Any) -> Optional[str]:
    text = str(value).strip() if value is not None else ""
    return text or None


def _parse_score(value: Any) -> Optional[float]:
    try:
        score = float(str(value).strip().replace(",", "."))
        return score if 0 <= score <= 5 else None
    except (TypeError, ValueError):
        return None
