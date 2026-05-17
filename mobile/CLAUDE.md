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

- S0 Phase D (done 2026-05-17): `lib/ble/ble_transport.dart` ships `BleTransport.scanAndConnect()` + `sendSubtitle(text, seq)` + ACK notify subscription. `SpikeScreen` wired: Scan button connects, Send Hello sends seq incrementing from 1. ACK arrival logs to UI. MTU requested 247 (Android only; iOS auto). UTF-8 via `utf8.encode`.
- S0 Phase E: handle MTU negotiation result and split with `splitUtf8(text, mtu - 3 - packetOverhead)`.
- S0 Phase F: implement `LatencyLogger` that records `send_ts` per fragment, matches ACK by `sequence_id`, exports CSV with p50/p90/p95. Wire to `_onRun20Pressed`.

## Do not

- Add `axios` or any HTTP-call shim that pulls in non-Flutter web deps. Backend integration is post-S0 and uses Dart's built-in `http` package.
- Persist user audio on device. Spike sends only text typed into the app for now.
- Touch the platform shells (`android/`, `ios/`) for any logic that should be in Dart.
