// Native-env unit tests for SubtitleAssembler. Run with:
//   pio test -e native -f test_subtitle_assembler
//
// Covers the multi-fragment reassembly rules locked in SKILL.md:
//   - single-fragment subtitle completes on the first feed
//   - multi-fragment in-order assembly produces concatenated payload
//   - out-of-order fragment_index returns OutOfOrder and resets the buffer
//   - changing fragment_count mid-sequence returns Inconsistent
//   - exceeding ASSEMBLED_MAX returns Overflow
//   - older sequence_id arriving mid-assembly returns Stale WITHOUT disturbing
//     the active buffer (the in-progress sequence must still be completable)
//   - sequence_id wrap-around is treated as newer
//   - newer sequence_id mid-assembly drops the old buffer and starts fresh

#include <unity.h>

#include <cstdint>
#include <cstring>
#include <vector>

#include "subtitle_assembler.h"

using subtitle_assembler::FeedResult;
using subtitle_assembler::SubtitleAssembler;

void setUp() {}
void tearDown() {}

namespace {

// Convenience: feed a fragment from a std::vector<uint8_t>.
FeedResult feed_vec(SubtitleAssembler& asm_, uint16_t seq, uint8_t idx,
                    uint8_t count, const std::vector<uint8_t>& payload) {
  return asm_.feed(seq, idx, count, payload.data(),
                   static_cast<uint8_t>(payload.size()));
}

}  // namespace

static void test_single_fragment_completes_immediately() {
  SubtitleAssembler asm_;
  const std::vector<uint8_t> p = {'H', 'i'};
  const auto r = feed_vec(asm_, 1, 0, 1, p);
  TEST_ASSERT_EQUAL_INT(static_cast<int>(FeedResult::Complete),
                        static_cast<int>(r));
  TEST_ASSERT_EQUAL_size_t(2, asm_.length());
  TEST_ASSERT_EQUAL_MEMORY(p.data(), asm_.assembled(), 2);
  TEST_ASSERT_EQUAL_UINT16(1, asm_.completed_sequence_id());
  TEST_ASSERT_FALSE(asm_.is_assembling());
}

static void test_multi_fragment_in_order_completes() {
  SubtitleAssembler asm_;
  const std::vector<uint8_t> a = {'A', 'B', 'C'};
  const std::vector<uint8_t> b = {'D', 'E'};
  const std::vector<uint8_t> c = {'F', 'G', 'H', 'I'};

  TEST_ASSERT_EQUAL_INT(static_cast<int>(FeedResult::Incomplete),
                        static_cast<int>(feed_vec(asm_, 42, 0, 3, a)));
  TEST_ASSERT_TRUE(asm_.is_assembling());
  TEST_ASSERT_EQUAL_INT(static_cast<int>(FeedResult::Incomplete),
                        static_cast<int>(feed_vec(asm_, 42, 1, 3, b)));
  TEST_ASSERT_EQUAL_INT(static_cast<int>(FeedResult::Complete),
                        static_cast<int>(feed_vec(asm_, 42, 2, 3, c)));
  TEST_ASSERT_FALSE(asm_.is_assembling());
  TEST_ASSERT_EQUAL_UINT16(42, asm_.completed_sequence_id());
  TEST_ASSERT_EQUAL_size_t(9, asm_.length());
  const char expected[] = "ABCDEFGHI";
  TEST_ASSERT_EQUAL_MEMORY(expected, asm_.assembled(), 9);
}

static void test_out_of_order_fragment_index_resets() {
  SubtitleAssembler asm_;
  TEST_ASSERT_EQUAL_INT(static_cast<int>(FeedResult::Incomplete),
                        static_cast<int>(feed_vec(asm_, 7, 0, 3, {'A'})));
  // Skip index 1, send index 2 -> OutOfOrder, buffer reset.
  TEST_ASSERT_EQUAL_INT(static_cast<int>(FeedResult::OutOfOrder),
                        static_cast<int>(feed_vec(asm_, 7, 2, 3, {'C'})));
  TEST_ASSERT_FALSE(asm_.is_assembling());
  // Old length was 1; reset must have cleared it.
  TEST_ASSERT_EQUAL_size_t(0, asm_.length());
}

