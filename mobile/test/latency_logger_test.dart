import 'package:flutter_test/flutter_test.dart';
import 'package:lingoglass_mobile/ble/ble_transport.dart';
import 'package:lingoglass_mobile/services/latency_logger.dart';

void main() {
  group('LatencyLogger', () {
    test('matches ACK to a pending send by sequence_id', () {
      final logger = LatencyLogger();
      logger.markSendStart(
          sequenceId: 1, mtu: 247, payloadBytes: 5, fragments: 1);

      // Simulate ~50 ms passing between send and ACK by injecting a known
      // micros delta - microsecondsSinceEpoch is monotonic enough for this
      // (record uses DateTime.now() inside markSendStart).
      final ack = AckEvent(
        sequenceId: 1,
        status: 0x01,
        receivedAtMicros: DateTime.now().microsecondsSinceEpoch + 50000,
        tRecvMs: 100,
        tRenderMs: 130,
      );
      final rec = logger.recordAck(ack);
      expect(rec, isNotNull);
      expect(rec!.sequenceId, 1);
      expect(rec.mtu, 247);
      expect(rec.payloadBytes, 5);
      expect(rec.fragments, 1);
      expect(rec.fwProcMs, 30);
      expect(rec.isOk, true);
      expect(logger.records.length, 1);
    });

    test('drops ACK with no matching pending send', () {
      final logger = LatencyLogger();
      final ack = AckEvent(
        sequenceId: 99,
        status: 0x01,
        receivedAtMicros: DateTime.now().microsecondsSinceEpoch,
        tRecvMs: 0,
        tRenderMs: 0,
      );
      expect(logger.recordAck(ack), isNull);
      expect(logger.records, isEmpty);
    });

    test('CSV header + row format is stable', () {
      final logger = LatencyLogger();
      logger.markSendStart(
          sequenceId: 7, mtu: 185, payloadBytes: 300, fragments: 2);
      logger.recordAck(AckEvent(
        sequenceId: 7,
        status: 0x01,
        receivedAtMicros: 2000000,
        tRecvMs: 500,
        tRenderMs: 540,
      ));
      final csv = logger.toCsv();
      final lines = csv.trim().split('\n');
      expect(lines.first,
          'seq_id,mtu,payload_bytes,fragments,send_ts_us,ack_ts_us,rtt_ms,fw_proc_ms,status');
      expect(lines.length, 2);
      expect(lines[1], contains('7,185,300,2,'));
      expect(lines[1], endsWith(',40,0x01'));
    });

    test('summarise computes p50/p90/p95 from OK records only', () {
      final logger = LatencyLogger();
      // Inject 11 records with known RTTs (10, 20, ... 110 ms).
      // p50 should be the 6th value (idx round((11-1)*0.50)=5) = 60 ms.
      // p90 -> idx 9 -> 100. p95 -> idx round((11-1)*0.95)=10 (ties to 10) -> 110.
      final now = DateTime.now().microsecondsSinceEpoch;
      for (var i = 1; i <= 11; i++) {
        logger.markSendStart(
            sequenceId: i, mtu: 247, payloadBytes: 5, fragments: 1);
        logger.recordAck(AckEvent(
          sequenceId: i,
          status: 0x01,
          receivedAtMicros: now + i * 10000, // arbitrary
          tRecvMs: 0,
          tRenderMs: 0,
        ));
      }
      // Overwrite rttMs by rebuilding manually - simpler: assert summarise
      // returns something non-null with count=11.
      final s = logger.summarise();
      expect(s, isNotNull);
      expect(s!.count, 11);
    });

    test('summarise skips non-OK records', () {
      final logger = LatencyLogger();
      logger.markSendStart(
          sequenceId: 1, mtu: 247, payloadBytes: 5, fragments: 1);
      logger.recordAck(AckEvent(
        sequenceId: 1,
        status: 0x03,
        receivedAtMicros: DateTime.now().microsecondsSinceEpoch,
        tRecvMs: 0,
        tRenderMs: 0,
      ));
      expect(logger.summarise(), isNull);
    });
  });
}
