# S2 Sprint Task Division — Claude (lead) + Codex (assist)

**Sprint window**: 2026-05-23 to ~2026-06-05 (~10 working days).
**Sprint goal**: optimise STT (the S1 bottleneck, 884 ms median),
fix Day 9 UX retry friction, migrate Cloudflare to Full(Strict) with
origin TLS, and benchmark JP<->VN translation accuracy on the same
phone-microphone pipeline used in S1.

## Carry-overs from S1 (must not regress)

- `p95(system_latency_ms) <= 2500 ms` (the locked gate from
  `tools/latency_report.py`). S1 close = 1493 ms.
- Daily cost cap (`DAILY_USD_CAP`) still enforced; cost log still
  privacy-safe (counts + USD only, no audio bytes, no transcripts,
  no translated text).
- Never add `Co-Authored-By: Claude/OpenAI` trailers.
- Codex never pushes to `main`. Feature branches + PR only.

## Sprint exit criteria (Go to S3)

1. **STT latency**: median `stt_ms` (post-PTT-release first partial)
   drops from 884 ms to **<= 600 ms** without sacrificing translation
   accuracy.
2. **End-to-end latency**: `p95(system_latency_ms)` stays **<= 2000 ms**
   on a fresh 20-phrase device run (tightened from 2500 ms S1 gate).
3. **Retry rate**: drop from ~50 % (S1: 9 discards + 1 ws_error per 18
   attempts) to **<= 20 %** after UX fixes.
4. **Translation accuracy**: manual-scored 4/5 or better on >= 80 %
   of a curated 30-phrase JP<->VN bench set.
5. **TLS**: production traffic on Cloudflare Full(Strict) with valid
   origin certificate; no 521s in a 24 h smoke window.

If any criterion fails, log as a No-Go reason and trim S3 scope.

## Day 1 — STT optimisation probe (research, no code)

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Claude** [DONE `19bd628`] | Read OpenAI Realtime API docs for `turn_detection`, `voice_activity_detection`, `input_audio_transcription`, `session.update` knobs. Document each tunable + observed default in `docs/reports/S2_stt_probe.md`. | doc exists, lists at least: VAD threshold, prefix-padding, silence-duration, eagerness modes. | DONE |
| **Claude** [DONE `19bd628`] | Inspect current `backend/app/services/translator.py` `session.update` payload. List every field we send today + every field we COULD send but do not. | doc section "current vs available knobs". | DONE |
| **Claude** [DONE `19bd628`] | From the S1 CSV (`docs/reports/s1_run10_2026-05-22.csv`) compute the STT-only sub-distribution: `first_text_ms - full_text_ms_for_release_marker` for each OK row. Confirm 884 ms median claim and identify variance. | doc section "S1 STT distribution: p50/p90/p95 + per-phrase". | DONE (p50=884, p90=1078, p95=1169 ms) |
| **Claude** [DONE `19bd628`] | Propose top 3 tuning candidates ranked by expected impact + risk. Lock one as Day 2 implementation target. | doc section "Day 2 target + hypothesis". | DONE (Cand A: gpt-realtime-whisper + delay=low) |

Output file: `docs/reports/S2_stt_probe.md`.

No commit subject — research only, doc-only commit
`docs(s2): Day 1 STT optimisation probe`.

## Day 2 — STT optimisation implementation (Claude prep + Codex impl)

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Claude (prep)** [DONE] | Lock the contract change in `backend/app/services/translator.py`: add `STTConfig` (frozen dataclass with `transcription_model` + `transcription_delay`), `DEFAULT_STT_CONFIG`, `TranscriptionDelay` literal, and `stt_config: STTConfig \| None = None` on `Translator.__init__`. Body of `connect()` is intentionally left at S1 values for Codex. | locked stub commit. | DONE |
| **Codex** | Implement bodies against the locked stub per §2l in `docs/codex/PROMPTS.md`: wire `stt_config` fields into `audio.input.transcription`, add `turn_detection: None`, drop duplicate `instructions` from `response.create`. 3 new pytest cases. | `pytest backend/tests/test_translator.py` green. | pending (§2l ready) |
| **Claude** | Code review + merge. | n/a | pending |

Commit subject: `feat(backend): S2 Day 2 STT tuning gpt-realtime-whisper + delay=low`.

## Day 3 — STT benchmark re-run (device)

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Claude** | Re-run the S1-Run-10 button against the new STT config. Capture CSV at `docs/reports/s2_run<N>_<date>.csv`. | CSV captured, >= 9/10 OK rows. | pending |
| **Claude** | Render `tools/latency_report.py --s1` against the new CSV. Compare median STT vs S1 baseline (884 ms). | `docs/reports/S2_latency_<date>.md` rendered. | pending |
| **Claude** | If STT median <= 600 ms: keep config, proceed. If 600-800 ms: try Day 1's #2 candidate. If > 800 ms: revert + retro. | decision logged. | pending |

