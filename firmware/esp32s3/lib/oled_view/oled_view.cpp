#include "oled_view.h"

#include <algorithm>
#include <cstring>

#if defined(ARDUINO)
#include <Arduino.h>
#include <U8g2lib.h>
#include <Wire.h>
#endif

namespace {

constexpr int OLED_WIDTH_PX = 128;
constexpr int OLED_HEIGHT_PX = 64;
constexpr uint32_t PAGE_HOLD_MS = 2500;
constexpr const char* kTruncationMarker = "\xE2\x80\xA6";

bool is_continuation(uint8_t byte) { return (byte & 0xC0) == 0x80; }

size_t next_utf8_boundary(const char* text, size_t length, size_t offset) {
  if (offset >= length) return length;
  const uint8_t lead = static_cast<uint8_t>(text[offset]);
  size_t bytes = 1;
  if ((lead & 0x80) == 0) {
    bytes = 1;
  } else if ((lead & 0xE0) == 0xC0) {
    bytes = 2;
  } else if ((lead & 0xF0) == 0xE0) {
    bytes = 3;
  } else if ((lead & 0xF8) == 0xF0) {
    bytes = 4;
  }

  const size_t end = std::min(length, offset + bytes);
  for (size_t index = offset + 1; index < end; ++index) {
    if (!is_continuation(static_cast<uint8_t>(text[index]))) {
      return index;
    }
  }
  return end;
}

size_t previous_utf8_boundary(const std::string& text, size_t offset) {
  if (offset == 0) return 0;
  size_t boundary = std::min(offset - 1, text.size() - 1);
  while (boundary > 0 &&
         is_continuation(static_cast<uint8_t>(text[boundary]))) {
    --boundary;
  }
  return boundary;
}

bool is_break_space(uint8_t byte) {
  return byte == ' ' || byte == '\t' || byte == '\n' || byte == '\r';
}

bool is_ascii_punctuation(uint8_t byte) {
  return byte == ',' || byte == '.' || byte == '!' || byte == '?' ||
         byte == ':' || byte == ';' || byte == '-' || byte == '/';
}

std::string trimmed_slice(const char* text, size_t start, size_t end) {
  while (end > start && is_break_space(static_cast<uint8_t>(text[end - 1]))) {
    --end;
  }
  return std::string(text + start, end - start);
}

void skip_leading_spaces(const char* text, size_t length, size_t& offset) {
  while (offset < length &&
         is_break_space(static_cast<uint8_t>(text[offset]))) {
    ++offset;
  }
}

void add_truncation_marker(oled_view::WrappedLines& wrapped,
                           int max_width_px,
                           const oled_view::Utf8WidthFn& width) {
  if (wrapped.lines.empty()) return;

  std::string& last = wrapped.lines.back();
  std::string candidate = last + kTruncationMarker;
  while (!last.empty() && width(candidate.c_str()) > max_width_px) {
    last.erase(previous_utf8_boundary(last, last.size()));
    candidate = last + kTruncationMarker;
  }
  last = candidate;
}

#if defined(ARDUINO)

struct FontChoice {
  const uint8_t* font;
  uint8_t line_height;
};

// Full-buffer SSD1306 over hardware I2C. Reset pin is not wired on the
// modules we target, so U8X8_PIN_NONE. Wire must already be begun by main.
U8G2_SSD1306_128X64_NONAME_F_HW_I2C g_display(U8G2_R0, U8X8_PIN_NONE);
bool g_ready = false;
std::string g_header;
std::vector<std::string> g_body_lines;
FontChoice g_body_font = {u8g2_font_unifont_t_vietnamese1, 16};
std::vector<size_t> g_page_starts;
size_t g_page_index = 0;
size_t g_page_count = 0;
uint32_t g_next_page_ms = 0;

// Hiragana, Katakana, and CJK ideographs use leading UTF-8 bytes
// 0xE3-0xE9. Vietnamese precomposed diacritics use Latin coverage.
FontChoice pick_font(const char* utf8) {
  if (utf8 != nullptr) {
    for (const uint8_t* p = reinterpret_cast<const uint8_t*>(utf8); *p != 0;
         ++p) {
      if (*p >= 0xE3 && *p <= 0xE9) {
        return {u8g2_font_b12_t_japanese2, 12};
      }
    }
  }
  return {u8g2_font_unifont_t_vietnamese1, 16};
}

uint8_t header_height() {
  if (g_header.empty()) return 0;
  return pick_font(g_header.c_str()).line_height;
}

void compute_pages() {
  g_page_starts.clear();
  if (g_body_lines.empty()) {
    g_page_count = 0;
    return;
  }

  g_page_starts.push_back(0);
  int y = header_height();
  for (size_t index = 0; index < g_body_lines.size(); ++index) {
    const uint8_t line_height =
        pick_font(g_body_lines[index].c_str()).line_height;
    const bool starts_page = index == g_page_starts.back();
    if (!starts_page && y + line_height > OLED_HEIGHT_PX) {
      g_page_starts.push_back(index);
      y = header_height();
    }
    y += line_height;
  }
  g_page_count = g_page_starts.size();
}

void draw_current_page() {
  if (!g_ready) return;

  g_display.clearBuffer();
  g_display.setFontPosTop();
  if (!g_header.empty()) {
    const FontChoice header_font = pick_font(g_header.c_str());
    g_display.setFont(header_font.font);
    g_display.drawUTF8(0, 0, g_header.c_str());
  }

  const size_t first_line =
      g_page_index < g_page_starts.size() ? g_page_starts[g_page_index] : 0;
  const size_t last_line = g_page_index + 1 < g_page_starts.size()
                               ? g_page_starts[g_page_index + 1]
                               : g_body_lines.size();
  int y = header_height();
  for (size_t index = first_line; index < last_line; ++index) {
    const FontChoice line_font = pick_font(g_body_lines[index].c_str());
    g_display.setFont(line_font.font);
    g_display.drawUTF8(0, y, g_body_lines[index].c_str());
    y += line_font.line_height;
  }

  g_display.sendBuffer();
}

void reset_paging_clock(uint32_t now_ms) {
  if (g_page_count <= 1) {
    g_next_page_ms = 0;
    return;
  }
  const bool last_page = g_page_index + 1 == g_page_count;
  g_next_page_ms = now_ms + (last_page ? PAGE_HOLD_MS * 2 : PAGE_HOLD_MS);
}

void clear_paging_state() {
  g_body_lines.clear();
  g_page_starts.clear();
  g_page_index = 0;
  g_page_count = 0;
  g_next_page_ms = 0;
}

#endif

}  // namespace

