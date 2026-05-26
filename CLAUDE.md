# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LingoGlass AR là kính hiển thị phụ đề và bản dịch thời gian gần thực cho du lịch và giao tiếp đa ngôn ngữ. Đây là dự án **solo founder + AI agents**. S0 (BLE+OLED spike) và S1 (audio→WS→OpenAI Realtime) đã DONE; hiện đang ở **S2** (tối ưu STT, Cloudflare Full(Strict), UX polish). Trạng thái sprint mới nhất xem `README.md` + `docs/codex/S2_TASKS.md`.

Kiến trúc MVP: điện thoại làm gateway (thu âm, OCR, kết nối cloud) → Cloud AI (STT/dịch/OCR) → ESP32-S3 controller → Micro-OLED/waveguide display.

## Tài liệu hiện có

| File | Nội dung |
|---|---|
| `LingoGlass_AR_Project_Plan.md` | Tổng quan sản phẩm, MVP scope, tech stack, BOM, roadmap, go/no-go criteria |
| `LingoGlass_AR_Strategic_Analysis.md` | Phân tích thị trường, đối thủ, điểm nghẽn kỹ thuật, risk register, KPI pilot |
| `LingoGlass_AR_Development_Plan.md` | V-model phát triển, spike spec, FR/NFR, thiết kế chi tiết firmware/BLE/backend |

## Build, test, run

Three independent components, each with its own toolchain. The per-component
`CLAUDE.md` files are authoritative for rules; this is the command cheat-sheet
(including the single-test runs the README omits). Run commands from the dirs shown.

**Backend** (`backend/`, Python 3.12 / FastAPI):
```powershell
cd backend
docker compose up -d --build         # prod-parity run; GET :8000/healthz
pytest                               # unit tests; pass whether redis is up or down
pytest tests/test_translator.py -k stt   # run a single test by name
ruff check . ; ruff format .         # lint + format (no black, no isort)
```

**Mobile** (`mobile/`, Flutter / Dart 3.4+):
```powershell
cd mobile
flutter pub get
flutter test                                   # all unit/widget tests, no device
flutter test test/translate_screen_test.dart   # single file
flutter analyze                                 # 2 pre-existing warnings are allowed
flutter run                                     # device required (PTT translate flow)
```

**Firmware** (`firmware/esp32s3/`, PlatformIO / C++17, board = ESPr Developer S3):
```powershell
pio run -e esp32s3 -d firmware/esp32s3                      # build
pio run -e esp32s3 -t upload -t monitor -d firmware/esp32s3 # flash + serial
pio test -e native -d firmware/esp32s3                      # ble_protocol tests, no hardware
```

**Reports** (`tools/`, stdlib Python only) — consume the CSV from the mobile
app's "Copy E2E CSV" button:
```powershell
$env:PYTHONIOENCODING='utf-8'    # required: report strings use chars cp932 can't encode
py tools/latency_report.py --s1 docs/reports/<run>.csv   # e2e latency, gate p95 <= 2000 ms
py tools/latency_report.py --s2 docs/reports/<run>.csv   # + translation accuracy by direction
```

## Cross-component architecture

One utterance, end to end: phone mic records PCM16 24 kHz mono → WebSocket
session to the FastAPI backend → OpenAI Realtime API (STT + JP↔VN translation,
streamed back) → phone receives translated text → phone encodes it into the BLE
subtitle packet → ESP32-S3 reassembles and renders on the SSD1306 OLED →
firmware ACKs over a notify characteristic. **The phone is the only internet
gateway; the glasses are a BLE peripheral that never talks to the cloud.**

Files that own each leg: phone audio + WS = `mobile/lib/audio/recorder.dart`,
`mobile/lib/services/{translator_ws,session_client}.dart`; backend bridge =
`backend/app/services/translator.py` + `backend/app/api/sessions.py`
(`POST /v1/sessions` + `WS /v1/sessions/{id}/stream`); BLE central =
`mobile/lib/ble/`; BLE peripheral = `firmware/esp32s3/lib/{ble_server,subtitle_assembler,oled_view}/`.

### Invariants that span repos (why you must read multiple files)

1. **The BLE subtitle protocol has FOUR mirrors that change together in one
   commit**: the spec (`.claude/skills/ble-protocol/SKILL.md` — single source of
   truth), the Dart impl (`mobile/lib/ble/ble_protocol.dart`), the C++ impl
   (`firmware/esp32s3/lib/ble_protocol/`), and the shared vectors
   (`tests/ble_vectors.json`) loaded by both Dart and C++ test suites. If code
   disagrees with the skill, fix the code. (Packet layout is in the section below.)

2. **The WS wire contract is dual-owned**: `docs/api-contract/`
   (`openapi.yaml`, `ws-events.schema.json`) is authoritative; the backend and
   `mobile/lib/services/translator_ws.dart` mirror it. Change contract + both
   sides in the same commit.

3. **The latency definition is fixed**: `system_latency_ms = ble_ack_ms -
   audio_ms` (post-PTT-release). Handshake runs concurrently while the user is
   still holding PTT, so `backend_ack_ms < audio_ms` is normal, NOT clock skew.
   The formula lives in `tools/latency_report.py` and
   `mobile/lib/services/latency_logger.dart`; keep them in sync. S2 gate: p95 ≤ 2000 ms.

4. **Privacy boundary (every component)**: never log, store, or export audio
   bytes, **camera image bytes, OCR'd text**, transcripts, translated text, or
   OpenAI tokens/keys — not in code, logs, CSVs, or nippo. Counts, durations,
   and error codes only. This is why translation accuracy is scored live by eye
   and never from stored text. **OCR (S3) is on-device (ML Kit): the captured
   image never leaves the phone and the temp capture file is deleted right
   after recognition; only the recognised text crosses the WS.** OCR
   recognition quality is likewise scored live by eye (key-line pass/fail), not
   from stored text.

