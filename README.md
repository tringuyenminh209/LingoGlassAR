# LingoGlass AR

Real-time subtitle and translation eyewear for travel and multilingual
communication.

Status: S1 sprint complete - see
[`docs/reports/S1_Day9_report.md`](docs/reports/S1_Day9_report.md).

## Architecture

```text
+-----------------+      +-----------------------------+
| Phone (Flutter) | ---> | Backend (FastAPI, AWS Osaka) |
+-----------------+      +-----------------------------+
                                      |
                                      v
                            +---------------------+
                            | OpenAI Realtime API |
                            +---------------------+
                                      |
                                      v
+---------------------+      +-----------------------------+
| Phone (BLE central) | <--- | Backend (FastAPI, AWS Osaka) |
+---------------------+      +-----------------------------+
         |
         v
+----------------------------+      +--------------+
| ESP32-S3 (BLE peripheral) | ---> | SSD1306 OLED |
+----------------------------+      +--------------+
```

The phone is the input gateway. It records speech as PCM16 24 kHz mono
audio and sends the utterance to the backend over a WebSocket session.

The FastAPI backend bridges that stream to the OpenAI Realtime API for
speech-to-text and translation. Translated text returns to the phone over
the backend WebSocket.

The Flutter app then sends subtitle packets over BLE to the ESP32-S3
controller. The SSD1306 OLED renders the subtitle for the wearer.

The current latency budget is `p95 system_latency <= 2500 ms`. The S1
device run measured `1493 ms` on 2026-05-22; the report explains the
post-PTT-release measurement boundary and the observed stage breakdown.

## Repository layout

- `mobile/` - Flutter companion app for Android and iOS.
- `backend/` - FastAPI service and WebSocket bridge to OpenAI Realtime.
- `firmware/` - ESP32-S3 ESP-IDF / PlatformIO firmware.
- `infra/` - EC2 bootstrap and deployment scripts.
- `docs/` - Architecture notes, API contracts, runbooks, and reports.
- `tools/` - CSV report renderers for Phase F and S1.
- `tests/` - BLE protocol vectors shared by Dart and C++ tests.

## Quick start

Each component has its own local rules and test details. The commands
below are the shortest paths for a fresh checkout.

### Backend (local Docker)

Create the backend environment file before starting the Compose stack.
The OpenAI API key is required for live translation sessions.

```sh
cd backend
cp .env.example .env  # add OPENAI_API_KEY
docker compose up
# http://localhost:8000/healthz -> {"status":"ok",...}
```

The backend health endpoint is useful before wiring a phone or firmware
device into the loop.

### Mobile (Flutter)

Flutter unit tests do not need a physical phone. Running the app does.

```sh
cd mobile
flutter pub get
flutter test       # 33/33 tests
flutter run        # device required
```

The mobile app owns the microphone, the backend WebSocket client, and the
BLE central role.

### Firmware (ESP32-S3)

Flash the controller from the PlatformIO project under the firmware tree.

```sh
cd firmware/esp32s3
pio run -t upload  # PlatformIO; ESPr Developer S3 + SSD1306
```

The S0 hardware baseline is the ESPr Developer S3 with an SSD1306 OLED.
See the firmware notes and hardware decision record before changing board
or display assumptions.

## Key technical decisions

- Audio input comes from the phone microphone, not a microphone on the
  eyewear.
- The phone camera is the source for future OCR work in S3.
- Subtitle transport is BLE first; Wi-Fi is only a debug fallback.
- The wearable controller is ESP32-S3 using the ESP-IDF / Arduino stack.
- The backend is FastAPI with WebSockets; the MVP does not use Kubernetes.
- A physical privacy LED is required for S2 and later hardware work; an
  OLED icon alone is not enough.

## Sprint progress

| Sprint | Status | Highlights |
| --- | --- | --- |
| S0 | DONE 2026-05-18 | BLE + OLED spike, MTU 23/185/247 verified |
| S1 | DONE 2026-05-22 | Audio + WS + OpenAI Realtime + cost cap + e2e latency 1493 ms p95 |
| S2 | starting | STT optimisation, Cloudflare Full(Strict), UX polish |

The S1 decision trail and measured latency results are in
[`docs/reports/S1_Day9_report.md`](docs/reports/S1_Day9_report.md).

## Documentation map

- [`docs/LingoGlass_AR_Project_Plan.md`](docs/LingoGlass_AR_Project_Plan.md)
  - product spec, bill of materials, roadmap, and go/no-go criteria.
- [`docs/LingoGlass_AR_Strategic_Analysis.md`](docs/LingoGlass_AR_Strategic_Analysis.md)
  - market analysis, risks, and validation strategy.
- [`docs/LingoGlass_AR_Development_Plan.md`](docs/LingoGlass_AR_Development_Plan.md)
  - V-model development plan, testing matrix, and traceability.
- [`docs/api-contract/`](docs/api-contract/)
  - WebSocket schema, samples, and OpenAPI contract.
- [`docs/codex/`](docs/codex/)
  - Codex briefing, sprint task tables, and task prompts.
- [`docs/runbook/`](docs/runbook/)
  - AWS deployment runbooks and operator steps.
- [`docs/reports/`](docs/reports/)
  - sprint reports, raw measurements, and rendered latency summaries.
- [`docs/nippo/`](docs/nippo/)
  - daily Japanese work reports.
- [`CLAUDE.md`](CLAUDE.md)
  - high-level Claude Code rules for this repository.
- [`mobile/CLAUDE.md`](mobile/CLAUDE.md),
  [`backend/CLAUDE.md`](backend/CLAUDE.md), and
  [`firmware/CLAUDE.md`](firmware/CLAUDE.md)
  - component-specific rules and workflow notes.

## License

All rights reserved. Contact:
