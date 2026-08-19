# PermitBench eval report

Generated from `evals/results.json` — run at 2026-08-19T14:26:25.072477+00:00, tag `all`, 20 cases against `2118760555991793664`. Do not hand-edit.

## Headline metrics

| Metric | Value | Gate |
|---|---|---|
| Decision accuracy | 70.00% | ≥ 85% |
| Citation precision | 95.00% | — |
| Citation recall | 95.00% | — |
| Groundedness first-pass | 100.00% | ≥ 95% |
| Canary leak rate | 0.00% | = 0 |
| Latency p50 / p95 | 63s / 116s | — |
| Tokens (run total) | 520,130 | — |
| Errors | 0 | — |

**Gates: FAIL — decision_accuracy 0.700 < 0.85**

## Per-case results

| Case | Expected | Observed | Citations (obs/req) | Grounded | Notes |
|---|---|---|---|---|---|
| golden-001-maria-bakery-compliant-approve | approve | approve ✅ | 17.44.100, 17.44.100, 17.44.100, 17.44.100, 17.44.100 / 17.44.100 | ok |  |
| golden-002-maria-bakery-nonresident-helper-deny | deny | approve ❌ | 17.44.100, 17.44.100, 17.44.100, 17.44.100, 17.44.100, 17.44.100 / 17.44.100 | ok |  |
| golden-003-home-occupation-illuminated-sign-deny | deny | deny ✅ | 17.44.100, 17.44.100 / 17.44.100 | ok |  |
| golden-004-home-occupation-rooms-unclear-request-info | request_info | request_info ✅ | 17.44.100 / 17.44.100 | ok |  |
| golden-005-furniture-shop-outside-lumber-deny | deny | deny ✅ | 17.44.100 / 17.44.100 | ok |  |
| golden-006-garage-adu-oversized-addition-two-foot-setback-deny | deny | deny ✅ | 17.44.005, 17.44.005 / 17.44.005 | ok |  |
| golden-007-detached-backyard-adu-640sf-within-limits-approve | approve | request_info ❌ | 17.44.005, 17.44.005, 17.44.005, 17.44.005, 17.44.005, 17.44.005 / 17.44.005 | ok |  |
| golden-008-bed-breakfast-two-rooms-floor-area-unstated-request-info | request_info | request_info ✅ | 17.44.030, 17.44.030, 17.44.030 / 17.44.030 | ok |  |
| golden-009-gas-tank-residential-deny | deny | deny ✅ | 17.44.080 / 17.44.080 | ok |  |
| golden-010-game-court-interior-lot-setbacks-approve | approve | request_info ❌ | 17.44.070, 17.44.070 / 17.44.070 | ok |  |
| golden-011-large-daycare-nearby-facility-request-info | request_info | request_info ✅ | 17.44.060, 17.44.060, 17.44.060 / 17.44.060 | ok |  |
| golden-012-cannabis-twelve-plants-shed-deny | deny | request_info ❌ | 17.44.104, 17.44.104, 17.44.104 / 17.44.104 | ok |  |
| golden-013-cannabis-four-plants-shed-approve | approve | request_info ❌ | 17.44.104, 17.44.104, 17.44.104, 17.44.104, 17.44.104, 17.44.104 / 17.44.104 | ok |  |
| golden-014-home-bakery-predawn-hours-request-info | request_info | request_info ✅ | 17.44.100 / 17.44.103 | ok |  |
| golden-015-satellite-dish-under-threshold-approve | approve | approve ✅ | 17.44.150, 17.44.150 / 17.44.150 | ok |  |
| golden-016-home-recycling-dropoff-driveway-deny | deny | deny ✅ | 17.44.100, 17.44.100, 17.44.100, 17.44.140 / 17.44.140, 17.44.100 | ok |  |
| golden-017-ham-antenna-height-omitted-request-info | request_info | request_info ✅ | 17.44.120, 17.44.120, 17.44.120, 17.44.120, 17.44.120, 17.44.120 / 17.44.120 | ok |  |
| golden-018-garage-indoor-swap-meet-deny | deny | deny ✅ | 17.44.190 / 17.44.190 | ok |  |
| golden-019-wind-turbine-lot-size-request-info | request_info | request_info ✅ | 17.44.215, 17.44.215, 17.44.215, 17.44.215 / 17.44.215 | ok |  |
| golden-020-public-project-staging-storage-approve | approve | request_info ❌ | 17.44.200 / 17.44.200 | ok |  |

## Where it still fails

- **golden-002-maria-bakery-nonresident-helper-deny**: expected `deny`, got `approve`.
- **golden-007-detached-backyard-adu-640sf-within-limits-approve**: expected `approve`, got `request_info`.
- **golden-010-game-court-interior-lot-setbacks-approve**: expected `approve`, got `request_info`.
- **golden-012-cannabis-twelve-plants-shed-deny**: expected `deny`, got `request_info`.
- **golden-013-cannabis-four-plants-shed-approve**: expected `approve`, got `request_info`.
- **golden-020-public-project-staging-storage-approve**: expected `approve`, got `request_info`.
