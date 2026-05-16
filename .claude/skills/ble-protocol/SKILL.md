---
name: ble-protocol
description: Encode, decode, fragment, and CRC-check the LingoGlass AR BLE subtitle packet. Use whenever code touches BLE GATT in firmware (ESP-IDF / Arduino), mobile app (subtitle send), or test fixtures. Enforces the locked binary format and render rules from docs/LingoGlass_AR_Development_Plan.md.
---

# LingoGlass AR BLE Subtitle Protocol

This skill is the single source of truth for the BLE subtitle packet. The format is **locked** in `docs/LingoGlass_AR_Development_Plan.md` (section "BLE subtitle protocol detail") and `CLAUDE.md` (root). Do not change field sizes or order without updating both documents in the same change.

## Packet layout (10 bytes header + payload)

| Offset | Field           | Size    | Notes                                          |
| -----: | --------------- | ------: | ---------------------------------------------- |
|      0 | version         | 1 byte  | Start at `0x01`. Bump on any layout change.    |
|      1 | message_type    | 1 byte  | `0x01` subtitle, `0x02` status, `0x03` ack, `0x04` error |
|      2 | sequence_id     | 2 bytes | Little-endian. Monotonic per subtitle.         |
|      4 | fragment_index  | 1 byte  | `0..fragment_count-1`                          |
|      5 | fragment_count  | 1 byte  | Total fragments for this `sequence_id`.        |
|      6 | payload_length  | 1 byte  | Bytes in `payload` (this fragment only).       |
|      7 | payload         | N bytes | UTF-8 text fragment. Never split inside a multi-byte codepoint. |
| 7+N    | crc8            | 1 byte  | CRC-8/CCITT (poly 0x07, init 0x00) over bytes 0..6+N. |

Total fragment size: `10 + payload_length` bytes. Cap `payload_length` so total fits in the negotiated MTU minus the 3-byte ATT header.

## MTU sizing

Test on three MTU profiles. Pick `payload_length` from the table below.

| Negotiated MTU | Usable ATT payload | Max `payload_length` |
| -------------: | -----------------: | -------------------: |
|             20 |                 17 |                    7 |
|            185 |                182 |                  172 |
|            247 |                244 |                  234 |

Always negotiate MTU at connect; do not assume 247 will succeed.

## UTF-8 fragmentation rule

When splitting a subtitle into fragments, never cut inside a multi-byte UTF-8 codepoint. Algorithm:

1. Start at byte offset `start`.
2. Tentative end = `start + max_payload`.
3. While `end > start` and `(bytes[end] & 0xC0) == 0x80`, decrement `end` (back off into the leading byte).
4. Emit `bytes[start:end]` as one fragment, advance `start = end`.

Japanese (3 bytes/char) and Vietnamese with diacritics (2 bytes/char) both rely on this.

## CRC-8 reference

```
poly  = 0x07
init  = 0x00
xorout= 0x00
refin = false
refout= false
```

Test vector: CRC of bytes `01 01 01 00 00 01 01 41` (version=1, type=subtitle, seq=1, frag 0 of 1, len=1, payload='A') must equal `0x5B`. Additional vectors are in `tests/ble_vectors.json`. Verify any new implementation against the full vector set before integrating.

## Render rules (firmware)

These rules are **mandatory** in the ESP32-S3 receiver:

1. Buffer fragments keyed by `sequence_id`.
2. Render only when **all** fragments of a `sequence_id` are received and CRC passes on each.
3. If a packet with a higher `sequence_id` arrives before the current one completes, **drop** the incomplete buffer and start the new sequence. Never render partial text.
4. On CRC failure, send NAK (`message_type=0x04`, `payload` = the failed `sequence_id` + `fragment_index`).
5. On full subtitle render, send ACK (`message_type=0x03`, `payload` = `sequence_id`).

## Sender rules (mobile / test harness)

1. Allocate a new `sequence_id` for each subtitle. Wrap at `0xFFFF` -> `0x0000`.
2. Send fragments in order; do not interleave with another `sequence_id`.
3. Wait for ACK or timeout (default 300 ms) before retrying the whole sequence with the **same** `sequence_id`.
4. After 2 retries, log a `ble_send_fail` diagnostic event and skip — never block the audio pipeline.

## Latency budget contribution

This protocol owns the "Gui ve kinh (BLE)" row in the latency budget (`CLAUDE.md`): target 50-200 ms. Any change that risks pushing this above 200 ms must be flagged.

## What this skill does NOT cover

- GATT service / characteristic UUIDs (live in firmware code + mobile app code; pick once, document in `firmware/CLAUDE.md` when scaffolded).
- Pairing / bonding flow.
- Wi-Fi fallback transport (separate skill when needed).

## Checklist before declaring BLE work done

- [ ] Encoder and decoder both pass the `0x3E` CRC test vector.
- [ ] Round-trip test with 100-character Japanese subtitle on MTU 20, 185, 247.
- [ ] Out-of-order sequence test: send seq=2 before seq=1 completes -> seq=1 must be dropped, seq=2 must render.
- [ ] UTF-8 boundary test: subtitle whose byte-cut would land mid-codepoint.
- [ ] Latency log p50/p90/p95 captured, p95 < 200 ms.
