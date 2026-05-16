# LingoGlass AR Display Decision Record

DOC-ID: DDR-LGA-001
Rev: 1.0
Date: 2026-05-13
Status: Approved for S0 spike

## Decision

For S0, use the hardware already available in the lab to prove the text pipeline:

- Controller: ESPr Developer S3 Type C WROOM-1.
- Flash: 16 MB.
- PSRAM: 8 MB.
- Display: 0.96 inch IIC/I2C white OLED module, 128x64, Arduino-compatible.
- Wiring: solderless breadboard + jumper wire kit.
- USB: USB-C data cable.
- Scope: BLE packet receive, fragment assembly, 1-2 line text rendering, latency logging.
- Not validated in S0: AR optics, eyebox, outdoor readability, wearable mechanical fit.

For S4, evaluate an AR dev kit or waveguide module separately:

- Preferred AR validation path: Brilliant Monocle or Vuzix Blade/Z100 if available.
- Fallback: phone-mounted wearable mock for text readability and user-flow testing.

## Rationale

The project must answer the smallest blocking question first:

Phone -> BLE -> ESP32-S3 -> display text.

Using the available ESPr Developer S3 board and 0.96 inch I2C OLED keeps S0 independent from optical module shipping, SDK licensing, and custom hardware lead time. AR readability remains a separate S4 gate.

## S0 Module Checklist

| Item | S0 requirement |
| --- | --- |
| Interface | I2C for current 0.96 inch OLED |
| Driver/sample | Arduino or ESP-IDF compatible sample required |
| Text | 1-2 subtitle lines, fixed font, no layout jump |
| Latency | App-to-display target under 200 ms |
| Availability | Already available |
| Cost | Low enough to replace if damaged |

## Pinout To Confirm Before Coding

| Signal | Required decision |
| --- | --- |
| VCC | Prefer 3.3 V if OLED supports it; otherwise use module-rated VCC |
| GND | Common ground |
| SCL | GPIO 9 |
| SDA | GPIO 8 |
| I2C address | Usually 0x3C, confirm by I2C scan before display test |

## Fallbacks

| Failure | Action |
| --- | --- |
| OLED sample driver fails | Switch to another SSD1306/SH1106 module with known sample code |
| BLE latency exceeds 200 ms | Test MTU 185/247, reduce payload length, then test Wi-Fi fallback |
| Text too small | Keep OLED for pipeline only, move readability to S4 AR/dev-kit test |
| AR dev kit unavailable | Continue S1-S3 with OLED and schedule S4 readability after shipping clears |

## Decision Gates

| Gate | Pass condition |
| --- | --- |
| S0 | 20 consecutive subtitles displayed, average app-to-display under 200 ms |
| S4 | At least 80% of testers can read subtitle text in target lighting |
