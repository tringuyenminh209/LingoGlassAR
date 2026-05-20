# LingoGlass AR S0 - Phase F Latency Report

Status: **Run 1 complete** (2026-05-20). Verdict: **CONDITIONAL GO** at the
operating MTU profile, with caveats for low-MTU fallback. Detail below.

## What this measures

The BLE leg only - phone `send_ts` to ACK `ack_ts`, on the phone's
monotonic clock. Does NOT include audio capture, STT, translation, OCR,
or AR display - those are downstream phases (S2-S4).

| Stage | In Phase F scope | Source clock |
|---|---|---|
| Phone subtitle write -> ACK arrival | YES (primary metric, `rtt_ms`) | Phone `microsecondsSinceEpoch` |
| ESP32 fragment-recv -> OLED render done | YES (diagnostic, `fw_proc_ms`) | ESP32 `millis()` |
| Air time on Bluetooth link | inferred = `rtt - fw_proc_ms` | derived |

## Target

Per `CLAUDE.md` latency budget, the "Gui ve kinh (BLE)" row gets 50-200 ms.
Go/No-Go is on **p95 at the operating MTU**:

| Verdict | Criterion |
|---|---|
| **GO** | p95 of OK RTT samples <= 200 ms at the negotiated MTU (typically 247 on Android 10+) |
| **CONDITIONAL GO** | p95 <= 200 ms at MTU 247 but >200 ms at MTU 23/185 fallback - product must enforce MTU >= 185 |
| **NO-GO** | p95 > 200 ms even at MTU 247 |

MTU 23 is the BLE 4.0 ATT minimum and produces ~18 fragments for a 200-byte
subtitle. Per-fragment BLE write timing is dominated by the connection
interval, so multi-fragment payloads at MTU 23 are inherently slow. The
product should refuse to send subtitles below MTU 185 in normal operation
and surface a degraded-mode banner otherwise.

## How to reproduce

Hardware: ESPr Developer S3 + 0.96 inch I2C OLED 128x64. Mobile: Samsung
Galaxy S10 (Android 12), `flutter_blue_plus` 1.32.x.

1. Flash latest firmware: `pio run -e esp32s3 -t upload` from `firmware/esp32s3/`.
2. `flutter run` from `mobile/` on a phone with BT on and granted permissions.
3. Tap **Scan** -> wait for `CONN mtu=247` chip.
4. Tap **Run 20**. Wait ~30 s for completion - log shows `latency run done n=X p50=...`.
5. Tap **Copy CSV** -> paste into a local file, e.g. `out/run_YYYY-MM-DD.csv`.
6. Generate this report:
   ```powershell
   py tools/latency_report.py out/run_YYYY-MM-DD.csv > docs/phase_f_report_runN.md
   ```

## Result - Run 1 (2026-05-20)

Device: Samsung Galaxy S10, MTU negotiated to 247 at connect.
Firmware commit: `3566f44` (Phase F.1 ACK timestamps).
Mobile commit: `a9d1429` (Phase F.2 LatencyLogger).
Source CSV: `out/run_2026-05-20.csv` (20 OK samples, 0 errors).

### Per-MTU RTT (phone clock)

| MTU | n_ok / n_total | p50 ms | p90 ms | p95 ms | min ms | max ms | mean ms | fw_p50 ms | fw_p95 ms |
|----:|---------------:|-------:|-------:|-------:|-------:|-------:|--------:|----------:|----------:|
| 23  | 3 / 3          | 621.7  | 639.7  | 639.7  | 619.9  | 639.7  | 627.1   | 472.0     | 569.0     |
| 185 | 3 / 3          | 201.9  | 240.2  | 240.2  | 126.6  | 240.2  | 189.6   | 79.0      | 129.0     |
| 247 | 14 / 14        | 161.4  | 199.9  | 199.9  | 99.0   | 209.1  | 157.9   | 32.0      | 32.0      |

### Observations

1. **MTU 247 is at the budget ceiling.** p95 = 199.9 ms, literally one
   millisecond under the 200 ms cap. Worst single sample 209 ms. We have
   essentially no headroom for OS jitter or coex with other 2.4 GHz radios.
2. **Firmware processing floor is ~32 ms** at MTU 247 - dominated by the
   U8g2 `sendBuffer()` over I2C (1 KB to push at 400 kHz I2C clock). This
   is constant whether the subtitle is 16 bytes or 208 bytes (single fragment).
3. **MTU 23 is unusable** for any subtitle longer than ~12 bytes. Each of
   18 fragments crosses the BLE link separately and fw_proc reaches
   ~500 ms (because the assembler is sitting waiting between fragments).
   This is a BLE-spec limitation, not a code defect.
4. **MTU 185 is acceptable but tighter.** p95 = 240 ms is 40 ms over budget.
   `fw_proc` jumps to 79-129 ms because the assembler holds the first
   fragment while waiting for the second. Two fragments roundtrip in
   ~110-180 ms before the OLED even renders.
5. **n = 14 at MTU 247 is small.** Stats are not yet stable; a second run
   on a different day / RF environment would tighten the p95 estimate.

### Per-sample budget breakdown (MTU 247 median)

| Component | Time (ms) | Source |
|---|---:|---|
| Phone -> ESP32 fragment delivery | ~129 | rtt - fw_proc - ack_air_back |
| ESP32 assembly + OLED render | 32 | `fw_proc` median |
| ESP32 -> phone ACK delivery | ~0-10 | inferred |
| **Total** | **~161 ms** | rtt p50 |

The phone-to-ESP32 leg dominates. This is the central BLE write/notify
latency over a ~50 ms connection interval typical for Android.

## Decision

**CONDITIONAL GO.** Proceed to S1 (real audio + STT pipeline) with these
guardrails:

- Mobile MUST refuse to send subtitles when the negotiated MTU is below 185.
  Show a "low-MTU mode, subtitles disabled" banner instead. This protects
  the user-facing latency claim and matches what the BLE physical layer
  can actually deliver.
- The MTU 247 result of p95 = 199.9 ms is *at* the budget cap, not under
  it. Treat any S1+ change that touches the BLE path (notify size, GATT
  property tweaks, security upgrade) as latency-affecting and re-run
  Phase F before merge.
- Schedule a Run 2 on a different RF day / location to confirm n=14
  wasn't lucky.

If a future audio-driven pipeline needs to push subtitle updates faster
than once per 200 ms (e.g. progressive STT updates), revisit:

- OLED render strategy - dirty-rect or partial update to drop the 32 ms
  floor toward ~10 ms.
- Connection interval - request a shorter interval at connect (Android
  honours 7.5-15 ms intervals on most chipsets).
- Switch I2C to 1 MHz on the OLED to halve the sendBuffer cost.

## Out of scope

- End-to-end pipeline (S2+): audio capture, STT, translation, display.
- Power / thermal: tracked separately in `LingoGlass_AR_Strategic_Analysis.md`
  risk register and pilot KPI doc.
- iOS-specific MTU behaviour: deferred until S1 (`flutter_blue_plus`
  auto-negotiates on iOS; current dev runs on Android only).
