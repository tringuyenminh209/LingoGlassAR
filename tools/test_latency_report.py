from tools.latency_report import (
    render_s1_markdown,
    render_s2_markdown,
    render_s3_markdown,
)


def _row(
    phrase_id: str,
    *,
    audio: str,
    backend: str,
    first: str,
    final: str,
    ble: str,
    total: str,
    error: str = "",
    accuracy: str = "",
) -> dict[str, str]:
    return {
        "phrase_id": phrase_id,
        "audio_ms": audio,
        "backend_ack_ms": backend,
        "first_text_ms": first,
        "full_text_ms": final,
        "ble_ack_ms": ble,
        "total_ms": total,
        "session_id": "",
        "ble_seq_id": "",
        "error": error,
        "accuracy_score": accuracy,
    }


def _s2_row(
    phrase_id: str, *, audio: str, ble: str, accuracy: str = "", error: str = ""
) -> dict[str, str]:
    # Latency-relevant cells only; intermediate stages are not exercised by
    # the S2 report (it consumes system_latency = ble - audio + accuracy).
    # An `error` makes the row an aborted attempt (feeds the retry-rate gate).
    return _row(
        phrase_id,
        audio=audio,
        backend="0",
        first="0",
        final="0",
        ble=ble,
        total=ble,
        accuracy=accuracy,
        error=error,
    )


def test_s1_render_happy_path() -> None:
    # system_lat = ble - audio: 890, 980, 1140 → p95 idx round(2*0.95)=2 → 1140
    report = render_s1_markdown(
        [
            _row("a", audio="100", backend="180", first="700", final="900", ble="990", total="990"),
            _row("b", audio="120", backend="210", first="760", final="980", ble="1100", total="1100"),
            _row("c", audio="110", backend="200", first="800", final="1050", ble="1250", total="1250"),
        ]
    )

    assert "- **GO**" in report
    assert "p95(system_latency_ms) = 1140 ms" in report


def test_s1_render_real_world_handshake_during_hold() -> None:
    # Real-flow shape: backend_ack (~1s) arrives during PTT hold (~4-5s).
    # The old contract treated backend_ack - audio_ms as a stage and would
    # have flagged this as clock skew. The new contract treats handshake
    # as concurrent (info-only) and does not fire the skew footer.
    report = render_s1_markdown(
        [
            _row(
                "greeting-01",
                audio="4778",
                backend="1132",
                first="6038",
                final="6176",
                ble="6271",
                total="6271",
            )
        ]
    )

    assert "- **GO**" in report
    assert "Clock skew" not in report
    # system_lat = 6271 - 4778 = 1493
    assert "p95(system_latency_ms) = 1493 ms" in report


def test_s1_render_failure_section() -> None:
    report = render_s1_markdown(
        [
            _row("ok", audio="100", backend="180", first="700", final="900", ble="990", total="990"),
            _row(
                "bad",
                audio="100",
                backend="",
                first="",
                final="",
                ble="",
                total="",
                error="ws_error",
            ),
        ]
    )

    assert "## Failures" in report
    assert "| ws_error | 1 |" in report
    assert "| 1 / 2 |" in report


def test_s1_render_clock_skew_footer() -> None:
    # final_text arrives BEFORE first_text → translate stage negative.
    # This is real out-of-order (server bug or network reorder), unlike
    # the legitimate handshake-during-hold case above.
    report = render_s1_markdown(
        [
            _row(
                "skew",
                audio="100",
                backend="150",
                first="800",
                final="700",
                ble="900",
                total="900",
            )
        ]
    )

    assert "Clock skew: 1 rows had negative post-release stage deltas." in report


def test_s2_pending_when_unscored() -> None:
    # No accuracy_score filled yet: latency is reported, accuracy is PENDING.
    report = render_s2_markdown(
        [
            _s2_row("ja-greet-01", audio="3000", ble="4200"),
            _s2_row("vi-greet-01", audio="3000", ble="4100"),
        ]
    )
    assert "Result: **PENDING — accuracy not scored**" in report
    assert "Latency: p95" in report and "**PASS**" in report


def test_s2_go_when_both_directions_pass() -> None:
    # 4/5 good in each direction -> 80% -> meets the 80% gate; latency low.
    rows = []
    for i in range(5):
        rows.append(
            _s2_row("ja-greet-0%d" % i, audio="3000", ble="4000",
                    accuracy="5" if i < 4 else "2")
        )
        rows.append(
            _s2_row("vi-greet-0%d" % i, audio="3000", ble="4000",
                    accuracy="4" if i < 4 else "1")
        )
    report = render_s2_markdown(rows)
    assert "| ja->vi | 5 | 80% |" in report
    assert "| vi->ja | 5 | 80% |" in report
    assert "Result: **GO**" in report


