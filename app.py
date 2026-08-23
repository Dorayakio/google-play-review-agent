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
CUSTOM_OPTION = "custom"

COUNTRY_OPTIONS = [
    ("fr", "法国 / France"),
    ("us", "美国 / United States"),
    ("gb", "英国 / United Kingdom"),
    ("ca", "加拿大 / Canada"),
    ("au", "澳大利亚 / Australia"),
    ("de", "德国 / Germany"),
    ("es", "西班牙 / Spain"),
    ("it", "意大利 / Italy"),
    ("nl", "荷兰 / Netherlands"),
    ("jp", "日本 / Japan"),
    ("kr", "韩国 / South Korea"),
    ("hk", "中国香港 / Hong Kong"),
    ("tw", "中国台湾 / Taiwan"),
    ("sg", "新加坡 / Singapore"),
    ("in", "印度 / India"),
    (CUSTOM_OPTION, "自定义 / Custom"),
]

REVIEW_LANGUAGE_OPTIONS = [
    ("fr", "法语 / French"),
    ("en", "英语 / English"),
    ("zh", "中文 / Chinese"),
    ("de", "德语 / German"),
    ("es", "西班牙语 / Spanish"),
    ("it", "意大利语 / Italian"),
    ("ja", "日语 / Japanese"),
    ("ko", "韩语 / Korean"),
    ("pt", "葡萄牙语 / Portuguese"),
    ("ru", "俄语 / Russian"),
    ("tr", "土耳其语 / Turkish"),
    ("hi", "印地语 / Hindi"),
    (CUSTOM_OPTION, "自定义 / Custom"),
]

UI_TEXT = {
    "zh": {
        "language_name": "中文",
        "page_title": "Google Play 应用评论洞察 Agent",
        "caption": "一次分析一个 Google Play 应用。Deliveroo 只是默认的缓存演示数据。",
        "data_source": "数据来源",
        "package_name": "Google Play 包名",
        "country": "国家/地区",
        "review_language": "评论语言",
        "custom_country": "自定义国家/地区代码（例如 de）",
        "custom_language": "自定义评论语言代码（例如 de）",
        "review_count": "评论数量",
        "sort": "排序方式",
        "newest": "最新评论",
        "relevant": "最相关",
        "start_date": "起始日期（YYYY-MM-DD）",
        "end_date": "结束日期（YYYY-MM-DD）",
        "source": "评论来源",
        "cached": "缓存/演示数据",
        "fetch": "抓取 Google Play",
        "upload": "上传 CSV",
        "csv_file": "CSV 文件",
        "fetch_reviews": "抓取评论",
        "fetched": "已抓取 {count} 条评论。",
        "switch_source": "你可以切换到缓存/演示数据，或上传 CSV 继续分析。",
        "no_reviews": "没有找到可用评论。请抓取、上传，或选择缓存/演示数据。",
        "loaded": "已从 {source}加载 {count} 条评论。",
        "ask": "向评论分析 Agent 提问",
        "question": "最重要的用户问题是什么？产品团队应该优先改进什么？",
        "report_language": "报告语言",
        "analyze": "分析评论",
        "analyzing": "正在分析评论……",
        "demo_mode": "演示模式：未配置 LLM API Key，本报告由离线规则生成。",
        "reviews": "评论数",
        "average_score": "平均评分",
        "low_score_rate": "低评分占比",
        "topics": "主题数",
        "overview": "总体概况",
        "priority_themes": "优先主题",
        "recommendation": "建议",
        "topic_meta": "评论数：{count}（{share:.1f}%） · 平均评分：{score:.2f} · 严重度：{severity:.2f} · 近期性：{recency:.2f} · 优先级：{priority:.3f}",
        "facts": "事实",
        "inferences": "推断",
        "evidence": "评论证据",
        "limitations": "局限性",
        "trace": "Agent 工具调用轨迹",
        "download_json": "下载 JSON",
        "download_markdown": "下载 Markdown",
        "google_play": "Google Play",
        "uploaded": "上传的 CSV",
        "cached_csv": "缓存 CSV",
        "built_in_demo": "内置演示数据",
        "report_zh": "中文",
        "report_en": "English",
        "interface_language": "界面语言 / Interface language",
    },
    "en": {
        "language_name": "English",
        "page_title": "Google Play App Review Intelligence Agent",
        "caption": "Analyze one Google Play app at a time. Deliveroo is only the default cached demo dataset.",
        "data_source": "Data source",
        "package_name": "Google Play package name",
        "country": "Country",
        "review_language": "Review language",
        "custom_country": "Custom country code (e.g. de)",
        "custom_language": "Custom review language code (e.g. de)",
        "review_count": "Review count",
        "sort": "Sort",
        "newest": "Newest",
        "relevant": "Most relevant",
        "start_date": "Start date (YYYY-MM-DD)",
        "end_date": "End date (YYYY-MM-DD)",
        "source": "Source",
        "cached": "Cached/demo",
        "fetch": "Fetch Google Play",
        "upload": "Upload CSV",
        "csv_file": "CSV file",
        "fetch_reviews": "Fetch reviews",
        "fetched": "Fetched {count} reviews.",
        "switch_source": "You can switch to Cached/demo or upload a CSV to continue.",
        "no_reviews": "No usable reviews found. Fetch, upload, or choose Cached/demo.",
        "loaded": "Loaded {count} reviews from {source}.",
        "ask": "Ask the review analyst",
        "question": "What are the most important user problems, and what should the product team improve first?",
        "report_language": "Report language",
        "analyze": "Analyze reviews",
        "analyzing": "Running review analysis...",
        "demo_mode": "Demo mode: no LLM API key was configured, so the offline fallback generated this report.",
        "reviews": "Reviews",
        "average_score": "Average score",
        "low_score_rate": "Low-score rate",
        "topics": "Topics",
        "overview": "Overview",
        "priority_themes": "Priority themes",
        "recommendation": "Recommendation",
        "topic_meta": "Reviews: {count} ({share:.1f}%) · Avg score: {score:.2f} · Severity: {severity:.2f} · Recency: {recency:.2f} · Priority: {priority:.3f}",
        "facts": "Facts",
        "inferences": "Inferences",
        "evidence": "Evidence",
        "limitations": "Limitations",
        "trace": "Agent tool trace",
        "download_json": "Download JSON",
        "download_markdown": "Download Markdown",
        "google_play": "Google Play",
        "uploaded": "uploaded CSV",
        "cached_csv": "cached CSV",
        "built_in_demo": "built-in demo",
        "report_zh": "中文",
        "report_en": "English",
        "interface_language": "Interface language / 界面语言",
    },
}


