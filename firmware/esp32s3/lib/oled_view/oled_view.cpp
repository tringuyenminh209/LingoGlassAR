#include "oled_view.h"

#include <Arduino.h>
#include <U8g2lib.h>
#include <Wire.h>

namespace {

// Full-buffer SSD1306 over hardware I2C. Reset pin is not wired on the
// modules we target, so U8X8_PIN_NONE. Wire must already be begun by main.
U8G2_SSD1306_128X64_NONAME_F_HW_I2C g_display(U8G2_R0, U8X8_PIN_NONE);
bool g_ready = false;

// S1 Day 7b: switched from `u8g2_font_6x10_tf` (ASCII only) to dual
// unifont coverage so the OLED can render the live JP / VN translation
// stream. Both fonts are 16 px tall; layout below is recomputed
// accordingly (LINE2_Y = 24 instead of 16).
//
// U8g2 cannot show JP + VN with a single small font (japanese* lacks the
// Vietnamese precomposed diacritics at U+1EA0-1EFF; vietnamese* has no
// CJK). We detect the dominant script per line by sniffing the UTF-8
// leading bytes and pick the appropriate font.
constexpr uint8_t LINE1_Y = 0;
constexpr uint8_t LINE2_Y = 24;

// Pick a font for the given UTF-8 string. Hiragana, Katakana, and CJK
// ideographs all live in U+3000-U+9FFF, which encodes to UTF-8 leading
// bytes 0xE3-0xE9 inclusive. Vietnamese precomposed diacritics sit in
// U+1EA0-U+1EFF (leading byte 0xE1) and are covered by vietnamese1.
// ASCII (`< 0x80`) and Latin-1 supplement / Latin Extended-A are present
// in both fonts, so pure-ASCII labels (e.g. "LingoGlass S0") render
// identically and we default to the JP font in that case.
const uint8_t* pick_font(const char* utf8) {
  if (utf8 != nullptr) {
    for (const uint8_t* p = reinterpret_cast<const uint8_t*>(utf8); *p != 0;
         ++p) {
      if (*p >= 0xE3 && *p <= 0xE9) {
        return u8g2_font_unifont_t_japanese2;
      }
    }
  }
  return u8g2_font_unifont_t_vietnamese1;
}

void draw_two_lines(const char* line1, const char* line2) {
  g_display.clearBuffer();
  g_display.setFontPosTop();
  if (line1 != nullptr) {
    g_display.setFont(pick_font(line1));
    g_display.drawUTF8(0, LINE1_Y, line1);
  }
  if (line2 != nullptr) {
    g_display.setFont(pick_font(line2));
    g_display.drawUTF8(0, LINE2_Y, line2);
  }
  g_display.sendBuffer();
}

}  // namespace

namespace oled_view {

bool begin(uint8_t i2c_address_7bit) {
  // U8g2 wants the 8-bit (left-shifted) address.
  g_display.setI2CAddress(static_cast<uint8_t>(i2c_address_7bit << 1));
  g_ready = g_display.begin();
  if (!g_ready) {
    return false;
  }
  // Default font is the JP unifont variant. draw_two_lines() will
  // override per call based on the line's script.
  g_display.setFont(u8g2_font_unifont_t_japanese2);
  g_display.setFontPosTop();
  g_display.clearBuffer();
  g_display.sendBuffer();
  return true;
}

bool is_ready() { return g_ready; }

void show_status(const char* line1, const char* line2) {
  if (!g_ready) return;
  draw_two_lines(line1, line2);
}

void show_heartbeat(uint32_t counter) {
  if (!g_ready) return;
  char line2[24];
  snprintf(line2, sizeof(line2), "Heartbeat: %lu",
           static_cast<unsigned long>(counter));
  draw_two_lines("LingoGlass S0", line2);
}

}  // namespace oled_view
