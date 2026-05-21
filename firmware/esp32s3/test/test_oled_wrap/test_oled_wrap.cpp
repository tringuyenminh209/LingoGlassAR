#include <unity.h>

#include <cstring>
#include <string>

#include "oled_view.h"

void setUp() {}
void tearDown() {}

namespace {

int byte_width(const char* slice) {
  return static_cast<int>(std::strlen(slice)) * 4;
}

bool starts_on_utf8_boundary(const std::string& line) {
  if (line.empty()) return true;
  return (static_cast<uint8_t>(line[0]) & 0xC0) != 0x80;
}

bool ends_on_utf8_boundary(const std::string& line) {
  if (line.empty()) return true;
  size_t index = line.size() - 1;
  while (index > 0 && (static_cast<uint8_t>(line[index]) & 0xC0) == 0x80) {
    --index;
  }
  const uint8_t lead = static_cast<uint8_t>(line[index]);
  size_t bytes = 1;
  if ((lead & 0xE0) == 0xC0) bytes = 2;
  if ((lead & 0xF0) == 0xE0) bytes = 3;
  if ((lead & 0xF8) == 0xF0) bytes = 4;
  return index + bytes == line.size();
}

}  // namespace

static void test_empty_string_returns_no_lines() {
  const auto lines = oled_view::wrap_utf8_lines("", 128, byte_width);
  TEST_ASSERT_EQUAL_size_t(0u, lines.lines.size());
  TEST_ASSERT_FALSE(lines.truncated);
}

static void test_short_jp_that_fits_stays_on_one_line() {
  const char jp[] = "\xE3\x81\x93\xE3\x82\x93\xE3\x81\xAB";
  const auto lines = oled_view::wrap_utf8_lines(jp, 128, byte_width);
  TEST_ASSERT_EQUAL_size_t(1u, lines.lines.size());
  TEST_ASSERT_EQUAL_STRING(jp, lines.lines[0].c_str());
}

static void test_long_jp_wraps_at_codepoint_boundary_at_width_edge() {
  const char jp[] =
      "\xE6\x97\xA5\xE6\x9C\xAC\xE8\xAA\x9E\xE6\x97\xA5\xE6\x9C\xAC"
      "\xE8\xAA\x9E\xE6\x97\xA5\xE6\x9C\xAC\xE8\xAA\x9E";
  const auto lines = oled_view::wrap_utf8_lines(jp, 24, byte_width);
  TEST_ASSERT_TRUE(lines.lines.size() > 1u);
  for (const auto& line : lines.lines) {
    TEST_ASSERT_TRUE(starts_on_utf8_boundary(line));
    TEST_ASSERT_TRUE(ends_on_utf8_boundary(line));
    TEST_ASSERT_TRUE(byte_width(line.c_str()) <= 24);
  }
}

static void test_long_vn_wraps_at_word_boundaries_when_possible() {
  const auto lines =
      oled_view::wrap_utf8_lines("mot cau tieng viet rat dai", 48, byte_width);
  TEST_ASSERT_TRUE(lines.lines.size() > 1u);
  TEST_ASSERT_EQUAL_STRING("mot cau", lines.lines[0].c_str());
  TEST_ASSERT_EQUAL_STRING("tieng viet", lines.lines[1].c_str());
}

static void test_mixed_jp_vn_ascii_wraps_cleanly() {
  const char mixed[] = "JP "
                       "\xE6\x97\xA5\xE6\x9C\xAC"
                       " xin chao 123";
  const auto lines = oled_view::wrap_utf8_lines(mixed, 32, byte_width);
  TEST_ASSERT_TRUE(lines.lines.size() > 1u);
  for (const auto& line : lines.lines) {
    TEST_ASSERT_TRUE(starts_on_utf8_boundary(line));
    TEST_ASSERT_TRUE(ends_on_utf8_boundary(line));
  }
}

static void test_line_cap_truncates_with_trailing_marker() {
  std::string text;
  for (size_t index = 0; index < 80; ++index) {
    text += "word ";
  }

  const auto lines = oled_view::wrap_utf8_lines(text.c_str(), 16, byte_width);
  TEST_ASSERT_EQUAL_size_t(oled_view::MAX_WRAPPED_LINES, lines.lines.size());
  TEST_ASSERT_TRUE(lines.truncated);
  TEST_ASSERT_TRUE(lines.lines.back().find("\xE2\x80\xA6") !=
                   std::string::npos);
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_empty_string_returns_no_lines);
  RUN_TEST(test_short_jp_that_fits_stays_on_one_line);
  RUN_TEST(test_long_jp_wraps_at_codepoint_boundary_at_width_edge);
  RUN_TEST(test_long_vn_wraps_at_word_boundaries_when_possible);
  RUN_TEST(test_mixed_jp_vn_ascii_wraps_cleanly);
  RUN_TEST(test_line_cap_truncates_with_trailing_marker);
  return UNITY_END();
}
