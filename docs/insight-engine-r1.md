# Insight Engine R1

Status: deterministic feature, evidence, story ranking and renderer authority.
Related: #2 Hermes R1 EPIC, #4 News & Event Intelligence, #6 Dual Delivery.

## Pipeline and source contract

The engine consumes the existing canonical morning payload and preserves its raw market indicators, news, economic calendar, earnings, options and data-quality fields. It appends an insight object with features, anomalies, claims, market map, story clusters, contextualized events, ranked earnings, research queue, and watch items. Email and Telegram renderers prefer insight; legacy payloads use a raw-data fallback.

All calculations in this release are deterministic. The narrative adapter contract is render(insight, style) and intentionally has no configured provider. Causal language stays an evidence-backed interpretation and includes support and counter-evidence.

## Feature and anomaly semantics

Equity changes and spreads are percentage points. Rates use the quote's yield change multiplied by 100 to convert percentage points to basis points. BTC/ETH remain explicitly 24-hour changes. Futures direction is compared with the mean direction of available futures and the prior cash session. Cross-asset confirmation counts positive contributions from equities, growth, falling rates, falling VIX, falling DXY and BTC.

An anomaly is emitted when the absolute change meets or exceeds its threshold. HIGH begins at 1.5x the threshold for absolute moves and relative spreads; otherwise the qualifying anomaly is MEDIUM.

| Feature | Threshold |
|---|---:|
| SOXX − S&P spread | 2.0 pp |
| Nasdaq − Russell spread | 1.5 pp |
| Nasdaq − S&P spread | 1.5 pp |
| US 10Y change | 5 bp |
| VIX change | 8% |
| DXY change | 0.5% |
| WTI change | 3.5% |
| Gold change | 2% |
| Silver change | 3% |
| BTC 24h change | 5% |
| ETH 24h change | 6% |

Each anomaly carries stable anomaly_id, severity, direction, metric, numeric value, threshold, and human-readable reason.

## Claim semantics

Claims are emitted only when observable conditions qualify. Required families include NARROW_GROWTH_RISK_ON, BROAD_RISK_ON, RISK_OFF_CONFIRMED, CROSS_ASSET_MIXED, RATES_TAILWIND_GROWTH, RATES_HEADWIND_GROWTH, VOLATILITY_EXPANSION, OIL_DISINFLATION_TAILWIND, OIL_DEMAND_SCARE, SEMI_LEADERSHIP, SMALL_CAP_LAG, and CRYPTO_CONFIRMATION. Optional SIGMA_OI_CONFIRMED / SIGMA_OI_CONFLICT are emitted only when Sigma/OI inputs exist.

Claim cutoffs are independent from anomaly cutoffs: SEMI_LEADERSHIP requires SOXX to beat the S&P by at least 1.0 pp; RATES_TAILWIND_GROWTH / RATES_HEADWIND_GROWTH require a 10Y move of at least 3 bp in the matching direction and a Nasdaq move in the confirming direction. Conclusion and subject wording must meet these same cutoffs; sub-threshold rate changes are omitted from driver language.

Every claim contains support, counter_evidence, confidence (HIGH / MEDIUM / LOW), affected_assets, what_to_watch, and interpretation_type. Co-movement is not proof of cause. The oil-tailwind claim therefore explicitly notes that a supply release and demand weakness imply different readings.

## Stories, evidence and research queue

News is ranked by exact topic/entity keyword matches, relevance to current anomalies and claims, and source URL presence. Same explicit cluster IDs or dominant topic keywords share a story cluster. The story contract is what_happened, why_it_matters, market_reaction, counter_evidence, what_to_watch, and sources.

Large moves create pending deep-research jobs for a later Grok/Work/Web adapter. The queue is written to state/insight/research_queue_latest.json; it does not send data externally. Semiconductor, oil, rates and other anomaly queries ask for dated catalyst evidence and counter-evidence. Queue fields: priority, anomaly_id, query, reason, required_evidence, status.

## Rendering and safety

Email begins with the central conclusion and includes 30-second takeaways, interpreted Market Map, top market drivers, 3–5 relevance-ranked story clusters, contextual calendar items, at most five ranked earnings with watch points, options/OI, and watch items. Full HTTP source failures stay in canonical state/logs; user-facing reports use a short source-delay summary.

Telegram renders the same insight object in one or two compact messages, aiming for 1,500–2,500 characters, with a number plus a one-line interpretation and a “why it matters” explanation.

Economic context may raise an event's importance when its topic overlaps a current anomaly (EIA during a large oil move; Treasury/Fed during a large 10Y move). Earnings ranking combines a stable known-importance ordering with current claim relevance; remaining items are summarized as 기타 실적 N개.
