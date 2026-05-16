#include "ble_protocol.h"

namespace ble_protocol {

uint8_t crc8(const uint8_t* data, std::size_t length) {
  uint8_t crc = 0x00;
  for (std::size_t i = 0; i < length; ++i) {
    crc ^= data[i];
    for (int bit = 0; bit < 8; ++bit) {
      if (crc & 0x80) {
        crc = static_cast<uint8_t>((crc << 1) ^ 0x07);
      } else {
        crc = static_cast<uint8_t>(crc << 1);
      }
    }
  }
  return crc;
}

std::size_t encode_fragment(MessageType type,
                            uint16_t sequence_id,
                            uint8_t fragment_index,
                            uint8_t fragment_count,
                            const uint8_t* payload,
                            uint8_t payload_length,
                            uint8_t* out_buffer,
                            std::size_t out_buffer_size) {
  const std::size_t needed = OVERHEAD + payload_length;
  if (out_buffer_size < needed) return 0;
  if (fragment_index >= fragment_count) return 0;

  out_buffer[0] = PROTOCOL_VERSION;
  out_buffer[1] = static_cast<uint8_t>(type);
  out_buffer[2] = static_cast<uint8_t>(sequence_id & 0xFF);         // LE low
  out_buffer[3] = static_cast<uint8_t>((sequence_id >> 8) & 0xFF);  // LE high
  out_buffer[4] = fragment_index;
  out_buffer[5] = fragment_count;
  out_buffer[6] = payload_length;
  for (uint8_t i = 0; i < payload_length; ++i) {
    out_buffer[HEADER_SIZE + i] = payload[i];
  }
  out_buffer[HEADER_SIZE + payload_length] = crc8(out_buffer, HEADER_SIZE + payload_length);
  return needed;
}

DecodeStatus decode_fragment(const uint8_t* data,
                             std::size_t length,
                             DecodedPacket& out_packet) {
  if (length < OVERHEAD) return DecodeStatus::TooShort;
  if (data[0] != PROTOCOL_VERSION) return DecodeStatus::UnknownVersion;

  uint8_t mt = data[1];
  if (mt < 0x01 || mt > 0x04) return DecodeStatus::UnknownMessageType;

  uint8_t payload_length = data[6];
  if (length != static_cast<std::size_t>(OVERHEAD) + payload_length) {
    return DecodeStatus::LengthMismatch;
  }

  uint8_t expected_crc = crc8(data, HEADER_SIZE + payload_length);
  if (expected_crc != data[HEADER_SIZE + payload_length]) {
    return DecodeStatus::CrcMismatch;
  }

  out_packet.header.version         = data[0];
  out_packet.header.message_type    = data[1];
  out_packet.header.sequence_id     = static_cast<uint16_t>(data[2]) |
                                      (static_cast<uint16_t>(data[3]) << 8);
  out_packet.header.fragment_index  = data[4];
  out_packet.header.fragment_count  = data[5];
  out_packet.header.payload_length  = data[6];
  out_packet.payload                = data + HEADER_SIZE;
  out_packet.payload_length         = payload_length;
  return DecodeStatus::Ok;
}

std::vector<FragmentRange> split_utf8(const uint8_t* input,
                                      std::size_t input_length,
                                      std::size_t max_payload) {
  std::vector<FragmentRange> ranges;
  if (max_payload == 0 || input_length == 0) return ranges;

  std::size_t start = 0;
  while (start < input_length) {
    std::size_t end = start + max_payload;
    if (end >= input_length) {
      ranges.push_back({start, input_length - start});
      break;
    }
    // Back off while end points at a UTF-8 continuation byte (10xxxxxx).
    while (end > start && (input[end] & 0xC0) == 0x80) {
      --end;
    }
    if (end == start) {
      // Pathological: a single codepoint longer than max_payload. Emit as-is
      // by advancing to the next leading byte after start.
      end = start + 1;
      while (end < input_length && (input[end] & 0xC0) == 0x80) ++end;
    }
    ranges.push_back({start, end - start});
    start = end;
  }
  return ranges;
}

}  // namespace ble_protocol