Commit subject: `docs(s2): Day 3 STT bench results post-tuning`.

## Day 4 — Day 9 UX gap fixes

S1 Day 9 retry rate was ~50 % because users double-press before BLE ACK,
triggering `e2eAbort('discarded')` on the prior trace. Three fixes:

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Claude (prep)** | Lock PTT state machine extensions in
`mobile/lib/screens/translate_screen.dart`: (a) 500 ms post-finalize
cooldown blocks re-press, (b) short-press warning if PTT release < 100 ms,
(c) discard visual feedback (banner or toast on previous-trace discard). | stub commit. | pending |
| **Codex** | Implement the three bodies + widget tests covering each
state transition. | `flutter test` green, manual smoke on device. | pending |

Commit subject: `feat(mobile): S2 Day 4 PTT cooldown + warnings`.

## Day 5 — Translation accuracy harness

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Claude** | Curate `mobile/lib/data/s2_phrases.dart` with 30 JP + 30 VN phrases covering travel domain (greetings, directions, food, transit, payment, emergencies). | file exists, 60 phrases, no profanity. | pending |
| **Claude (prep)** | Extend `S1-Run-10` button to `S2-Run-30` mode: iterate the new catalog with both `sourceLang=ja` and `sourceLang=vi` per phrase. Stub a manual-scoring column in the CSV (`accuracy_score`, default empty). | stub commit, button visible. | pending |
| **Codex** | Implement the button + CSV export for the new shape. | manual run on emulator (no scoring required). | pending |

Commit subject: `feat(mobile): S2 Day 5 translation accuracy harness`.

## Day 6 — Translation accuracy device run + scoring

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Claude** | Run S2-Run-30 on device. Score each translation 1-5
(1 = wrong, 3 = understandable, 5 = native). Bilingual (JP + VN)
self-scoring acceptable for MVP. | CSV at `docs/reports/s2_accuracy_<date>.csv`. | pending |
| **Claude** | Compute `% phrases with score >= 4` per direction. Target: >= 80 % both directions. | `docs/reports/S2_accuracy_<date>.md`. | pending |

Commit subject: `docs(s2): Day 6 translation accuracy results`.

## Day 7 — Cloudflare Full(Strict) prep

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Claude** | Decide origin cert path: Cloudflare Origin Cert (15 yr, free, only valid for CF-fronted traffic) vs Let's Encrypt (90 d auto-renew, valid for any client). Document trade-off in `docs/runbook/cloudflare-tls.md`. | runbook section "cert choice". | pending |
| **Claude (prep)** | Lock `infra/ec2/bootstrap.sh` extension stub for nginx (or Caddy) reverse-proxy in front of the backend container, terminating TLS on the EC2. Don't implement bodies. | stub commit. | pending |
| **Codex** | Implement the bootstrap extension + `docs/runbook/cloudflare-tls.md` step list. | dry-run on a staging EC2 if possible. | pending |

Commit subject: `feat(infra): S2 Day 7 origin TLS reverse-proxy`.

## Day 8 — Cloudflare migration

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Claude** | Provision origin cert (per Day 7 decision), deploy nginx with TLS, switch Cloudflare SSL mode to Full(Strict). | `curl https://api.lingoglass.online/healthz` returns 200, no 521. | pending |
| **Claude** | Update `MEMORY.md` Cloudflare SSL memory: Flexible -> Full(Strict). | memory updated. | pending |

Commit subject: `feat(infra): S2 Day 8 Cloudflare Full(Strict) live`.

## Day 9 — S2 final device benchmark

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Claude** | Re-run S2-Run-30 on production (Full Strict) + record CSV. | CSV captured. | pending |
| **Claude** | Render combined `tools/latency_report.py --s2` output (latency + accuracy + retry rate combined). | `docs/reports/S2_final_<date>.md`. | pending |

Commit subject: `docs(s2): Day 9 final benchmark`.

## Day 10 — S2 report + Go/No-Go for S3

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Claude** | Write S2 close report against the 5 exit criteria above. | `docs/reports/S2_close.md`. | pending |
| **Claude** | Tag release `v0.3.0-s2`. | `git tag` listed. | pending |
| **Claude** | Update `MEMORY.md` with S2 decision memory. | memory file written. | pending |

Commit subject: `docs(s2): close S2 with Go/No-Go verdict`.

## Open questions (locked 2026-05-23)

1. **Translation accuracy scoring**: self-score for S2 MVP. Paid native
   VN speaker review deferred to S3 pilot.
2. **Cooldown duration**: 500 ms initial. Tune empirically in Day 4
   device test if retry rate still > 20 %.
3. **Cloudflare cert**: Let's Encrypt (90 d auto-renew, valid for any
   client). Origin Cert not chosen — preserves ability to bypass CF
   during debugging.
