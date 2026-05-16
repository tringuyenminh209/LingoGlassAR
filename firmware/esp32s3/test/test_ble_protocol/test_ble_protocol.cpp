// Native-env unit tests for ble_protocol. Run with:
//   pio test -e native
//
// Vectors mirror tests/ble_vectors.json. When updating one side, update both.

#include <unity.h>

#include <cstdint>
#include <cstring>
#include <vector>

#include "ble_protocol.h"

using namespace ble_protocol;

void setUp() {}
void tearDown() {}

static void test_crc8_subtitle_A_seq1() {
  const uint8_t bytes[] = {0x01, 0x01, 0x01, 0x00, 0x00, 0x01, 0x01, 0x41};
  TEST_ASSERT_EQUAL_HEX8(0x5B, crc8(bytes, sizeof(bytes)));
}

static void test_crc8_subtitle_Hello_seq2() {
  const uint8_t bytes[] = {0x01, 0x01, 0x02, 0x00, 0x00, 0x01, 0x05,
                           0x48, 0x65, 0x6C, 0x6C, 0x6F};
  TEST_ASSERT_EQUAL_HEX8(0x36, crc8(bytes, sizeof(bytes)));
}

static void test_crc8_subtitle_jp_ko_seq3() {
  const uint8_t bytes[] = {0x01, 0x01, 0x03, 0x00, 0x00, 0x01, 0x03,
                           0xE3, 0x81, 0x93};
  TEST_ASSERT_EQUAL_HEX8(0x5C, crc8(bytes, sizeof(bytes)));
}

static void test_crc8_seq_wrap_FFFF_frag1of2_AB() {
  const uint8_t bytes[] = {0x01, 0x01, 0xFF, 0xFF, 0x01, 0x02, 0x02,
                           0x41, 0x42};
  TEST_ASSERT_EQUAL_HEX8(0x9E, crc8(bytes, sizeof(bytes)));
}

static void test_crc8_ack_seq1() {
  const uint8_t bytes[] = {0x01, 0x03, 0x01, 0x00, 0x00, 0x01, 0x02,
                           0x01, 0x00};
  TEST_ASSERT_EQUAL_HEX8(0x46, crc8(bytes, sizeof(bytes)));
}

static void test_encode_subtitle_A_seq1_matches_vector() {
  const uint8_t payload[] = {0x41};
  uint8_t out[64];
  std::size_t n = encode_fragment(MessageType::Subtitle, 1, 0, 1,
                                  payload, sizeof(payload),
                                  out, sizeof(out));
  TEST_ASSERT_EQUAL_size_t(9u, n);
  const uint8_t expected[] = {0x01, 0x01, 0x01, 0x00, 0x00, 0x01, 0x01, 0x41, 0x5B};
  TEST_ASSERT_EQUAL_HEX8_ARRAY(expected, out, sizeof(expected));
}

static void test_encode_returns_zero_when_buffer_too_small() {
  const uint8_t payload[] = {0x41};
  uint8_t small[4];
  std::size_t n = encode_fragment(MessageType::Subtitle, 1, 0, 1,
                                  payload, 1, small, sizeof(small));
  TEST_ASSERT_EQUAL_size_t(0u, n);
}

static void test_encode_rejects_index_ge_count() {
  const uint8_t payload[] = {0x41};
  uint8_t out[64];
  std::size_t n = encode_fragment(MessageType::Subtitle, 1, 2, 2,
                                  payload, 1, out, sizeof(out));
  TEST_ASSERT_EQUAL_size_t(0u, n);
}

static void test_decode_ok_subtitle_A_seq1() {
  const uint8_t bytes[] = {0x01, 0x01, 0x01, 0x00, 0x00, 0x01, 0x01, 0x41, 0x5B};
  DecodedPacket pkt;
  TEST_ASSERT_EQUAL(static_cast<int>(DecodeStatus::Ok),
                    static_cast<int>(decode_fragment(bytes, sizeof(bytes), pkt)));
  TEST_ASSERT_EQUAL_UINT8(0x01, pkt.header.version);
  TEST_ASSERT_EQUAL_UINT8(0x01, pkt.header.message_type);
  TEST_ASSERT_EQUAL_UINT16(1u, pkt.header.sequence_id);
  TEST_ASSERT_EQUAL_UINT8(0u, pkt.header.fragment_index);
  TEST_ASSERT_EQUAL_UINT8(1u, pkt.header.fragment_count);
  TEST_ASSERT_EQUAL_UINT8(1u, pkt.header.payload_length);
  TEST_ASSERT_EQUAL_size_t(1u, pkt.payload_length);
  TEST_ASSERT_EQUAL_UINT8(0x41, pkt.payload[0]);
}