def test_s2_no_go_when_one_direction_below_gate() -> None:
    # ja->vi all good, vi->ja only 2/5 good (40%) -> overall NO-GO.
    rows = [
        _s2_row("ja-greet-01", audio="3000", ble="4000", accuracy="5"),
        _s2_row("ja-greet-02", audio="3000", ble="4000", accuracy="4"),
        _s2_row("vi-greet-01", audio="3000", ble="4000", accuracy="5"),
        _s2_row("vi-greet-02", audio="3000", ble="4000", accuracy="4"),
        _s2_row("vi-greet-03", audio="3000", ble="4000", accuracy="2"),
        _s2_row("vi-greet-04", audio="3000", ble="4000", accuracy="1"),
        _s2_row("vi-greet-05", audio="3000", ble="4000", accuracy="3"),
    ]
    report = render_s2_markdown(rows)
    assert "Accuracy ja->vi: **PASS**" in report
    assert "Accuracy vi->ja: **FAIL**" in report
    assert "Result: **NO-GO**" in report


def test_s2_latency_fail_blocks_go() -> None:
    # Accuracy perfect both directions, but latency p95 > 2000ms -> NO-GO.
    rows = [
        _s2_row("ja-greet-01", audio="3000", ble="6000", accuracy="5"),
        _s2_row("vi-greet-01", audio="3000", ble="6000", accuracy="5"),
    ]
    report = render_s2_markdown(rows)
    assert "Latency: p95 3000 ms vs 2000 ms -> **FAIL**" in report
    assert "Result: **NO-GO**" in report


def test_s2_duplicate_clean_rows_count_as_retries() -> None:
    # A clean re-run is a redo: 1 duplicate / 3 attempts = 33% -> FAIL.
    rows = [
        _s2_row("ja-greet-01", audio="3000", ble="4000"),
        _s2_row("ja-greet-01", audio="3100", ble="4100"),
        _s2_row("vi-greet-01", audio="3000", ble="4000"),
    ]
    report = render_s2_markdown(rows)
    assert "| duplicate clean rows | 1 |" in report
    assert "| unique phrases | 2 |" in report
    assert "| ja-greet-01 | 2 |" in report
    assert "Retry rate: 1/3 = 33% vs <= 20% -> **FAIL**" in report


def test_s2_retry_rate_mixes_dups_and_aborts() -> None:
    # 1 clean re-run + 1 abort = 2 redos / 5 attempts = 40% -> FAIL.
    rows = [
        _s2_row("ja-greet-01", audio="3000", ble="4000"),
        _s2_row("ja-greet-01", audio="3100", ble="4100"),
        _s2_row("vi-greet-01", audio="3000", ble="4000"),
        _s2_row("vi-greet-02", audio="3000", ble="4000"),
        _s2_row("ja-greet-02", audio="3000", ble="", error="discarded"),
    ]
    report = render_s2_markdown(rows)
    assert "| duplicate clean rows | 1 |" in report
    assert "| aborted attempts | 1 |" in report
    assert "| redo attempts | 2 |" in report
    assert "Retry rate: 2/5 = 40% vs <= 20% -> **FAIL**" in report


def test_s2_retry_rate_pass_at_gate() -> None:
    # 1 aborted of 5 attempts = 20% == gate -> PASS; unscored stays PENDING.
    rows = [
        _s2_row("ja-greet-01", audio="3000", ble="4000"),
        _s2_row("ja-greet-02", audio="3000", ble="4000"),
        _s2_row("vi-greet-01", audio="3000", ble="4000"),
        _s2_row("vi-greet-02", audio="3000", ble="4000"),
        _s2_row("ja-greet-03", audio="3000", ble="", error="discarded"),
    ]
    report = render_s2_markdown(rows)
    assert "| retry rate | 20% |" in report
    assert "Retry rate: 1/5 = 20% vs <= 20% -> **PASS**" in report
    assert "Result: **PENDING — accuracy not scored**" in report


def test_s2_retry_rate_fail_blocks_go() -> None:
    # 2 aborted of 4 = 50% -> FAIL, NO-GO even though latency is fine and
    # accuracy is unscored (hard data gate).
    rows = [
        _s2_row("ja-greet-01", audio="3000", ble="4000"),
        _s2_row("vi-greet-01", audio="3000", ble="4000"),
        _s2_row("ja-greet-02", audio="3000", ble="", error="discarded"),
        _s2_row("vi-greet-02", audio="3000", ble="", error="ws_error"),
    ]
    report = render_s2_markdown(rows)
    assert "Retry rate: 2/4 = 50% vs <= 20% -> **FAIL**" in report
    assert "Result: **NO-GO** (latency/retry gate failed)" in report


