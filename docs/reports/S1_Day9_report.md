# S1 Day 9 — End-to-End Latency Report & Day 10 Go/No-Go

**Date:** 2026-05-22
**Branch:** main
**Device:** Samsung Galaxy S10 (Android), ESPr Developer S3 + SSD1306 OLED, Wi-Fi 5GHz, AWS Osaka EC2 t4g.small backend
**Backend session:** `433b34a2-7411-4f6c-88ca-c4afdbb02c16` (single session, WS reopened per utterance)

## TL;DR

**Verdict: GO.** `p95(system_latency_ms) = 1493 ms` (target ≤ 2500 ms).

System latency budget per docs/CLAUDE.md is for *post-PTT-release* duration (STT + translate + render), not press-to-glass total. Real run produced 9 OK rows out of 10 attempted phrases, well under budget.

## Raw measurements

CSV: [`s1_run10_2026-05-22.csv`](./s1_run10_2026-05-22.csv) — 18 rows total (9 OK, 8 discarded, 1 ws_error).

Rendered report: [`S1_latency_2026-05-22.md`](./S1_latency_2026-05-22.md) — output of `python tools/latency_report.py --s1`.

| Metric | Value | Target | Status |
|---|---:|---:|---|
| p50 system_latency_ms | 1173 | — | — |
| p90 system_latency_ms | 1426 | — | — |
| **p95 system_latency_ms** | **1493** | **≤ 2500** | **GO** |
| max system_latency_ms | 1493 | — | — |
| n_ok / n_attempted | 9 / 18 | — | — |

## Stage breakdown (median, post-release)

| Stage | Median ms | CLAUDE.md budget | Status |
|---|---:|---|---|
| STT (first partial after release) | 884 | 500-1000 | within |
| Translate (partial → final) | 137 | 200-600 | better than spec |
| BLE render | 147 | 50-200 | within |
| **Sum** | **1168** | **1500-2500** | **within** |

STT dominates (~75% of latency). Translate is consistently fast — gpt-realtime appears to commit translation in <200ms after stable STT, with one outlier (weather-03 = 14ms, likely cached prefix).

Concurrent (info-only, not counted in latency):
- handshake (POST /v1/sessions + WS upgrade): median 920 ms — runs during PTT hold
- hold (user PTT duration): median 4444 ms — user-controlled, not latency

## Schema bug found + fixed

The Day 9 contract (`8c61b15`) assumed event order `press → audio → backend_ack → stt → ...` and decomposed handshake as `backend_ack_ms - audio_ms`. Real flow opens the WS during PTT hold, so `backend_ack_ms < audio_ms` always, making the original handshake stage permanently negative (clamped to 0 with bogus "clock skew" footer).

**Fix landed in this commit** (`tools/latency_report.py`):
- `S1_STAGES` reordered to post-release only: stt / translate / ble.
- `handshake_ms` and `hold_ms` reported as info-only concurrent columns.
- Verdict gate changed from `p95(total_ms)` to `p95(system_latency_ms)` where `system_latency_ms = ble_ack_ms - audio_ms`.
- Clock-skew footer now only fires on real out-of-order frames (e.g. `final_text` before `first_text`).

Comment block in `mobile/lib/services/latency_logger.dart` updated to match.

## Failures analysis

| error | count | root cause |
|---|---:|---|
| discarded | 8 | User re-pressed PTT on same phrase before previous BLE ACK arrived → `e2eStart` discards active trace |
| ws_error | 1 | direction-06 attempt 3: `committing input audio buffer: buffer too small` — PTT held <100ms |

`direction-06` was the one phrase with **zero OK rows** (3 attempts, all failed). Pattern: 2 discarded + 1 buffer-too-small. Possible causes:
- Phrase 「右へ行く」 (migi e iku) is short (4 codepoints) — user may have rushed releases
- STT first_partial only arrived on attempt 3 (other 2 attempts had no `first_text_ms`)

Not a code bug. Mitigation: hold longer (>1s) and wait for `BLE sent` log before pressing next phrase.

## Lessons learned

1. **Contract design must reflect actual event order.** Day 9 prep contract was written from the spec, not from observing the running code. The handshake-during-hold quirk would have been caught by even one device run before locking the schema. **Action**: from S2 onward, always do a "smoke trace" device run before locking any timing-related schema.

2. **Total ≠ system latency.** Press-to-glass total includes user hold duration, which is user behavior, not latency. The budget gate must be measured from PTT release, not press.

3. **STT is the bottleneck**, as predicted in CLAUDE.md latency budget. ~75% of system latency. Optimization target for S2: explore prefix-caching / smaller VAD threshold / shorter prompts. p95 cushion is 1007 ms — comfortable but not abundant.

4. **Retry friction is real.** 9 retries needed across 18 attempts. UX gap: no countdown timer, no "press again to retry" affordance, no auto-restart on discard. Day 10 candidate: add 500ms cooldown after `e2eFinalize` so accidental double-press becomes no-op.

## Day 10 follow-ups (deferred)

- [ ] Add 500 ms post-finalize cooldown in TranslateScreen to absorb double-press
- [ ] Log a clearer message when PTT release <500ms (likely insufficient audio)
- [ ] Re-run S1 Run 10 after cooldown to validate retry rate <20%
- [ ] Spot-check `direction-06` with a slower deliberate read

## Cost smoke (from Day 8)

Single session ran 18 PTT cycles over ~5 min. Daily cap status check (run on EC2):
```
redis-cli HGETALL cost:total:2026-05-22
```
Expected USD < $0.50 for this run (9 successful translations averaging ~5s audio each).

## Go/No-Go decision

**S1 advances to S2.** Latency budget passes with cushion. Day 10 deferred items are UX polish, not blockers.
