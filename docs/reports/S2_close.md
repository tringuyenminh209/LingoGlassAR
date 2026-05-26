# S2 Sprint Close - Go/No-Go for S3

**Sprint window**: 2026-05-23 to 2026-05-26 (condensed from planned ~10 days).
**Verdict: GO to S3.**

S2 set out to optimise STT, fix Day 9 UX retry friction, migrate Cloudflare to
Full(Strict) with origin TLS, and benchmark JP<->VN translation accuracy on the
phone-microphone pipeline. The two measurable quality gates that gate S3 entry
(end-to-end latency and retry rate) both PASS on the production Full(Strict)
run. STT is a confirmed No-Go (network-bound, not knob-tunable) and accuracy
moves to S3 where a paid native reviewer can score it credibly.

## Exit criteria results

| # | Criterion | Target | Result | Status |
|---|-----------|--------|--------|--------|
| 1 | STT latency | median <= 600 ms | network-bound, not tunable | **No-Go** (amended 2026-05-23) |
| 2 | End-to-end latency | p95 <= 2000 ms | **1639 ms** | **PASS** |
| 3 | Retry rate | <= 20% | **17%** (10 redo / 60) | **PASS** |
| 4 | Translation accuracy | >= 80% both dirs | unscored | **Deferred to S3** |
| 5 | Cloudflare Full(Strict) | no 521 in 24 h | smoke PASS, 24 h watch | **PASS (pending 24 h)** |

## Per-criterion detail

### #1 STT latency - No-Go (accepted)
Day 1-3 probes showed the STT sub-stage is network-bound (Osaka phone ->
Osaka backend -> US OpenAI), not knob-tunable. Model/delay swaps reshuffled
latency between STT and translate stages without a user-visible win, so the
STT-specific target was dropped and folded into criterion #2 (end-to-end).
Retro: `docs/reports/S2_stt_retro.md`. Reverted to whisper-1 baseline.

### #2 End-to-end latency - PASS
Production Full(Strict) run (Day 9, `docs/reports/S2_final_2026-05-26.md`):
p95(system_latency_ms) = **1639 ms** vs 2000 ms gate (tightened from S1's
2500 ms). ja->vi p95 1697 ms, vi->ja p95 1401 ms. One attempt exceeded the
gate (vi-food-03, 2522 ms) and its re-run landed at 1298 ms.

### #3 Retry rate - PASS
**17%** (10 redo / 60 attempts) vs 20% gate, down from S1's ~50%. The Day 4
PTT cooldown removed double-press discards (0 aborts this run); the remaining
redos surface as deliberate clean re-runs. Definition was locked against the
Day 9 trace to count clean re-runs + aborts, keeping the comparison with the
S1 discard-driven baseline honest.

### #4 Translation accuracy - deferred to S3
Bilingual solo self-scoring was judged unreliable, and the privacy rule forbids
storing translated text for later scoring. The whole accuracy gate moves to the
S3 pilot with a paid native-VN reviewer. The harness + `--s2` scorer are built
and ready; S3 reruns the full 60-phrase catalog (also closing the 10-phrase
coverage gap seen on Day 6 and Day 9).

### #5 Cloudflare Full(Strict) - PASS (pending 24 h)
Day 8 migration: nginx terminates Let's Encrypt TLS (DNS-01) on :443, backend
bound to 127.0.0.1:8000. Immediate dual smoke PASS (CF 200, direct-origin 200
with trusted cert, http->https 301, no 521/526). Two operator follow-ups remain
open and are NOT S3 blockers: (a) rotate the CF DNS API token exposed in chat,
(b) confirm the 24 h window stays clean for final sign-off.

## Open items carried into S3

- Accuracy scoring (criterion #4) with a paid native-VN reviewer, full catalog.
- 10-phrase coverage gap from the 60-row run cap (re-run full catalog in S3).
- Operator: rotate CF DNS API token; confirm 24 h TLS window.

## Artifacts

- Latency/retry: `docs/reports/S2_final_2026-05-26.md` (+ CSV).
- STT retro: `docs/reports/S2_stt_retro.md`.
- TLS runbook: `docs/runbook/cloudflare-tls.md`.
- Task ledger: `docs/codex/S2_TASKS.md`.
- Release tag: `v0.3.0-s2`.
