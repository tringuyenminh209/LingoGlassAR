// LingoGlass AR S0 firmware entry point.
//
// Phase A: I2C scan + board info on Serial. Carried over from Test/Test.ino.
// Phase B (current): U8g2 OLED text render.
// Phase C: NimBLE GATT receiver.
// Phase D-E: subtitle packet parser + fragmentation + ACK.
//
// Hardware: ESPr Developer S3 + 0.96 inch I2C OLED 128x64.
// I2C: SDA = GPIO 8, SCL = GPIO 9.

#include <Arduino.h>
#include <Wire.h>

#include "oled_view.h"

static const int I2C_SDA_PIN = 8;
static const int I2C_SCL_PIN = 9;
static const uint32_t SERIAL_BAUD = 115200;
static const uint8_t OLED_ADDRESS_7BIT = 0x3C;

#if defined(LED_BUILTIN)
static const int STATUS_LED_PIN = LED_BUILTIN;
#else
static const int STATUS_LED_PIN = -1;
#endif

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
      oled_view::show_status("LingoGlass S0", "Phase B: OLED ok");
    } else {
      Serial.println("[oled] init FAILED after I2C detect");
    }
  } else {
    Serial.println("[oled] skipped: 0x3C not detected on I2C bus");
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

  Serial.printf("Heartbeat %lu | free heap: %u\n",
                (unsigned long)counter, ESP.getFreeHeap());
  oled_view::show_heartbeat(counter);

  counter++;
  delay(1000);
}
