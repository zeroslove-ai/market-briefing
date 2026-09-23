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

    subject, email, _html = render_email_full(payload)
    telegram = "\n".join(render_telegram_compact(payload))
    assert "SOXX +4.9%" in subject and "WTI -5.5%" in subject
    assert subject.index("SOXX") < subject.index("WTI")
    assert "HTTP 403" not in email and "HTTP 404" not in email
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
