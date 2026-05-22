// LingoGlass AR latency logger.
//
// Two record families share this file:
//
//   1. S0 Phase F BLE-leg measurements: `LatencyRecord` rows record one
//      subtitle send -> ACK round-trip on the phone clock. Use
//      `markSendStart` + `recordAck` and export via `toCsv` /
//      `summarise`.  These keep the BLE leg honest against the 50-200 ms
//      budget.
//
//   2. S1 Day 9 end-to-end measurements: `E2eLatencyRecord` rows track
//      one push-to-talk utterance from press through audio recording,
//      backend session handshake, STT/translation deltas, and the BLE
//      ACK of the rendered subtitle.  Use `e2eStart` + the per-stage
//      `e2eMark*` methods + `e2eFinalize`; export via `toE2eCsv` /
//      `summariseE2e`.  Targets `p95(total_ms) <= 2500 ms` per
//      docs/CLAUDE.md latency budget.
//
// Clock notes:
//   - send_ts / ack_ts / press_ts are phone-side microsecondsSinceEpoch.
//     RTTs and stage durations are deltas on the same clock and so are
//     monotone with sane error bars.
//   - fw_proc_ms comes from ESP32 millis() (t_render_ms - t_recv_ms) and
//     is a different clock; only ever interpreted as a delta.

import '../ble/ble_transport.dart';

class LatencyRecord {
  const LatencyRecord({
    required this.sequenceId,
    required this.mtu,
    required this.payloadBytes,
    required this.fragments,
    required this.sendTsMicros,
    required this.ackTsMicros,
    required this.rttMs,
    required this.fwProcMs,
    required this.status,
  });

  final int sequenceId;
  final int mtu;
  final int payloadBytes;
  final int fragments;
  final int sendTsMicros;
  final int ackTsMicros;
  final double rttMs;
  final int? fwProcMs;
  final int status;

  bool get isOk => status == 0x01;

  String toCsvRow() {
    final fw = fwProcMs?.toString() ?? '';
    return '$sequenceId,$mtu,$payloadBytes,$fragments,$sendTsMicros,'
        '$ackTsMicros,${rttMs.toStringAsFixed(2)},$fw,'
        '0x${status.toRadixString(16).padLeft(2, '0')}';
  }

  static const String csvHeader =
      'seq_id,mtu,payload_bytes,fragments,send_ts_us,ack_ts_us,'
      'rtt_ms,fw_proc_ms,status';
}

class _PendingSend {
  _PendingSend({
    required this.mtu,
    required this.payloadBytes,
    required this.fragments,
    required this.sendTsMicros,
  });

  final int mtu;
  final int payloadBytes;
  final int fragments;
  final int sendTsMicros;
}

class LatencyStats {
  const LatencyStats({
    required this.count,
    required this.p50,
    required this.p90,
    required this.p95,
    required this.min,
    required this.max,
  });

  final int count;
  final double p50;
  final double p90;
  final double p95;
  final double min;
  final double max;

  @override
  String toString() => 'n=$count p50=${p50.toStringAsFixed(1)}ms '
      'p90=${p90.toStringAsFixed(1)}ms p95=${p95.toStringAsFixed(1)}ms '
      'min=${min.toStringAsFixed(1)} max=${max.toStringAsFixed(1)}';
}

/// One end-to-end record per push-to-talk utterance.
///
/// All `*Ms` fields are milliseconds **relative to PTT press** so they
/// compose into a stacked timeline without re-anchoring in the report
/// tool. `totalMs` is an alias of `bleAckMs` — the e2e budget gate —
/// kept as its own column so a CSV row can be read top-to-bottom for
/// the cumulative timeline without computing it.
///
/// Any field other than `phraseId`, `audioMs`, and `pressTsMicros` is
/// nullable: a stage that did not complete (network failure, BLE
/// disconnect, user abort) leaves its column empty and `errorCode`
/// describes the failure. The report tool tolerates and reports on
/// these.
class E2eLatencyRecord {
  const E2eLatencyRecord({
    required this.phraseId,
    required this.pressTsMicros,
    required this.audioMs,
    required this.backendAckMs,
    required this.firstTextMs,
    required this.fullTextMs,
    required this.bleAckMs,
    required this.totalMs,
    required this.sessionId,
    required this.bleSequenceId,
    required this.errorCode,
  });

  /// Identifier of the prompt that was spoken — the catalog key in
  /// `mobile/lib/data/s1_phrases.dart` (Codex adds that file in Day 9).
  final String phraseId;

