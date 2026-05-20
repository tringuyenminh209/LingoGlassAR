# mobile/ — Flutter sender app

Scope: the phone-side companion app that sends subtitles to the ESP32-S3 controller over BLE. S0 goal is a minimal spike harness, not a polished product.

## Stack

- Flutter (Dart 3.4+).
- `flutter_blue_plus` for BLE central role.
- `permission_handler` for runtime Bluetooth / Location prompts.
- No state management library yet; `setState` is fine until S1.

## GATT contract (mirror of firmware/CLAUDE.md)

| Role | UUID |
| --- | --- |
| Service | `7c3d8b00-9e8a-4f15-b6c3-1d2e3f4a5b6c` |
| Subtitle write | `7c3d8b01-9e8a-4f15-b6c3-1d2e3f4a5b6c` |
| ACK / status notify | `7c3d8b02-9e8a-4f15-b6c3-1d2e3f4a5b6c` |

Filter scan by service UUID + advertised name `LingoGlass-S0`. Request MTU 247 immediately after connect; fall back gracefully if the OS returns less.

## Bootstrapping the project shells

The `android/`, `ios/`, etc. directories are not committed — generate them once on a fresh checkout:

```powershell
flutter create . --project-name lingoglass_mobile --org com.lingoglass --platforms=android,ios
flutter pub get
```

Then add to `android/app/src/main/AndroidManifest.xml`:
- `android.permission.BLUETOOTH_SCAN` (with `usesPermissionFlags="neverForLocation"` if not using location for ranging)
- `android.permission.BLUETOOTH_CONNECT`
- `android.permission.ACCESS_FINE_LOCATION` (Android 11 and below)

And to `ios/Runner/Info.plist`:
- `NSBluetoothAlwaysUsageDescription` with a one-line justification.

## Run / test

```powershell
flutter pub get
flutter test              # unit tests, no device required
flutter run               # device must be connected; runs spike_screen
```

## Coding conventions

- Lib layout: `lib/ble/` (protocol + transport), `lib/screens/` (one file per screen), `lib/services/` (latency logger, CSV exporter — Phase F). No `lib/utils.dart` catch-all.
- Protocol code (`lib/ble/ble_protocol.dart`) is a Dart mirror of the C++ in `firmware/esp32s3/lib/ble_protocol/`. Both sides must pass the vectors in `tests/ble_vectors.json`. When you change one side, change the other in the same commit and re-run both test suites.
- Prefer `Uint8List` over `List<int>` at BLE boundaries to avoid copies.
- Time measurements: `Stopwatch` or `DateTime.now().microsecondsSinceEpoch` — pick one and stay consistent in `lib/services/`.

## Sprint hooks

- S0 Phase D (done 2026-05-17): `lib/ble/ble_transport.dart` ships `BleTransport.scanAndConnect()` + `sendSubtitle(text, seq)` + ACK notify subscription. MTU 247 requested at connect; **actual negotiated MTU is stored in `_negotiatedMtu`** and used by `sendSubtitle` when caller does not pass an explicit `mtu` (default 23 = BLE minimum until requestMtu returns). UTF-8 via `dart:convert` `utf8.encode`. `AckEvent.isOk` is `status == 0x01`; `0x02` = unsupported, `0x03` = decode error.
- S0 Phase E (done 2026-05-18): `SpikeScreen` adds **Send JA** (~100-char Japanese sample) and **MTU matrix 23/185/247** buttons. `_sendText(text, mtu:)` lets callers force a specific MTU per send (passes through to `BleTransport.sendSubtitle`). The matrix iterates `[23, 185, 247]` with a 1500 ms gap between sends so the firmware assembler can complete + ACK before the next sequence starts. Firmware-side reassembly verified by ACK status=0x01 carrying the original `sequence_id`. `splitUtf8` is unchanged from Phase D; codepoint-boundary correctness covered by `test/ble_protocol_test.dart`.
- S0 Phase F (in progress): `lib/services/latency_logger.dart` records send timestamps per `sequence_id` via `markSendStart` (called from `BleTransport.sendSubtitle`'s `onSendStart` hook so the timer fires just before the first BLE write). `recordAck` matches incoming `AckEvent` to the pending entry and produces a `LatencyRecord` (RTT in ms from phone clock, `fw_proc_ms = t_render_ms - t_recv_ms` from the ESP32 clock). `BleTransport.sendSubtitle` now returns a `SendInfo` struct (bytes, fragments, effective MTU). `AckEvent` carries `tRecvMs` and `tRenderMs` parsed from the Phase F 10-byte payload; 0 means "no firmware timestamp". `SpikeScreen.Run 20` runs the `_latencyRunPlan` (4 warmups + 8 JP MTU-cycle + 8 short bursts) and prints p50/p90/p95 to the on-screen log. The `Copy CSV` button puts `LatencyRecord.csvHeader` + rows on the clipboard for pasting into the Phase F report.

## Do not

- Add `axios` or any HTTP-call shim that pulls in non-Flutter web deps. Backend integration is post-S0 and uses Dart's built-in `http` package.
- Persist user audio on device. Spike sends only text typed into the app for now.
- Touch the platform shells (`android/`, `ios/`) for any logic that should be in Dart.
