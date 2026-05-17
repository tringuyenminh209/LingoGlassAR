// LingoGlass AR S0 firmware entry point.
//
// Phase A: I2C scan + board info on Serial. Carried over from Test/Test.ino.
// Phase B: U8g2 OLED text render.
// Phase C: NimBLE GATT receiver.
// Phase D (current): decode subtitle fragments, render on OLED, ACK back.
//                    Single-fragment only; multi-fragment assembler is Phase E.
// Phase E: fragment buffer + sequence drop rule + MTU matrix.
// Phase F: latency harness + p50/p95.
//
// Hardware: ESPr Developer S3 + 0.96 inch I2C OLED 128x64.
// I2C: SDA = GPIO 8, SCL = GPIO 9.

#include <Arduino.h>
#include <Wire.h>

#include "ble_protocol.h"
#include "ble_server.h"
#include "oled_view.h"

static const int I2C_SDA_PIN = 8;
static const int I2C_SCL_PIN = 9;
static const uint32_t SERIAL_BAUD = 115200;
static const uint8_t OLED_ADDRESS_7BIT = 0x3C;
static const char* BLE_DEVICE_NAME = "LingoGlass-S0";

#if defined(LED_BUILTIN)
static const int STATUS_LED_PIN = LED_BUILTIN;
#else
static const int STATUS_LED_PIN = -1;
#endif

static volatile uint32_t g_total_write_bytes = 0;
static volatile uint32_t g_total_write_count = 0;
static volatile uint32_t g_total_subtitles = 0;
static volatile uint32_t g_total_decode_errors = 0;
static char g_last_subtitle[64] = {0};  // null-terminated, latin only for Phase D

static void printBoardInfo() {
  Serial.println();
  Serial.println("=== LingoGlass S0 board test ===");
  Serial.print("Chip model: ");
  Serial.println(ESP.getChipModel());
  Serial.print("Chip revision: ");
  Serial.println(ESP.getChipRevision());
  Serial.print("CPU MHz: ");
  Serial.println(ESP.getCpuFreqMHz());
  Serial.print("Flash bytes: ");
  Serial.println(ESP.getFlashChipSize());
  Serial.print("PSRAM bytes: ");
  Serial.println(ESP.getPsramSize());
  Serial.print("Free heap: ");
  Serial.println(ESP.getFreeHeap());
  Serial.println("Expected flash: 16 MB, PSRAM: 8 MB.");
}

static bool scanI2C() {
  Serial.println();
  Serial.print("[i2c] Scanning on SDA=GPIO");
  Serial.print(I2C_SDA_PIN);
  Serial.print(", SCL=GPIO");
  Serial.println(I2C_SCL_PIN);

  bool foundOled = false;
  uint8_t foundCount = 0;
  for (uint8_t address = 1; address < 127; ++address) {
    Wire.beginTransmission(address);
    uint8_t error = Wire.endTransmission();
    if (error == 0) {
      Serial.printf("[i2c] device found at 0x%02X\n", address);
      foundCount++;
      if (address == OLED_ADDRESS_7BIT) {
        foundOled = true;
      }
    } else if (error == 4) {
      Serial.printf("[i2c] unknown error at 0x%02X\n", address);
    }
  }

  if (foundCount == 0) {
    Serial.println("[i2c] no devices found. Check VCC/GND/SDA/SCL and OLED voltage.");
  } else {
    Serial.printf("[i2c] scan done. devices=%u. OLED is usually 0x3C or 0x3D.\n",
                  foundCount);
  }
  return foundOled;
}

// Build and send an ACK packet for the given subtitle sequence_id.
// Phase D payload: [status=0x01 ok, reserved=0x00].
static void sendAck(uint16_t sequence_id) {
  uint8_t ack_buffer[ble_protocol::MAX_PACKET_SIZE];
  const uint8_t ack_payload[2] = {0x01, 0x00};
  const size_t written = ble_protocol::encode_fragment(
      ble_protocol::MessageType::Ack,
      sequence_id,
      /*fragment_index=*/0,
      /*fragment_count=*/1,
      ack_payload,
      sizeof(ack_payload),
      ack_buffer,
      sizeof(ack_buffer));
  if (written == 0) {
    Serial.println("[ack] encode FAILED");
    return;
  }
  if (!ble_server::notify_ack(ack_buffer, written)) {
    Serial.println("[ack] notify FAILED (no central?)");
    return;
  }
  Serial.printf("[ack] notified seq=%u (%u bytes)\n", sequence_id,
                static_cast<unsigned>(written));
}