  /// Phone-clock microsecondsSinceEpoch at PTT press. Stored for the
  /// debug column and for cross-correlating against backend logs; the
  /// stage fields below are deltas, not absolute times.
  final int pressTsMicros;

  /// PTT hold duration: release_ts - press_ts. Not a latency itself
  /// (user-controlled), but the report tool uses it as the audio stage
  /// in the stacked bar.
  final int audioMs;

  /// `session.opened` WS frame received, relative to press. Captures
  /// HTTP `POST /v1/sessions` + WS connect + server-side accept. ~50 ms
  /// on a warm connection.
  final int? backendAckMs;

  /// First `translation.partial` frame received, relative to press.
  /// Reflects upload + STT first-token latency.
  final int? firstTextMs;

  /// `translation.final` frame received, relative to press. Reflects
  /// full STT + translation processing time.
  final int? fullTextMs;

  /// BLE ACK (status=0x01) for the subtitle send, relative to press.
  /// The user-visible "subtitle on the lens" event.
  final int? bleAckMs;

  /// Same value as [bleAckMs] when populated. The e2e Go/No-Go gate is
  /// `p95(totalMs) <= 2500 ms`.
  final int? totalMs;

  /// Backend session id from `POST /v1/sessions`, for cross-correlation
  /// with `redis-cli HGETALL session:<id>:cost`.
  final String? sessionId;

  /// BLE sequence id used for the subtitle send; lets the operator pair
  /// the e2e row with the Phase F `LatencyRecord` for the same send.
  final int? bleSequenceId;

  /// Short tag when the utterance did not complete cleanly. Examples:
  /// `ws_error`, `ble_disconnect`, `mic_denied`, `user_abort`, `timeout`.
  final String? errorCode;

  /// True iff every stage completed and `errorCode` is null.
  bool get isOk =>
      errorCode == null &&
      backendAckMs != null &&
      firstTextMs != null &&
      fullTextMs != null &&
      bleAckMs != null;

  String toCsvRow() {
    String n(int? v) => v?.toString() ?? '';
    return '$phraseId,$audioMs,${n(backendAckMs)},${n(firstTextMs)},'
        '${n(fullTextMs)},${n(bleAckMs)},${n(totalMs)},'
        '${sessionId ?? ''},${n(bleSequenceId)},${errorCode ?? ''}';
  }

  static const String csvHeader =
      'phrase_id,audio_ms,backend_ack_ms,first_text_ms,full_text_ms,'
      'ble_ack_ms,total_ms,session_id,ble_seq_id,error';
}

/// p50/p90/p95/p99 of `total_ms` across OK e2e records.
///
/// Stage durations (computed by the report tool, not the logger):
///   stage_audio_ms     = audio_ms
///   stage_handshake_ms = backend_ack_ms - audio_ms       (>=0)
///   stage_stt_ms       = first_text_ms - backend_ack_ms  (>=0)
///   stage_translate_ms = full_text_ms - first_text_ms    (>=0)
///   stage_ble_ms       = ble_ack_ms    - full_text_ms    (>=0)
///
/// The mobile-side `summariseE2e` returns only the overall total stats;
/// the per-stage decomposition is produced by `tools/latency_report.py
/// --s1` so a single source of truth handles negative-delta edge cases
/// (server-clock skew) consistently.
class E2eLatencyStats {
  const E2eLatencyStats({
    required this.count,
    required this.p50,
    required this.p90,
    required this.p95,
    required this.p99,
    required this.min,
    required this.max,
  });

  final int count;
  final double p50;
  final double p90;
  final double p95;
  final double p99;
  final double min;
  final double max;

  @override
  String toString() => 'n=$count p50=${p50.toStringAsFixed(0)}ms '
      'p90=${p90.toStringAsFixed(0)}ms p95=${p95.toStringAsFixed(0)}ms '
      'p99=${p99.toStringAsFixed(0)}ms';
}

/// Mutable per-utterance trace. Implementation detail of [LatencyLogger];
/// not exposed.
class _E2eTrace {
  _E2eTrace({required this.phraseId, required this.pressTsMicros});

  final String phraseId;
  final int pressTsMicros;
  int? releaseTsMicros;
  int? sessionOpenedTsMicros;
  int? firstTextTsMicros;
  int? finalTextTsMicros;
  int? bleAckTsMicros;
  String? sessionId;
  int? bleSequenceId;
  String? errorCode;
}

class LatencyLogger {
  LatencyLogger();

