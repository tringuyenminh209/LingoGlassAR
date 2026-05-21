// OLED view for LingoGlass S0 spike.
// Wraps U8g2 SSD1306 128x64 I2C. ASCII-only for S0; Japanese font is S1+.
// Caller owns Wire setup (Wire.begin(SDA, SCL) must be called before begin()).

#pragma once

#include <stddef.h>
#include <stdint.h>

#include <functional>
#include <string>
#include <vector>

namespace oled_view {

constexpr size_t MAX_WRAPPED_LINES = 32;

using Utf8WidthFn = std::function<int(const char*)>;

struct WrappedLines {
  std::vector<std::string> lines;
  bool truncated = false;
};

// Split UTF-8 text into display-width-bounded lines without breaking
// multi-byte codepoints. Exposed for native wrap tests.
WrappedLines wrap_utf8_lines(const char* utf8,
                             int max_width_px,
                             const Utf8WidthFn& width);

// Initializes the display. Returns true if the SSD1306 responded on Wire.
// Address defaults to 0x3C. Pass 0x3D for the alternate-strap variant.
bool begin(uint8_t i2c_address_7bit = 0x3C);

// Returns true if begin() succeeded. Safe to call show_* even when false
// (they become no-ops); use this when deciding whether to log fallbacks.
bool is_ready();

// Two-line status. line1 is the title row, line2 is the body row.
// nullptr is treated as an empty string. Long body text wraps and pages.
void show_status(const char* line1, const char* line2);

// Convenience helper for the S0 heartbeat screen.
// Renders "LingoGlass S0" on line 1 and "Heartbeat: <counter>" on line 2.
void show_heartbeat(uint32_t counter);

// Cheap main-loop hook that advances wrapped subtitle pages when due.
void tick(uint32_t now_ms);

// Number of pages occupied by the current subtitle body.
size_t page_count();

}  // namespace oled_view
