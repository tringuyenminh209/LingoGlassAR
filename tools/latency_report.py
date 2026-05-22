#!/usr/bin/env python3
"""Latency report generator.

Two modes, selected by the input CSV's column shape (or by the explicit
`--s1` flag for the S1 Day 9 e2e report):

* **Phase F (default)**: per-MTU BLE-leg RTT p50/p90/p95 from the
  `LatencyRecord` CSV produced by the Flutter "Copy CSV" button.
  Target: BLE leg `p95 <= 200 ms`.

* **S1 (--s1)**: per-stage end-to-end timeline from the
  `E2eLatencyRecord` CSV produced by the Flutter "S1-Run-10" button
  (Codex adds the button on Day 9). Stages are decomposed into audio,
  handshake, STT, translation, and BLE legs, then rendered as a
  stacked-bar markdown table with overall p50/p90/p95/p99 of
  `total_ms`. Target: `p95(total_ms) <= 2500 ms`.

Usage:
    python tools/latency_report.py path/to/latency.csv         # Phase F
    python tools/latency_report.py - < latency.csv             # stdin
    python tools/latency_report.py --s1 path/to/s1_run.csv     # Day 9
    python tools/latency_report.py --s1 - < s1_run.csv         # stdin

Output is markdown on stdout - paste into the matching report doc or
pipe to a file. No external dependencies; standard library only.
"""

from __future__ import annotations

import csv
import statistics
import sys
from collections import defaultdict
from typing import Iterable


# BLE leg of the LingoGlass AR latency budget. See CLAUDE.md "Latency Budget".
TARGET_MIN_MS = 50.0
TARGET_MAX_MS = 200.0

# S1 Day 9 end-to-end budget. p95(total_ms) <= 2500 ms is the Go gate.
S1_TARGET_TOTAL_MS = 2500.0

# Per-stage decomposition for the S1 stacked-bar report. Each entry is
# (stage_label, csv_start_column, csv_end_column). Subtracting end-start
# yields the stage duration; the audio stage is special-cased because its
# start column is implicitly t=0 (PTT press).
S1_STAGES: list[tuple[str, str | None, str]] = [
    ("audio",     None,             "audio_ms"),
    ("handshake", "audio_ms",       "backend_ack_ms"),
    ("stt",       "backend_ack_ms", "first_text_ms"),
    ("translate", "first_text_ms",  "full_text_ms"),
    ("ble",       "full_text_ms",   "ble_ack_ms"),
]


def percentile(sorted_values: list[float], p: float) -> float:
    """Linear-interpolation percentile; matches the LatencyLogger.summarise
    formula closely enough for human-readable summaries."""
    if not sorted_values:
        return float("nan")
    idx = round((len(sorted_values) - 1) * p)
    return sorted_values[idx]


