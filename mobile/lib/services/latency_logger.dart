// LingoGlass AR S0 Phase F latency logger.
//
// Records send_ts per sequence_id, matches incoming AckEvent by sequence_id,
// and accumulates LatencyRecord rows that can be exported as CSV or
// summarised as p50/p90/p95 buckets.
//
// Clock notes:
//   - send_ts and ack_ts are phone-side microsecondsSinceEpoch. RTT is their
//     difference and is the primary metric.
//   - fw_proc_ms comes from ESP32 millis() (t_render_ms - t_recv_ms) and is
//     a different clock; it is only ever interpreted as a delta.

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

class LatencyLogger {
  LatencyLogger();

  final List<LatencyRecord> _records = <LatencyRecord>[];
  final Map<int, _PendingSend> _pending = <int, _PendingSend>{};

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
}
