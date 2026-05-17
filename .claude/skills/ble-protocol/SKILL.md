---
name: ble-protocol
description: Encode, decode, fragment, and CRC-check the LingoGlass AR BLE subtitle packet. Use whenever code touches BLE GATT in firmware (ESP-IDF / Arduino), mobile app (subtitle send), or test fixtures. Enforces the locked binary format and render rules from docs/LingoGlass_AR_Development_Plan.md.
---

# LingoGlass AR BLE Subtitle Protocol

This skill is the single source of truth for the BLE subtitle packet. The format is **locked** in `firmware/CLAUDE.md` and the shipping code at `firmware/esp32s3/lib/ble_protocol/` (C++) and `mobile/lib/ble/ble_protocol.dart` (Dart mirror). When this skill changes, both code paths must change in the same commit.

## GATT layout (locked)

| Role | UUID |
| --- | --- |
| Service | `7c3d8b00-9e8a-4f15-b6c3-1d2e3f4a5b6c` |
| Subtitle write (WRITE + WRITE_NR) | `7c3d8b01-9e8a-4f15-b6c3-1d2e3f4a5b6c` |
| ACK / status notify (NOTIFY + READ) | `7c3d8b02-9e8a-4f15-b6c3-1d2e3f4a5b6c` |

Advertised device name: `LingoGlass-S0`.

## Packet layout (7-byte header + payload + 1-byte CRC trailer)

| Offset | Field           | Size    | Notes                                          |
| -----: | --------------- | ------: | ---------------------------------------------- |
|      0 | version         | 1 byte  | `0x01`. Bump on any layout change.             |
|      1 | message_type    | 1 byte  | `0x01` subtitle, `0x02` status, `0x03` ack, `0x04` error |
|      2 | sequence_id     | 2 bytes | **Little-endian**. Monotonic per subtitle, wraps at `0xFFFF`. |
|      4 | fragment_index  | 1 byte  | `0..fragment_count-1`                          |
|      5 | fragment_count  | 1 byte  | Total fragments for this `sequence_id`.        |
|      6 | payload_length  | 1 byte  | Bytes in `payload` (this fragment only).       |
|      7 | payload         | N bytes | UTF-8 text fragment. Never split inside a multi-byte codepoint. |
|   7+N  | crc8            | 1 byte  | CRC-8/CCITT (poly 0x07, init 0x00) over bytes 0..6+N. |

Total fragment size: `8 + payload_length` bytes. Cap `payload_length` so the whole packet fits in the negotiated MTU minus the 3-byte ATT header (op code + handle).

## MTU sizing

Test on three MTU profiles. Pick `payload_length` from the table below.

`max_payload = negotiated_mtu - 3 (ATT) - 8 (our overhead)`

| Negotiated MTU | Usable ATT payload | Max `payload_length` |
| -------------: | -----------------: | -------------------: |
|             23 |                 20 |                   12 |
|            185 |                182 |                  174 |
|            247 |                244 |                  236 |

Always request MTU 247 at connect; **use the negotiated value** (not the request) when computing fragment size. Android phones often return less than 247.

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

Test vector: CRC of bytes `01 01 01 00 00 01 01 41` (version=1, type=subtitle, seq=1, frag 0 of 1, len=1, payload='A') must equal **`0x5B`**. Additional vectors are in `tests/ble_vectors.json`. Verify any new implementation against the full vector set before integrating.

## ACK / error packet (firmware → mobile, on notify char)

Sent over characteristic `7c3d8b02-...`. Format mirrors the subtitle packet:

- `message_type = 0x03` (Ack)
- `sequence_id` = sequence_id of the subtitle being acknowledged
- `fragment_index = 0`, `fragment_count = 1`
- `payload_length = 2`
- `payload[0]` = status code:
  - `0x01` = OK, subtitle rendered on display
  - `0x02` = UNSUPPORTED (e.g., multi-fragment before Phase E ships the assembler)
  - `0x03` = DECODE_ERROR (CRC fail, length mismatch, unknown version)
- `payload[1]` = reserved, must be `0x00`

There is **no separate NAK message type**. Failures are signalled via the status code in the Ack payload. Mobile treats `payload[0] != 0x01` as failure and decides whether to retry.

## Render rules (firmware)

These rules are **mandatory** in the ESP32-S3 receiver:

1. Buffer fragments keyed by `sequence_id`.
2. Render only when **all** fragments of a `sequence_id` have been received and CRC passes on each.
3. If a packet with a higher `sequence_id` arrives before the current one completes, **drop** the incomplete buffer and start the new sequence. Never render partial text.
4. On CRC failure or other decode error, send Ack with `status = 0x03`. Do not render anything.
5. On full subtitle render, send Ack with `status = 0x01`.

## Sender rules (mobile / test harness)

1. Allocate a new `sequence_id` for each subtitle. Wrap at `0xFFFF` -> `0x0000`.
2. Compute `max_payload` from the actually negotiated MTU, not the requested 247.
3. Send fragments in order; do not interleave with another `sequence_id`.
4. Wait for Ack with `status == 0x01` or timeout (default 300 ms) before considering the subtitle delivered.
5. On `status != 0x01` or timeout, retry the whole sequence at most 2 times with the **same** `sequence_id`.
6. After 2 retries, log a `ble_send_fail` diagnostic event and skip — never block the audio pipeline.

## Latency budget contribution

This protocol owns the "Gui ve kinh (BLE)" row in the latency budget (`CLAUDE.md`): target 50-200 ms. Any change that risks pushing this above 200 ms must be flagged.

## What this skill does NOT cover

- Pairing / bonding flow.
- Wi-Fi fallback transport (separate skill when needed).
- OTA firmware update protocol (future work).

## Checklist before declaring BLE work done

- [ ] Encoder and decoder both pass the `0x5B` CRC test vector and all vectors in `tests/ble_vectors.json`.
- [ ] Round-trip test with 100-character Japanese subtitle on MTU 23, 185, 247.
- [ ] Out-of-order sequence test: send seq=2 before seq=1 completes -> seq=1 must be dropped, seq=2 must render.
- [ ] UTF-8 boundary test: subtitle whose byte-cut would land mid-codepoint.
- [ ] Multi-fragment Ack returns `status=0x01` only after **all** fragments are assembled and rendered.
- [ ] Mobile uses negotiated MTU (not requested 247) for fragment sizing.
- [ ] Latency log p50/p90/p95 captured, p95 < 200 ms.