  final List<LatencyRecord> _records = <LatencyRecord>[];
  final Map<int, _PendingSend> _pending = <int, _PendingSend>{};

  final List<E2eLatencyRecord> _e2eRecords = <E2eLatencyRecord>[];
  _E2eTrace? _activeTrace;

  /// Read-only view of all records collected so far.
  List<LatencyRecord> get records => List.unmodifiable(_records);

  /// Clear all in-memory state (records + pending matches).
  void clear() {
    _records.clear();
    _pending.clear();
  }

  /// Call right before [BleTransport.sendSubtitle] is awaited so the timer
  /// includes the BLE write itself.
  void markSendStart({
    required int sequenceId,
    required int mtu,
    required int payloadBytes,
    required int fragments,
  }) {
    _pending[sequenceId] = _PendingSend(
      mtu: mtu,
      payloadBytes: payloadBytes,
      fragments: fragments,
      sendTsMicros: DateTime.now().microsecondsSinceEpoch,
    );
  }

  /// Feed every AckEvent. Records that match a pending sequence become
  /// LatencyRecord; orphan ACKs are ignored (logged by caller if desired).
  /// Returns the new record if matched, null otherwise.
  LatencyRecord? recordAck(AckEvent ack) {
    final pending = _pending.remove(ack.sequenceId);
    if (pending == null) return null;
    final rttUs = ack.receivedAtMicros - pending.sendTsMicros;
    final rec = LatencyRecord(
      sequenceId: ack.sequenceId,
      mtu: pending.mtu,
      payloadBytes: pending.payloadBytes,
      fragments: pending.fragments,
      sendTsMicros: pending.sendTsMicros,
      ackTsMicros: ack.receivedAtMicros,
      rttMs: rttUs / 1000.0,
      fwProcMs: ack.fwProcMs,
      status: ack.status,
    );
    _records.add(rec);
    return rec;
  }

  /// CSV body including header and one row per record.
  String toCsv() {
    final sb = StringBuffer()..writeln(LatencyRecord.csvHeader);
    for (final r in _records) {
      sb.writeln(r.toCsvRow());
    }
    return sb.toString();
  }

  /// p50/p90/p95 across all OK records. Returns null when there are no
  /// OK samples to summarise.
  LatencyStats? summarise() {
    final okRtts = _records.where((r) => r.isOk).map((r) => r.rttMs).toList()
      ..sort();
    if (okRtts.isEmpty) return null;
    double pct(double p) {
      final idx = ((okRtts.length - 1) * p).round();
      return okRtts[idx];
    }

    return LatencyStats(
      count: okRtts.length,
      p50: pct(0.50),
      p90: pct(0.90),
      p95: pct(0.95),
      min: okRtts.first,
      max: okRtts.last,
    );
  }

  // ------------------------------------------------------------------
  // S1 Day 9 — end-to-end utterance trace
  // ------------------------------------------------------------------
  //
  // Lifecycle (Codex implements; signatures locked):
  //
  //   logger.e2eStart('greeting-01')                  // on PTT press
  //   logger.e2eMarkPttRelease()                      // on PTT release
  //   logger.e2eMarkSessionOpened(sessionId)          // session.opened
  //   logger.e2eMarkFirstText()                       // 1st partial
  //   logger.e2eMarkTranslationFinal()                // final
  //   logger.e2eMarkBleAck(sequenceId)                // BLE ack 0x01
  //   final record = logger.e2eFinalize();            // commits
  //
  // Any e2eMark*/finalize call without a matching e2eStart is a no-op
  // returning null. e2eAbort('error_code') closes the active trace
  // with errorCode set, no e2eMark* required.

  /// Read-only view of committed e2e records.
  List<E2eLatencyRecord> get e2eRecords => List.unmodifiable(_e2eRecords);

  /// True while an utterance is being traced (between [e2eStart] and
  /// [e2eFinalize]/[e2eAbort]).
  bool get e2eInProgress => _activeTrace != null;

  /// Begin a new utterance trace. Discards any prior unfinalised trace
  /// by finalising it with `errorCode='discarded'` first so no data is
  /// lost; the operator sees the discard in the CSV.
  void e2eStart(String phraseId) {
    if (_activeTrace != null) {
      _activeTrace!.errorCode = 'discarded';
      e2eFinalize();
    }
    _activeTrace = _E2eTrace(
      phraseId: phraseId,
      pressTsMicros: DateTime.now().microsecondsSinceEpoch,
    );
  }

