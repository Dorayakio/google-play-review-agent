"""Deterministic, multilingual fallback used for demos and offline runs."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from .data import dataset_stats, parse_date
from .models import Evidence, InsightReport, Review, TopicInsight, ToolTrace


THEME_PATTERNS: Sequence[Tuple[str, str, str, Tuple[str, ...], Tuple[str, ...]]] = (
    ("Reliability and bugs", "稳定性与故障", "Issues with crashes, errors or features not working.",
     ("crash", "bug", "error", "freeze", "lag", "broken", "plantage", "bug", "erreur", "bloque", "崩溃", "闪退", "卡顿", "故障"),
     ("Improve reliability and add clearer error recovery.", "提升稳定性，并提供更清晰的错误恢复路径。")),
    ("Login and account access", "登录与账户访问", "Users cannot log in, verify an account or recover access.",
     ("login", "log in", "sign in", "password", "account", "verification", "connexion", "compte", "mot de passe", "登录", "账号", "验证码"),
     ("Audit authentication and recovery flows, especially after updates.", "检查登录和找回账户流程，特别关注版本更新后的异常。")),
    ("Performance and battery/data use", "性能与电量/流量消耗", "Complaints about slow performance, loading or excessive resource use.",
     ("slow", "loading", "battery", "data", "lent", "chargement", "batterie", "耗电", "流量", "加载", "慢"),
     ("Profile slow paths and reduce unnecessary background work.", "定位慢路径，减少不必要的后台任务。")),
    ("Pricing, payments and subscriptions", "价格、支付与订阅", "Users report unexpected charges, pricing or subscription problems.",
     ("price", "expensive", "charge", "payment", "refund", "subscription", "prix", "paiement", "remboursement", "abonnement", "价格", "收费", "退款", "订阅"),
     ("Make fees and renewal terms explicit and simplify refund handling.", "明确费用和续订规则，并简化退款处理。")),
    ("Ads and interruptions", "广告与打断", "Advertising or interruptions interfere with the core experience.",
     ("ad", "ads", "advert", "popup", "pub", "publicité", "广告", "弹窗"),
     ("Review ad frequency, placement and the value exchange for users.", "检查广告频率、位置以及用户获得的价值。")),
    ("Customer support and response", "客服与响应", "Users cannot get help or receive a timely response.",
     ("support", "customer service", "help", "contact", "response", "support", "aide", "service client", "客服", "帮助", "响应"),
     ("Add clear escalation paths and publish expected response times.", "提供清晰的升级渠道，并公开预计响应时间。")),
    ("Usability and navigation", "易用性与导航", "Users struggle to understand, find or complete key actions.",
     ("confusing", "difficult", "hard to use", "navigation", "interface", "compliqué", "interface", "难用", "复杂", "界面", "找不到"),
     ("Test the highest-traffic flows with new and returning users.", "针对高频流程测试新用户和回访用户的使用路径。")),
    ("Content or feature quality", "内容或功能质量", "The app content or core features do not meet expectations.",
     ("feature", "content", "quality", "missing", "useless", "fonction", "contenu", "qualité", "功能", "内容", "不好用", "缺少"),
     ("Prioritize the most repeated unmet need and validate it with users.", "优先解决重复出现的核心需求，并用用户反馈验证改进。")),
)


def build_heuristic_report(reviews: Sequence[Review], app_id: str,
                           country: Optional[str], language: Optional[str],
                           output_language: str, question: str,
                           trace: Optional[List[ToolTrace]] = None,
                           demo_mode: bool = True) -> InsightReport:
    stats = dataset_stats(reviews)
    candidates = [review for review in reviews if review.score <= 3] or list(reviews)
    topics: List[TopicInsight] = []
    max_share = 0.0
    raw_topics = []
    for key, name_zh, summary_en, keywords, recommendations in THEME_PATTERNS:
        matched = [review for review in candidates if _contains_any(review.content, keywords)]
        if not matched:
            continue
        raw_topics.append((key, name_zh, summary_en, matched, recommendations))
        max_share = max(max_share, len(matched) / max(1, len(candidates)))

    if not raw_topics and candidates:
        raw_topics.append((
            "General low-rating feedback", "整体低评分反馈",
            "Low-rating reviews without a repeated keyword pattern.", candidates[:20],
            ("Review these examples manually before making a product decision.", "先人工阅读这些案例，再制定产品决策。"),
        ))

    for key, name_zh, summary_en, matched, recommendations in raw_topics:
        count = len(matched)
        share = count / max(1, len(candidates))
        average_score = sum(review.score for review in matched) / count
        severity = max(0.0, min(1.0, 1.0 - average_score / 5.0))
        recency = _recency_share(matched, reviews)
        prevalence = share / max_share if max_share else 0.0
        priority = 0.5 * prevalence + 0.3 * severity + 0.2 * recency
        evidence = [
            Evidence(
                review_id=review.review_id,
                score=review.score,
                quote=review.content,
                review_date=review.review_date,
                why_relevant="Matched the automatically discovered theme." if output_language == "en" else "评论文本与该主题匹配。",
            )
            for review in sorted(matched, key=lambda item: (item.score, item.review_date or "", item.review_id))[:3]
        ]
        if output_language == "zh":
            name = name_zh
            summary = _translate_summary(key, name_zh)
            recommendation = recommendations[1]
            impact = "高" if priority >= 0.65 else "中" if priority >= 0.4 else "低"
            facts = ["该主题占低评分评论的 %.1f%%。" % (share * 100), "相关评论平均评分为 %.2f/5。" % average_score]
            inferences = ["该问题可能影响用户留存或后续使用意愿。"]
        else:
            name = key
            summary = summary_en
            recommendation = recommendations[0]
            impact = "High" if priority >= 0.65 else "Medium" if priority >= 0.4 else "Low"
            facts = ["This theme represents %.1f%% of low-rating reviews." % (share * 100), "Matched reviews average %.2f/5." % average_score]
            inferences = ["This issue may affect retention or continued use."]
        topics.append(TopicInsight(
            name=name,
            summary=summary,
            review_count=count,
            share=round(share, 4),
            average_score=round(average_score, 3),
            severity=round(severity, 4),
            recency=round(recency, 4),
            priority_score=round(priority, 4),
            impact=impact,
            recommendation=recommendation,
            evidence=evidence,
            facts=facts,
            inferences=inferences,
        ))
    topics.sort(key=lambda topic: topic.priority_score, reverse=True)
    topics = topics[:7]
    overview = _overview(stats, topics, output_language)
    recommendations = [topic.recommendation for topic in topics[:3]]
    limitations = (
        ["主题由离线启发式规则发现，未调用云端模型。", "评论样本来自 Google Play，可能不代表全部用户。"]
        if output_language == "zh" else
        ["Topics were discovered by offline heuristics because no cloud model was configured.", "Google Play reviews may not represent the full user population."]
    )
    return InsightReport(
        app_id=app_id,
        country=country,
        language=language,
        review_count=len(reviews),
        average_score=stats["average_score"],
        low_score_rate=stats["low_score_rate"],
        date_range=stats["date_range"],
        overview=overview,
        topics=topics,
        recommendations=recommendations,
        limitations=limitations,
        language_output=output_language,
        demo_mode=demo_mode,
        trace=trace or [],
    )


def _contains_any(content: str, keywords: Sequence[str]) -> bool:
    text = content.lower()
    return any(keyword.lower() in text for keyword in keywords)


def _recency_share(topic_reviews: Sequence[Review], all_reviews: Sequence[Review]) -> float:
    dates = [parse_date(review.review_date) for review in all_reviews if parse_date(review.review_date)]
    topic_dates = [parse_date(review.review_date) for review in topic_reviews if parse_date(review.review_date)]
    if not dates or not topic_dates:
        return 0.5
    newest = max(dates)
    oldest = min(dates)
    window = max(1, (newest - oldest).days)
    cutoff = newest - timedelta(days=max(1, int(window * 0.3)))
    return sum(1 for date in topic_dates if date >= cutoff) / len(topic_dates)


def _overview(stats: Dict[str, object], topics: Sequence[TopicInsight], language: str) -> str:
    top = topics[0].name if topics else ("no repeated issue" if language == "en" else "暂无重复出现的主要问题")
    if language == "zh":
        return "共分析 %d 条评论，平均评分 %.2f/5，低评分评论占 %.1f%%。优先关注：%s。" % (
            stats["review_count"], stats["average_score"], stats["low_score_rate"] * 100, top)
    return "Analyzed %d reviews with an average score of %.2f/5; %.1f%% were low-score reviews. First priority: %s." % (
        stats["review_count"], stats["average_score"], stats["low_score_rate"] * 100, top)


def _translate_summary(key: str, name_zh: str) -> str:
    mapping = {
        "Reliability and bugs": "用户反馈应用崩溃、报错、卡顿或功能无法正常使用。",
        "Login and account access": "用户在登录、验证账号或找回访问权限时遇到问题。",
        "Performance and battery/data use": "用户反馈加载慢、性能不稳定或消耗过多电量/流量。",
        "Pricing, payments and subscriptions": "用户对价格、扣款、退款或订阅规则存在疑问或不满。",
        "Ads and interruptions": "广告或弹窗打断了核心使用体验。",
        "Customer support and response": "用户难以获得帮助，或客服响应不及时。",
        "Usability and navigation": "用户难以理解界面或完成关键操作。",
        "Content or feature quality": "应用内容或核心功能没有满足用户预期。",
    }
    return mapping.get(key, "%s 是评论中重复出现的一类问题。" % name_zh)