def load_rows(path: str) -> list[dict[str, str]]:
    if path == "-":
        reader = csv.DictReader(sys.stdin)
        return list(reader)
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def group_by_mtu(rows: Iterable[dict[str, str]]) -> dict[int, list[dict[str, str]]]:
    groups: dict[int, list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        try:
            mtu = int(r["mtu"])
        except (KeyError, ValueError):
            continue
        groups[mtu].append(r)
    return groups


def summarise_group(rows: list[dict[str, str]]) -> dict[str, float | int]:
    ok_rtts = sorted(float(r["rtt_ms"]) for r in rows if r.get("status") == "0x01")
    fw_proc = sorted(
        int(r["fw_proc_ms"]) for r in rows
        if r.get("status") == "0x01" and r.get("fw_proc_ms")
    )
    total = len(rows)
    ok = len(ok_rtts)
    if ok == 0:
        return {"total": total, "ok": 0}
    return {
        "total": total,
        "ok": ok,
        "p50": percentile(ok_rtts, 0.50),
        "p90": percentile(ok_rtts, 0.90),
        "p95": percentile(ok_rtts, 0.95),
        "min": ok_rtts[0],
        "max": ok_rtts[-1],
        "mean": statistics.fmean(ok_rtts),
        "fw_p50": percentile(fw_proc, 0.50) if fw_proc else float("nan"),
        "fw_p95": percentile(fw_proc, 0.95) if fw_proc else float("nan"),
    }


def verdict(p95: float) -> str:
    if p95 != p95:  # NaN
        return "NO DATA"
    if p95 <= TARGET_MAX_MS:
        return f"GO (p95 {p95:.1f} ms <= {TARGET_MAX_MS:.0f} ms target)"
    return f"NO-GO (p95 {p95:.1f} ms > {TARGET_MAX_MS:.0f} ms target)"


def render_markdown(groups: dict[int, list[dict[str, str]]]) -> str:
    lines: list[str] = []
    lines.append("# Phase F Latency Report")
    lines.append("")
    lines.append(
        f"Target: BLE leg `p95 <= {TARGET_MAX_MS:.0f} ms` "
        f"(budget range {TARGET_MIN_MS:.0f}-{TARGET_MAX_MS:.0f} ms per CLAUDE.md)."
    )
    lines.append("")
    lines.append("## Per-MTU RTT (phone clock)")
    lines.append("")
    lines.append("| MTU | n_ok / n_total | p50 ms | p90 ms | p95 ms | min ms | max ms | mean ms | fw_p50 ms | fw_p95 ms |")
    lines.append("|----:|---------------:|-------:|-------:|-------:|-------:|-------:|--------:|----------:|----------:|")

    all_p95: list[float] = []
    for mtu in sorted(groups.keys()):
        s = summarise_group(groups[mtu])
        if s["ok"] == 0:
            lines.append(f"| {mtu} | 0 / {s['total']} | - | - | - | - | - | - | - | - |")
            continue
        all_p95.append(s["p95"])
        lines.append(
            f"| {mtu} | {s['ok']} / {s['total']} | "
            f"{s['p50']:.1f} | {s['p90']:.1f} | {s['p95']:.1f} | "
            f"{s['min']:.1f} | {s['max']:.1f} | {s['mean']:.1f} | "
            f"{s['fw_p50']:.1f} | {s['fw_p95']:.1f} |"
        )

    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    if all_p95:
        worst = max(all_p95)
        lines.append(f"- Worst p95 across MTUs: **{worst:.1f} ms**")
        lines.append(f"- Result: **{verdict(worst)}**")
    else:
        lines.append("- **NO DATA**: no OK samples in any MTU group.")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# S1 Day 9 — end-to-end stacked-bar report (Codex implements)
# ---------------------------------------------------------------------------
#
# Input CSV header (matches E2eLatencyRecord.csvHeader in
# mobile/lib/services/latency_logger.dart):
#
#   phrase_id,audio_ms,backend_ack_ms,first_text_ms,full_text_ms,
#   ble_ack_ms,total_ms,session_id,ble_seq_id,error
#
# Required output:
#
#   # S1 Day 9 End-to-End Latency Report
#
#   Target: e2e `p95(total_ms) <= 2500 ms` per docs/CLAUDE.md.
#
#   ## Stacked-bar by stage (median ms)
#
#   | phrase | audio | handshake | stt | translate | ble | total |
#   |--------|-------|-----------|-----|-----------|-----|-------|
#   | greeting-01 | ... |
#   ...
#   | **median** | ... | ... | ... | ... | ... | ... |
#
#   ## Overall total_ms
#
#   | n_ok / n_total | p50 | p90 | p95 | p99 | min | max |
#
#   ## Per-stage percentiles
#
#   (one row per stage with p50/p90/p95)
#
#   ## Verdict
#
#   - p95(total_ms) = X ms vs target 2500 ms
#   - **GO** / **NO-GO**
#   - If NO-GO: which stage is the biggest contributor (highest median).
#
# Errors: rows with non-empty `error` column are reported in a "Failures"
# section by error code count, and excluded from percentile math.
#
# Codex fills the body of render_s1_markdown and the --s1 dispatch in main.


def render_s1_markdown(rows: list[dict[str, str]]) -> str:
    """Build the S1 Day 9 stacked-bar markdown.  See block comment above
    for the required output structure and the verdict gate.

    Implementation hints:
    - Use percentile() and a per-stage list comprehension on `rows`.
    - Skip rows where any required column for a given stage is missing
      (empty string) and count them under "Failures" instead.
    - Clamp negative stage durations to 0 in display, but flag them in
      a "Clock skew" footer if any appear (server-clock drift symptom).
    """
    raise NotImplementedError("S1 Day 9 — Codex implements render_s1_markdown")


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == "--s1":
        rows = load_rows(argv[2])
        if not rows:
            print("no rows in input CSV", file=sys.stderr)
            return 1
        print(render_s1_markdown(rows))
        return 0
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    rows = load_rows(argv[1])
    if not rows:
        print("no rows in input CSV", file=sys.stderr)
        return 1
    groups = group_by_mtu(rows)
    print(render_markdown(groups))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
