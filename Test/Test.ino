#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// LingoGlass S0 OLED smoke test.
// Board: ESPr Developer S3 Type-C (ESP32-S3-WROOM-1)
// OLED: 0.96 inch I2C white OLED 128x64
// Verified I2C: SDA = GPIO 8, SCL = GPIO 9, address = 0x3C

static const int I2C_SDA_PIN = 8;
static const int I2C_SCL_PIN = 9;
static const uint8_t OLED_ADDRESS = 0x3C;
static const int SCREEN_WIDTH = 128;
static const int SCREEN_HEIGHT = 64;
static const uint32_t SERIAL_BAUD = 115200;

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

#if defined(LED_BUILTIN)
static const int STATUS_LED_PIN = LED_BUILTIN;
#else
static const int STATUS_LED_PIN = -1;
#endif

void printBoardInfo() {
  Serial.println();
  Serial.println("=== LingoGlass S0 OLED test ===");
  Serial.print("Chip model: ");
  Serial.println(ESP.getChipModel());
  Serial.print("Chip revision: ");
  Serial.println(ESP.getChipRevision());
  Serial.print("CPU frequency MHz: ");
  Serial.println(ESP.getCpuFreqMHz());
  Serial.print("Flash size bytes: ");
  Serial.println(ESP.getFlashChipSize());
  Serial.print("PSRAM size bytes: ");
  Serial.println(ESP.getPsramSize());
  Serial.print("Free heap bytes: ");
  Serial.println(ESP.getFreeHeap());
}

bool scanExpectedOled() {
  Serial.println();
  Serial.print("Checking OLED at 0x");
  Serial.println(OLED_ADDRESS, HEX);

  Wire.beginTransmission(OLED_ADDRESS);
  byte error = Wire.endTransmission();

  if (error == 0) {
    Serial.println("OLED I2C ACK OK.");
    return true;
  }

  Serial.print("OLED not found. I2C error code: ");
  Serial.println(error);
  Serial.println("Check GND, VCC, SDA IO8, SCL IO9.");
  return false;
}

void drawStartupScreen() {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);

  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println("LingoGlass AR");
  display.println("S0 OLED PASS");
  display.println();
  display.println("I2C: 0x3C");
  display.println("SDA: IO8");
  display.println("SCL: IO9");

  display.setCursor(0, 56);
  display.print("Subtitle ready");
  display.display();
}

void drawHeartbeat(uint32_t counter) {
  display.fillRect(84, 40, 44, 24, SSD1306_BLACK);
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(84, 40);
  display.print("HB ");
  display.println(counter);
  display.display();
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(2000);

  if (STATUS_LED_PIN >= 0) {
    pinMode(STATUS_LED_PIN, OUTPUT);
  }

  printBoardInfo();

  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  Wire.setClock(100000);

  if (!scanExpectedOled()) {
    Serial.println("Setup stopped before display init.");
    return;
  }

  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDRESS)) {
    Serial.println("SSD1306 init failed.");
    return;
  }

  drawStartupScreen();
  Serial.println("OLED display init OK.");
  Serial.println("Heartbeat will update Serial and OLED every 1 second.");
}

void loop() {
  static uint32_t counter = 0;
  static bool ledOn = false;

  if (STATUS_LED_PIN >= 0) {
    ledOn = !ledOn;
    digitalWrite(STATUS_LED_PIN, ledOn ? HIGH : LOW);
  }

  Serial.print("Heartbeat ");
  Serial.print(counter);
  Serial.print(" | free heap: ");
  Serial.println(ESP.getFreeHeap());

  drawHeartbeat(counter);
  counter++;

  delay(1000);
}