def _t(language: str, key: str, **values: object) -> str:
    text = UI_TEXT.get(language, UI_TEXT["zh"]).get(key, UI_TEXT["en"].get(key, key))
    return text.format(**values)


def _source_label(language: str, source: str) -> str:
    return _t(language, source)


def _option_label(options: list[tuple[str, str]], value: str) -> str:
    return dict(options).get(value, value)


def main() -> None:
    try:
        import streamlit as st
    except ImportError:
        raise SystemExit("Streamlit is not installed. Run: pip install -r requirements.txt")

    st.set_page_config(page_title="Google Play App Review Intelligence", page_icon="🔎", layout="wide")

    with st.sidebar:
        ui_language = st.selectbox(
            "Language / 界面语言",
            ["zh", "en"],
            format_func=lambda item: _t(item, "language_name"),
            index=0,
        )
        t = lambda key, **values: _t(ui_language, key, **values)

        st.header(t("data_source"))
        app_id = st.text_input(t("package_name"), value=DEFAULT_APP_ID)
        country_choice = st.selectbox(
            t("country"),
            [code for code, _ in COUNTRY_OPTIONS],
            index=0,
            format_func=lambda item: _option_label(COUNTRY_OPTIONS, item),
        )
        country = (
            st.text_input(t("custom_country"), value="", placeholder="de").strip().lower()
            if country_choice == CUSTOM_OPTION else country_choice
        )
        language_choice = st.selectbox(
            t("review_language"),
            [code for code, _ in REVIEW_LANGUAGE_OPTIONS],
            index=0,
            format_func=lambda item: _option_label(REVIEW_LANGUAGE_OPTIONS, item),
        )
        language = (
            st.text_input(t("custom_language"), value="", placeholder="de").strip().lower()
            if language_choice == CUSTOM_OPTION else language_choice
        )
        count = st.slider(t("review_count"), min_value=20, max_value=5000, value=500, step=20)
        sort = st.selectbox(
            t("sort"),
            ["newest", "relevant"],
            index=0,
            format_func=lambda item: t(item),
        )
        start_date = st.text_input(t("start_date"), value="")
        end_date = st.text_input(t("end_date"), value="")
        source = st.radio(
            t("source"),
            ["cached", "fetch", "upload"],
            format_func=lambda item: _source_label(ui_language, item),
        )
        uploaded = st.file_uploader(t("csv_file"), type=["csv"]) if source == "upload" else None

        if source == "fetch":
            fetch_clicked = st.button(t("fetch_reviews"))
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
                    st.session_state["source_label"] = "google_play"
                    st.success(t("fetched", count=len(fetched)))
                except CollectorError as exc:
                    st.error(str(exc))
                    st.info(t("switch_source"))

    st.title(t("page_title"))
    st.caption(t("caption"))

    reviews, source_label = _resolve_reviews(source, app_id, country, language, uploaded, st)
    if not reviews:
        st.warning(t("no_reviews"))
        return

    st.info(t("loaded", count=len(reviews), source=_source_label(ui_language, source_label)))
    question = st.text_area(
        t("ask"),
        value=t("question"),
        height=80,
    )
    output_language = st.selectbox(
        t("report_language"),
        ["zh", "en"],
        index=0 if ui_language == "zh" else 1,
        format_func=lambda item: t("report_" + item),
    )

    if st.button(t("analyze"), type="primary"):
        with st.spinner(t("analyzing")):
            context = ToolContext(reviews, app_id=app_id, country=country, language=language)
            report = ReviewAgent(context, output_language=output_language).run(question)
        st.session_state["report"] = report

    report = st.session_state.get("report")
    if report:
        _render_report(st, report, ui_language)


