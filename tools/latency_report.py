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

* **S2 (--s2)**: S2 Day 6/9 translation-accuracy + retry report from the
  same `E2eLatencyRecord` CSV (now with the trailing `accuracy_score`
  column). Reports accuracy `% >= 4` by direction (ja->vi / vi->ja) and
  domain, system latency by direction, and retry rate (redo attempts /
  total, where a redo is a clean re-run or an aborted attempt). Gates:
  accuracy >= 80% both directions AND
  `p95(system_latency_ms) <= 2000 ms` AND retry rate <= 20%. Accuracy
  stays PENDING until the operator fills the score column; latency and
  retry rate are always computed (the Day 9 live gates while accuracy is
  deferred to S3).

* **S3 (--s3)**: S3 Day 6 OCR quality + latency report from the
  `OcrLatencyRecord` CSV produced by the Flutter "Copy OCR latency CSV"
  button. Reports criterion #1 key-line recognition `% pass` (by domain,
  from an operator-appended `recognised_pass` column) and criterion #2
  `p95(ocr_system_latency_ms)` with a recognise/translate/ble leg
  breakdown. Gates: recognition >= 80% AND
  `p95(ocr_system_latency_ms) <= 1500 ms` (provisional). Recognition stays
  PENDING until the operator fills `recognised_pass`; latency is always
  computed.

Usage:
    python tools/latency_report.py path/to/latency.csv         # Phase F
    python tools/latency_report.py - < latency.csv             # stdin
    python tools/latency_report.py --s1 path/to/s1_run.csv     # Day 9
    python tools/latency_report.py --s1 - < s1_run.csv         # stdin
    python tools/latency_report.py --s2 path/to/s2_run.csv     # Day 6
    python tools/latency_report.py --s2 - < s2_run.csv         # stdin

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

# S2 Day 6 — translation accuracy run. The system-latency gate is tightened
# to 2000 ms (from S1's 2500 ms; see S1 GO decision). The accuracy gate is
# manual: operator scores each rendered translation 1-5 by eye and fills the
# `accuracy_score` column afterwards. PASS iff >= 80% of scored rows are >= 4
# in BOTH directions (ja->vi from `ja-*` phrases, vi->ja from `vi-*`).
S2_TARGET_SYSTEM_MS = 2000.0
S2_ACCURACY_MIN_PCT = 80.0
S2_ACCURACY_GOOD = 4  # a translation is "good" if scored >= 4 out of 5
# Criterion #3: retry rate = redo attempts / total attempts. A redo is either
# an aborted attempt (row with a non-empty `error`, e.g. 'discarded' from a
# double-press, or 'ws_error') OR a clean re-run of a phrase that already had a
# clean row (a "duplicate clean row"). After the Day 4 PTT cooldown, redos
# shifted from auto-discards to deliberate clean re-runs, so BOTH forms are
# counted to stay comparable to the S1 baseline (~50%: 9 discards + 1 ws_error
# per 18 attempts). Target: <= 20%. (Definition locked 2026-05-26 against the
# Day 9 trace, which had 0 aborts but 10 clean re-runs.)
S2_RETRY_RATE_MAX_PCT = 20.0

# S3 Day 6 — OCR quality + latency. Latency is anchored at CAPTURE (not a PTT
# release), so `ocr_system_latency_ms == ble_ack_ms` is the gate value directly
# — there is no audio-hold to subtract. The 1500 ms gate is provisional:
# tighter than speech's 2000 ms because there is no audio upload and no STT;
# device-confirm on Galaxy S10 before locking. Recognition is criterion #1 —
# key-line pass/fail scored by eye, gate >= 80% of images pass.
S3_TARGET_OCR_SYSTEM_MS = 1500.0
S3_RECOGNITION_MIN_PCT = 80.0

