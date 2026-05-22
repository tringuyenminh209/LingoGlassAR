from tools.latency_report import render_s1_markdown


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
    }


def test_s1_render_happy_path() -> None:
    report = render_s1_markdown(
        [
            _row("a", audio="100", backend="180", first="700", final="900", ble="990", total="990"),
            _row("b", audio="120", backend="210", first="760", final="980", ble="1100", total="1100"),
            _row("c", audio="110", backend="200", first="800", final="1050", ble="1250", total="1250"),
        ]
    )

    assert "- **GO**" in report
    assert "p95(total_ms) = 1250 ms" in report


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
    report = render_s1_markdown(
        [
            _row(
                "skew",
                audio="200",
                backend="150",
                first="600",
                final="800",
                ble="900",
                total="900",
            )
        ]
    )

    assert "Clock skew: 1 rows had negative stage deltas." in report
