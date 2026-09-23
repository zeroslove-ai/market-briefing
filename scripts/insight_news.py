"""Headline relevance, lightweight story clustering, and deep-research queue creation."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from state_store import atomic_write_json, state_path


TOPICS = {
    "semiconductor": {"semiconductor", "chip", "chips", "tsmc", "nvda", "nvidia", "amd", "micron", "mu", "soxx"},
    "oil": {"oil", "wti", "hormuz", "opec", "supply", "demand", "eia", "crude", "petroleum", "diesel"},
    "rates": {"yield", "bond", "fed", "federal reserve", "auction", "inflation", "interest rate", "interest rates", "treasury auction"},
    "growth": {"nasdaq", "growth", "technology", "tech", "russell", "small-cap", "small cap"},
    "crypto": {"bitcoin", "btc", "ethereum", "eth", "crypto"},
}
STOPWORDS = {
    "the", "and", "for", "with", "after", "amid", "says", "said", "from", "into",
    "what", "could", "would", "about", "this", "that", "their", "over", "under",
    "stocks", "stock", "market", "markets", "update", "live", "key", "takeaways",
    "business", "company", "news", "report", "day", "week", "today", "trump",
    "administration", "officials", "situation", "amid", "floats", "conditions",
}


def _text(item: dict) -> str:
    return " ".join(str(item.get(k) or "") for k in ("title", "title_ko", "summary", "description")).lower()


def _topic_scores(text: str) -> dict[str, int]:
    return {topic: sum((3 if len(term) > 3 else 2) if re.search(r"\b" + re.escape(term) + r"\b", text) else 0 for term in terms) for topic, terms in TOPICS.items()}


def _event_tokens(item: dict) -> set[str]:
    title = " ".join((str(item.get("title_ko") or ""), str(item.get("title") or ""))).lower()
    return {word for word in re.findall(r"[a-z0-9]{3,}", title) if word not in STOPWORDS}


def _best_topic(item: dict) -> str:
    title = " ".join((str(item.get("title_ko") or ""), str(item.get("title") or ""))).lower()
    scores = _topic_scores(title)
    return max(scores, key=scores.get) if max(scores.values(), default=0) else "market"


def _cluster_key(item: dict, text: str) -> str:
    explicit = item.get("story_id") or item.get("cluster_id")
    if explicit:
        return str(explicit)
    scores = _topic_scores(text)
    if max(scores.values(), default=0):
        return max(scores, key=scores.get)
    words = sorted(_event_tokens(item))
    return " ".join(words[:5]) or str(item.get("title") or "untitled").lower()


def rank_and_cluster_news(news: list[dict], anomalies: list[dict], claims: list[dict], limit: int = 5) -> list[dict]:
    anomaly_topics = set()
    for anomaly in anomalies:
        metric = anomaly.get("anomaly_id", "")
        if "wti" in metric:
            anomaly_topics.add("oil")
        if "soxx" in metric or "nasdaq" in metric:
            anomaly_topics.update(("semiconductor", "growth"))
        if "us10y" in metric:
            anomaly_topics.add("rates")
        if "btc" in metric or "eth" in metric:
            anomaly_topics.add("crypto")
    claim_topics = set()
    for claim in claims:
        claim_topics.update(str(x) for x in claim.get("affected_assets", []))
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in news or []:
        if not isinstance(item, dict) or item.get("error"):
            continue
        raw_title = str(item.get("title_ko") or item.get("title") or "").strip()
        if not raw_title or raw_title == "-":
            continue
        text = _text(item)
        title = " ".join((str(item.get("title_ko") or ""), str(item.get("title") or ""))).lower()
        scores = _topic_scores(title)
        relevance = sum(min(score, 4) + (2 if topic in anomaly_topics else 0) for topic, score in scores.items() if score)
        relevant_assets = [topic for topic, score in scores.items() if score]
        if any(
            topic in claim_topics
            or (topic == "semiconductor" and bool(claim_topics & {"semiconductors", "technology"}))
            or (topic == "growth" and bool(claim_topics & {"growth", "small_caps"}))
            for topic in relevant_assets
        ):
            relevance += 2
        if item.get("url") or item.get("link"):
            relevance += 1
        enriched = {**item, "relevance_score": relevance, "matched_topics": relevant_assets}
        tokens = _event_tokens(item)
        cluster = _cluster_key(item, title)
        if not item.get("story_id") and not item.get("cluster_id"):
            for candidate, existing in grouped.items():
                other = _event_tokens(existing[0])
                overlap = tokens & other
                if len(overlap) >= 3 or (overlap and len(overlap) / max(1, len(tokens | other)) >= 0.55):
                    cluster = candidate
                    break
        grouped[cluster].append(enriched)
    clusters = []
    for key, members in grouped.items():
        members.sort(key=lambda item: (item["relevance_score"], item.get("time") or ""), reverse=True)
        lead = members[0]
        title = lead.get("title_ko") or lead.get("title") or "제목 없음"
        topic = _best_topic(lead)
        why = {
            "semiconductor": "반도체 초과수익과 맞닿아 있지만, headline만으로 당일 가격 원인으로 단정할 수 없습니다.",
            "oil": "급격한 유가 변동의 공급·수요 설명을 구분하는 데 필요합니다.",
            "rates": "금리 민감 자산의 할인율과 다음 금리 촉매를 해석하는 데 필요합니다.",
            "growth": "성장주와 시장 폭의 괴리가 지속되는지 판단하는 맥락입니다.",
            "crypto": "위험자산 동조 여부를 보조 확인합니다.",
        }.get(topic, "시장 관련성을 현재 가격 움직임과 대조할 보조 근거입니다.")
        links = [{"title": item.get("title_ko") or item.get("title"), "url": item.get("url") or item.get("link"), "source": item.get("source"), "time": item.get("time")} for item in members[:4]]
        related_anomalies = [a for a in anomalies if (topic == "oil" and "wti" in a["anomaly_id"]) or (topic == "semiconductor" and "soxx" in a["anomaly_id"]) or (topic == "rates" and "us10y" in a["anomaly_id"]) or (topic == "growth" and any(x in a["anomaly_id"] for x in ("nasdaq", "soxx")))]
        reactions = []
        for anomaly in related_anomalies:
            value = anomaly["value"]
            unit = "pp" if "spread" in anomaly["anomaly_id"] else "bp" if anomaly["anomaly_id"] == "us10y_change_bp" else "%"
            reactions.append(f"{anomaly['metric']} {value:+.2f}{unit}")
        market_reaction = (
            "관찰된 같은 세션 움직임: " + ", ".join(reactions) + ". 동시성만으로 인과를 확정하지 않습니다."
            if reactions else "이 스토리와 직접 연결되는 가격 반응은 확인되지 않았습니다."
        )
        clusters.append({
            "story_id": key, "topic": topic, "relevance_score": max(x["relevance_score"] for x in members),
            "what_happened": title, "why_it_matters": why,
            "market_reaction": market_reaction,
            "counter_evidence": "뉴스 시점과 가격 움직임의 동시성만으로 인과를 단정하지 않습니다.",
            "what_to_watch": "후속 공식 발표와 관련 자산의 가격 반응",
            "sources": links,
        })
    # A source link alone is not evidence of market relevance. Drop generic feed
    # items with no asset/topic match so the ranking cannot become a top-N RSS list.
    return [item for item in sorted(clusters, key=lambda x: x["relevance_score"], reverse=True)
            if item["relevance_score"] >= 3][:limit]


QUERY_BY_ANOMALY = {
    "soxx_sp500_spread_pp": ("semiconductor AI chip stocks NVDA AMD MU TSMC catalyst earnings news", ["sector/index catalyst", "relevant company filings or earnings", "timestamp aligned to cash session"]),
    "wti_change_pct": ("oil WTI crude sharp move supply demand Hormuz OPEC EIA inventory news", ["dated supply or demand catalyst", "EIA/OPEC/official source where available", "timestamp aligned to price move"]),
    "us10y_change_bp": ("US Treasury 10-year yield move real yields Fed auction macro catalyst", ["yield and real-yield context", "Fed/Treasury event or macro release", "timestamp aligned to session"]),
    "nasdaq_russell_spread_pp": ("Nasdaq Russell 2000 relative performance drivers sector breadth rates", ["breadth or sector composition evidence", "rates and macro catalysts", "session-aligned market data"]),
}


def build_research_queue(anomalies: list[dict]) -> list[dict]:
    queue = []
    for anomaly in anomalies:
        query, evidence = QUERY_BY_ANOMALY.get(anomaly["anomaly_id"], (
            f"investigate cause and confirmation for {anomaly['metric']} move {anomaly['value']}",
            ["dated primary-source evidence", "cross-asset or sector confirmation", "counter-evidence"],
        ))
        queue.append({
            "priority": 1 if anomaly["severity"] == "HIGH" else 2,
            "anomaly_id": anomaly["anomaly_id"], "query": query,
            "reason": anomaly["reason"],
            "required_evidence": evidence, "status": "pending",
        })
    return sorted(queue, key=lambda x: (x["priority"], x["anomaly_id"]))


def write_research_queue(queue: list[dict]) -> Path:
    path = state_path("insight", "research_queue_latest.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, {"schema_version": 1, "items": queue})
    return path