# OCR latency legs. Stage fields are cumulative from capture (capture = 0), so
# a leg is end - start; the recognise leg measures straight off capture.
S3_LEGS: list[tuple[str, str | None, str]] = [
    ("recognise", None, "recognise_ms"),
    ("translate", "recognise_ms", "translate_ms"),
    ("ble", "translate_ms", "ble_ack_ms"),
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
        sys_lat = _system_latency_ms(row)
        if sys_lat is not None:
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


# ---------------------------------------------------------------------------
# S2 Day 6 — translation accuracy report
# ---------------------------------------------------------------------------
#
# Same E2eLatencyRecord CSV as --s1, plus the trailing `accuracy_score`
# column (added S2 Day 5). The operator runs S2-Run-30 (60 phrases: 30
# ja->vi + 30 vi->ja), scores each rendered translation 1-5 by eye against
# the on-screen "Last final", and fills `accuracy_score` in a spreadsheet
# afterwards (never on device — privacy: no translated text leaves the run).
#
# Direction and domain are derived from the phrase_id prefix, e.g.
# `ja-greet-01` -> direction "ja->vi", domain "greet";
# `vi-emerg-05` -> direction "vi->ja", domain "emerg".
#
# Two row-count signals, both feed the retry-rate gate (criterion #3):
#   * "duplicate clean rows" = the same phrase ran twice and BOTH attempts
#     completed cleanly (no `error`) — a deliberate re-run. The operator scores
#     only one for accuracy, but each extra clean attempt counts as a redo.
#   * "aborted attempts" = rows with a non-empty `error` ('discarded',
#     'ws_error', ...). An aborted row carries no usable latency and is
#     excluded from the latency/accuracy/coverage tallies but still counts as
#     an attempt (and a redo).
# redo attempts = duplicate clean rows + aborted attempts; retry_rate =
# redo / total. The two are disjoint (clean dups live in clean_rows, aborts do
# not), so summing them never double-counts a row.


def _direction(phrase_id: str) -> str:
    if phrase_id.startswith("ja-"):
        return "ja->vi"
    if phrase_id.startswith("vi-"):
        return "vi->ja"
    return "?"


def _domain(phrase_id: str) -> str:
    parts = phrase_id.split("-")
    return parts[1] if len(parts) >= 3 else "?"


def _accuracy_cell(row: dict[str, str]) -> int | None:
    """Parsed 1-5 accuracy score, or None if the operator left it blank."""
    raw = row.get("accuracy_score", "").strip()
    if not raw:
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def _pct_good(scores: list[int]) -> float:
    if not scores:
        return float("nan")
    good = sum(1 for s in scores if s >= S2_ACCURACY_GOOD)
    return 100.0 * good / len(scores)


def render_s2_markdown(rows: list[dict[str, str]]) -> str:
    """Build the S2 Day 6 translation-accuracy report.

    Sections: run summary (coverage + retries), accuracy by direction,
    accuracy by domain x direction, system-latency by direction, verdict
    (accuracy gate per direction AND latency gate), and failures.

    Accuracy is PENDING until the operator fills `accuracy_score`; latency
    is always computed so the run's timing can be reviewed immediately.
    """
    clean_rows = [r for r in rows if not r.get("error", "").strip()]
    failures: dict[str, int] = defaultdict(int)
    for row in rows:
        error = row.get("error", "").strip()
        if error:
            failures[error] += 1

    # Coverage / retries (counted over clean rows only).
    seen: dict[str, int] = defaultdict(int)
    for row in clean_rows:
        seen[row.get("phrase_id", "").strip() or "<missing>"] += 1
    unique_phrases = len(seen)
    retry_phrases = {pid: n for pid, n in seen.items() if n > 1}
    duplicate_rows = sum(n - 1 for n in retry_phrases.values())

    # Retry-rate gate (criterion #3): redo attempts / total attempts, where a
    # redo is a duplicate clean re-run OR an aborted attempt (disjoint sets).
    aborted_rows = sum(failures.values())
    redo_attempts = duplicate_rows + aborted_rows
    retry_rate_pct = (100.0 * redo_attempts / len(rows)) if rows else float("nan")

    scores_by_dir: dict[str, list[int]] = defaultdict(list)
    scores_by_dir_domain: dict[tuple[str, str], list[int]] = defaultdict(list)
    lat_by_dir: dict[str, list[float]] = defaultdict(list)
    for row in clean_rows:
        pid = row.get("phrase_id", "").strip()
        direction = _direction(pid)
        score = _accuracy_cell(row)
        if score is not None:
            scores_by_dir[direction].append(score)
            scores_by_dir_domain[(direction, _domain(pid))].append(score)
        sys_lat = _system_latency_ms(row)
        if sys_lat is not None and sys_lat >= 0:
            lat_by_dir[direction].append(sys_lat)

    directions = ["ja->vi", "vi->ja"]
    total_scored = sum(len(s) for s in scores_by_dir.values())

    lines: list[str] = [
        "# S2 Translation Accuracy + Retry Report",
        "",
        (
            f"Gates: accuracy `>= {S2_ACCURACY_MIN_PCT:.0f}% of scored rows "
            f">= {S2_ACCURACY_GOOD}/5` in BOTH directions, latency "
            f"`p95(system_latency_ms) <= {S2_TARGET_SYSTEM_MS:.0f} ms`, AND "
            f"retry rate `<= {S2_RETRY_RATE_MAX_PCT:.0f}%`."
        ),
        "",
        "`accuracy_score` is filled manually after the run (1-5 by eye). "
        "Translated text is never stored — privacy rule.",
        "",
        "## Run summary",
        "",
        "| metric | value |",
        "|--------|------:|",
        f"| total rows | {len(rows)} |",
        f"| clean rows | {len(clean_rows)} |",
        f"| unique phrases | {unique_phrases} |",
        f"| duplicate clean rows | {duplicate_rows} |",
        f"| aborted attempts | {aborted_rows} |",
        f"| redo attempts | {redo_attempts} |",
        f"| retry rate | {retry_rate_pct:.0f}% |",
        f"| scored rows | {total_scored} |",
    ]

    # Accuracy by direction.
    lines.extend(
        [
            "",
            "## Accuracy by direction",
            "",
            "| direction | n_scored | % >= 4 | mean | gate |",
            "|-----------|---------:|-------:|-----:|------|",
        ]
    )
    accuracy_pass: dict[str, bool | None] = {}
    for direction in directions:
        scores = scores_by_dir.get(direction, [])
        if not scores:
            accuracy_pass[direction] = None
            lines.append(f"| {direction} | 0 | - | - | PENDING |")
            continue
        pct = _pct_good(scores)
        mean = statistics.fmean(scores)
        passed = pct >= S2_ACCURACY_MIN_PCT
        accuracy_pass[direction] = passed
        gate = "PASS" if passed else "FAIL"
        lines.append(
            f"| {direction} | {len(scores)} | {pct:.0f}% | {mean:.2f} | {gate} |"
        )

    # Accuracy by domain x direction (only when something is scored).
    if total_scored:
        lines.extend(
            [
                "",
                "## Accuracy by domain",
                "",
                "| domain | direction | n_scored | % >= 4 |",
                "|--------|-----------|---------:|-------:|",
            ]
        )
        for (direction, domain) in sorted(scores_by_dir_domain.keys()):
            scores = scores_by_dir_domain[(direction, domain)]
            lines.append(
                f"| {domain} | {direction} | {len(scores)} | "
                f"{_pct_good(scores):.0f}% |"
            )

    # System latency by direction + overall.
    lines.extend(
        [
            "",
            "## System latency by direction (ms)",
            "",
            "| direction | n | p50 | p90 | p95 | max |",
            "|-----------|--:|----:|----:|----:|----:|",
        ]
    )
    all_lat: list[float] = []
    for direction in directions:
        values = sorted(lat_by_dir.get(direction, []))
        all_lat.extend(values)
        if values:
            lines.append(
                f"| {direction} | {len(values)} | "
                f"{percentile(values, 0.50):.0f} | "
                f"{percentile(values, 0.90):.0f} | "
                f"{percentile(values, 0.95):.0f} | {values[-1]:.0f} |"
            )
        else:
            lines.append(f"| {direction} | 0 | - | - | - | - |")
    all_lat.sort()
    if all_lat:
        lines.append(
            f"| **overall** | {len(all_lat)} | "
            f"{percentile(all_lat, 0.50):.0f} | "
            f"{percentile(all_lat, 0.90):.0f} | "
            f"{percentile(all_lat, 0.95):.0f} | {all_lat[-1]:.0f} |"
        )

    # Verdict.
    lines.extend(["", "## Verdict", ""])
    if all_lat:
        lat_p95 = percentile(all_lat, 0.95)
        lat_pass = lat_p95 <= S2_TARGET_SYSTEM_MS
        lines.append(
            f"- Latency: p95 {lat_p95:.0f} ms vs {S2_TARGET_SYSTEM_MS:.0f} ms "
            f"-> **{'PASS' if lat_pass else 'FAIL'}**"
        )
    else:
        lat_pass = False
        lines.append("- Latency: **NO DATA**")

    if rows:
        retry_pass = retry_rate_pct <= S2_RETRY_RATE_MAX_PCT
        lines.append(
            f"- Retry rate: {redo_attempts}/{len(rows)} = {retry_rate_pct:.0f}% "
            f"vs <= {S2_RETRY_RATE_MAX_PCT:.0f}% -> "
            f"**{'PASS' if retry_pass else 'FAIL'}**"
        )
    else:
        retry_pass = False
        lines.append("- Retry rate: **NO DATA**")

    # Latency + retry are hard data gates; a failure there is NO-GO even
    # while accuracy is unscored (Day 9 reads these two while #4 is in S3).
    hard_fail = (not lat_pass) or (not retry_pass)
    if total_scored == 0:
        lines.append("- Accuracy: **PENDING** (fill `accuracy_score` and rerun)")
        if hard_fail:
            lines.append("- Result: **NO-GO** (latency/retry gate failed)")
        else:
            lines.append("- Result: **PENDING — accuracy not scored**")
    else:
        acc_pass = all(accuracy_pass.get(d) for d in directions)
        for direction in directions:
            state = accuracy_pass.get(direction)
            label = "PASS" if state else ("PENDING" if state is None else "FAIL")
            lines.append(f"- Accuracy {direction}: **{label}**")
        decision = "GO" if (acc_pass and lat_pass and retry_pass) else "NO-GO"
        lines.append(f"- Result: **{decision}**")

    # Duplicate-phrase + failures detail.
    if retry_phrases:
        lines.extend(
            ["", "## Duplicate clean rows", "", "| phrase | attempts |", "|--------|---------:|"]
        )
        for pid in sorted(retry_phrases):
            lines.append(f"| {pid} | {retry_phrases[pid]} |")

    if failures:
        lines.extend(["", "## Failures", "", "| error | rows |", "|-------|-----:|"])
        for error, count in sorted(failures.items()):
            lines.append(f"| {error} | {count} |")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# S3 Day 6 — OCR quality + latency report
# ---------------------------------------------------------------------------
#
# Input CSV header (OcrLatencyRecord.csvHeader in latency_logger.dart):
#   capture_id,recognise_ms,translate_ms,ble_ack_ms,
#   ocr_system_latency_ms,recognised_chars,ble_seq_id,error
# All *_ms columns are deltas off the CAPTURE instant, so
# ocr_system_latency_ms == ble_ack_ms is the gate value directly.
#
# Two operator annotations are added in a spreadsheet AFTER the run (same
# discipline as --s2 accuracy — nothing extra is stored on device):
#   * `recognised_pass` (appended column) — criterion #1 key-line pass/fail by
#     eye. 1/pass/yes/true/ok -> pass; 0/fail/no/false -> fail; blank ->
#     unscored. The recognised TEXT is never stored; only pass/fail + the char
#     count cross into the bench.
#   * `capture_id` relabelled from the on-device `ocr-NNN` to the curated image
#     id (`sign-01`..`label-05`) so recognition groups by domain. Un-relabelled
#     rows fall into a single `ocr` group and still tally.

_PASS_TRUE = {"1", "pass", "y", "yes", "true", "ok"}
_PASS_FALSE = {"0", "fail", "n", "no", "false"}


def _ocr_domain(capture_id: str) -> str:
    """Domain prefix of a curated image id (`sign-01` -> `sign`). Un-relabelled
    `ocr-NNN` rows return `ocr`; an empty id returns `?`."""
    cid = capture_id.strip()
    if not cid:
        return "?"
    return cid.split("-")[0]


def _ocr_pass_cell(row: dict[str, str]) -> bool | None:
    """Parsed key-line pass/fail, or None if the operator left it blank."""
    raw = row.get("recognised_pass", "").strip().lower()
    if raw in _PASS_TRUE:
        return True
    if raw in _PASS_FALSE:
        return False
    return None


def _pct_pass(flags: list[bool]) -> float:
    if not flags:
        return float("nan")
    return 100.0 * sum(1 for f in flags if f) / len(flags)


def render_s3_markdown(rows: list[dict[str, str]]) -> str:
    """Build the S3 Day 6 OCR quality + latency report.

    Sections: run summary, recognition by domain (criterion #1), OCR system
    latency + recognise/translate/ble leg breakdown (criterion #2), verdict,
    failures. Latency is always computed over completed captures; recognition
    is PENDING until the operator fills `recognised_pass` (mirrors --s2
    accuracy). A capture is "completed" iff `error` is blank AND
    `ocr_system_latency_ms` is present — `ble_unavailable`/`no_text` rows are
    aborts, so they count as attempts but are excluded from the latency tally.
    """
    completed = [
        r
        for r in rows
        if not r.get("error", "").strip()
        and _float_cell(r, "ocr_system_latency_ms") is not None
    ]
    failures: dict[str, int] = defaultdict(int)
    for row in rows:
        error = row.get("error", "").strip()
        if error:
            failures[error] += 1
    aborted_rows = sum(failures.values())

    # Recognition (criterion #1) — scored over any row carrying a pass/fail.
    pass_by_domain: dict[str, list[bool]] = defaultdict(list)
    all_pass: list[bool] = []
    for row in rows:
        flag = _ocr_pass_cell(row)
        if flag is None:
            continue
        pass_by_domain[_ocr_domain(row.get("capture_id", ""))].append(flag)
        all_pass.append(flag)

    # Latency (criterion #2) + per-leg, over completed captures only.
    system_lat: list[float] = []
    leg_values: dict[str, list[float]] = defaultdict(list)
    chars: list[float] = []
    for row in completed:
        sys_lat = _float_cell(row, "ocr_system_latency_ms")
        if sys_lat is not None and sys_lat >= 0:
            system_lat.append(sys_lat)
        for label, start_col, end_col in S3_LEGS:
            end = _float_cell(row, end_col)
            start = 0.0 if start_col is None else _float_cell(row, start_col)
            if end is None or start is None:
                continue
            leg = end - start
            if leg >= 0:
                leg_values[label].append(leg)
        c = _float_cell(row, "recognised_chars")
        if c is not None:
            chars.append(c)
    system_lat.sort()

    lines: list[str] = [
        "# S3 OCR Quality + Latency Report",
        "",
        (
            f"Gates: recognition `>= {S3_RECOGNITION_MIN_PCT:.0f}% key-line "
            f"pass` AND latency `p95(ocr_system_latency_ms) <= "
            f"{S3_TARGET_OCR_SYSTEM_MS:.0f} ms` (provisional)."
        ),
        "",
        "`recognised_pass` is scored by eye after the run (key line, "
        "meaning-preserving). Recognised text is never stored — privacy rule.",
        "",
        "## Run summary",
        "",
        "| metric | value |",
        "|--------|------:|",
        f"| total rows | {len(rows)} |",
        f"| completed captures | {len(completed)} |",
        f"| aborted attempts | {aborted_rows} |",
        f"| recognition-scored rows | {len(all_pass)} |",
    ]

    # Recognition by domain.
    lines.extend(
        [
            "",
            "## Recognition by domain (criterion #1)",
            "",
            "| domain | n_scored | % pass |",
            "|--------|---------:|-------:|",
        ]
    )
    if all_pass:
        for domain in sorted(pass_by_domain):
            flags = pass_by_domain[domain]
            lines.append(f"| {domain} | {len(flags)} | {_pct_pass(flags):.0f}% |")
        lines.append(
            f"| **overall** | {len(all_pass)} | {_pct_pass(all_pass):.0f}% |"
        )
    else:
        lines.append("| - | 0 | - |")

    # OCR system latency.
    lines.extend(
        [
            "",
            "## OCR system latency (criterion #2)",
            "",
            "| n_ok / n_total | p50 | p90 | p95 | p99 | min | max |",
            "|---------------:|----:|----:|----:|----:|----:|----:|",
        ]
    )
    if system_lat:
        lines.append(
            f"| {len(system_lat)} / {len(rows)} | "
            f"{percentile(system_lat, 0.50):.0f} | "
            f"{percentile(system_lat, 0.90):.0f} | "
            f"{percentile(system_lat, 0.95):.0f} | "
            f"{percentile(system_lat, 0.99):.0f} | "
            f"{system_lat[0]:.0f} | {system_lat[-1]:.0f} |"
        )
    else:
        lines.append(f"| 0 / {len(rows)} | - | - | - | - | - | - |")

    # Per-leg breakdown.
    lines.extend(
        [
            "",
            "## Per-leg latency (ms, completed captures)",
            "",
            "| leg | n | p50 | p90 | p95 |",
            "|-----|--:|----:|----:|----:|",
        ]
    )
    for label, _, _ in S3_LEGS:
        values = sorted(leg_values.get(label, []))
        if values:
            lines.append(
                f"| {label} | {len(values)} | "
                f"{percentile(values, 0.50):.0f} | "
                f"{percentile(values, 0.90):.0f} | "
                f"{percentile(values, 0.95):.0f} |"
            )
        else:
            lines.append(f"| {label} | 0 | - | - | - |")

    if chars:
        lines.extend(
            [
                "",
                f"Recognised chars (info): median {statistics.median(chars):.0f}, "
                f"max {max(chars):.0f} over {len(chars)} completed captures.",
            ]
        )

    # Verdict.
    lines.extend(["", "## Verdict", ""])
    if system_lat:
        lat_p95 = percentile(system_lat, 0.95)
        lat_pass = lat_p95 <= S3_TARGET_OCR_SYSTEM_MS
        lines.append(
            f"- Latency: p95 {lat_p95:.0f} ms vs {S3_TARGET_OCR_SYSTEM_MS:.0f} ms "
            f"-> **{'PASS' if lat_pass else 'FAIL'}**"
        )
    else:
        lat_pass = False
        lines.append("- Latency: **NO DATA**")

    if not all_pass:
        lines.append(
            "- Recognition: **PENDING** (fill `recognised_pass` and rerun)"
        )
        if not lat_pass:
            lines.append("- Result: **NO-GO** (latency gate failed)")
        else:
            lines.append("- Result: **PENDING — recognition not scored**")
    else:
        rec_pct = _pct_pass(all_pass)
        rec_pass = rec_pct >= S3_RECOGNITION_MIN_PCT
        lines.append(
            f"- Recognition: {rec_pct:.0f}% vs {S3_RECOGNITION_MIN_PCT:.0f}% "
            f"-> **{'PASS' if rec_pass else 'FAIL'}**"
        )
        decision = "GO" if (rec_pass and lat_pass) else "NO-GO"
        lines.append(f"- Result: **{decision}**")

    if failures:
        lines.extend(
            ["", "## Failures", "", "| error | rows |", "|-------|-----:|"]
        )
        for error, count in sorted(failures.items()):
            lines.append(f"| {error} | {count} |")

    lines.append("")
    return "\n".join(lines)


def _system_latency_ms(row: dict[str, str]) -> float | None:
    """Post-PTT-release latency: ble_ack_ms - audio_ms. None if either cell
    is missing. Negative results are real clock skew / reordering and are
    left for the caller to clamp."""
    audio = _float_cell(row, "audio_ms")
    ble = _float_cell(row, "ble_ack_ms")
    if audio is None or ble is None:
        return None
    return ble - audio


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
    if len(argv) == 3 and argv[1] in ("--s1", "--s2", "--s3"):
        rows = load_rows(argv[2])
        if not rows:
            print("no rows in input CSV", file=sys.stderr)
            return 1
        renderer = {
            "--s1": render_s1_markdown,
            "--s2": render_s2_markdown,
            "--s3": render_s3_markdown,
        }[argv[1]]
        print(renderer(rows))
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