## Repo workflow

- **Per-component `CLAUDE.md` is authoritative** — read `backend/CLAUDE.md`,
  `mobile/CLAUDE.md`, or `firmware/CLAUDE.md` before touching that tree.
  `AGENTS.md` is stale (it predates the source tree, says "no application source
  yet"); prefer the sub-CLAUDE files + `README.md`.
- **Claude + Codex split**: Claude leads; Codex assists on feature branches +
  PR only and never pushes to `main`. Task tables and ready-to-paste prompts
  live in `docs/codex/` (`S2_TASKS.md`, `PROMPTS.md`). Tag every Codex prompt
  explicitly: "prep only" / "implement bodies only" / "tests only" / "full
  task". Choose the split by **"is a stub safe?"** — a live or benchmarked code
  path means prep = full implementation, Codex = tests.
- **Daily report**: write `docs/nippo/YYYY-MM-DD.md` every work day (Japanese);
  append an addendum to the same-day file, never overwrite a prior section.
- **Encoding**: Vietnamese Markdown is intentionally ASCII-only (mojibake
  guard); Japanese design HTML and nippo are intentionally UTF-8.

## Quyết định kỹ thuật đã được lock

- **Audio MVP**: microphone điện thoại (không phải mic trên kính)
- **Camera OCR**: camera điện thoại (không phải camera trên kính)
- **Kết nối subtitle**: BLE trước, Wi-Fi chỉ là fallback/debug
- **Controller**: ESP32-S3 (ESP-IDF)
- **Backend MVP**: FastAPI hoặc Node.js + WebSocket (không Kubernetes)
- **Privacy indicator**: LED vật lý bắt buộc trong MVP, không chỉ dùng icon trên OLED

## BLE Subtitle Protocol

Binary packet format đã được define:

```
version(1) | message_type(1) | sequence_id(2) | fragment_index(1) |
fragment_count(1) | payload_length(1) | payload(N) | crc8(1)
```

Quy tắc render: chỉ render khi nhận đủ fragment của sequence hiện tại. Sequence mới hơn hủy subtitle cũ chưa hoàn tất; sequence cũ hơn đến trễ thì giữ active buffer và trả ACK 0x03. Test trên MTU 23/185/247 bytes (BLE ATT MTU minimum là 23, không phải 20).

## Roadmap Solo (ưu tiên dùng)

| Sprint | Thời lượng | Output bắt buộc |
|---|---:|---|
| S0 | 1 tuần | Spike: Phone → BLE → ESP32-S3 → display, pass/fail với log latency |
| S1 | 2 tuần | App gửi subtitle, diagnostics cơ bản |
| S2 | 2-3 tuần | STT + translation benchmark với audio điện thoại |
| S3 | 2 tuần | OCR qua phone camera, hiển thị kết quả trên display |
| S4 | 2-4 tuần | Readability test với AR dev kit hoặc wearable mock |
| S5 | 2-4 tuần | 5-10 người test, report p50/p95, cost |

Mỗi sprint phải làm được bởi 1 người trong thời gian đó. Nếu không, phải cắt scope.

## Ứng viên phần cứng

| Lựa chọn | Dùng để làm gì |
|---|---|
| Waveshare OLED (SSD1306, SPI/I2C) | Spike rẻ nhất cho BLE → ESP32 → text render |
| Brilliant Monocle | AR dev kit (cần xác minh availability trước khi mua) |
| Vuzix Blade/Z100 | Backup software-first nếu custom hardware quá chậm |

**Lưu ý**: Kiểm tra availability và giá thực tế trước khi mua bất kỳ module nào.

## Plan B Spike

| Lỗi | Hướng xử lý |
|---|---|
| BLE latency > 200ms | Tăng MTU, binary packet, giảm subtitle length, fallback Wi-Fi local |
| Fragment lỗi | ACK type=0x03 với status code (0x01 OK / 0x03 error), retry theo sequence_id, chỉ render khi đủ fragment |
| ESP32-S3 render không ổn | Đơn giản hóa font/render, thử ESP32-P4/STM32/RP2040 |
| Display không có datasheet | Loại module đó, chỉ dùng module có sample code |
| Waveguide không đọc được | Thử module khác, giảm target ngoài trời, pilot software-first trên Vuzix/Monocle |

## Go/No-Go Criteria

| Hạng mục | Go | No-go |
|---|---|---|
| Latency hội thoại | 1.5-2.5s với câu ngắn | Thường xuyên > 3.5s |
| Hiển thị ngoài trời | Đọc được trong ánh sáng ban ngày vừa | Phải nhìn lâu mới đọc được |
| Pin | 2-4h active, 8h mixed use | Dưới 1h active |
| Nhiệt | Đeo liên tục không nóng khó chịu | Nóng ở vùng thái dương/sống mũi |

## Latency Budget

| Bước | Mục tiêu |
|---|---:|
| VAD/cắt đoạn âm thanh | 100-300ms |
| Upload audio | 100-300ms |
| STT streaming | 500-1,000ms |
| Dịch | 200-600ms |
| Gửi về kính (BLE) | 50-200ms |
| Render display | <100ms |
| **Tổng** | **1.5-2.5s** |

Log p50/p90/p95 — không chỉ đo demo tốt nhất.

## Cloud Cost Pilot (50 users)

Ước tính $100-550 USD/tháng (75-450 AI + 25-100 infra). Đặt hard cap usage và log chi phí theo session trong pilot.