  /// Record PTT release (audio.end semantically). Stores
  /// release_ts_micros on the active trace.
  void e2eMarkPttRelease() {
    final trace = _activeTrace;
    if (trace == null) return;
    trace.releaseTsMicros = DateTime.now().microsecondsSinceEpoch;
  }

  /// Record `session.opened` frame from backend WS. Stores
  /// sessionOpened_ts and the backend sessionId on the trace.
  void e2eMarkSessionOpened(String sessionId) {
    final trace = _activeTrace;
    if (trace == null) return;
    trace.sessionOpenedTsMicros = DateTime.now().microsecondsSinceEpoch;
    trace.sessionId = sessionId;
  }

  /// Record the first `translation.partial` frame.
  void e2eMarkFirstText() {
    final trace = _activeTrace;
    if (trace == null || trace.firstTextTsMicros != null) return;
    trace.firstTextTsMicros = DateTime.now().microsecondsSinceEpoch;
  }

  /// Record the `translation.final` frame.
  void e2eMarkTranslationFinal() {
    final trace = _activeTrace;
    if (trace == null) return;
    trace.finalTextTsMicros = DateTime.now().microsecondsSinceEpoch;
  }

  /// Record the BLE ACK (status=0x01) for the subtitle send.
  void e2eMarkBleAck(int sequenceId) {
    final trace = _activeTrace;
    if (trace == null) return;
    trace.bleAckTsMicros = DateTime.now().microsecondsSinceEpoch;
    trace.bleSequenceId = sequenceId;
  }

  /// Close the active trace with an error code (no completion required).
  /// Subsequent e2eMark* calls are no-ops until [e2eStart] runs again.
  E2eLatencyRecord? e2eAbort(String errorCode) {
    final trace = _activeTrace;
    if (trace == null) return null;
    trace.errorCode = errorCode;
    return e2eFinalize();
  }

  /// Snapshot the active trace into an immutable [E2eLatencyRecord],
  /// append it to [e2eRecords], and clear the active trace. Returns the
  /// record (or null if nothing was active).
  ///
  /// `audioMs`, `backendAckMs`, etc. are computed as
  /// `(ts - pressTsMicros) / 1000` rounded to the nearest millisecond.
  /// `totalMs` is set to `bleAckMs` (or null if BLE never acked).
  E2eLatencyRecord? e2eFinalize() {
    final trace = _activeTrace;
    if (trace == null) return null;

    int? delta(int? ts) {
      if (ts == null) return null;
      return ((ts - trace.pressTsMicros) / 1000).round();
    }

    final bleAckMs = delta(trace.bleAckTsMicros);
    final record = E2eLatencyRecord(
      phraseId: trace.phraseId,
      pressTsMicros: trace.pressTsMicros,
      audioMs: delta(trace.releaseTsMicros) ?? 0,
      backendAckMs: delta(trace.sessionOpenedTsMicros),
      firstTextMs: delta(trace.firstTextTsMicros),
      fullTextMs: delta(trace.finalTextTsMicros),
      bleAckMs: bleAckMs,
      totalMs: bleAckMs,
      sessionId: trace.sessionId,
      bleSequenceId: trace.bleSequenceId,
      errorCode: trace.errorCode,
    );
    _e2eRecords.add(record);
    _activeTrace = null;
    return record;
  }

  /// CSV body including [E2eLatencyRecord.csvHeader] and one row per
  /// finalised record.
  String toE2eCsv() {
    final sb = StringBuffer()..writeln(E2eLatencyRecord.csvHeader);
    for (final record in _e2eRecords) {
      sb.writeln(record.toCsvRow());
    }
    return sb.toString();
  }

  /// p50/p90/p95/p99 of `total_ms` across OK e2e records. Returns null
  /// when no OK samples exist. Per-stage breakdown is the report tool's
  /// job (`tools/latency_report.py --s1`).
  E2eLatencyStats? summariseE2e() {
    final totals = _e2eRecords
        .where((record) => record.isOk)
        .map((record) => record.totalMs!.toDouble())
        .toList()
      ..sort();
    if (totals.isEmpty) return null;

    double pct(double p) {
      final idx = ((totals.length - 1) * p).round();
      return totals[idx];
    }

    return E2eLatencyStats(
      count: totals.length,
      p50: pct(0.50),
      p90: pct(0.90),
      p95: pct(0.95),
      p99: pct(0.99),
      min: totals.first,
      max: totals.last,
    );
  }

  /// Clear e2e state without touching Phase F records.
  void clearE2e() {
    _e2eRecords.clear();
    _activeTrace = null;
  }
}
