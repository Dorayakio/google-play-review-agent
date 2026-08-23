"""Legacy baseline for comparison with the generic Agent.

This intentionally keeps the original French/Deliveroo keyword categories
out of the main product. It is only useful for showing a baseline comparison.
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data import load_reviews_csv


LEGACY_CATEGORIES = (
    ("delivery_delay", ("livreur", "retard", "attente", "estim", "durée")),
    ("order_quality", ("manque", "article", "trompé", "mauvais", "écrasé", "renversé", "incomplet")),
    ("price_and_fees", ("frais", "prix", "cher", "chère", "coûte", "montant")),
    ("payment_and_refund", ("paiement", "payement", "débité", "bancaire", "paypal", "remboursement")),
    ("support", ("service client", "aide", "contact", "chat", "sav", "réponse")),
    ("technical_experience", ("application", "appli", "bug", "crash", "erreur", "notification", "écran")),
)


def classify_legacy(text: str) -> str:
    lowered = text.lower()
    for category, keywords in LEGACY_CATEGORIES:
        if any(keyword in lowered for keyword in keywords):
            return category
    return "other"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the original keyword baseline.")
    parser.add_argument("--csv", default="data/samples/deliveroo_reviews_fr.csv")
    args = parser.parse_args()
    reviews = [review for review in load_reviews_csv(args.csv) if review.score <= 3]
    counts = Counter(classify_legacy(review.content) for review in reviews)
    print("Legacy baseline on %d low-score reviews" % len(reviews))
    for category, count in counts.most_common():
        print("%-24s %d" % (category, count))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
