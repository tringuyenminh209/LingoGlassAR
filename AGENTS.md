# Repository Guidelines

## Project Structure & Module Organization

This repository currently contains planning, strategy, and design documents for the LingoGlass AR project. There is no application source tree yet.

- `docs/LingoGlass_AR_Project_Plan.md`: product scope, MVP plan, roadmap, BOM, cloud cost, and execution strategy.
- `docs/LingoGlass_AR_Strategic_Analysis.md`: market, technical risks, architecture, privacy, compliance, and validation strategy.
- `docs/LingoGlass_AR_Development_Plan.md`: V-model development process, solo-founder workflow, spike plan, testing matrix, and traceability.
- `docs/LingoGlass_AR_Display_Decision_Record.md`: approved S0 hardware baseline and display decision.
- `docs/docs-html/`: Japanese design documents. Treat the HTML files as the editable source of the design package.
- `docs/docs-pdf/`: rendered PDF copies. Do not manually edit PDFs; regenerate them from HTML when needed.
- `docs/api-contract/`: executable REST and WebSocket contract artifacts.
- `tests/cases/test_cases_master.csv`: master list of 63 planned test cases.
- `.claude/`: local assistant/tooling metadata. Do not edit unless explicitly required.

When code is added, prefer clear top-level folders such as `firmware/esp32s3/`, `apps/mobile/`, `services/api/`, `packages/ble-protocol/`, `packages/shared-types/`, `tests/`, and `assets/`.

## S0 Hardware Baseline

Use the hardware already selected in `docs/LingoGlass_AR_Display_Decision_Record.md` for the first development spike. Do not switch back to ESP32-S3 DevKitC-1, Waveshare 0.49 inch OLED, Freenove CAM, or other boards unless the user explicitly changes the hardware baseline.

Current S0 hardware:

- Controller: ESPr Developer S3 Type-C, ESP32-S3-WROOM-1.
- Flash: 16 MB.
- PSRAM: 8 MB.
- Display: 0.96 inch IIC/I2C white OLED, 128x64, Arduino-compatible.
- Wiring: solderless breadboard plus jumper wire kit.
- USB: USB-C data cable.
- I2C pins: `SDA = GPIO 8`, `SCL = GPIO 9`.
- Expected OLED I2C address: scan first; likely `0x3C` or `0x3D`.

S0 development order:

1. I2C scanner.
2. Static OLED text render.
3. BLE GATT receiver.
4. BLE subtitle packet parser, CRC8, fragmentation, ACK with status code (0x01/0x02/0x03).
5. 20 consecutive subtitle display test with app-to-display latency under 200 ms.

## Build, Test, and Development Commands

There are currently no build or test commands because the repository is documentation-only.

Useful validation commands:

```powershell
rg --files
Select-String -Path docs\*.md,AGENTS.md -Pattern '[^\x00-\x7F]'
rg -n "Rev 0\.1|86|tests/cases/\*|ESP32-S3-DevKitC-1|Waveshare 0\.49|Freenove" docs\docs-html docs\LingoGlass_AR_Display_Decision_Record.md tests
(Import-Csv tests\cases\test_cases_master.csv).Count
```

Use the first command to list project files, the second to detect non-ASCII in ASCII-only Markdown guidance files, the third to catch stale design references, and the fourth to verify the master test list remains 63 cases.

## Coding Style & Naming Conventions

For Markdown, use concise headings, short paragraphs, and tables for requirements, risks, and decision criteria. Keep filenames descriptive and stable, using the existing `LingoGlass_AR_*.md` pattern for major documents.

This repo intentionally uses ASCII-only Vietnamese text without diacritics in Vietnamese Markdown planning files to avoid the mojibake/encoding problems seen in earlier files. Japanese HTML design files intentionally contain Japanese text and must remain UTF-8.

## Testing Guidelines

For document changes, verify:

- Links and section references are still correct.
- Requirements have measurable acceptance criteria.
- Roadmaps remain realistic for a solo founder with AI agent support.
- No non-ASCII encoding artifacts are introduced.
- S0 hardware references stay aligned with the ESPr Developer S3 + 0.96 inch I2C OLED baseline.
- The test case count remains consistent between the test specification HTML and `tests/cases/test_cases_master.csv`.

When code is added, include test instructions in this file and keep test names tied to requirement IDs where possible, for example `FR-01_display_subtitle`.

## Commit & Pull Request Guidelines

This directory is not currently a Git repository, so no commit history conventions exist yet. If Git is initialized, use short imperative commit messages, for example:

- `Add BLE spike plan`
- `Update cloud cost model`
- `Clarify display module checklist`

Pull requests should include a brief summary, affected documents, key decision changes, and any validation performed.

## Agent-Specific Instructions

Keep edits scoped and evidence-driven. Do not expand the product scope without updating risks, cost, and test criteria. For planning changes, update all affected documents so project plan, strategic analysis, and development plan remain consistent.