static void test_fragment_count_change_mid_sequence_returns_inconsistent() {
  SubtitleAssembler asm_;
  TEST_ASSERT_EQUAL_INT(static_cast<int>(FeedResult::Incomplete),
                        static_cast<int>(feed_vec(asm_, 5, 0, 3, {'X'})));
  // Same seq, but fragment_count flipped from 3 to 2.
  TEST_ASSERT_EQUAL_INT(static_cast<int>(FeedResult::Inconsistent),
                        static_cast<int>(feed_vec(asm_, 5, 1, 2, {'Y'})));
  TEST_ASSERT_FALSE(asm_.is_assembling());
}

static void test_fragment_count_zero_returns_inconsistent() {
  SubtitleAssembler asm_;
  TEST_ASSERT_EQUAL_INT(static_cast<int>(FeedResult::Inconsistent),
                        static_cast<int>(feed_vec(asm_, 1, 0, 0, {'A'})));
}

static void test_fragment_index_ge_count_returns_inconsistent() {
  SubtitleAssembler asm_;
  TEST_ASSERT_EQUAL_INT(static_cast<int>(FeedResult::Inconsistent),
                        static_cast<int>(feed_vec(asm_, 1, 3, 3, {'A'})));
}

static void test_overflow_returns_overflow() {
  SubtitleAssembler asm_;
  // ASSEMBLED_MAX = 1024. Build a payload that exceeds it across many fragments.
  // 64 fragments * 17 bytes = 1088 bytes > 1024.
  const std::vector<uint8_t> chunk(17, 'Z');
  const uint8_t total = 64;
  FeedResult last = FeedResult::Incomplete;
  for (uint8_t i = 0; i < total; ++i) {
    last = feed_vec(asm_, 9, i, total, chunk);
    if (last == FeedResult::Overflow) break;
  }
  TEST_ASSERT_EQUAL_INT(static_cast<int>(FeedResult::Overflow),
                        static_cast<int>(last));
  TEST_ASSERT_FALSE(asm_.is_assembling());
}

static void test_fragment_count_above_max_returns_inconsistent() {
  SubtitleAssembler asm_;
  // MAX_FRAGMENTS = 64. Anything above must be rejected before any allocation.
  TEST_ASSERT_EQUAL_INT(
      static_cast<int>(FeedResult::Inconsistent),
      static_cast<int>(feed_vec(asm_, 1, 0, 65, {'A'})));
}

static void test_stale_older_seq_does_not_disturb_active() {
  SubtitleAssembler asm_;
  // Start assembling seq=10, get 2 of 3 fragments in.
  TEST_ASSERT_EQUAL_INT(static_cast<int>(FeedResult::Incomplete),
                        static_cast<int>(feed_vec(asm_, 10, 0, 3, {'A', 'B'})));
  TEST_ASSERT_EQUAL_INT(static_cast<int>(FeedResult::Incomplete),
                        static_cast<int>(feed_vec(asm_, 10, 1, 3, {'C'})));
  TEST_ASSERT_TRUE(asm_.is_assembling());

  // Stale older seq arrives. Must be rejected with Stale and NOT reset.
  TEST_ASSERT_EQUAL_INT(static_cast<int>(FeedResult::Stale),
                        static_cast<int>(feed_vec(asm_, 9, 0, 1, {'X'})));
  TEST_ASSERT_TRUE(asm_.is_assembling());

  // Complete the original seq=10 - should still work.
  TEST_ASSERT_EQUAL_INT(
      static_cast<int>(FeedResult::Complete),
      static_cast<int>(feed_vec(asm_, 10, 2, 3, {'D', 'E', 'F'})));
  TEST_ASSERT_EQUAL_UINT16(10, asm_.completed_sequence_id());
  TEST_ASSERT_EQUAL_size_t(6, asm_.length());
  const char expected[] = "ABCDEF";
  TEST_ASSERT_EQUAL_MEMORY(expected, asm_.assembled(), 6);
}

