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

1. ~~**STT latency**: median `stt_ms` drops from 884 ms to **<= 600 ms**.~~
   **No-Go, criterion amended 2026-05-23.** Day 3 + 3b benches showed the
   STT sub-stage is network-bound (Osaka phone -> Osaka backend -> US
   OpenAI), not knob-tunable. Model swap reshuffled latency between
   STT and translate stages without a user-visible win. Full retro in
   `docs/reports/S2_stt_retro.md`. Replaced by criterion #2 alone.
2. **End-to-end latency**: `p95(system_latency_ms)` stays **<= 2000 ms**
   on a fresh 20-phrase device run (tightened from 2500 ms S1 gate).
   S1 1493 ms, Day 3 1478 ms, Day 3b 1535 ms — all already passing.
3. **Retry rate**: drop from ~50 % (S1: 9 discards + 1 ws_error per 18
   attempts) to **<= 20 %** after UX fixes.
4. ~~**Translation accuracy**: manual-scored 4/5 or better on >= 80 %
   of a curated 30-phrase JP<->VN bench set.~~ **Deferred to S3
   (2026-05-25).** Day 6 device run produced 60 latency rows but bilingual
   solo self-scoring was judged unreliable, and privacy forbids storing the
   translated text for later scoring. Accuracy gate moves to the S3 pilot
   with a paid native-VN reviewer (open question #1). Harness + `--s2`
   scorer are built and ready. See `docs/reports/S2_accuracy_2026-05-25.md`.
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
| **Codex** [DONE PR #11 `19ad38e`] | Implement bodies against the locked stub per §2l in `docs/codex/PROMPTS.md`: wire `stt_config` fields into `audio.input.transcription`, add `turn_detection: None` (nested under `audio.input`, not session top-level — re-locked after live smoke), drop duplicate `instructions` from `response.create`. 3 new pytest cases + 2 bonus. | `pytest backend/tests/test_translator.py` green (6/6). | DONE |
| **Claude** [DONE 2026-05-23] | Code review + merge. Smoke caught wrong `turn_detection` nesting before code — re-locked spec in `d9f8e19`. | n/a | DONE |

Commit subject: `feat(backend): S2 Day 2 STT tuning gpt-realtime-whisper + delay=low`.

## Day 3 — STT benchmark re-run (device)

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Claude** [DONE 2026-05-23] | Re-run the S1-Run-10 button against the new STT config (delay="low"). Capture CSV at `docs/reports/s2_run11_2026-05-23.csv`. | 10/10 OK rows. | DONE |
| **Claude** [DONE 2026-05-23] | Render `tools/latency_report.py --s1` against the new CSV. Compare median STT vs S1 baseline (884 ms). | `docs/reports/S2_latency_2026-05-23.md` rendered. | DONE |
| **Claude** [DONE 2026-05-23] | Decision: STT median 1044 ms > 800 ms → strict-revert per plan, but Option B chosen instead (flip `delay="low"` → `delay="minimal"` only — single-knob change, cheaper than full revert). Outcome logged in `docs/reports/S2_stt_probe.md` §8. | decision logged. | DONE |
| **Claude (prep)** [DONE 2026-05-23] | Flip default `STTConfig.transcription_delay` from `"low"` to `"minimal"`. Update tests. Backend redeploy required by user before re-bench. | `pytest backend/tests/test_translator.py` green (6/6). | DONE |
| **Claude** [DONE 2026-05-23] | Day 3b re-bench (`docs/reports/s2_run12_2026-05-23.csv`): STT median 1010 ms — knob not the bottleneck. Full revert chosen. | report rendered. | DONE |
| **Claude (retro)** [DONE 2026-05-23] | Revert STTConfig defaults to whisper-1 + no delay knob. Keep `turn_detection: null` + instructions-dedup trims. Keep STTConfig surface. Amend criterion #1 -> system_latency_ms p95 ≤ 2000 ms. Retro doc `docs/reports/S2_stt_retro.md`. | pytest 6/6 green. | DONE |

Commit subject (initial bench + flip): `docs(s2): Day 3 STT bench - delay=low regressed, flip to minimal`.
Commit subject (re-bench): `docs(s2): Day 3b re-bench with delay=minimal`.
Commit subject (revert + retro): `revert(backend): S2 Day 3 - revert STT model swap, criterion #1 No-Go`.

## Day 4 — Day 9 UX gap fixes

S1 Day 9 retry rate was ~50 % because users double-press before BLE ACK,
triggering `e2eAbort('discarded')` on the prior trace. Three fixes:

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Claude (prep)** [DONE 2026-05-23] | Lock PTT UX surface in `mobile/lib/screens/translate_screen.dart`: file-level tunables `_kPostFinalizeCooldown` (500 ms) + `_kShortPressMin` (100 ms); state `_cooldownTimer` + `_pressDownTsMicros`; impl (a) cooldown (`_isInCooldown` + `_startPostFinalizeCooldown`) in full; stub `_isShortPress` + UI methods `_showShortPressWarning` / `_showDiscardBanner`. Change `LatencyLogger.e2eStart` return type to `E2eLatencyRecord?` for (c) wiring. 2 new logger tests. | `flutter analyze` 0 issues; `flutter test test/latency_logger_test.dart` green (11 tests). | DONE |
| **Codex** [DONE PR #12 `85ddd92`] | Per `docs/codex/PROMPTS.md` §2m: flip `_isShortPress` body, fill `_showShortPressWarning` + `_showDiscardBanner` SnackBars, add `mobile/test/translate_screen_test.dart` with 3 widget test groups (cooldown / short-press / discard-banner) + heavy fake HttpOverrides so `_sessionClient.createSession` hangs cleanly under tester. | `flutter test` 14/14 green (3 widget + 11 logger). | DONE |
| **Claude** [DONE 2026-05-23] | Code review + merge. PR #12 was draft → marked ready → squash merge. Manual device smoke deferred — Day 9 final bench will cover it. | n/a | DONE |

Commit subject: `feat(mobile): S2 Day 4 PTT cooldown + warnings`.

## Day 5 — Translation accuracy harness

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Claude** [DONE 2026-05-24] | Curate `mobile/lib/data/s2_phrases.dart` with 30 JP + 30 VN phrases covering travel domain (greetings, directions, food, transit, payment, emergencies). | file exists, 60 phrases, no profanity. | DONE |
| **Claude (prep)** [DONE 2026-05-24] | Extend `S1-Run-10` button to `S2-Run-30` mode + add `accuracy_score` CSV column. **Scope change vs plan**: the button + CSV export were implemented in full (not stubbed) because the live S1 run engine could not be left half-wired without breaking S1, and the no-duplicate rule forbids a parallel S2 engine — so the S1 engine was generalised into one catalog-driven engine (`_startRun`/`_armRunPhrase`/`_scheduleRunAdvance` over a flat `RunPhrase` list). `_onPressDown` now passes per-phrase `sourceLang`/`targetLang` into `_ws.connect` (already supported, default ja->vi). `accuracy_score` is the last CSV column, nullable, never auto-set. Same prep/impl axis as Day 4 cooldown. | `flutter analyze` 0 new issues; `flutter test` 37/37 green. | DONE |
| **Codex** [DONE PR #13 `b95b67c`] | Per `docs/codex/PROMPTS.md` §2n (tag: tests only): add `mobile/test/data/s2_phrases_test.dart` (catalog invariants — 60 phrases, 30/30 split, 6 domains x 5 x 2, targetLang derivation, unique ids, no blank text) + an `S2 Run 30` widget-test group to `translate_screen_test.dart` (banner shows first phrase + `1/60` counter + ready log). No lib changes. | `flutter test` 43/43 green, analyze 0 new issues. | DONE |
| **Claude** [DONE 2026-05-24] | Code review + merge. Tests-only scope confirmed (2 files, no `lib/` touch). Squash merge + delete branch. | n/a | DONE |

Commit subject (prep): `feat(mobile): S2 Day 5 translation accuracy harness`.
Commit subject (Codex): `test(mobile): S2 Day 5 accuracy harness coverage`.

## Day 6 — Translation accuracy device run + scoring

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Claude** [DONE 2026-05-25] | Run S2-Run-30 on device (Galaxy S10 + BLE, whisper-1 backend). CSV captured `docs/reports/s2_accuracy_2026-05-25.csv` (60 rows, 54/60 unique + 6 retries). | CSV exists. | DONE |
| **Claude** [DONE 2026-05-25] | Build `--s2` scorer (added to `tools/latency_report.py`, shared `_system_latency_ms` helper, 5 new tests / 9 total green, `37dd796`). Render report. | `docs/reports/S2_accuracy_2026-05-25.md`. | DONE |
| **Claude** [DEFERRED -> S3] | Manual 1-5 accuracy scoring + `% >= 4` per direction. Deferred to S3 pilot with paid native-VN reviewer (criterion #4 amended; privacy forbids storing text for later scoring). Latency criterion #2 confirmed PASS on this run (p95 1449 ms). | deferred. | DEFERRED |

Commit subject: `docs(s2): Day 6 latency confirmed, accuracy deferred to S3`.

## Day 7 — Cloudflare Full(Strict) prep

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Claude** [DONE 2026-05-25] | Decide origin cert path. **Locked: Let's Encrypt via DNS-01** (orange-cloud blocks HTTP-01; Origin Cert breaks direct-to-origin debugging). Full trade-off table in `docs/runbook/cloudflare-tls.md` §1. | runbook §1 "cert path decision". | DONE |
| **Claude (prep)** [DONE 2026-05-25] | Lock `infra/ec2/bootstrap.sh` nginx reverse-proxy stub: 3 functions (`install_tls_proxy` / `issue_origin_cert` / `configure_nginx_reverse_proxy`) + env vars + default-OFF `LINGOGLASS_TLS_PROXY` guard (no behaviour change when unset). Bodies = `:` no-ops for Codex. `bash -n` clean. | stub commit, syntax OK. | DONE |
| **Codex** [DONE PR #15 `6d27233`] | Implement the bootstrap bodies + runbook command placeholders per `docs/codex/PROMPTS.md` §2o. Filled all 3 functions (DNS-01 certbot, idempotent nginx site + WS upgrade, certbot.timer), added `CERTBOT_EMAIL`, and made the compose binding loopback-capable via `API_BIND_ADDRESS` (default `0.0.0.0`, backward-compatible). `bash -n` clean, default-OFF guard intact. | dry-run / `bash -n`; staging EC2 if available. | DONE |
| **Claude** [DONE 2026-05-25] | Review + merge PR #15. Verified default-OFF, compose backward-compat, idempotency, locked decisions honoured. Squash-merge + delete branch. Day 7 prep complete; the live Full(Strict) flip is the Day 8 operator step. | n/a | DONE |

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

1. **Translation accuracy scoring**: ~~self-score for S2 MVP. Paid native
   VN speaker review deferred to S3 pilot.~~ **Updated 2026-05-25**: the
   whole accuracy gate (not just native review) is deferred to S3 — Day 6
   showed bilingual solo self-scoring is unreliable. S3 pilot runs the full
   catalog with a paid native-VN reviewer using the ready `--s2` scorer.
2. **Cooldown duration**: 500 ms initial. Tune empirically in Day 4
   device test if retry rate still > 20 %.
3. **Cloudflare cert**: Let's Encrypt (90 d auto-renew, valid for any
   client). Origin Cert not chosen — preserves ability to bypass CF
   during debugging.
