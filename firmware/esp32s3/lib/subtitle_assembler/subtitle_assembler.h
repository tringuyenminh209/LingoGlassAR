// SubtitleAssembler - reassembles multi-fragment subtitle packets keyed by
// sequence_id. Single-fragment subtitles complete on the first feed() call.
//
// Assumes fragments for a given sequence_id arrive in fragment_index order.
// BLE write-without-response is ordered per-characteristic per-connection, so
// in S0 we can rely on this. Out-of-order is reported as an error to the
// caller (sender will retry the whole sequence with a new sequence_id).
//
// A newer sequence_id silently drops any in-progress buffer for the older
// sequence. This is the documented render rule from SKILL.md.
//
// Static storage. No heap allocation. Safe to call from a BLE callback.

#pragma once

#include <stddef.h>
#include <stdint.h>

namespace subtitle_assembler {

// Caps tuned for S0 OLED text:
//   - ASSEMBLED_MAX = 1024 bytes covers ~340 Japanese chars (3 bytes/char UTF-8)
//     which is far more than the OLED can display, but leaves headroom for
//     stress tests.
//   - MAX_FRAGMENTS = 64 covers the worst-case MTU 23 path: 12 byte payload
//     per fragment * 64 = 768 bytes, larger than ASSEMBLED_MAX.
constexpr size_t ASSEMBLED_MAX = 1024;
constexpr uint8_t MAX_FRAGMENTS = 64;

enum class FeedResult : uint8_t {
  Incomplete,     // fragment accepted, more expected
  Complete,       // assembled payload ready; read via assembled()/length()
  OutOfOrder,     // fragment_index != next expected for this sequence
  Inconsistent,   // fragment_count changed mid-sequence, or count == 0
  Overflow,       // would exceed ASSEMBLED_MAX
};

class SubtitleAssembler {
 public:
  // Feed one decoded subtitle fragment. The caller has already validated CRC
  // and header (via ble_protocol::decode_fragment) and confirmed message_type
  // is Subtitle.
  //
  // Returns Complete on the final fragment of a sequence. After Complete,
  // call assembled() / length() / completed_sequence_id() before the next
  // feed() (which may reset state).
  FeedResult feed(uint16_t sequence_id,
                  uint8_t fragment_index,
                  uint8_t fragment_count,
                  const uint8_t* payload,
                  uint8_t payload_length);

  // Buffer holding the most recently completed payload. Stable until reset()
  // or the next feed() that starts a new sequence.
  const uint8_t* assembled() const { return assembled_; }
  size_t length() const { return assembled_length_; }
  uint16_t completed_sequence_id() const { return completed_seq_; }

  // Clear all state. Use on disconnect.
  void reset();

  // True between the first fragment of a sequence and Complete/error.
  bool is_assembling() const { return active_; }

 private:
  void start_new_sequence(uint16_t sequence_id, uint8_t fragment_count);

  bool active_ = false;
  uint16_t current_seq_ = 0;
  uint8_t expected_fragment_count_ = 0;
  uint8_t next_expected_fragment_ = 0;

  uint8_t assembled_[ASSEMBLED_MAX] = {0};
  size_t assembled_length_ = 0;
  uint16_t completed_seq_ = 0;
};

}  // namespace subtitle_assembler
