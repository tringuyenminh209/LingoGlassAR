# LingoGlass AR — Codex Onboarding Briefing

Read this first. Then read `S1_TASKS.md` for what to do. This file is the
**minimum context** you need; for deeper investigation, the canonical
sources are listed at the bottom.

## 1. Product in one paragraph

LingoGlass AR is a wearable subtitle/translation display for travel and
multilingual conversation. Phone is the gateway (records audio via mic,
runs OCR via camera, talks to cloud AI). Cloud AI returns translated
text. Phone forwards text over **BLE** to an **ESP32-S3** controller
that drives a small **OLED / waveguide** display worn on glasses.
Solo founder + AI agents. Target market: Japanese tourist sector + VN/EN
visitors to Japan.

## 2. Where we are (2026-05-20)

**S0 spike done** (Phase A through F). End-to-end BLE leg validated:
phone -> ESP32 -> OLED renders subtitle text in **~200 ms p95** at MTU
247. Conditional GO verdict. Real audio + STT pipeline is **S1**, which
starts next.

| Phase | Status | Output |
|---|---|---|
| A scaffold | done | Flutter + PlatformIO + NimBLE + U8g2 |
| B OLED | done | ASCII text on SSD1306 128x64 |
| C BLE GATT | done | NimBLE service `7c3d8b00...`, write + notify chars |
| D single-frag | done | Decode + render single-fragment subtitle |
| E multi-frag | done | SubtitleAssembler, MTU 23/185/247, stale handling |
| F latency | done | ACK timestamps, Run 20 harness, p95 = 199.9 ms |
| **S1 audio** | **next** | Phone PTT -> backend -> OpenAI Realtime -> BLE |

Verdict file: `docs/phase_f_report.md`. Raw run: `out/run_2026-05-20.csv`.

## 3. Repo map (only paths Codex will likely touch)

```
firmware/esp32s3/        ESP-IDF + Arduino, PlatformIO project
  src/main.cpp            wiring only; protocol logic lives in libs
  lib/ble_protocol/       packet codec (C++) - mirror of mobile dart
  lib/ble_server/         NimBLE server wrapper
  lib/subtitle_assembler/ multi-fragment reassembly
  lib/oled_view/          U8g2 wrapper
  test/                   native (host) unit tests via pio test -e native
  platformio.ini          board = esp32-s3-devkitc-1, overridden to N16R8

mobile/                   Flutter Dart 3.4+, flutter_blue_plus 1.32.x
  lib/ble/                ble_protocol.dart (mirror of firmware C++)
                          ble_transport.dart (FBP wrapper, AckEvent, SendInfo)
  lib/services/           latency_logger.dart (Phase F)
  lib/screens/            spike_screen.dart (S0 dev UI)
  test/                   flutter test - shared vectors with firmware

backend/                  TO BE CREATED in S1 Day 1. Python 3.12 + FastAPI
                          + uvicorn + websockets + openai SDK. Docker
                          Compose with Redis.

docs/                     Planning docs (mostly Vietnamese ASCII-only),
                          Japanese design docs in docs-html/,
                          phase F report, daily reports under nippo/.

tests/                    Shared cross-stack assets: ble_vectors.json
                          (binary protocol vectors used by both firmware
                          C++ and mobile Dart test suites).

tools/                    Python utilities (stdlib only).
                          latency_report.py reads CSV from mobile Run 20.

out/                      Raw experiment data. CSV files from device runs.
                          Committed for reproducibility.

.claude/                  Local agent metadata. Do NOT edit unless
                          explicitly instructed.
  skills/ble-protocol/SKILL.md   single source of truth for the BLE
                                  packet format. Firmware + mobile must
                                  stay in sync with this file.
```

## 4. Hard rules — DO NOT BREAK

Pulled from CLAUDE.md hierarchy (`./CLAUDE.md`, `firmware/CLAUDE.md`,
`mobile/CLAUDE.md`) and user feedback memory:

1. **Commits**: conventional commits in English. Subject under 70 chars.
   Body explains the *why* and key facts (numbers, side effects).
2. **Never** add `Co-Authored-By: Claude` or any Anthropic agent
   trailer to a commit message. Hard project rule.
3. **Never** add `axios` to mobile dependencies. Use Dart `http` or the
   project's BLE / WS primitives.
4. **ASCII-only Vietnamese**: Vietnamese text in Markdown planning files
   uses no diacritics. Japanese files use full Japanese characters.
5. **BLE packet layout is locked**. If you change anything in the codec,
   you must update `firmware/esp32s3/lib/ble_protocol/`,
   `mobile/lib/ble/ble_protocol.dart`, `tests/ble_vectors.json`, and
   `.claude/skills/ble-protocol/SKILL.md` in the same commit.
6. **Hardware baseline is locked**: ESPr Developer S3 (Switch Science,
   N16R8 module). Do not switch to ESP32-S3-DevKitC-1, Waveshare 0.49",
   Freenove CAM, or another board without explicit user approval.
7. **I2C pins are locked**: SDA = GPIO 8, SCL = GPIO 9. OLED at 0x3C.
8. **No destructive ops without explicit ask**: never `rm -rf`,
   `git reset --hard`, `git push --force`. The user's `.claude/settings`
   already blocks the worst patterns; assume the spirit of the rule.
