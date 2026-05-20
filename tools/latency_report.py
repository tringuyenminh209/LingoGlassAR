#!/usr/bin/env python3
"""Phase F latency report generator.

Reads a CSV emitted by the mobile spike harness (Copy CSV button in the
Flutter app) and prints a markdown summary with per-MTU p50/p90/p95 plus
the Go/No-Go verdict against the 50-200ms BLE leg budget.

Usage:
    python tools/latency_report.py path/to/latency.csv
    python tools/latency_report.py - < latency.csv  # stdin

Output is markdown on stdout - paste into docs/phase_f_report.md or pipe to
a file. No external dependencies; standard library only.
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


def main(argv: list[str]) -> int:
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
