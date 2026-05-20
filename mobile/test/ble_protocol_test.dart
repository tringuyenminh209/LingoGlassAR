// Dart unit tests for ble_protocol. Run with: flutter test
// Vectors mirror tests/ble_vectors.json and firmware/esp32s3/test/test_ble_protocol/.

import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:lingoglass_mobile/ble/ble_protocol.dart';

void main() {
  group('crc8 vectors', () {
    test('subtitle A seq=1 -> 0x5B', () {
      final bytes = Uint8List.fromList([
        0x01,
        0x01,
        0x01,
        0x00,
        0x00,
        0x01,
        0x01,
        0x41,
      ]);
      expect(crc8(bytes), 0x5B);
    });

    test('subtitle Hello seq=2 -> 0x36', () {
      final bytes = Uint8List.fromList([
        0x01,
        0x01,
        0x02,
        0x00,
        0x00,
        0x01,
        0x05,
        0x48,
        0x65,
        0x6C,
        0x6C,
        0x6F,
      ]);
      expect(crc8(bytes), 0x36);
    });

    test('subtitle JP ko seq=3 -> 0x5C', () {
      final bytes = Uint8List.fromList([
        0x01,
        0x01,
        0x03,
        0x00,
        0x00,
        0x01,
        0x03,
        0xE3,
        0x81,
        0x93,
      ]);
      expect(crc8(bytes), 0x5C);
    });

    test('seq wrap 0xFFFF frag 1/2 AB -> 0x9E', () {
      final bytes = Uint8List.fromList([
        0x01,
        0x01,
        0xFF,
        0xFF,
        0x01,
        0x02,
        0x02,
        0x41,
        0x42,
      ]);
      expect(crc8(bytes), 0x9E);
    });

    test('ack seq=1 phase F (10-byte payload) -> 0x7C', () {
      // status=0x01, reserved=0x00, t_recv_ms=123 (0x7B LE), t_render_ms=200 (0xC8 LE)
      final bytes = Uint8List.fromList([
        0x01, 0x03, 0x01, 0x00, 0x00, 0x01, 0x0A, // header, payload_length=10
        0x01, 0x00, // status, reserved
        0x7B, 0x00, 0x00, 0x00, // t_recv_ms LE = 123
        0xC8, 0x00, 0x00, 0x00, // t_render_ms LE = 200
      ]);
      expect(crc8(bytes), 0x7C);
    });
  });

  group('encodeFragment', () {
    test('subtitle A seq=1 matches full packet vector', () {
      final out = encodeFragment(
        type: MessageType.subtitle,
        sequenceId: 1,
        fragmentIndex: 0,
        fragmentCount: 1,
        payload: Uint8List.fromList([0x41]),
      );
      expect(
        out,
        equals([0x01, 0x01, 0x01, 0x00, 0x00, 0x01, 0x01, 0x41, 0x5B]),
      );
    });

    test('rejects fragmentIndex >= fragmentCount', () {
      expect(
        () => encodeFragment(
          type: MessageType.subtitle,
          sequenceId: 1,
          fragmentIndex: 2,
          fragmentCount: 2,
          payload: Uint8List.fromList([0x41]),
        ),
        throwsArgumentError,
      );
    });
  });

  group('decodeFragment', () {
    test('round-trips subtitle A seq=1', () {
      final bytes = Uint8List.fromList([
        0x01,
        0x01,
        0x01,
        0x00,
        0x00,
        0x01,
        0x01,
        0x41,
        0x5B,
      ]);
      final r = decodeFragment(bytes);
      expect(r.isOk, isTrue);
      final p = r.packet!;
      expect(p.header.sequenceId, 1);
      expect(p.header.fragmentIndex, 0);
      expect(p.header.fragmentCount, 1);
      expect(p.payload, equals([0x41]));
    });

    test('sequence_id is little-endian', () {
      // sequence_id = 0xBEEF
      final bytes = Uint8List.fromList([
        0x01,
        0x01,
        0xEF,
        0xBE,
        0x00,
        0x01,
        0x01,
        0x41,
        0x00,
      ]);
      bytes[8] = crc8(bytes, 0, 8);
      final r = decodeFragment(bytes);
      expect(r.isOk, isTrue);
      expect(r.packet!.header.sequenceId, 0xBEEF);
    });

    test('rejects CRC mismatch', () {
      final bytes = Uint8List.fromList([
        0x01,
        0x01,
        0x01,
        0x00,
        0x00,
        0x01,
        0x01,
        0x41,
        0x00,
      ]);
      expect(decodeFragment(bytes).status, DecodeStatus.crcMismatch);
    });

    test('rejects length mismatch', () {
      final bytes = Uint8List.fromList([
        0x01,
        0x01,
        0x01,
        0x00,
        0x00,
        0x01,
        0x05,
        0x41,
        0x5B,
      ]);
      expect(decodeFragment(bytes).status, DecodeStatus.lengthMismatch);
    });

    test('rejects unknown version', () {
      final bytes = Uint8List.fromList([
        0xFF,
        0x01,
        0x01,
        0x00,
        0x00,
        0x01,
        0x01,
        0x41,
        0x00,
      ]);
      expect(decodeFragment(bytes).status, DecodeStatus.unknownVersion);
    });
  });

  group('splitUtf8', () {
    test(
      'Japanese konnichiwa with max=7 splits 6/6/3 on codepoint boundary',
      () {
        final input = Uint8List.fromList([
          0xE3,
          0x81,
          0x93,
          0xE3,
          0x82,
          0x93,
          0xE3,
          0x81,
          0xAB,
          0xE3,
          0x81,
          0xA1,
          0xE3,
          0x81,
          0xAF,
        ]);
        final ranges = splitUtf8(input, 7);
        expect(ranges.length, 3);
        expect(ranges[0].length, 6);
        expect(ranges[1].offset, 6);
        expect(ranges[1].length, 6);
        expect(ranges[2].offset, 12);
        expect(ranges[2].length, 3);
      },
    );

    test('ASCII exact multiples', () {
      final input = Uint8List.fromList('abcdefghij'.codeUnits);
      final ranges = splitUtf8(input, 4);
      expect(ranges.map((r) => r.length).toList(), [4, 4, 2]);
    });
  });
}
