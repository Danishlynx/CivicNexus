# PermitBench eval report

Generated from `evals/results.json` — run at 2026-08-28T14:24:59.091016+00:00, tag `smoke`, 12 cases against `2118760555991793664`. Do not hand-edit.

## Headline metrics

| Metric | Value | Gate |
|---|---|---|
| Decision accuracy | 100.00% | ≥ 85% |
| Citation precision | 95.83% | — |
| Citation recall | 100.00% | — |
| Groundedness first-pass | 100.00% | ≥ 95% |
| Verifier first-pass (§7.3 headline) | 91.67% | reported |
| Canary leak rate | 0.00% | = 0 |
| Latency p50 / p95 | 56s / 68s | — |
| Tokens (run total) | 257,315 | — |
| Errors | 0 | — |

**Gates: PASS**

## Per-case results

| Case | Expected | Observed | Citations (obs/req) | Grounded | Notes |
|---|---|---|---|---|---|
| golden-001-maria-bakery-compliant-approve | approve | approve ✅ | 17.44.100 / 17.44.100 | ok |  |
| golden-002-maria-bakery-nonresident-helper-deny | deny | deny ✅ | 17.44.100 / 17.44.100 | ok |  |
| golden-003-home-occupation-illuminated-sign-deny | deny | deny ✅ | 17.44.100, 17.44.100 / 17.44.100 | ok |  |
| golden-004-home-occupation-rooms-unclear-request-info | request_info | request_info ✅ | 17.44.100 / 17.44.100 | ok |  |
| golden-005-furniture-shop-outside-lumber-deny | deny | deny ✅ | 17.44.100 / 17.44.100 | ok |  |
| golden-006-garage-adu-oversized-addition-two-foot-setback-deny | deny | deny ✅ | 17.44.005 / 17.44.005 | ok |  |
| golden-007-detached-backyard-adu-640sf-within-limits-approve | approve | approve ✅ | 17.44.005, 17.44.005, 17.44.005, 17.44.005, 17.44.005, 17.44.005 / 17.44.005 | ok |  |
| golden-009-gas-tank-residential-deny | deny | deny ✅ | 17.44.080, 17.44.080 / 17.44.080 | ok |  |
| golden-012-cannabis-twelve-plants-shed-deny | deny | deny ✅ | 17.44.104 / 17.44.104 | ok |  |
| golden-015-satellite-dish-under-threshold-approve | approve | approve ✅ | 17.44.150, 17.44.150 / 17.44.150 | ok |  |
| golden-016-home-recycling-dropoff-driveway-deny | deny | deny ✅ | 17.44.100, 17.44.100, 17.44.100, 17.44.140 / 17.44.140, 17.44.100 | ok |  |
| golden-018-garage-indoor-swap-meet-deny | deny | deny ✅ | 17.44.190, 17.44.190, 17.44.100, 17.44.100 / 17.44.190 | ok |  |

## Where it still fails

No misses in this run. (Stay suspicious: n is small.)
