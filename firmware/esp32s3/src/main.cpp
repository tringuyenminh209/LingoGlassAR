// LingoGlass AR S0 firmware entry point.
//
// Phase A: I2C scan + board info on Serial. Carried over from Test/Test.ino.
// Phase B: U8g2 OLED text render.
// Phase C: NimBLE GATT receiver.
// Phase D: decode subtitle fragments, render on OLED, ACK back.
// Phase E: SubtitleAssembler reassembles multi-fragment payloads
//          keyed by sequence_id. Newer sequence drops stale buffer.
//          ACK status=0x01 only on full assembly; per-fragment Incomplete
//          is silent. Errors (OutOfOrder/Inconsistent/Overflow) -> 0x03.
// Phase F (current): ACK payload extended to 10 bytes - status, reserved,
//                    t_recv_ms (uint32 LE), t_render_ms (uint32 LE). Mobile
//                    uses these alongside its own send_ts to compute RTT
//                    and firmware processing time for the latency report.
//
// Hardware: ESPr Developer S3 + 0.96 inch I2C OLED 128x64.
// I2C: SDA = GPIO 8, SCL = GPIO 9.

#include <Arduino.h>
#include <Wire.h>

#include "ble_protocol.h"
#include "ble_server.h"
#include "oled_view.h"
#include "subtitle_assembler.h"

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
static volatile uint32_t g_total_assembler_errors = 0;
static char g_last_subtitle[128] = {0};  // null-terminated UTF-8
static subtitle_assembler::SubtitleAssembler g_assembler;

// Phase F: per-sequence timing. millis() at the moment we entered the write
// callback for the FIRST fragment of the current sequence. ESP32 millis() is
// a different clock from the phone's, so absolute values are not comparable
// to send_ts on the mobile side. The difference t_render_ms - t_recv_ms gives
// the firmware processing time (assembler + OLED) for the diagnostic column
// in the latency CSV. Sentinel 0xFFFF means "no current sequence".
static uint16_t g_seq_in_progress = 0xFFFF;
static uint32_t g_seq_recv_ms = 0;

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

// Status codes for the ACK payload. See .claude/skills/ble-protocol/SKILL.md.
namespace AckStatus {
constexpr uint8_t Ok            = 0x01;  // subtitle rendered on display
constexpr uint8_t Unsupported   = 0x02;  // e.g., multi-fragment before Phase E
constexpr uint8_t DecodeError   = 0x03;  // CRC / length / version failure
}  // namespace AckStatus

// Build and send an ACK packet. Phase F payload layout (10 bytes):
//   [0] status (Ok/Unsupported/DecodeError)
//   [1] reserved (0x00)
//   [2..5] t_recv_ms (uint32 LE) - millis() of first fragment in this sequence
//   [6..9] t_render_ms (uint32 LE) - millis() right after OLED sendBuffer, or 0
// Mobile reads these to compute fw_proc_ms = t_render_ms - t_recv_ms while
// RTT is measured on the phone clock as ack_arrival - send_ts.
static void sendAck(uint16_t sequence_id,
                    uint8_t status,
                    uint32_t t_recv_ms,
                    uint32_t t_render_ms) {
  uint8_t ack_buffer[ble_protocol::MAX_PACKET_SIZE];
  uint8_t ack_payload[10];
  ack_payload[0] = status;
  ack_payload[1] = 0x00;
  ack_payload[2] = static_cast<uint8_t>(t_recv_ms & 0xFF);
  ack_payload[3] = static_cast<uint8_t>((t_recv_ms >> 8) & 0xFF);
  ack_payload[4] = static_cast<uint8_t>((t_recv_ms >> 16) & 0xFF);
  ack_payload[5] = static_cast<uint8_t>((t_recv_ms >> 24) & 0xFF);
  ack_payload[6] = static_cast<uint8_t>(t_render_ms & 0xFF);
  ack_payload[7] = static_cast<uint8_t>((t_render_ms >> 8) & 0xFF);
  ack_payload[8] = static_cast<uint8_t>((t_render_ms >> 16) & 0xFF);
  ack_payload[9] = static_cast<uint8_t>((t_render_ms >> 24) & 0xFF);
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
  Serial.printf("[ack] seq=%u status=0x%02X t_recv=%lu t_render=%lu\n",
                sequence_id, status,
                static_cast<unsigned long>(t_recv_ms),
                static_cast<unsigned long>(t_render_ms));
}

