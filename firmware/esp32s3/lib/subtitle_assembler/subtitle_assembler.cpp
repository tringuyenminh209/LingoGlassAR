#include "subtitle_assembler.h"

#include <string.h>

namespace subtitle_assembler {

namespace {
// True if `candidate` is strictly newer than `reference` under 16-bit wrap.
// Treats the half-circle (32768) as the boundary; older fragments arriving
// late are rejected as Stale.
bool is_newer_seq(uint16_t candidate, uint16_t reference) {
  return static_cast<int16_t>(static_cast<uint16_t>(candidate - reference)) > 0;
}
}  // namespace

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
  // STALE CHECK MUST RUN BEFORE ANY VALIDATION THAT CALLS reset().
  // A stale fragment may have garbage fragment_count / fragment_index fields
  // (sender retry of a long-discarded sequence, or a hostile/malformed
  // packet). If we validated first, a stale packet with fragment_count==0
  // or fragment_index>=fragment_count would reset() the active buffer for
  // the *current* (newer) sequence - destroying legitimate in-progress work.
  // The fix is to classify by sequence_id first, then validate.
  if (active_ && sequence_id != current_seq_ &&
      !is_newer_seq(sequence_id, current_seq_)) {
    return FeedResult::Stale;
  }

  if (fragment_count == 0 || fragment_count > MAX_FRAGMENTS) {
    // Cannot represent. Treat as a contract violation by the sender.
    reset();
    return FeedResult::Inconsistent;
  }
  if (fragment_index >= fragment_count) {
    reset();
    return FeedResult::Inconsistent;
  }

  // Sequence transition rules (see SKILL.md "Render rules"). At this point
  // we know any sequence_id mismatch is a NEWER sequence (older was already
  // short-circuited above as Stale).
  //   - Continuing current sequence: validate fragment_index in order.
  //   - Newer sequence_id while assembling: drop old, start new at frag 0.
  //   - Not active: any fragment with index == 0 starts a fresh assembly.
  //     Non-zero index without context is OutOfOrder.
  if (active_) {
    if (sequence_id == current_seq_) {
      if (fragment_count != expected_fragment_count_) {
        reset();
        return FeedResult::Inconsistent;
      }
      if (fragment_index != next_expected_fragment_) {
        reset();
        return FeedResult::OutOfOrder;
      }
    } else {
      // Must be newer (older was returned as Stale above).
      if (fragment_index != 0) {
        // New sequence skipped its first fragment. Drop both and report.
        reset();
        return FeedResult::OutOfOrder;
      }
      start_new_sequence(sequence_id, fragment_count);
    }
  } else {
    if (fragment_index != 0) {
      return FeedResult::OutOfOrder;
    }
    start_new_sequence(sequence_id, fragment_count);
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
