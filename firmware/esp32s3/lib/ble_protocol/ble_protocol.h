#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

// LingoGlass AR BLE subtitle protocol. The packet layout is locked in
// docs/LingoGlass_AR_Development_Plan.md and .claude/skills/ble-protocol/SKILL.md.
// Do not change field sizes or order here without updating both documents
// and the shared test vectors in tests/ble_vectors.json.

namespace ble_protocol {

constexpr uint8_t PROTOCOL_VERSION = 0x01;
constexpr std::size_t HEADER_SIZE = 7;
constexpr std::size_t TRAILER_SIZE = 1;
constexpr std::size_t OVERHEAD = HEADER_SIZE + TRAILER_SIZE;
constexpr std::size_t MAX_PAYLOAD = 244;
constexpr std::size_t MAX_PACKET_SIZE = OVERHEAD + MAX_PAYLOAD;

enum class MessageType : uint8_t {
  Subtitle = 0x01,
  Status   = 0x02,
  Ack      = 0x03,
  Error    = 0x04,
};

struct PacketHeader {
  uint8_t  version;
  uint8_t  message_type;
  uint16_t sequence_id;
  uint8_t  fragment_index;
  uint8_t  fragment_count;
  uint8_t  payload_length;
};

struct DecodedPacket {
  PacketHeader header;
  const uint8_t* payload;  // pointer into the source buffer (no copy)
  std::size_t payload_length;
};

enum class DecodeStatus {
  Ok,
  TooShort,
  LengthMismatch,
  CrcMismatch,
  UnknownVersion,
  UnknownMessageType,
};

struct FragmentRange {
  std::size_t offset;
  std::size_t length;
};

uint8_t crc8(const uint8_t* data, std::size_t length);

// Encode a single fragment. Returns bytes written, or 0 if out_buffer is too small.
std::size_t encode_fragment(MessageType type,
                            uint16_t sequence_id,
                            uint8_t fragment_index,
                            uint8_t fragment_count,
                            const uint8_t* payload,
                            uint8_t payload_length,
                            uint8_t* out_buffer,
                            std::size_t out_buffer_size);

DecodeStatus decode_fragment(const uint8_t* data,
                             std::size_t length,
                             DecodedPacket& out_packet);

// Split UTF-8 input into fragment ranges that never cut inside a multi-byte
// codepoint. Each range length is at most max_payload.
std::vector<FragmentRange> split_utf8(const uint8_t* input,
                                      std::size_t input_length,
                                      std::size_t max_payload);

}  // namespace ble_protocol
