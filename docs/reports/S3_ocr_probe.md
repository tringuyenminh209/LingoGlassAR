# S3 Day 1 - OCR probe + metric lock

Desk research for the phone-camera OCR path. On-device ML Kit, tap-to-capture,
image never leaves the phone (locked scope, see `docs/codex/S3_TASKS.md`).
Facts below are verified from pub.dev / ML Kit docs; items marked
**[device-confirm]** must be re-checked on a real build (Galaxy S10).

## Package

`google_mlkit_text_recognition` (Flutter, on-device ML Kit Text Recognition v2).
The plugin forwards to Google's native ML Kit; recognition runs on-device and
works offline. No 32-bit support (i386/armv7); arm64 only — Galaxy S10 is arm64,
OK. Default build recognises Latin only; Japanese needs a script dependency.

### Japanese script setup
- **Android**: `com.google.mlkit:text-recognition-japanese:16.0.0` (bundled,
  larger app, faster first use) OR
  `com.google.android.gms:play-services-mlkit-text-recognition-japanese:16.0.1`
  (unbundled, model downloaded via Play Services, ~260 KB app-size impact).
  **Pick unbundled** to keep the APK small; accept a one-time model download on
  first use. **[device-confirm]** model download happens once, then offline.
- **iOS**: pod `GoogleMLKit/TextRecognitionJapanese` (~9.0.0); models ship in
  the pod (adds tens of MB to the app). **[device-confirm]** iOS app size.
- Dart API: `TextRecognizer(script: TextRecognitionScript.japanese)`;
  `recognizer.processImage(InputImage)` -> `RecognizedText` with blocks ->
  lines -> elements + bounding boxes.

### Capture pipeline
- `camera` package: `CameraController.takePicture()` -> `XFile` (temp path) ->
  `InputImage.fromFilePath(xfile.path)` -> recognise -> **delete the temp file
  immediately** (privacy: image bytes never persisted, never sent).
- Permissions: Android `CAMERA` in manifest; iOS `NSCameraUsageDescription`.
- Alternative `image_picker` (system camera UI) is simpler but heavier UX;
  prefer `camera` for an in-app tap-to-capture button consistent with PTT.

## On-device / privacy confirmation

Recognition is fully on-device and offline — the captured image is never
uploaded for OCR. Only the recognised **text** is sent onward to the backend
translate-only path. This keeps the existing privacy boundary intact: no new
cloud surface for image bytes. The temp capture file is deleted right after
`processImage` returns. (Privacy rule extended in CLAUDE.md this day to name
image bytes + OCR'd text.)

## Metrics locked

### Criterion #1 - OCR recognition quality (LOCKED: key-line accuracy)
Score **key-line accuracy**, not raw per-character accuracy. Per test image
there is one designated "key line" (the user-relevant text: the sign caption,
the menu item, the notice headline). An image PASSES if ML Kit recognises that
key line with no error that changes meaning (minor spacing/punctuation noise is
OK). Rationale: char accuracy punishes harmless noise and undersells product
value; key-line is what actually reaches the glasses and the translator.
- Gate: **>= 80%** of images pass.
- Scored **by eye, live**, recording only a stable image id + pass/fail +
  capture/latency timings. **The recognised text is never stored** (privacy),
  same discipline as translation accuracy scoring.

### Criterion #2 - OCR end-to-end latency (definition LOCKED, gate provisional)
`ocr_system_latency_ms = ble_ack_ms - capture_ms`, where `capture_ms` is the
tap-to-capture timestamp (analogue of PTT release for speech). Decomposable into
capture, on-device OCR, translate, BLE legs.
- Gate: **p95 <= 1500 ms** (provisional). Tighter than the speech 2000 ms gate
  because there is no audio upload and no STT. **[device-confirm]**: measure the
  on-device OCR step alone on Galaxy S10 before locking; the gate must keep a
  margin like speech did (~550 ms cushion at S2 close). Re-lock after the first
  device build (Day 3/5).

## Curated image set (locked shape)

~20 real Japanese photos, ASCII-safe ids, 4 domains x 5:
- `sign-01..05` - street/station signage
- `menu-01..05` - restaurant menus
- `notice-01..05` - warnings / info notices
- `label-01..05` - product / package labels

Sourced from real-world photos (no faces, no personal data). Each image gets one
designated key line for criterion #1. The set is for benchmarking only; images
are local test assets, not user data.

## Day 2 input (translate-only transport)

Open question #3 stays for Day 2: REST POST vs new WS message type for
translate-only. Probe note: the speech path streams partial transcripts; OCR has
the full text up front, so a one-shot request fits. REST is simpler, but reusing
the warm WS session avoids a second OpenAI connection setup. Decide Day 2 by
least contract churn against `backend/app/api/sessions.py`.

## Sources

- [google_mlkit_text_recognition (pub.dev)](https://pub.dev/packages/google_mlkit_text_recognition)
- [ML Kit Text Recognition v2 (Google)](https://developers.google.com/ml-kit/vision/text-recognition/v2)
- [ML Kit Text Recognition v2 - Android](https://developers.google.com/ml-kit/vision/text-recognition/v2/android)