static void test_newer_seq_mid_assembly_drops_old_starts_fresh() {
  SubtitleAssembler asm_;
  TEST_ASSERT_EQUAL_INT(static_cast<int>(FeedResult::Incomplete),
                        static_cast<int>(feed_vec(asm_, 5, 0, 2, {'A', 'B'})));
  // Newer seq arrives at frag 0 -> drop seq=5, start seq=6.
  TEST_ASSERT_EQUAL_INT(static_cast<int>(FeedResult::Complete),
                        static_cast<int>(feed_vec(asm_, 6, 0, 1, {'Z'})));
  TEST_ASSERT_EQUAL_UINT16(6, asm_.completed_sequence_id());
  TEST_ASSERT_EQUAL_size_t(1, asm_.length());
  TEST_ASSERT_EQUAL_UINT8('Z', asm_.assembled()[0]);
}

static void test_newer_seq_skipping_first_fragment_returns_outoforder() {
  SubtitleAssembler asm_;
  TEST_ASSERT_EQUAL_INT(static_cast<int>(FeedResult::Incomplete),
                        static_cast<int>(feed_vec(asm_, 5, 0, 2, {'A'})));
  // Newer seq but skipping frag 0 -> OutOfOrder, both dropped.
  TEST_ASSERT_EQUAL_INT(static_cast<int>(FeedResult::OutOfOrder),
                        static_cast<int>(feed_vec(asm_, 6, 1, 2, {'Y'})));
  TEST_ASSERT_FALSE(asm_.is_assembling());
}

static void test_seq_wrap_around_treated_as_newer() {
  SubtitleAssembler asm_;
  // Start at seq=0xFFFF mid-assembly.
  TEST_ASSERT_EQUAL_INT(static_cast<int>(FeedResult::Incomplete),
                        static_cast<int>(feed_vec(asm_, 0xFFFF, 0, 2, {'A'})));
  // Wrap to seq=0 - must be treated as newer, dropping 0xFFFF buffer.
  TEST_ASSERT_EQUAL_INT(static_cast<int>(FeedResult::Complete),
                        static_cast<int>(feed_vec(asm_, 0x0000, 0, 1, {'B'})));
  TEST_ASSERT_EQUAL_UINT16(0x0000, asm_.completed_sequence_id());
}

static void test_reset_clears_state() {
  SubtitleAssembler asm_;
  feed_vec(asm_, 1, 0, 2, {'A'});
  TEST_ASSERT_TRUE(asm_.is_assembling());
  asm_.reset();
  TEST_ASSERT_FALSE(asm_.is_assembling());
  TEST_ASSERT_EQUAL_size_t(0, asm_.length());
  // After reset, a fragment with index != 0 must be rejected.
  TEST_ASSERT_EQUAL_INT(static_cast<int>(FeedResult::OutOfOrder),
                        static_cast<int>(feed_vec(asm_, 7, 1, 2, {'X'})));
}

static void test_non_zero_fragment_index_when_idle_rejected() {
  SubtitleAssembler asm_;
  TEST_ASSERT_EQUAL_INT(static_cast<int>(FeedResult::OutOfOrder),
                        static_cast<int>(feed_vec(asm_, 1, 1, 2, {'A'})));
  TEST_ASSERT_FALSE(asm_.is_assembling());
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_single_fragment_completes_immediately);
  RUN_TEST(test_multi_fragment_in_order_completes);
  RUN_TEST(test_out_of_order_fragment_index_resets);
  RUN_TEST(test_fragment_count_change_mid_sequence_returns_inconsistent);
  RUN_TEST(test_fragment_count_zero_returns_inconsistent);
  RUN_TEST(test_fragment_index_ge_count_returns_inconsistent);
  RUN_TEST(test_overflow_returns_overflow);
  RUN_TEST(test_fragment_count_above_max_returns_inconsistent);
  RUN_TEST(test_stale_older_seq_does_not_disturb_active);
  RUN_TEST(test_newer_seq_mid_assembly_drops_old_starts_fresh);
  RUN_TEST(test_newer_seq_skipping_first_fragment_returns_outoforder);
  RUN_TEST(test_seq_wrap_around_treated_as_newer);
  RUN_TEST(test_reset_clears_state);
  RUN_TEST(test_non_zero_fragment_index_when_idle_rejected);
  return UNITY_END();
}
