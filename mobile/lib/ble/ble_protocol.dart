// LingoGlass AR BLE subtitle protocol — Dart mirror of firmware/esp32s3/lib/ble_protocol.
//
// Packet layout is locked in docs/LingoGlass_AR_Development_Plan.md and
// .claude/skills/ble-protocol/SKILL.md. When updating one side, update both.
// Test vectors live in tests/ble_vectors.json.

import 'dart:typed_data';

const int protocolVersion = 0x01;
const int headerSize = 7;
const int trailerSize = 1;
const int packetOverhead = headerSize + trailerSize;
const int maxPayload = 244;

enum MessageType {
  subtitle(0x01),
  status(0x02),
  ack(0x03),
  error(0x04);

  const MessageType(this.value);
  final int value;
}

class PacketHeader {
  const PacketHeader({
    required this.version,
    required this.messageType,
    required this.sequenceId,
    required this.fragmentIndex,
    required this.fragmentCount,
    required this.payloadLength,
  });

  final int version;
  final int messageType;
  final int sequenceId;
  final int fragmentIndex;
  final int fragmentCount;
  final int payloadLength;
}

class DecodedPacket {
  const DecodedPacket(this.header, this.payload);
  final PacketHeader header;
  final Uint8List payload;
}

enum DecodeStatus {
  ok,
  tooShort,
  lengthMismatch,
  crcMismatch,
  unknownVersion,
  unknownMessageType,
}

class DecodeResult {
  const DecodeResult.ok(DecodedPacket this.packet) : status = DecodeStatus.ok;
  const DecodeResult.error(this.status) : packet = null;
  final DecodeStatus status;
  final DecodedPacket? packet;
  bool get isOk => status == DecodeStatus.ok;
}

int crc8(List<int> data, [int start = 0, int? end]) {
  final stop = end ?? data.length;
  int crc = 0x00;
  for (int i = start; i < stop; i++) {
    crc ^= data[i] & 0xFF;
    for (int bit = 0; bit < 8; bit++) {
      if ((crc & 0x80) != 0) {
        crc = ((crc << 1) ^ 0x07) & 0xFF;
      } else {
        crc = (crc << 1) & 0xFF;
      }
    }
  }
  return crc;
}

Uint8List encodeFragment({
  required MessageType type,
  required int sequenceId,
  required int fragmentIndex,
  required int fragmentCount,
  required Uint8List payload,
}) {
  if (payload.length > 0xFF) {
    throw ArgumentError('payload too long: ${payload.length}');
  }
  if (fragmentIndex >= fragmentCount) {
    throw ArgumentError('fragmentIndex >= fragmentCount');
  }
  if (sequenceId < 0 || sequenceId > 0xFFFF) {
    throw ArgumentError('sequenceId out of range');
  }
  final out = Uint8List(packetOverhead + payload.length);
  out[0] = protocolVersion;
  out[1] = type.value;
  out[2] = sequenceId & 0xFF;
  out[3] = (sequenceId >> 8) & 0xFF;
  out[4] = fragmentIndex;
  out[5] = fragmentCount;
  out[6] = payload.length;
  out.setRange(headerSize, headerSize + payload.length, payload);
  out[headerSize + payload.length] = crc8(out, 0, headerSize + payload.length);
  return out;
}

DecodeResult decodeFragment(Uint8List data) {
  if (data.length < packetOverhead) {
    return const DecodeResult.error(DecodeStatus.tooShort);
  }
  if (data[0] != protocolVersion) {
    return const DecodeResult.error(DecodeStatus.unknownVersion);
  }
  final mt = data[1];
  if (mt < 0x01 || mt > 0x04) {
    return const DecodeResult.error(DecodeStatus.unknownMessageType);
  }
  final payloadLength = data[6];
  if (data.length != packetOverhead + payloadLength) {
    return const DecodeResult.error(DecodeStatus.lengthMismatch);
  }
  final expectedCrc = crc8(data, 0, headerSize + payloadLength);
  if (expectedCrc != data[headerSize + payloadLength]) {
    return const DecodeResult.error(DecodeStatus.crcMismatch);
  }
  final header = PacketHeader(
    version: data[0],
    messageType: data[1],
    sequenceId: data[2] | (data[3] << 8),
    fragmentIndex: data[4],
    fragmentCount: data[5],
    payloadLength: payloadLength,
  );
  final payload = Uint8List.sublistView(
    data,
    headerSize,
    headerSize + payloadLength,
  );
  return DecodeResult.ok(DecodedPacket(header, payload));
}

class FragmentRange {
  const FragmentRange(this.offset, this.length);
  final int offset;
  final int length;
}

/// Split UTF-8 bytes into fragments at codepoint boundaries.
/// Each fragment length <= maxPayloadBytes.
List<FragmentRange> splitUtf8(Uint8List input, int maxPayloadBytes) {
  final ranges = <FragmentRange>[];
  if (maxPayloadBytes == 0 || input.isEmpty) return ranges;

  int start = 0;
  while (start < input.length) {
    int end = start + maxPayloadBytes;
    if (end >= input.length) {
      ranges.add(FragmentRange(start, input.length - start));
      break;
    }
    // Back off while end is a UTF-8 continuation byte (10xxxxxx).
    while (end > start && (input[end] & 0xC0) == 0x80) {
      end--;
    }
    if (end == start) {
      // Single codepoint longer than maxPayloadBytes — emit as-is.
      end = start + 1;
      while (end < input.length && (input[end] & 0xC0) == 0x80) {
        end++;
      }
    }
    ranges.add(FragmentRange(start, end - start));
    start = end;
  }
  return ranges;
}
