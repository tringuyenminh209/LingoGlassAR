# firmware/ — ESP32-S3 controller code

Scope of this directory: everything that runs on the wearable controller. Mobile and backend code live elsewhere; the contract between them is the BLE subtitle protocol (`.claude/skills/ble-protocol/SKILL.md`).

## Active board

ESPr Developer S3 (Switch Science), ESP32-S3-WROOM-1, 16 MB flash, 8 MB PSRAM. Locked baseline in `docs/LingoGlass_AR_Display_Decision_Record.md` — do not switch back to ESP32-S3-DevKitC-1, Waveshare 0.49 inch OLED, or other boards without an explicit user decision.

## Pin map (S0)

| Function | GPIO | Notes |
| --- | ---: | --- |
| I2C SDA | 8 | OLED |
| I2C SCL | 9 | OLED |
| Status LED | LED_BUILTIN | Heartbeat |

Expected OLED I2C address: `0x3C` or `0x3D`. Run the I2C scanner in `main.cpp` to confirm before assuming.

## GATT (locked for S0)

| Role | UUID |
| --- | --- |
| Service | `7c3d8b00-9e8a-4f15-b6c3-1d2e3f4a5b6c` |
| Subtitle write (write, write-no-response) | `7c3d8b01-9e8a-4f15-b6c3-1d2e3f4a5b6c` |
| ACK / status notify | `7c3d8b02-9e8a-4f15-b6c3-1d2e3f4a5b6c` |

Advertised device name: `LingoGlass-S0`. Negotiate MTU 247 at connect; accept whatever the central agrees to.

## Build system

PlatformIO. Project root: `firmware/esp32s3/`.

```powershell
# Build for device
pio run -e esp32s3 -d firmware/esp32s3

# Flash + monitor
pio run -e esp32s3 -t upload -t monitor -d firmware/esp32s3

# Native unit tests for ble_protocol (no hardware needed)
pio test -e native -d firmware/esp32s3
```

Do not commit `.pio/` build artifacts.

## Coding conventions

- C++17, Arduino framework on top of ESP-IDF.
- One job per file: `main.cpp` is wiring only. Protocol logic lives in `lib/ble_protocol/`. BLE server logic will live in `lib/ble_server/` (Phase C). OLED rendering in `lib/oled_view/` (Phase B).
- Use `Serial.printf` for hot-path diagnostics, `Serial.println` for one-shot status. Tag each line so it greps cleanly: `[ble]`, `[oled]`, `[i2c]`.
- Memory: avoid `String` in BLE callbacks. Use raw `uint8_t*` + length. Heap fragmentation kills long-running ESP32 firmware.
- Latency-sensitive code must not allocate inside loops; reuse static buffers sized to `MAX_PACKET_SIZE`.

## Protocol rules (do not re-derive)

The packet layout, CRC8 algorithm, fragmentation rule, and render rule are in `.claude/skills/ble-protocol/SKILL.md`. The skill is the single source of truth — if firmware code disagrees with it, fix the code, not the skill. The test vectors in `tests/ble_vectors.json` are shared with the mobile app; both must pass.

## Sprint hooks

- S0 Phase B (done 2026-05-17): OLED render. `lib/oled_view/` wraps `U8G2_SSD1306_128X64_NONAME_F_HW_I2C`, font `u8g2_font_6x10_tf`, two-line layout at y=0 and y=16. Caller owns `Wire.begin(SDA, SCL)`. Default address 0x3C, override via `oled_view::begin(0x3D)` if needed. ASCII only; Japanese font is S1+.
- S0 Phase C (done 2026-05-17): NimBLE server. `lib/ble_server/` exposes `begin(name, on_write_callback)` / `is_connected()` / `notify_ack(data, len)`. Auto-restarts advertising on disconnect. Requested MTU 247.
- S0 Phase D (done 2026-05-17): `main.cpp` `onSubtitleWrite` calls `ble_protocol::decode_fragment`. On Ok + single-fragment subtitle: render payload as null-terminated text on OLED, send Ack with `status=0x01`. On multi-fragment: send Ack with `status=0x02` UNSUPPORTED (Phase E will assemble + render). On decode failure: send Ack with `status=0x03` DECODE_ERROR. Status codes are defined in `AckStatus` namespace at top of `main.cpp` and mirror `.claude/skills/ble-protocol/SKILL.md`. End-to-end verified: Flutter app sends "Hello", OLED shows "Hello", app receives Ack status=0x01.
- S0 Phase D-E: wire `ble_protocol::decode_fragment` into the write callback. Fragment buffer keyed by `sequence_id`. Drop stale buffer when a higher `sequence_id` arrives.
- S0 Phase F: timestamp `millis()` at write callback entry, include in ACK payload after subtitle is fully rendered.

## When you finish a sprint phase

Update the relevant section here only if the rule for the next sprint changes (pin map, UUID, library swap). Do not log per-PR change history — that belongs in the report at `docs/S0_spike_report.md`.
