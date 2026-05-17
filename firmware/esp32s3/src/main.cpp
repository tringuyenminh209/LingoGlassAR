// LingoGlass AR S0 firmware entry point.
//
// Phase A: I2C scan + board info on Serial. Carried over from Test/Test.ino.
// Phase B: U8g2 OLED text render.
// Phase C (current): NimBLE GATT receiver. Write callback logs raw bytes;
//                    Phase D wires ble_protocol::decode_fragment + ACK.
// Phase D-E: subtitle packet parser + fragmentation + ACK.
//
// Hardware: ESPr Developer S3 + 0.96 inch I2C OLED 128x64.
// I2C: SDA = GPIO 8, SCL = GPIO 9.

#include <Arduino.h>
#include <Wire.h>

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

// Phase C subtitle handler: log only. Phase D will decode + ACK.
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
  Serial.println("Setup complete. Heartbeat every 1s.");
}

void loop() {
  static uint32_t counter = 0;
  static bool ledOn = false;

  if (STATUS_LED_PIN >= 0) {
    ledOn = !ledOn;
    digitalWrite(STATUS_LED_PIN, ledOn ? HIGH : LOW);
  }

  const bool connected = ble_server::is_connected();
  Serial.printf("Heartbeat %lu | heap=%u | ble=%s | rx_count=%lu rx_bytes=%lu\n",
                (unsigned long)counter, ESP.getFreeHeap(),
                connected ? "CONNECTED" : "adv",
                (unsigned long)g_total_write_count,
                (unsigned long)g_total_write_bytes);

  char line2[24];
  if (connected) {
    snprintf(line2, sizeof(line2), "BLE OK rx=%lu",
             (unsigned long)g_total_write_count);
  } else {
    snprintf(line2, sizeof(line2), "Adv #%lu",
             (unsigned long)counter);
  }
  oled_view::show_status("LingoGlass S0", line2);

  counter++;
  delay(1000);
}