// Subtitle write handler: decode, assemble, render, ACK with Phase F timing.
static void onSubtitleWrite(const uint8_t* data, size_t length) {
  // Capture the moment this fragment arrived. We'll latch it as the "recv"
  // timestamp for the sequence on the first fragment we see for that seq_id.
  const uint32_t t_now = millis();
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
    // We don't have a reliable sequence_id since decode failed. Best-effort:
    // try to read bytes 2-3 as little-endian seq if there are enough bytes,
    // otherwise use 0xFFFF as a sentinel. Sender treats any status != 0x01
    // as failure regardless of seq match.
    const uint16_t seq_guess =
        length >= 4 ? static_cast<uint16_t>(data[2] | (data[3] << 8)) : 0xFFFF;
    sendAck(seq_guess, AckStatus::DecodeError, t_now, 0);
    return;
  }

  const auto& h = packet.header;
  Serial.printf("[decode] type=%u seq=%u frag=%u/%u payload_len=%u\n",
                h.message_type, h.sequence_id,
                h.fragment_index + 1, h.fragment_count, h.payload_length);

  if (h.message_type != static_cast<uint8_t>(ble_protocol::MessageType::Subtitle)) {
    Serial.printf("[decode] ignoring non-subtitle type=%u\n", h.message_type);
    sendAck(h.sequence_id, AckStatus::Unsupported, t_now, 0);
    return;
  }

  // Latch t_recv on the first fragment of a new sequence. Subsequent
  // fragments of the same sequence keep the original recv timestamp so the
  // ACK reports the start-to-render duration, not just last-frag-to-render.
  if (h.sequence_id != g_seq_in_progress) {
    g_seq_in_progress = h.sequence_id;
    g_seq_recv_ms = t_now;
  }

  // Feed every subtitle fragment through the assembler. Single-fragment
  // subtitles complete on the first call; multi-fragment accumulate until
  // the final fragment_index == fragment_count - 1 arrives.
  const auto feed_result = g_assembler.feed(
      h.sequence_id, h.fragment_index, h.fragment_count,
      packet.payload, h.payload_length);

  switch (feed_result) {
    case subtitle_assembler::FeedResult::Incomplete:
      Serial.printf("[asm] frag %u/%u seq=%u accepted, waiting\n",
                    h.fragment_index + 1, h.fragment_count, h.sequence_id);
      // No ACK yet. Sender expects one ACK per sequence_id, on completion.
      return;

    case subtitle_assembler::FeedResult::Complete: {
      const size_t asm_len = g_assembler.length();
      const size_t copy_len = asm_len < sizeof(g_last_subtitle) - 1
                                  ? asm_len
                                  : sizeof(g_last_subtitle) - 1;
      memcpy(g_last_subtitle, g_assembler.assembled(), copy_len);
      g_last_subtitle[copy_len] = '\0';
      g_total_subtitles++;

      Serial.printf("[subtitle] seq=%u len=%u frags=%u text=\"%s\"\n",
                    h.sequence_id, static_cast<unsigned>(asm_len),
                    h.fragment_count, g_last_subtitle);
      oled_view::show_status("LingoGlass S0", g_last_subtitle);
      const uint32_t t_render = millis();
      sendAck(h.sequence_id, AckStatus::Ok, g_seq_recv_ms, t_render);
      g_seq_in_progress = 0xFFFF;
      return;
    }

    case subtitle_assembler::FeedResult::Stale:
      // Older sequence_id arrived while a newer one is mid-assembly.
      // Active buffer is preserved; tell the sender this fragment was
      // rejected so it stops retrying. Counts as a soft error.
      g_total_assembler_errors++;
      Serial.printf("[asm] stale seq=%u (active seq still assembling)\n",
                    h.sequence_id);
      // Use t_now (not g_seq_recv_ms) - stale belongs to a different seq.
      sendAck(h.sequence_id, AckStatus::DecodeError, t_now, 0);
      return;

    case subtitle_assembler::FeedResult::OutOfOrder:
    case subtitle_assembler::FeedResult::Inconsistent:
    case subtitle_assembler::FeedResult::Overflow:
      g_total_assembler_errors++;
      Serial.printf("[asm] error %d on seq=%u frag=%u/%u\n",
                    static_cast<int>(feed_result),
                    h.sequence_id, h.fragment_index, h.fragment_count);
      sendAck(h.sequence_id, AckStatus::DecodeError, g_seq_recv_ms, 0);
      g_seq_in_progress = 0xFFFF;
      return;
  }
}

// Called by ble_server when the central disconnects. We drop any in-progress
// subtitle buffer so a reconnect starts from a clean slate.
static void onBleDisconnect() {
  if (g_assembler.is_assembling()) {
    Serial.println("[asm] disconnect mid-assembly - dropping buffer");
  }
  g_assembler.reset();
  g_seq_in_progress = 0xFFFF;
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

  ble_server::set_disconnect_callback(onBleDisconnect);
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
  Serial.printf("HB %lu | heap=%u | ble=%s | rx=%lu sub=%lu derr=%lu aerr=%lu asm=%s | last=\"%s\"\n",
                (unsigned long)counter, ESP.getFreeHeap(),
                connected ? "CONN" : "adv",
                (unsigned long)g_total_write_count,
                (unsigned long)g_total_subtitles,
                (unsigned long)g_total_decode_errors,
                (unsigned long)g_total_assembler_errors,
                g_assembler.is_assembling() ? "busy" : "idle",
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
