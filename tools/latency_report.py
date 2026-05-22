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

# S1 Day 9 end-to-end budget. Gate is p95(system_latency_ms) where
# system_latency_ms = ble_ack_ms - audio_ms — post-PTT-release latency
# only, excludes user hold duration. The CLAUDE.md "Latency Budget"
# 1.5-2.5s target is for system latency, not press-to-glass total.
S1_TARGET_TOTAL_MS = 2500.0

# Per-stage decomposition AFTER PTT release. Backend handshake runs
# CONCURRENT with PTT hold (session.opened arrives ~1s after press while
# user is still holding), so it is reported separately as an info-only
# column, not stacked on top of stt/translate/ble.
S1_STAGES: list[tuple[str, str, str]] = [
    ("stt",       "audio_ms",       "first_text_ms"),
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
# S1 Day 9 — end-to-end report
# ---------------------------------------------------------------------------
#
# Input CSV header (matches E2eLatencyRecord.csvHeader in
# mobile/lib/services/latency_logger.dart):
#
#   phrase_id,audio_ms,backend_ack_ms,first_text_ms,full_text_ms,
#   ble_ack_ms,total_ms,session_id,ble_seq_id,error
#
# All *_ms columns are deltas from PTT press_ts (NOT from PTT release).
# Important: backend WS session.opened arrives ~1s after press while the
# user is still holding PTT (audio_ms is typically 3-5s). So
# `backend_ack_ms < audio_ms` is the normal warm-WS case, NOT clock skew.
#
# The latency budget gate (CLAUDE.md "Latency Budget" 1.5-2.5s) applies
# to *system* latency: the duration from PTT RELEASE to BLE ACK, i.e.
#   system_latency_ms = ble_ack_ms - audio_ms
# Decomposed into stt / translate / ble post-release stages. Handshake
# and hold are reported separately as info-only columns.


def render_s1_markdown(rows: list[dict[str, str]]) -> str:
    """Build the S1 Day 9 markdown report.

    Output sections:
      1. Per-phrase median table (stt/translate/ble + system_lat + info).
      2. Overall system_latency_ms percentiles.
      3. Per-stage percentiles (post-release stages only).
      4. Verdict: GO iff p95(system_latency_ms) <= 2500ms.
      5. Failures table from the `error` column.
      6. Clock-skew footer if any post-release stage delta < 0 (real skew
         or out-of-order frames — backend issue, not the audio/handshake
         ordering quirk).
    """
    clean_rows = [row for row in rows if not row.get("error", "").strip()]
    failures: dict[str, int] = defaultdict(int)
    for row in rows:
        error = row.get("error", "").strip()
        if error:
            failures[error] += 1

    phrase_stages: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    phrase_system_lat: dict[str, list[float]] = defaultdict(list)
    phrase_handshake: dict[str, list[float]] = defaultdict(list)
    phrase_hold: dict[str, list[float]] = defaultdict(list)

    stage_values: dict[str, list[float]] = defaultdict(list)
    system_lat_values: list[float] = []
    handshake_values: list[float] = []
    hold_values: list[float] = []
    skew_rows = 0

    for row in clean_rows:
        phrase_id = row.get("phrase_id", "").strip() or "<missing>"
        row_had_skew = False

        for label, start_column, end_column in S1_STAGES:
            start = _float_cell(row, start_column)
            end = _float_cell(row, end_column)
            if start is None or end is None:
                continue
            stage_ms = end - start
            if stage_ms < 0:
                row_had_skew = True
                stage_ms = 0.0
            phrase_stages[phrase_id][label].append(stage_ms)
            stage_values[label].append(stage_ms)

        audio = _float_cell(row, "audio_ms")
        ble = _float_cell(row, "ble_ack_ms")
        if audio is not None and ble is not None:
            sys_lat = ble - audio
            if sys_lat < 0:
                row_had_skew = True
                sys_lat = 0.0
            phrase_system_lat[phrase_id].append(sys_lat)
            system_lat_values.append(sys_lat)

        handshake = _float_cell(row, "backend_ack_ms")
        if handshake is not None:
            phrase_handshake[phrase_id].append(handshake)
            handshake_values.append(handshake)
        if audio is not None:
            phrase_hold[phrase_id].append(audio)
            hold_values.append(audio)

        if row_had_skew:
            skew_rows += 1

    system_lat_values.sort()
    lines: list[str] = [
        "# S1 Day 9 End-to-End Latency Report",
        "",
        (
            f"Target: `p95(system_latency_ms) <= {S1_TARGET_TOTAL_MS:.0f} ms` "
            "per docs/CLAUDE.md latency budget."
        ),
        "",
        "`system_latency_ms = ble_ack_ms - audio_ms` — post-PTT-release "
        "duration. `hold_ms` and `handshake_ms` are concurrent with PTT "
        "press and reported info-only.",
        "",
        "## Per-phrase median (ms)",
        "",
        "| phrase | stt | translate | ble | system_lat | hold | handshake |",
        "|--------|----:|----------:|----:|-----------:|-----:|----------:|",
    ]
    all_phrase_ids = (
        set(phrase_stages)
        | set(phrase_system_lat)
        | set(phrase_handshake)
        | set(phrase_hold)
    )
    for phrase_id in sorted(all_phrase_ids):
        stage_cells = [
            _s1_median_cell(phrase_stages[phrase_id].get(label, []))
            for label, _, _ in S1_STAGES
        ]
        sys_cell = _s1_median_cell(phrase_system_lat.get(phrase_id, []))
        hold_cell = _s1_median_cell(phrase_hold.get(phrase_id, []))
        hs_cell = _s1_median_cell(phrase_handshake.get(phrase_id, []))
        lines.append(
            f"| {phrase_id} | {' | '.join(stage_cells)} | "
            f"{sys_cell} | {hold_cell} | {hs_cell} |"
        )

    median_cells = [
        _s1_median_cell(stage_values.get(label, [])) for label, _, _ in S1_STAGES
    ]
    lines.append(
        f"| **median** | {' | '.join(median_cells)} | "
        f"{_s1_median_cell(system_lat_values)} | "
        f"{_s1_median_cell(hold_values)} | "
        f"{_s1_median_cell(handshake_values)} |"
    )
    lines.extend(
        [
            "",
            "## Overall system_latency_ms",
            "",
            "| n_ok / n_total | p50 | p90 | p95 | p99 | min | max |",
            "|---------------:|----:|----:|----:|----:|----:|----:|",
        ]
    )
    if system_lat_values:
        lines.append(
            f"| {len(system_lat_values)} / {len(rows)} | "
            f"{percentile(system_lat_values, 0.50):.0f} | "
            f"{percentile(system_lat_values, 0.90):.0f} | "
            f"{percentile(system_lat_values, 0.95):.0f} | "
            f"{percentile(system_lat_values, 0.99):.0f} | "
            f"{system_lat_values[0]:.0f} | {system_lat_values[-1]:.0f} |"
        )
    else:
        lines.append(f"| 0 / {len(rows)} | - | - | - | - | - | - |")

    lines.extend(
        [
            "",
            "## Per-stage percentiles (post-release)",
            "",
            "| stage | n | p50 | p90 | p95 |",
            "|-------|--:|----:|----:|----:|",
        ]
    )
    for label, _, _ in S1_STAGES:
        values = sorted(stage_values.get(label, []))
        if values:
            lines.append(
                f"| {label} | {len(values)} | "
                f"{percentile(values, 0.50):.0f} | "
                f"{percentile(values, 0.90):.0f} | "
                f"{percentile(values, 0.95):.0f} |"
            )
        else:
            lines.append(f"| {label} | 0 | - | - | - |")

    lines.extend(["", "## Verdict", ""])
    if not system_lat_values:
        lines.append(
            f"- p95(system_latency_ms) = - vs target "
            f"{S1_TARGET_TOTAL_MS:.0f} ms"
        )
        lines.append("- **NO DATA**")
    else:
        p95_sys = percentile(system_lat_values, 0.95)
        decision = "GO" if p95_sys <= S1_TARGET_TOTAL_MS else "NO-GO"
        lines.append(
            f"- p95(system_latency_ms) = {p95_sys:.0f} ms vs target "
            f"{S1_TARGET_TOTAL_MS:.0f} ms"
        )
        lines.append(f"- **{decision}**")
        if decision == "NO-GO":
            stage_medians = {
                label: statistics.median(values)
                for label, values in stage_values.items()
                if values
            }
            if stage_medians:
                biggest = max(stage_medians, key=stage_medians.get)
                lines.append(f"- Biggest median contributor: **{biggest}**")

    if failures:
        lines.extend(["", "## Failures", "", "| error | rows |", "|-------|-----:|"])
        for error, count in sorted(failures.items()):
            lines.append(f"| {error} | {count} |")

    if skew_rows:
        lines.extend(
            ["", f"Clock skew: {skew_rows} rows had negative post-release stage deltas."]
        )
    lines.append("")
    return "\n".join(lines)


def _float_cell(row: dict[str, str], column: str) -> float | None:
    value = row.get(column, "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _s1_median_cell(values: Iterable[float]) -> str:
    values = list(values)
    return f"{statistics.median(values):.0f}" if values else "-"


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