namespace oled_view {

WrappedLines wrap_utf8_lines(const char* utf8,
                             int max_width_px,
                             const Utf8WidthFn& width) {
  WrappedLines wrapped;
  if (utf8 == nullptr || utf8[0] == '\0' || max_width_px <= 0 || !width) {
    return wrapped;
  }

  const size_t length = std::strlen(utf8);
  size_t line_start = 0;
  skip_leading_spaces(utf8, length, line_start);

  while (line_start < length) {
    size_t scan = line_start;
    size_t last_fit = line_start;
    size_t last_break = line_start;
    bool overflow = false;

    while (scan < length) {
      const size_t next = next_utf8_boundary(utf8, length, scan);
      const std::string candidate(utf8 + line_start, next - line_start);
      if (width(candidate.c_str()) > max_width_px) {
        overflow = true;
        break;
      }

      last_fit = next;
      const uint8_t current = static_cast<uint8_t>(utf8[scan]);
      if (is_break_space(current)) {
        last_break = scan;
      } else if (next == scan + 1 && is_ascii_punctuation(current)) {
        last_break = next;
      }
      scan = next;
    }

    size_t line_end = overflow ? last_break : length;
    if (line_end <= line_start) {
      line_end = overflow && last_fit > line_start
                     ? last_fit
                     : next_utf8_boundary(utf8, length, line_start);
    }

    wrapped.lines.push_back(trimmed_slice(utf8, line_start, line_end));
    line_start = line_end;
    skip_leading_spaces(utf8, length, line_start);

    if (wrapped.lines.size() == MAX_WRAPPED_LINES && line_start < length) {
      wrapped.truncated = true;
      add_truncation_marker(wrapped, max_width_px, width);
      return wrapped;
    }
  }

  return wrapped;
}

#if defined(ARDUINO)

bool begin(uint8_t i2c_address_7bit) {
  g_display.setI2CAddress(static_cast<uint8_t>(i2c_address_7bit << 1));
  g_ready = g_display.begin();
  if (!g_ready) {
    return false;
  }
  g_display.setFont(u8g2_font_b12_t_japanese2);
  g_display.setFontPosTop();
  g_display.clearBuffer();
  g_display.sendBuffer();
  return true;
}

bool is_ready() { return g_ready; }

void show_status(const char* line1, const char* line2) {
  if (!g_ready) return;

  g_header = line1 == nullptr ? "" : line1;
  clear_paging_state();

  if (line2 != nullptr && line2[0] != '\0') {
    g_body_font = pick_font(line2);
    g_display.setFont(g_body_font.font);
    g_body_lines = wrap_utf8_lines(
                       line2, OLED_WIDTH_PX,
                       [](const char* slice) {
                         return static_cast<int>(g_display.getUTF8Width(slice));
                       })
                       .lines;
    compute_pages();
  }

  draw_current_page();
  reset_paging_clock(millis());
}

void show_heartbeat(uint32_t counter) {
  if (!g_ready) return;
  char line2[24];
  snprintf(line2, sizeof(line2), "Heartbeat: %lu",
           static_cast<unsigned long>(counter));
  show_status("LingoGlass S0", line2);
  g_next_page_ms = 0;
}

void tick(uint32_t now_ms) {
  if (!g_ready || g_page_count <= 1 || g_next_page_ms == 0) return;
  if (static_cast<int32_t>(now_ms - g_next_page_ms) < 0) return;

  g_page_index = (g_page_index + 1) % g_page_count;
  draw_current_page();
  reset_paging_clock(now_ms);
}

size_t page_count() { return g_page_count; }

#else

bool begin(uint8_t) { return false; }
bool is_ready() { return false; }
void show_status(const char*, const char*) {}
void show_heartbeat(uint32_t) {}
void tick(uint32_t) {}
size_t page_count() { return 0; }

#endif

}  // namespace oled_view