static void test_decode_sequence_id_is_little_endian() {
  // sequence_id = 0xBEEF -> bytes EF BE
  uint8_t bytes[9] = {0x01, 0x01, 0xEF, 0xBE, 0x00, 0x01, 0x01, 0x41, 0x00};
  bytes[8] = crc8(bytes, 8);
  DecodedPacket pkt;
  TEST_ASSERT_EQUAL(static_cast<int>(DecodeStatus::Ok),
                    static_cast<int>(decode_fragment(bytes, sizeof(bytes), pkt)));
  TEST_ASSERT_EQUAL_UINT16(0xBEEFu, pkt.header.sequence_id);
}

static void test_decode_rejects_crc_mismatch() {
  uint8_t bytes[] = {0x01, 0x01, 0x01, 0x00, 0x00, 0x01, 0x01, 0x41, 0x00};
  DecodedPacket pkt;
  TEST_ASSERT_EQUAL(static_cast<int>(DecodeStatus::CrcMismatch),
                    static_cast<int>(decode_fragment(bytes, sizeof(bytes), pkt)));
}

static void test_decode_rejects_length_mismatch() {
  // payload_length says 5 but only 1 byte present
  const uint8_t bytes[] = {0x01, 0x01, 0x01, 0x00, 0x00, 0x01, 0x05, 0x41, 0x5B};
  DecodedPacket pkt;
  TEST_ASSERT_EQUAL(static_cast<int>(DecodeStatus::LengthMismatch),
                    static_cast<int>(decode_fragment(bytes, sizeof(bytes), pkt)));
}

static void test_decode_rejects_unknown_version() {
  const uint8_t bytes[] = {0xFF, 0x01, 0x01, 0x00, 0x00, 0x01, 0x01, 0x41, 0x00};
  DecodedPacket pkt;
  TEST_ASSERT_EQUAL(static_cast<int>(DecodeStatus::UnknownVersion),
                    static_cast<int>(decode_fragment(bytes, sizeof(bytes), pkt)));
}

static void test_split_utf8_jp_konnichiwa_max7() {
  // U+3053 U+3093 U+306B U+3061 U+306F = E38193 E38293 E381AB E381A1 E381AF
  const uint8_t input[] = {
    0xE3, 0x81, 0x93, 0xE3, 0x82, 0x93, 0xE3, 0x81, 0xAB,
    0xE3, 0x81, 0xA1, 0xE3, 0x81, 0xAF
  };
  auto ranges = split_utf8(input, sizeof(input), 7);
  TEST_ASSERT_EQUAL_size_t(3u, ranges.size());
  TEST_ASSERT_EQUAL_size_t(0u, ranges[0].offset);
  TEST_ASSERT_EQUAL_size_t(6u, ranges[0].length);
  TEST_ASSERT_EQUAL_size_t(6u, ranges[1].offset);
  TEST_ASSERT_EQUAL_size_t(6u, ranges[1].length);
  TEST_ASSERT_EQUAL_size_t(12u, ranges[2].offset);
  TEST_ASSERT_EQUAL_size_t(3u, ranges[2].length);
}

static void test_split_utf8_ascii_exact_multiples() {
  const uint8_t input[] = {'a','b','c','d','e','f','g','h','i','j'};
  auto ranges = split_utf8(input, sizeof(input), 4);
  TEST_ASSERT_EQUAL_size_t(3u, ranges.size());
  TEST_ASSERT_EQUAL_size_t(4u, ranges[0].length);
  TEST_ASSERT_EQUAL_size_t(4u, ranges[1].length);
  TEST_ASSERT_EQUAL_size_t(2u, ranges[2].length);
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_crc8_subtitle_A_seq1);
  RUN_TEST(test_crc8_subtitle_Hello_seq2);
  RUN_TEST(test_crc8_subtitle_jp_ko_seq3);
  RUN_TEST(test_crc8_seq_wrap_FFFF_frag1of2_AB);
  RUN_TEST(test_crc8_ack_seq1);
  RUN_TEST(test_encode_subtitle_A_seq1_matches_vector);
  RUN_TEST(test_encode_returns_zero_when_buffer_too_small);
  RUN_TEST(test_encode_rejects_index_ge_count);
  RUN_TEST(test_decode_ok_subtitle_A_seq1);
  RUN_TEST(test_decode_sequence_id_is_little_endian);
  RUN_TEST(test_decode_rejects_crc_mismatch);
  RUN_TEST(test_decode_rejects_length_mismatch);
  RUN_TEST(test_decode_rejects_unknown_version);
  RUN_TEST(test_split_utf8_jp_konnichiwa_max7);
  RUN_TEST(test_split_utf8_ascii_exact_multiples);
  return UNITY_END();
}
