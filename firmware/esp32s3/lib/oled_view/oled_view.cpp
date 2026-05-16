#include "oled_view.h"

#include <Arduino.h>
#include <U8g2lib.h>
#include <Wire.h>

namespace {

// Full-buffer SSD1306 over hardware I2C. Reset pin is not wired on the
// modules we target, so U8X8_PIN_NONE. Wire must already be begun by main.
U8G2_SSD1306_128X64_NONAME_F_HW_I2C g_display(U8G2_R0, U8X8_PIN_NONE);
bool g_ready = false;

constexpr uint8_t LINE1_Y = 0;
constexpr uint8_t LINE2_Y = 16;

void draw_two_lines(const char* line1, const char* line2) {
  g_display.clearBuffer();
  g_display.setFont(u8g2_font_6x10_tf);
  g_display.setFontPosTop();
  if (line1 != nullptr) {
    g_display.drawStr(0, LINE1_Y, line1);
  }
  if (line2 != nullptr) {
    g_display.drawStr(0, LINE2_Y, line2);
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
  g_display.setFont(u8g2_font_6x10_tf);
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
