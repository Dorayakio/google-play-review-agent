"""Command-line Google Play review collector.

Examples:
    python main.py --app-id com.deliveroo.orderapp --country fr --language fr
    python main.py --app-id com.example.app --output data/cache/example.csv
"""

import argparse
from pathlib import Path

from src.collector import CollectorError, collect_and_save


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect Google Play reviews for one app.")
    parser.add_argument("--app-id", required=True, help="Google Play package name")
    parser.add_argument("--country", default="us")
    parser.add_argument("--language", default="en")
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--sort", choices=["newest", "relevant"], default="newest")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--output", default="data/cache/reviews.csv")
    args = parser.parse_args()
    try:
        destination = collect_and_save(
            args.app_id,
            Path(args.output),
            country=args.country,
            language=args.language,
            count=args.count,
            sort=args.sort,
            start_date=args.start_date,
            end_date=args.end_date,
        )
    except CollectorError as exc:
        parser.error(str(exc))
        return 2
    print("Saved Google Play reviews to %s" % destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
