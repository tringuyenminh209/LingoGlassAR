# S3 Sprint Task Division — Claude (lead) + Codex (assist)

**Sprint window**: 2026-05-26 to ~2026-06-06 (~10 working days).
**Sprint goal**: add **phone-camera OCR** as a second input path — tap to
capture a still image, recognise Japanese text **on-device** (Google ML Kit,
no image leaves the phone), translate JP->VN through the existing backend, and
render on the BLE glasses. Plus close the S2-deferred **translation accuracy
gate (#4)** with a paid native-VN reviewer over the full catalog.

**Locked scope decisions (2026-05-26):**
- **OCR-first.** OCR is the primary S3 deliverable; the accuracy reviewer
  session runs in the background once a reviewer is booked.
- **On-device OCR (ML Kit).** `google_mlkit_text_recognition` with the Japanese
  script model runs on the phone. The captured image **never leaves the
  device**; only the recognised text is sent to the backend. This preserves the
  existing privacy boundary — no new cloud surface for image bytes.
- **Tap-to-capture (still image).** No live/streaming OCR. One tap -> one
  capture -> OCR -> translate -> display. Keeps latency measurable like PTT.

## Carry-overs from S2 (must not regress)

- `p95(system_latency_ms) <= 2000 ms` for the **speech** path (S2 gate). OCR
  introduces its own latency metric (see criterion #2) and must not slow speech.
- Retry-rate gate (criterion #3) and the `--s2` scorer stay as-is.
- Cloudflare Full(Strict) origin TLS stays live (S2 Day 8). Operator: rotate the
  exposed CF DNS API token + confirm the 24 h window (carried from S2 close).
- Privacy: never log/store/export audio, **image bytes**, transcripts, OCR'd
  text, or translated text. Counts/durations/error codes only.
- Never add `Co-Authored-By: Claude/OpenAI` trailers. No axios. ASCII-only
  Vietnamese Markdown; UTF-8 nippo/JP design.
- Codex never pushes to `main`. Feature branches + PR only; tag every prompt.

## Sprint exit criteria (Go to S4)

1. **OCR recognition quality**: on a curated set of real JP signage/menu photos,
   on-device ML Kit recognises the key text correctly on **>= 80%** of images
   (provisional; **lock the metric + threshold on Day 1** after the probe — char
   accuracy vs "key info usable" line accuracy).
2. **OCR end-to-end latency**: `p95(ocr_system_latency_ms) <= 1500 ms`
   (provisional; tighter than speech because there is no audio upload or STT —
   **lock on Day 1**). Define `ocr_system_latency_ms = ble_ack_ms - capture_ms`.
3. **Translation accuracy (S2 #4 carried over)**: native-VN reviewer scores
   `>= 80%` at `>= 4/5` in BOTH directions over the full 60-phrase catalog,
   using the ready `--s2` scorer. Closes the recurring 10-phrase coverage gap.
4. **Privacy holds for OCR**: verify image bytes never leave the phone (only
   recognised text crosses the WS) and nothing image/text is persisted. This is
   a design + code-review gate, not a metric.
5. **OCR result renders on glasses**: captured-text translation displays via the
   existing BLE subtitle protocol, MTU 23/185/247 safe (no protocol change).

If any criterion fails, log a No-Go reason and trim S4 scope.

## Day 1 — OCR probe + privacy + metric lock (research, no feature code)

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Claude** [DONE 2026-05-26] | Probe `google_mlkit_text_recognition` (Flutter): Japanese script model, on-device confirmation (no network), model/app-size cost, `camera` vs `image_picker` capture, Android/iOS min versions. Doc `docs/reports/S3_ocr_probe.md`. | doc lists package, JP model, on-device proof, capture pipeline, size. | DONE |
| **Claude** [DONE 2026-05-26] | Lock criterion #1 metric + #2 latency gate + the `ocr_system_latency_ms` definition. Pick the curated image-set size + sources. | **#1 = key-line accuracy >= 80% (by eye); #2 = `ocr_system_latency_ms = ble_ack_ms - capture_ms`, p95 <= 1500 ms provisional, device-confirm; set = 20 imgs, 4 domains x 5.** | DONE |
| **Claude (prep)** [DONE 2026-05-26] | Extend the privacy section of root `CLAUDE.md` to name **image bytes + OCR'd text** in the never-store/never-send list; note on-device OCR keeps images local. | CLAUDE.md invariant #4 updated. | DONE |

Doc-only commit: `docs(s3): Day 1 OCR probe + metric lock`.

**Day 1 notes:** Android unbundled JP model (`play-services-mlkit-text-recognition-japanese`, ~260 KB app impact, one-time download). iOS pod ships models. arm64-only (Galaxy S10 OK). `ocr_system_latency_ms` p95 gate stays provisional until the on-device OCR step is measured on the first device build (Day 3/5).

## Day 2 — translate-only WS/contract path (Claude prep + Codex impl)

The speech path does STT then translate. OCR already has text, so it needs a
**translate-only** request. Decide REST POST vs a new WS input message type;
reuse the OpenAI Realtime translation prompt either way.

**Decision (locked 2026-05-27): REST `POST /v1/translate`, not a new WS message
type.** OCR holds the full text up front, so a one-shot request/response fits
and keeps OCR fully isolated from the latency-gated speech WS state machine
(zero regression risk; `ws-events.schema.json` is untouched). It reuses the
Realtime `Translator` via a new `translate_text(text) -> TextResult` method
(same model, same JP<->VN prompt, same usage parsing — single source). Latency
headroom is large: STT (~880 ms) + audio upload (~300 ms) are gone, leaving
connect (~300) + translate (~400) + BLE (~150) ~= 850 ms vs the 1500 ms gate.
The old `/api/v1/ocr` image-upload draft is **superseded** (marked deprecated in
openapi.yaml) — implementing it would breach the privacy boundary (image bytes).

This is a **live OpenAI path**, so per the prep/impl split axis a stub is unsafe
(passes tests, fails on device). Claude implemented the bodies; Codex writes
tests only.

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Claude (prep+impl)** [DONE 2026-05-27] | Lock contract (`openapi.yaml`: `/v1/translate` + `TranslateRequest`/`TranslateResponse`, deprecate `/api/v1/ocr`). Implement `translate_text()`+`TextResult` in `translator.py`, `POST /v1/translate` in new `app/api/translate.py`, register in `main.py`. Generalised `SYSTEM_INSTRUCTIONS` for text+audio. | `py_compile` OK; contract diff in. | DONE |
| **Codex** | Tests only per `docs/codex/PROMPTS.md` "S3 Day 2" section (translate_text cases + endpoint tests + privacy assertion). Do NOT touch impl. | `pytest backend` + `ruff` green. | pending |
| **Claude** | Review + merge. | n/a | pending |

Commit subject (this prep): `feat(backend): S3 translate-only path for OCR`.

Day 2 closed on `main` (merge `2e3c5be`, PR #16): tests green (35 passed),
ruff clean. `style(backend)` commit `731d425` cleared a repo-wide ruff 0.15
format drift so `ruff format --check .` is green again.

## Day 3 — mobile OCR capture + recognition (Claude prep + Codex impl)

**Surface decision (locked 2026-05-27):** `lib/ocr/ocr_scanner.dart` owns
**recognition + privacy cleanup** (`OcrScanner.recognise(imagePath)` runs
on-device ML Kit then deletes the image in a `finally` — even on failure).
It mirrors `lib/audio/recorder.dart`: thin orchestrator + injectable
`OcrDriver` interface so the always-delete logic is unit-testable with a fake
(the ML Kit / file calls are not). The **camera preview + capture** lives in
the capture UI (it owns the `CameraController`) and hands `OcrScanner` the
captured file path — that part is UI + device, so it is Codex's row and is
validated at Day 5 smoke, not by unit tests.

`recognise()` is a **live ML Kit path** (a stub passes tests but fails on
device), so per the prep/impl split axis Claude implemented the body and
`_MlKitOcrDriver`; this overrides the original "Codex implements recognise"
plan. Codex builds the capture UI + the `OcrScanner` tests.

Resolved versions (after `flutter pub get`): `camera 0.11.2+1`,
`google_mlkit_text_recognition 0.13.1` (`google_mlkit_commons 0.8.1`).
Android unbundled JP model is still a [device-confirm] APK-size item (probe).

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Claude (prep+impl)** [DONE 2026-05-27] | Add `camera` + `google_mlkit_text_recognition` to pubspec. Implement `lib/ocr/ocr_scanner.dart` (`OcrScanner.recognise` + `OcrDriver` + `_MlKitOcrDriver` + `OcrError`). Camera permission: Android `CAMERA` + `uses-feature`, iOS `NSCameraUsageDescription`. | `flutter pub get` ok; `flutter analyze` clean (2 pre-existing warnings only). | DONE |
| **Codex** [DONE 2026-05-27, PR #17] | Build the capture UI screen (CameraPreview + tap-to-capture button -> `OcrScanner.recognise(path)`) + `test/ocr/ocr_scanner_test.dart` per PROMPTS.md "S3 Day 3". Do NOT touch `ocr_scanner.dart` impl. | `flutter test` + `flutter analyze` clean. | DONE |
| **Claude** [DONE 2026-05-27] | Review + merge. | n/a | DONE |

Day 3 closed on `main` (merge `20a5ab1`, PR #17). `lib/screens/ocr_screen.dart`
(permission-gated camera preview, tap-to-capture, button disabled in flight,
disposes controller + scanner, no image/text logged) + 4 `OcrScanner` unit
tests (incl. always-delete + error mapping). Local verify on the branch: 48
`flutter test` pass, `flutter analyze` 2 pre-existing warnings only.

Commit subject: `feat(mobile): S3 on-device OCR capture`.

## Day 4 — wire OCR text -> translate -> BLE (mobile end-to-end)

**Surface decision (locked 2026-05-28):** the OCR latency record is anchored at
**capture**, not a PTT press: `ocr_system_latency_ms = ble_ack_ms - capture_ms`
(locked Day 1), so `bleAckMs` IS the gate value (no audio-hold to subtract). The
record family in `latency_logger.dart` mirrors the e2e trace lifecycle
(`ocrStart` -> `ocrMarkRecognised(charCount)` -> `ocrMarkTranslated` ->
`ocrMarkBleAck` -> `ocrFinalize`; `ocrAbort(code)` for failures). `recognisedChars`
is a **count only** (never the text) so the bench can correlate the BLE leg with
subtitle length without breaching privacy. `summariseOcr()` reuses
`E2eLatencyStats` (generic percentile container — no duplicate stats logic).

Translate transport is the one-shot `TranslateClient` (new
`lib/services/translate_client.dart`, mirrors `session_client.dart`) hitting
`POST /v1/translate` (Day 2 contract). Per the prep/impl split axis, the live
legs (HTTP translate, camera, BLE) are Claude-implemented; Codex tests the two
pure-Dart units (`TranslateClient` with a fake `http.Client`, OCR latency record).

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Claude (prep+impl)** [DONE 2026-05-28] | OCR latency record family in `latency_logger.dart`. New `lib/services/translate_client.dart`. Wire `ocr_screen.dart`: capture -> `OcrScanner.recognise` -> `TranslateClient.translate` -> `BleTransport.sendSubtitle` + latency marks + on-screen translation + BLE connect/CSV actions. Route `/ocr` in `main.dart` + drawer entry in `translate_screen.dart`. | `flutter analyze` clean; `flutter test` green. | DONE |
| **Codex** [DONE 2026-05-28, PR #18] | Tests only per PROMPTS.md "S3 Day 4": `test/services/translate_client_test.dart` (200/429/502/non-200/malformed + no-text-leak assertion via fake `http.Client`) + OCR latency record cases in `test/latency_logger_test.dart` (finalize OK, `ocrSystemLatencyMs == bleAckMs`, CSV header/row, discard-on-restart, abort codes, no-op without start). Do NOT touch impl. | `flutter test` green. | DONE |
| **Claude** [DONE 2026-05-28] | Review + merge. | n/a | DONE |

Commit subject (this prep): `feat(mobile): S3 OCR -> translate -> BLE pipeline`.

Day 4 closed on `main` (prep `df6119d`; merge `233f616`, PR #18). 13 new tests
(7 OCR latency record + 6 TranslateClient incl. the no-leak assertion); local
verify on the branch: 61 `flutter test` pass, `flutter analyze` 2 pre-existing
warnings only. Scope clean (2 test files, 0 impl change).

## Day 5 — OCR device smoke

| Owner | Task | Verify | Status |
|---|---|---|---|
| **User (operator)** | Capture real JP signage/menu on device; confirm recognised text translates and renders on the glasses (MTU safe). | smoke pass/fail logged. | DONE 2026-05-29 |
| **Claude** | Triage smoke results; fix or file follow-ups. | n/a | DONE 2026-05-29 |

First on-device smoke (Galaxy S10) surfaced three defects, all fixed:

1. **App crash at first capture** — `ClassNotFoundException:
   JapaneseTextRecognizerOptions$Builder`. The `google_mlkit_text_recognition`
   plugin bundles only the Latin model and declares JP/CN/KR/Devanagari as
   `compileOnly`; the app must add the runtime model itself. Fixed by adding
   `implementation("com.google.mlkit:text-recognition-japanese:16.0.1")` to
   `mobile/android/app/build.gradle.kts` (bundled model → also removes the
   first-run model-download risk flagged on Day 1; recognition stays on-device).

2. **"Translation failed"** — `POST /v1/translate` → 404 on the live host while
   `/healthz` was 200. Triage: endpoint present on `main` (`main.py` mounts
   `translate_router`; `7ad32f0`/`731d425`), so the EC2 backend was running a
   pre-Day-2 build. **No code fix** — operator redeployed (`git pull` + `docker
   compose up -d --build`); endpoint verified live (200 + translatedText).

3. **Capture too soft for small glyphs** — camera was `ResolutionPreset.high`
   (~720p) with no active focus. Fixed in `ocr_screen.dart`: bumped to
   `veryHigh` (~1080p), enabled `setFocusMode(auto)` + `setExposureMode(auto)`
   after init, and added tap-to-focus (`setFocusPoint`+`setExposurePoint`) on
   the preview. Re-capture confirmed sharper by the operator.

Smoke verdict: **PASS** — recognise → translate → OLED render works end-to-end
on device. Commit `feat(mobile): S3 Day 5 smoke fixes`. MTU 23/185/247 spot
checks + latency CSV roll into the Day 6 bench.

## Day 6 — OCR quality + latency bench

| Owner | Task | Verify | Status |
|---|---|---|---|
| **User (operator)** | Run the curated OCR image set on device; export the OCR latency CSV. | CSV captured. | pending |
| **Claude (prep)** | Add an `--s3` (or extend) report mode to `tools/latency_report.py`: OCR recognition % + `p95(ocr_system_latency_ms)` against the locked gates. Tests. | tests green; renders. | DONE 2026-05-29 |
| **Claude** | Render the OCR bench report. | `docs/reports/S3_ocr_<date>.md`. | pending |

Commit subjects: `feat(tools): S3 OCR report mode`, `docs(s3): OCR bench`.

`--s3` mode added to `tools/latency_report.py` (`render_s3_markdown`): consumes
the `OcrLatencyRecord` CSV ("Copy OCR latency CSV"), reports criterion #1
key-line recognition `% pass` by domain (from an operator-appended
`recognised_pass` column; `capture_id` relabelled `ocr-NNN` -> `sign-01`.. for
grouping) and criterion #2 `p95(ocr_system_latency_ms)` with a
recognise/translate/ble leg breakdown (legs derived from the cumulative
from-capture deltas). Gates: recognition >= 80% AND p95 <= 1500 ms
(provisional). Recognition is PENDING until `recognised_pass` is filled;
latency + legs always compute, so the timing can be read immediately. 7 tests
added (pending/GO/recognition-fail/latency-fail/per-leg/aborted-excluded/
domain-grouping); `python -m pytest tools/test_latency_report.py` = 19 pass,
ruff clean. Operator next: run the curated ~20-image set, score
`recognised_pass` by eye, paste the CSV; then the render-report row produces
`docs/reports/S3_ocr_<date>.md`. **Reminder**: run the tool with
`PYTHONIOENCODING=utf-8` (report strings use em-dash; cp932 stdout otherwise
errors — see root CLAUDE.md).

## Day 7 — accuracy gate #4 (S2 carry-over, native-VN reviewer)

| Owner | Task | Verify | Status |
|---|---|---|---|
| **User (operator)** | Book a native-VN reviewer; run the full 60-phrase catalog (closes coverage gap); fill `accuracy_score`. | scored CSV. | pending |
| **Claude** | Render `--s2` accuracy report; record GO/NO-GO on criterion #3 (S3 numbering). | `docs/reports/S3_accuracy_<date>.md`. | pending |

## Day 8 — buffer / fixes from Day 5-7 triage

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Claude** | Address defects surfaced in smoke/bench; re-bench if needed. | gates re-checked. | pending |

## Day 9 — S3 final bench

| Owner | Task | Verify | Status |
|---|---|---|---|
| **User (operator)** | Final OCR run on production (Full Strict). | CSV captured. | pending |
| **Claude** | Render combined S3 report (OCR quality + OCR latency + speech accuracy). | `docs/reports/S3_final_<date>.md`. | pending |

## Day 10 — S3 report + Go/No-Go for S4

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Claude** | Write S3 close report against the 5 exit criteria. | `docs/reports/S3_close.md`. | pending |
| **Claude** | Tag release `v0.4.0-s3`. | `git tag`. | pending |
| **Claude** | Update memory with the S3 decision. | memory written. | pending |

Commit subject: `docs(s3): close S3 with Go/No-Go verdict`.

## Open questions (to lock on Day 1)

1. **OCR metric**: per-character accuracy vs "key info usable" per line/image.
   Char accuracy is objective but punishes minor noise; key-info is closer to
   user value but more subjective. Lock against the probe set on Day 1.
2. **OCR latency gate**: 1500 ms is provisional. Measure the on-device OCR step
   on the target phone (Galaxy S10) first; the gate must be achievable with
   margin like the speech path (~550 ms cushion at S2 close).
3. **Translate-only transport**: ~~REST POST vs new WS message type.~~
   **RESOLVED Day 2 (2026-05-27): REST `POST /v1/translate`.** Least churn
   (no speech WS surgery, WS schema untouched), reuses the Realtime translator
   for a single-sourced prompt, ample latency headroom. See Day 2 section.
4. **Reviewer logistics for #3**: paid native-VN reviewer availability + cost
   cap; same privacy rule (scores by eye, no stored text).
