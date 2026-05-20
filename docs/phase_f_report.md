# LingoGlass AR S0 - Phase F Latency Report

Status: **TEMPLATE** - real numbers will be filled after running the latency
suite on hardware. Last edited: 2026-05-20.

## What this measures

The BLE leg only - phone `send_ts` to ACK `ack_ts`, on the phone's
monotonic clock. Does NOT include audio capture, STT, translation, OCR,
or AR display - those are downstream phases (S2-S4).

| Stage | In Phase F scope | Source clock |
|---|---|---|
| Phone subtitle write -> ACK arrival | YES (primary metric, `rtt_ms`) | Phone `microsecondsSinceEpoch` |
| ESP32 fragment-recv -> OLED render done | YES (diagnostic, `fw_proc_ms`) | ESP32 `millis()` |
| Air time on Bluetooth link | inferred = `rtt - 2 * fw_proc_one_way` (approx) | derived |

## Target

Per `CLAUDE.md` latency budget, the "Gui ve kinh (BLE)" row gets 50-200 ms.
Go/No-Go is on **p95 across all MTUs**:

| Verdict | Criterion |
|---|---|
| **GO** | p95 of OK RTT samples <= 200 ms at every MTU profile |
| **NO-GO** | p95 > 200 ms at any MTU (means BLE leg eats too much of the 2.5 s end-to-end budget) |

## How to reproduce

Hardware: ESPr Developer S3 + 0.96 inch I2C OLED 128x64. Mobile: any
Android device with BLE 4.2+ (current dev: Samsung Galaxy S10).

1. Flash latest firmware: `pio run -e esp32s3 -t upload` from `firmware/esp32s3/`.
2. `flutter run` from `mobile/` on a phone with BT on and granted permissions.
3. Tap **Scan** -> wait for `CONN mtu=247` chip.
4. Tap **Run 20**. Wait ~30 s for completion - log shows `latency run done n=X pXX=...`.
5. Tap **Copy CSV** -> paste into a local file, e.g. `out/run_2026-05-20.csv`.
6. Generate this report:
   ```powershell
   py tools/latency_report.py out/run_2026-05-20.csv > docs/phase_f_report.md
   ```
   (Or paste the markdown table into the result section below by hand.)

## Result

### Run 1 - YYYY-MM-DD, device <model>, firmware <commit>

<!-- Paste the output of latency_report.py here. -->

```
(placeholder - run the suite and replace)
```

### Notes / anomalies

- (e.g. "MTU 23 occasionally negotiates 184 on Galaxy S10 - retried")
- (e.g. "BLE coex with Wi-Fi 2.4 GHz dropped p95 by ~20 ms on second run")

## Decision

**Pending data.** After Run 1 fill the table above, then mark:

- [ ] GO - leg BLE p95 fits 200 ms cap, proceed to S1 (real audio pipeline)
- [ ] NO-GO - investigate; candidates:
  - Increase MTU floor (drop MTU 23 from latency-critical path, accept MTU 23 only as a robustness fallback)
  - Reduce inter-fragment delay on mobile (currently natural BLE pacing)
  - Audit OLED `sendBuffer` - it is ~10-30 ms today; could batch with a dirty-rect strategy
  - Move to BLE write-with-response only for the last fragment to confirm assembler completion

## Out of scope

- End-to-end pipeline (S2+): audio capture, STT, translation, display.
- Power / thermal: tracked separately in `LingoGlass_AR_Strategic_Analysis.md`
  risk register and pilot KPI doc.
- iOS-specific MTU behaviour: deferred until S1 (`flutter_blue_plus`
  auto-negotiates on iOS; current dev runs on Android).