9. **No new commits with hook bypass** (`--no-verify`, `--no-gpg-sign`).
10. **PlatformIO board override** for N16R8 is in `platformio.ini`:
    `flash_size=16MB`, `arduino.memory_type=qio_opi`,
    `partitions=default_16MB.csv`, `-DBOARD_HAS_PSRAM`. Don't revert.

## 5. Tech stack snapshot

| Layer | Tech | Why |
|---|---|---|
| Firmware | C++17 on Arduino framework (PlatformIO + ESP-IDF) | Locked baseline |
| Firmware libs | NimBLE-Arduino ^1.4.2, U8g2 ^2.35.30, Unity (native tests) | Locked |
| Mobile | Flutter 3.22+, Dart 3.4+, flutter_blue_plus 1.32.x | Cross-platform sender |
| Backend | (S1) FastAPI + uvicorn + Redis on Docker Compose | Python familiarity, OpenAI SDK |
| Cloud | AWS Osaka ap-northeast-3, EC2 t4g.small Ubuntu 22.04 | Solo-dev friendly, AWS-native |
| TLS | Cloudflare proxied (orange cloud), domain `lingoglass.online` | Free edge TLS, no Let's Encrypt mgmt |
| AI | OpenAI Realtime API (S1) -> Whisper API + GPT-4o-mini (S2) | Existing OpenAI key, swap later for cost |
| CI | none yet | Add in S2 (GitHub Actions, native tests + flutter test) |

## 6. BLE protocol contract (must know for any pipeline work)

Service `7c3d8b00-9e8a-4f15-b6c3-1d2e3f4a5b6c`, write
`7c3d8b01-...`, notify `7c3d8b02-...`.

Packet = 7-byte header + payload + 1-byte CRC. CRC-8/CCITT poly 0x07
init 0x00. `sequence_id` little-endian.

ACK payload (Phase F+): `status(1) | reserved(1) | t_recv_ms(4 LE) |
t_render_ms(4 LE)` = 10 bytes total. Status `0x01` OK, `0x02`
unsupported, `0x03` decode error.

Full spec: `.claude/skills/ble-protocol/SKILL.md`. Vectors:
`tests/ble_vectors.json`.

## 7. Latency budget (the number that matters)

End-to-end target: **p95 < 2.5 s** from speech end to OLED render.

| Stage | Target (ms) | Current actual |
|---|---:|---|
| Audio VAD/chunk | 100-300 | n/a (S1) |
| Audio upload | 100-300 | n/a (S1) |
| STT streaming | 500-1000 | n/a (S1) |
| Translation | 200-600 | n/a (S1) |
| BLE leg phone -> OLED | 50-200 | **199.9 ms p95** (S0 measured) |
| OLED render included in above | <100 | 32 ms median (in fw_proc) |

**BLE leg has zero headroom**. Any S1+ change to the BLE path requires
re-running the Phase F harness.

## 8. Conventions worth scanning before contributing

- `CLAUDE.md` (root) - global rules: code hygiene, no dead code, single source of truth, grep before adding.
- `firmware/CLAUDE.md` - sprint hooks (locks per-phase decisions), pin map, build commands.
- `mobile/CLAUDE.md` - Flutter conventions, sprint hooks, BLE contract mirror.
- `.claude/skills/ble-protocol/SKILL.md` - BLE packet format.

## 9. Things that bit us before (anti-patterns)

1. **Stale BLE state in `flutter_blue_plus`**: cached `_device` ref kept saying "connected" after OS-level link drop. Fix: subscribe to `device.connectionState` and clear refs on disconnect. See commit `c453d46`.
2. **Assembler validation order**: a stale (older `sequence_id`) packet with malformed fields was destroying active buffer because validation ran before classification. Fix: classify by sequence first, then validate. See commit `338a24a`.
3. **Board cfg silently building as N8**: `platformio.ini` initially had no `flash_size` / `memory_type` overrides so the N16R8 hardware was treated as N8 (no PSRAM). Always grep build logs for `Flash bytes: 16777216 / PSRAM bytes: 8388608`.
4. **MTU 20 vs MTU 23 confusion**: docs originally said "MTU 20" which is actually the ATT payload at MTU 23. BLE 4.0 minimum MTU is 23. Use MTU 23 in all new docs.
5. **OLED font is ASCII only**: rendering CJK on the SSD1306 is deferred to S1+ because U8g2 CJK fonts add 50-200 KB flash. Don't be surprised by garbled glyphs - confirm via Serial log + ACK status `0x01` instead.

## 10. Sources to consult if confused

In rough order of usefulness:
1. `CLAUDE.md` hierarchy (root + firmware + mobile)
2. `.claude/skills/ble-protocol/SKILL.md`
3. Latest commits on `main` (run `git log --oneline -20`)
4. `docs/phase_f_report.md` - what S0 achieved and what's borderline
5. `docs/LingoGlass_AR_Development_Plan.md` - V-model, FR/NFR, detailed design
6. `docs/LingoGlass_AR_Project_Plan.md` - market, BOM, roadmap
7. `out/run_2026-05-20.csv` - real measurement data

Ask the user before:
- adding a new top-level directory
- changing the BLE packet layout in any way
- introducing a new third-party library
- modifying `.claude/` for anything other than what you were told to
- pushing to remote
