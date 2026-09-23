import json
from pathlib import Path

from insight_engine import build_insight
from delivery_render import render_email_full, render_telegram_compact


FIXTURE = Path(__file__).parent / "fixtures" / "insight_golden.json"


def test_golden_sample_builds_deterministic_claims_queue_and_insight_rendering():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    insight = build_insight(payload)
    payload["insight"] = insight
    claims = {item["claim_id"] for item in insight["claims"]}
    assert {"SEMI_LEADERSHIP", "SMALL_CAP_LAG", "RATES_TAILWIND_GROWTH", "CROSS_ASSET_MIXED"} <= claims
    oil = next(item for item in insight["anomalies"] if item["anomaly_id"] == "wti_change_pct")
    assert oil["severity"] == "HIGH"
    assert {"semiconductor", "oil"} <= {item["query"].split()[0] for item in insight["research_queue"]}
    assert insight["economic_events"][0]["contextual_importance"] == 3
    assert len(insight["earnings"]["top"]) <= 5
    futures = {row["metric"]: row for row in insight["market_map"] if row["metric"] in {"ES", "NQ", "YM", "RTY"}}
    assert set(futures) == {"ES", "NQ", "YM", "RTY"}
    assert "neutral_or_unavailable" not in " ".join(row["interpretation"] for row in futures.values())

    subject, email, email_html = render_email_full(payload)
    telegram = "\n".join(render_telegram_compact(payload))
    assert len(telegram) <= 2500
    assert "반도체 주도" in subject and "SOXX +4.9%" in subject and "WTI -5.5%" in subject
    assert "HTTP 403" not in email and "HTTP 404" not in email
    assert "HTTP 403" not in email_html and "HTTP 404" not in email_html
    assert "HTTP 403" not in telegram and "HTTP 404" not in telegram
    assert "일부 공식 소스 지연" in email
    assert "왜 중요한가" in email


def test_anomaly_records_include_canonical_threshold_reason_and_severity():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    insight = build_insight(payload)
    soxx = next(item for item in insight["anomalies"] if item["anomaly_id"] == "soxx_sp500_spread_pp")
    assert soxx["severity"] == "HIGH"
    assert soxx["direction"] == "up"
    assert soxx["threshold"] == 2.0
    assert soxx["reason"]


def test_claims_keep_interpretations_distinct_from_observed_support():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    claims = build_insight(payload)["claims"]
    oil = next(item for item in claims if item["claim_id"] == "OIL_DISINFLATION_TAILWIND")
    assert oil["interpretation_type"] == "evidence_backed_interpretation"
    assert any("원인은 확인되지 않음" in item for item in oil["counter_evidence"])


def test_sigma_oi_conflict_requires_both_sigma_and_observed_oi_values():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["sigma"] = {"symbols": ["NVDA"]}
    assert not any(c["claim_id"].startswith("SIGMA_OI_") for c in build_insight(payload)["claims"])
    payload["options"] = {"NVDA": {"total_oi": 10}}
    claims = {c["claim_id"] for c in build_insight(payload)["claims"]}
    assert "SIGMA_OI_CONFLICT" in claims


def test_dxy_interpretation_follows_observed_direction():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["indicators"]["fx"]["dxy"]["change_pct"] = -0.7
    row = next(x for x in build_insight(payload)["market_map"] if x["metric"] == "DXY")
    assert "달러 약세" in row["interpretation"]


def test_failed_news_records_are_not_rendered_as_stories():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["news"] = [{"error": "RSS HTTP 403"}]
    assert build_insight(payload)["story_clusters"] == []


def test_unmatched_headlines_do_not_fill_story_slots():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["news"] = [{"title": "UN General Assembly photo gallery", "url": "https://example.test/gallery"}]
    assert build_insight(payload)["story_clusters"] == []