def _resolve_reviews(source: str, app_id: str, country: str, language: str,
                     uploaded: object, st: object) -> Tuple[List[Review], str]:
    if source == "upload" and uploaded is not None:
        try:
            return load_reviews_csv(uploaded, app_id=app_id, country=country, language=language), "uploaded"
        except ValueError as exc:
            st.error(str(exc))
            return [], "uploaded"
    if source == "fetch" and "reviews" in st.session_state and st.session_state.get("source_label") == "google_play":
        return st.session_state["reviews"], "google_play"
    if source == "cached":
        cache_path = _find_cache(app_id)
        if cache_path:
            try:
                return load_reviews_csv(cache_path, app_id=app_id, country=country, language=language), "cached_csv"
            except ValueError:
                pass
    return _built_in_demo_reviews(app_id, country, language), "built_in_demo"


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


def _render_report(st: object, report: InsightReport, language: str) -> None:
    t = lambda key, **values: _t(language, key, **values)
    if report.demo_mode:
        st.warning(t("demo_mode"))
    metrics = st.columns(4)
    metrics[0].metric(t("reviews"), report.review_count)
    metrics[1].metric(t("average_score"), "%.2f/5" % report.average_score)
    metrics[2].metric(t("low_score_rate"), "%.1f%%" % (report.low_score_rate * 100))
    metrics[3].metric(t("topics"), len(report.topics))
    st.subheader(t("overview"))
    st.write(report.overview)
    st.subheader(t("priority_themes"))
    for index, topic in enumerate(report.topics, 1):
        with st.expander("%d. %s — %s" % (index, topic.name, topic.impact), expanded=index == 1):
            st.write(topic.summary)
            st.write("**%s:** %s" % (t("recommendation"), topic.recommendation))
            st.caption(t(
                "topic_meta",
                count=topic.review_count,
                share=topic.share * 100,
                score=topic.average_score,
                severity=topic.severity,
                recency=topic.recency,
                priority=topic.priority_score,
            ))
            if topic.facts:
                st.markdown("**%s**\n\n%s" % (t("facts"), "\n".join("- " + item for item in topic.facts)))
            if topic.inferences:
                st.markdown("**%s**\n\n%s" % (t("inferences"), "\n".join("- " + item for item in topic.inferences)))
            st.markdown("**%s**" % t("evidence"))
            for evidence in topic.evidence:
                st.markdown("- `%s` · %.1f/5 · %s" % (evidence.review_id, evidence.score, evidence.quote))
    with st.expander(t("limitations")):
        for item in report.limitations:
            st.write("- " + item)
    with st.expander(t("trace")):
        for item in report.trace:
            st.write("`%s` — %s" % (item.name, item.result_summary))
    st.download_button(t("download_json"), report_as_json(report), file_name="review_report.json", mime="application/json")
    st.download_button(t("download_markdown"), report_as_markdown(report), file_name="review_report.md", mime="text/markdown")


if __name__ == "__main__":
    main()
