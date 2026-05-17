#include "subtitle_assembler.h"

#include <string.h>

namespace subtitle_assembler {

void SubtitleAssembler::reset() {
  active_ = false;
  current_seq_ = 0;
  expected_fragment_count_ = 0;
  next_expected_fragment_ = 0;
  assembled_length_ = 0;
}

void SubtitleAssembler::start_new_sequence(uint16_t sequence_id,
                                           uint8_t fragment_count) {
  active_ = true;
  current_seq_ = sequence_id;
  expected_fragment_count_ = fragment_count;
  next_expected_fragment_ = 0;
  assembled_length_ = 0;
}

FeedResult SubtitleAssembler::feed(uint16_t sequence_id,
                                   uint8_t fragment_index,
                                   uint8_t fragment_count,
                                   const uint8_t* payload,
                                   uint8_t payload_length) {
  if (fragment_count == 0 || fragment_count > MAX_FRAGMENTS) {
    // Cannot represent. Treat as a contract violation by the sender.
    reset();
    return FeedResult::Inconsistent;
  }
  if (fragment_index >= fragment_count) {
    reset();
    return FeedResult::Inconsistent;
  }

  // Sequence transition rules:
  //   - first fragment of a different sequence_id while assembling -> drop old
  //   - sequence_id matches but we are not active -> only legal if fragment 0
  //   - mid-sequence different sequence_id -> drop old, start fresh if frag 0
  const bool sequence_changed = !active_ || (sequence_id != current_seq_);
  if (sequence_changed) {
    if (fragment_index != 0) {
      // Sender sent a non-zero fragment without us having seen the start.
      // Possible if we missed the first fragment or sender skipped.
      reset();
      return FeedResult::OutOfOrder;
    }
    start_new_sequence(sequence_id, fragment_count);
  } else {
    // Continuing current sequence. Validate fragment_count is stable.
    if (fragment_count != expected_fragment_count_) {
      reset();
      return FeedResult::Inconsistent;
    }
    if (fragment_index != next_expected_fragment_) {
      reset();
      return FeedResult::OutOfOrder;
    }
  }

  // Append payload to assembled buffer.
  if (assembled_length_ + payload_length > ASSEMBLED_MAX) {
    reset();
    return FeedResult::Overflow;
  }
  if (payload_length > 0 && payload != nullptr) {
    memcpy(assembled_ + assembled_length_, payload, payload_length);
    assembled_length_ += payload_length;
  }
  next_expected_fragment_ = static_cast<uint8_t>(fragment_index + 1);

  if (next_expected_fragment_ == expected_fragment_count_) {
    completed_seq_ = current_seq_;
    active_ = false;
    return FeedResult::Complete;
  }
  return FeedResult::Incomplete;
}

}  // namespace subtitle_assembler