// Phase D handler: decode subtitle, render on OLED, ACK back.
// Single-fragment only - multi-fragment assembly is Phase E.
static void onSubtitleWrite(const uint8_t* data, size_t length) {
  g_total_write_count++;
  g_total_write_bytes += static_cast<uint32_t>(length);

  Serial.printf("[ble] rx[%u]:", static_cast<unsigned>(length));
  const size_t preview = length > 16 ? 16 : length;
  for (size_t i = 0; i < preview; ++i) {
    Serial.printf(" %02X", data[i]);
  }
  if (length > preview) Serial.print(" ...");
  Serial.println();

  ble_protocol::DecodedPacket packet;
  const ble_protocol::DecodeStatus status =
      ble_protocol::decode_fragment(data, length, packet);
  if (status != ble_protocol::DecodeStatus::Ok) {
    g_total_decode_errors++;
    Serial.printf("[decode] status=%d (not OK)\n", static_cast<int>(status));
    return;
  }

  const auto& h = packet.header;
  Serial.printf("[decode] type=%u seq=%u frag=%u/%u payload_len=%u\n",
                h.message_type, h.sequence_id,
                h.fragment_index + 1, h.fragment_count, h.payload_length);

  if (h.message_type != static_cast<uint8_t>(ble_protocol::MessageType::Subtitle)) {
    Serial.printf("[decode] ignoring non-subtitle type=%u\n", h.message_type);
    return;
  }

  if (h.fragment_count > 1) {
    // Phase E will assemble multi-fragment. Phase D acknowledges but does
    // not render to avoid showing partial text.
    Serial.printf("[decode] multi-fragment (cnt=%u) - deferred to Phase E\n",
                  h.fragment_count);
    sendAck(h.sequence_id);
    return;
  }

  // Single fragment: copy payload to null-terminated buffer for OLED render.
  const size_t copy_len = packet.payload_length < sizeof(g_last_subtitle) - 1
                              ? packet.payload_length
                              : sizeof(g_last_subtitle) - 1;
  memcpy(g_last_subtitle, packet.payload, copy_len);
  g_last_subtitle[copy_len] = '\0';
  g_total_subtitles++;

  Serial.printf("[subtitle] seq=%u text=\"%s\"\n", h.sequence_id, g_last_subtitle);
  oled_view::show_status("LingoGlass S0", g_last_subtitle);

  sendAck(h.sequence_id);
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(2000);

  if (STATUS_LED_PIN >= 0) {
    pinMode(STATUS_LED_PIN, OUTPUT);
  }

  printBoardInfo();

  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  Wire.setClock(400000);
  const bool oledPresent = scanI2C();

  if (oledPresent) {
    if (oled_view::begin(OLED_ADDRESS_7BIT)) {
      Serial.println("[oled] init ok");
      oled_view::show_status("LingoGlass S0", "BLE init...");
    } else {
      Serial.println("[oled] init FAILED after I2C detect");
    }
  } else {
    Serial.println("[oled] skipped: 0x3C not detected on I2C bus");
  }

  if (!ble_server::begin(BLE_DEVICE_NAME, onSubtitleWrite)) {
    Serial.println("[ble] init FAILED");
    oled_view::show_status("LingoGlass S0", "BLE init FAIL");
  } else {
    oled_view::show_status("LingoGlass S0", "Adv: LingoGlass-S0");
  }

  Serial.println();
  Serial.println("Setup complete.");
}

void loop() {
  static uint32_t counter = 0;
  static bool ledOn = false;

  if (STATUS_LED_PIN >= 0) {
    ledOn = !ledOn;
    digitalWrite(STATUS_LED_PIN, ledOn ? HIGH : LOW);
  }

  const bool connected = ble_server::is_connected();
  Serial.printf("HB %lu | heap=%u | ble=%s | rx=%lu sub=%lu err=%lu | last=\"%s\"\n",
                (unsigned long)counter, ESP.getFreeHeap(),
                connected ? "CONN" : "adv",
                (unsigned long)g_total_write_count,
                (unsigned long)g_total_subtitles,
                (unsigned long)g_total_decode_errors,
                g_last_subtitle);

  // If we have a rendered subtitle, keep it on screen. Otherwise show status.
  if (g_total_subtitles == 0) {
    char line2[24];
    if (connected) {
      snprintf(line2, sizeof(line2), "BLE conn heap=%uk",
               static_cast<unsigned>(ESP.getFreeHeap() / 1024));
    } else {
      snprintf(line2, sizeof(line2), "Adv #%lu",
               static_cast<unsigned long>(counter));
    }
    oled_view::show_status("LingoGlass S0", line2);
  }
  // else: last subtitle stays on OLED until next one arrives.

  counter++;
  delay(1000);
}
