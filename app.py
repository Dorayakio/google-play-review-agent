"""Streamlit UI for the Google Play App Review Intelligence Agent."""

from pathlib import Path
from typing import List, Optional, Tuple

from src.agent import ReviewAgent
from src.collector import CollectorError, collect_reviews
from src.data import load_reviews_csv, write_reviews_csv
from src.models import InsightReport, Review
from src.reporting import report_as_json, report_as_markdown
from src.tools import ToolContext


ROOT = Path(__file__).resolve().parent
DEFAULT_APP_ID = "com.deliveroo.orderapp"
DEFAULT_CACHE = ROOT / "data" / "samples" / "deliveroo_reviews_fr.csv"


def main() -> None:
    try:
        import streamlit as st
    except ImportError:
        raise SystemExit("Streamlit is not installed. Run: pip install -r requirements.txt")

    st.set_page_config(page_title="Google Play Review Intelligence", page_icon="🔎", layout="wide")
    st.title("Google Play App Review Intelligence Agent")
    st.caption("Analyze one Google Play app at a time. Deliveroo is only the default cached demo dataset.")

    with st.sidebar:
        st.header("Data source")
        app_id = st.text_input("Google Play package name", value=DEFAULT_APP_ID)
        country = st.text_input("Country", value="fr")
        language = st.text_input("Review language", value="fr")
        count = st.slider("Review count", min_value=20, max_value=5000, value=500, step=20)
        sort = st.selectbox("Sort", ["newest", "relevant"], index=0)
        start_date = st.text_input("Start date (YYYY-MM-DD)", value="")
        end_date = st.text_input("End date (YYYY-MM-DD)", value="")
        source = st.radio("Source", ["Cached/demo", "Fetch Google Play", "Upload CSV"])
        uploaded = st.file_uploader("CSV file", type=["csv"]) if source == "Upload CSV" else None

        if source == "Fetch Google Play":
            fetch_clicked = st.button("Fetch reviews")
            if fetch_clicked:
                try:
                    fetched = collect_reviews(
                        app_id, country, language, count, sort,
                        start_date=start_date or None,
                        end_date=end_date or None,
                    )
                    cache_path = ROOT / "data" / "cache" / (app_id.replace(".", "_") + ".csv")
                    write_reviews_csv(fetched, cache_path)
                    st.session_state["reviews"] = fetched
                    st.session_state["source_label"] = "Google Play"
                    st.success("Fetched %d reviews." % len(fetched))
                except CollectorError as exc:
                    st.error(str(exc))
                    st.info("You can switch to Cached/demo or upload a CSV to continue.")

    reviews, source_label = _resolve_reviews(source, app_id, country, language, uploaded, st)
    if not reviews:
        st.warning("No usable reviews found. Fetch, upload, or choose Cached/demo.")
        return

    st.info("Loaded %d reviews from %s." % (len(reviews), source_label))
    question = st.text_area(
        "Ask the review analyst",
        value="What are the most important user problems, and what should the product team improve first?",
        height=80,
    )
    output_language = st.selectbox("Report language", [("English", "en"), ("中文", "zh")], format_func=lambda item: item[0])[1]

    if st.button("Analyze reviews", type="primary"):
        with st.spinner("Running review analysis..."):
            context = ToolContext(reviews, app_id=app_id, country=country, language=language)
            report = ReviewAgent(context, output_language=output_language).run(question)
        st.session_state["report"] = report

    report = st.session_state.get("report")
    if report:
        _render_report(st, report)


def _resolve_reviews(source: str, app_id: str, country: str, language: str,
                     uploaded: object, st: object) -> Tuple[List[Review], str]:
    if source == "Upload CSV" and uploaded is not None:
        try:
            return load_reviews_csv(uploaded, app_id=app_id, country=country, language=language), "uploaded CSV"
        except ValueError as exc:
            st.error(str(exc))
            return [], "uploaded CSV"
    if source == "Fetch Google Play" and "reviews" in st.session_state and st.session_state.get("source_label") == "Google Play":
        return st.session_state["reviews"], "Google Play"
    if source == "Cached/demo":
        cache_path = _find_cache(app_id)
        if cache_path:
            try:
                return load_reviews_csv(cache_path, app_id=app_id, country=country, language=language), "cached CSV"
            except ValueError:
                pass
    return _built_in_demo_reviews(app_id, country, language), "built-in demo"


def _find_cache(app_id: str) -> Optional[Path]:
    if app_id == DEFAULT_APP_ID and DEFAULT_CACHE.exists():
        return DEFAULT_CACHE
    cache = ROOT / "data" / "cache" / (app_id.replace(".", "_") + ".csv")
    return cache if cache.exists() else None


def _built_in_demo_reviews(app_id: str, country: str, language: str) -> List[Review]:
    return [
        Review("demo-1", app_id, 1, "The app crashes every time I try to open my account.", "2026-01-02", country, language),
        Review("demo-2", app_id, 2, "Loading is very slow and the screen freezes.", "2026-01-03", country, language),
        Review("demo-3", app_id, 1, "I was charged twice and support has not replied.", "2026-01-04", country, language),
        Review("demo-4", app_id, 3, "The navigation is confusing after the update.", "2026-01-05", country, language),
        Review("demo-5", app_id, 5, "Simple and useful app.", "2026-01-06", country, language),
    ]


def _render_report(st: object, report: InsightReport) -> None:
    if report.demo_mode:
        st.warning("Demo mode: no LLM API key was configured, so the offline fallback generated this report.")
    metrics = st.columns(4)
    metrics[0].metric("Reviews", report.review_count)
    metrics[1].metric("Average score", "%.2f/5" % report.average_score)
    metrics[2].metric("Low-score rate", "%.1f%%" % (report.low_score_rate * 100))
    metrics[3].metric("Topics", len(report.topics))
    st.subheader("Overview")
    st.write(report.overview)
    st.subheader("Priority themes")
    for index, topic in enumerate(report.topics, 1):
        with st.expander("%d. %s — %s" % (index, topic.name, topic.impact), expanded=index == 1):
            st.write(topic.summary)
            st.write("**Recommendation:** %s" % topic.recommendation)
            st.caption(
                "Reviews: %d (%.1f%%) · Avg score: %.2f · Severity: %.2f · Recency: %.2f · Priority: %.3f" %
                (topic.review_count, topic.share * 100, topic.average_score, topic.severity, topic.recency, topic.priority_score)
            )
            if topic.facts:
                st.markdown("**Facts**\n\n" + "\n".join("- " + item for item in topic.facts))
            if topic.inferences:
                st.markdown("**Inferences**\n\n" + "\n".join("- " + item for item in topic.inferences))
            st.markdown("**Evidence**")
            for evidence in topic.evidence:
                st.markdown("- `%s` · %.1f/5 · %s" % (evidence.review_id, evidence.score, evidence.quote))
    with st.expander("Limitations"):
        for item in report.limitations:
            st.write("- " + item)
    with st.expander("Agent tool trace"):
        for item in report.trace:
            st.write("`%s` — %s" % (item.name, item.result_summary))
    st.download_button("Download JSON", report_as_json(report), file_name="review_report.json", mime="application/json")
    st.download_button("Download Markdown", report_as_markdown(report), file_name="review_report.md", mime="text/markdown")


if __name__ == "__main__":
    main()
