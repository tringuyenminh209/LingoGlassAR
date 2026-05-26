from tools.latency_report import render_s1_markdown, render_s2_markdown


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