def _s3_row(
    capture_id: str,
    *,
    recognise: str = "",
    translate: str = "",
    ble: str = "",
    system: str = "",
    chars: str = "",
    error: str = "",
    recognised_pass: str = "",
) -> dict[str, str]:
    # OcrLatencyRecord CSV row + the operator-appended `recognised_pass` column.
    # A capture is "completed" iff error is blank AND `system` is present.
    return {
        "capture_id": capture_id,
        "recognise_ms": recognise,
        "translate_ms": translate,
        "ble_ack_ms": ble,
        "ocr_system_latency_ms": system,
        "recognised_chars": chars,
        "ble_seq_id": "",
        "error": error,
        "recognised_pass": recognised_pass,
    }


def test_s3_pending_when_unscored() -> None:
    # No recognised_pass: latency is computed (PASS), recognition is PENDING.
    # system_lat sorted [900, 1100], n=2 -> p95 idx round(1*0.95)=1 -> 1100.
    report = render_s3_markdown(
        [
            _s3_row("sign-01", system="900"),
            _s3_row("sign-02", system="1100"),
        ]
    )
    assert "Latency: p95 1100 ms vs 2500 ms -> **PASS**" in report
    assert "Recognition: **PENDING**" in report
    assert "Result: **PENDING — recognition not scored**" in report


def test_s3_go_when_recognition_and_latency_pass() -> None:
    # 4/5 key-line pass = 80% (meets gate), latency p95 900 ms -> GO.
    rows = [
        _s3_row(
            "sign-0%d" % i,
            system="900",
            recognised_pass="pass" if i < 4 else "fail",
        )
        for i in range(5)
    ]
    report = render_s3_markdown(rows)
    assert "| sign | 5 | 80% |" in report
    assert "| **overall** | 5 | 80% |" in report
    assert "- Recognition: 80% vs 80% -> **PASS**" in report
    assert "Result: **GO**" in report


def test_s3_no_go_when_recognition_below_gate() -> None:
    # 2/5 pass = 40% < 80% -> NO-GO even though latency is fine.
    rows = [
        _s3_row(
            "menu-0%d" % i,
            system="900",
            recognised_pass="1" if i < 2 else "0",
        )
        for i in range(5)
    ]
    report = render_s3_markdown(rows)
    assert "| **overall** | 5 | 40% |" in report
    assert "- Recognition: 40% vs 80% -> **FAIL**" in report
    assert "Result: **NO-GO**" in report


def test_s3_latency_fail_blocks_go() -> None:
    # Recognition perfect, but p95 latency 3000 > 2500 -> NO-GO.
    rows = [
        _s3_row("sign-01", system="3000", recognised_pass="pass"),
        _s3_row("sign-02", system="3000", recognised_pass="pass"),
    ]
    report = render_s3_markdown(rows)
    assert "- Recognition: 100% vs 80% -> **PASS**" in report
    assert "Latency: p95 3000 ms vs 2500 ms -> **FAIL**" in report
    assert "Result: **NO-GO**" in report


def test_s3_per_leg_breakdown_from_cumulative_deltas() -> None:
    # Cumulative deltas off capture: recognise 400, translate 700, ble 900.
    # Legs: recognise 400, translate 700-400=300, ble 900-700=200.
    report = render_s3_markdown(
        [
            _s3_row(
                "sign-01",
                recognise="400",
                translate="700",
                ble="900",
                system="900",
                chars="12",
            )
        ]
    )
    assert "| recognise | 1 | 400 | 400 | 400 |" in report
    assert "| translate | 1 | 300 | 300 | 300 |" in report
    assert "| ble | 1 | 200 | 200 | 200 |" in report


def test_s3_aborted_excluded_from_latency() -> None:
    # ble_unavailable carries no ble ack: an attempt + a failure, but not a
    # completed capture and not in the latency tally.
    report = render_s3_markdown(
        [
            _s3_row("sign-01", system="900"),
            _s3_row("sign-02", error="ble_unavailable"),
        ]
    )
    assert "| completed captures | 1 |" in report
    assert "| aborted attempts | 1 |" in report
    assert "| ble_unavailable | 1 |" in report
    assert "| 1 / 2 |" in report  # n_ok / n_total in the latency table


def test_s3_recognition_groups_by_domain() -> None:
    report = render_s3_markdown(
        [
            _s3_row("sign-01", system="900", recognised_pass="pass"),
            _s3_row("menu-01", system="900", recognised_pass="fail"),
        ]
    )
    assert "| menu | 1 | 0% |" in report
    assert "| sign | 1 | 100% |" in report
