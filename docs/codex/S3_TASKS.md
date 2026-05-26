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

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Claude (prep)** | Decide + lock the translate-only contract in `docs/api-contract/` (openapi.yaml + ws-events.schema.json) and the backend signature in `backend/app/services/translator.py` / `backend/app/api/sessions.py`. Bodies left for Codex if a stub is safe. | contract diff + locked stub. | pending |
| **Codex** | Implement the backend translate-only path + tests per a new `docs/codex/PROMPTS.md` S3 section. | `pytest backend` green. | pending |
| **Claude** | Review + merge. | n/a | pending |

Commit subject: `feat(backend): S3 translate-only path for OCR`.

## Day 3 — mobile OCR capture + recognition (Claude prep + Codex impl)

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Claude (prep)** | Add `camera` + `google_mlkit_text_recognition` to `mobile/pubspec.yaml`; lock `lib/ocr/` surface (capture controller + recognise() returning text, no image retained). Wire camera permission (Android manifest + iOS Info.plist). Stub recognise body if safe. | `flutter pub get` ok; analyze clean. | pending |
| **Codex** | Implement OCR recognise + capture UI bodies + tests per PROMPTS.md S3. | `flutter test` green. | pending |
| **Claude** | Review + merge. | n/a | pending |

Commit subject: `feat(mobile): S3 on-device OCR capture`.

## Day 4 — wire OCR text -> translate -> BLE (mobile end-to-end)

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Claude (prep)** | Wire OCR text into the translate-only path and on into the existing `BleTransport.sendSubtitle`. Add an OCR latency record (`capture_ms .. ble_ack_ms`) to `latency_logger.dart`, mirroring the speech record. | analyze clean; logger test. | pending |
| **Codex** | Tests for the OCR latency record + the wiring per PROMPTS.md S3. | `flutter test` green. | pending |
| **Claude** | Review + merge. | n/a | pending |

Commit subject: `feat(mobile): S3 OCR -> translate -> BLE pipeline`.

## Day 5 — OCR device smoke

| Owner | Task | Verify | Status |
|---|---|---|---|
| **User (operator)** | Capture real JP signage/menu on device; confirm recognised text translates and renders on the glasses (MTU safe). | smoke pass/fail logged. | pending |
| **Claude** | Triage smoke results; fix or file follow-ups. | n/a | pending |

## Day 6 — OCR quality + latency bench

| Owner | Task | Verify | Status |
|---|---|---|---|
| **User (operator)** | Run the curated OCR image set on device; export the OCR latency CSV. | CSV captured. | pending |
| **Claude (prep)** | Add an `--s3` (or extend) report mode to `tools/latency_report.py`: OCR recognition % + `p95(ocr_system_latency_ms)` against the locked gates. Tests. | tests green; renders. | pending |
| **Claude** | Render the OCR bench report. | `docs/reports/S3_ocr_<date>.md`. | pending |

Commit subjects: `feat(tools): S3 OCR report mode`, `docs(s3): OCR bench`.

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
3. **Translate-only transport**: REST POST vs new WS message type. WS reuses the
   warm session + streaming; REST is simpler for a one-shot translate. Decide
   Day 2 by which the existing backend supports with the least contract churn.
4. **Reviewer logistics for #3**: paid native-VN reviewer availability + cost
   cap; same privacy rule (scores by eye, no stored text).
