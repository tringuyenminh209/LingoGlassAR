#include "ble_server.h"

#include <Arduino.h>
#include <NimBLEDevice.h>

namespace {

constexpr const char* SERVICE_UUID =
    "7c3d8b00-9e8a-4f15-b6c3-1d2e3f4a5b6c";
constexpr const char* SUBTITLE_WRITE_UUID =
    "7c3d8b01-9e8a-4f15-b6c3-1d2e3f4a5b6c";
constexpr const char* ACK_NOTIFY_UUID =
    "7c3d8b02-9e8a-4f15-b6c3-1d2e3f4a5b6c";

constexpr uint16_t REQUESTED_MTU = 247;

ble_server::SubtitleWriteCallback g_callback = nullptr;
ble_server::DisconnectCallback g_disconnect_cb = nullptr;
NimBLEServer* g_server = nullptr;
NimBLECharacteristic* g_subtitle_char = nullptr;
NimBLECharacteristic* g_ack_char = nullptr;
volatile bool g_connected = false;

class ServerCallbacks : public NimBLEServerCallbacks {
  void onConnect(NimBLEServer* /*server*/) override {
    g_connected = true;
    Serial.println("[ble] central connected");
  }
  void onDisconnect(NimBLEServer* /*server*/) override {
    g_connected = false;
    Serial.println("[ble] central disconnected, restart advertising");
    NimBLEDevice::startAdvertising();
    if (g_disconnect_cb != nullptr) {
      g_disconnect_cb();
    }
  }
  void onMTUChange(uint16_t mtu, ble_gap_conn_desc* /*desc*/) override {
    Serial.printf("[ble] negotiated mtu=%u\n", mtu);
  }
};

class SubtitleWriteCallbacks : public NimBLECharacteristicCallbacks {
  void onWrite(NimBLECharacteristic* characteristic) override {
    std::string value = characteristic->getValue();
    Serial.printf("[ble] write %u bytes\n",
                  static_cast<unsigned>(value.size()));
    if (g_callback != nullptr && !value.empty()) {
      g_callback(reinterpret_cast<const uint8_t*>(value.data()), value.size());
    }
  }
};

ServerCallbacks g_server_cb;
SubtitleWriteCallbacks g_subtitle_cb;

}  // namespace

namespace ble_server {

bool begin(const char* device_name, SubtitleWriteCallback on_subtitle) {
  g_callback = on_subtitle;

  NimBLEDevice::init(device_name);
  NimBLEDevice::setMTU(REQUESTED_MTU);
  // Default TX power. Phase F can revisit if range is an issue.

  g_server = NimBLEDevice::createServer();
  if (g_server == nullptr) return false;
  g_server->setCallbacks(&g_server_cb);

  NimBLEService* service = g_server->createService(SERVICE_UUID);
  if (service == nullptr) return false;

  g_subtitle_char = service->createCharacteristic(
      SUBTITLE_WRITE_UUID,
      NIMBLE_PROPERTY::WRITE | NIMBLE_PROPERTY::WRITE_NR);
  g_subtitle_char->setCallbacks(&g_subtitle_cb);

  g_ack_char = service->createCharacteristic(
      ACK_NOTIFY_UUID,
      NIMBLE_PROPERTY::NOTIFY | NIMBLE_PROPERTY::READ);

  service->start();

  NimBLEAdvertising* adv = NimBLEDevice::getAdvertising();
  adv->addServiceUUID(SERVICE_UUID);
  adv->setScanResponse(true);
  // Min/max advertising interval in 0.625ms units. 100ms-200ms keeps the
  // scan window short enough for a phone to find us within ~1 second.
  adv->setMinPreferred(0x06);
  adv->setMaxPreferred(0x12);
  adv->start();

  Serial.printf("[ble] advertising name=%s service=%s\n", device_name,
                SERVICE_UUID);
  return true;
}

void set_disconnect_callback(DisconnectCallback on_disconnect) {
  g_disconnect_cb = on_disconnect;
}

bool is_connected() { return g_connected; }

bool notify_ack(const uint8_t* data, size_t length) {
  if (!g_connected || g_ack_char == nullptr || data == nullptr) return false;
  g_ack_char->setValue(data, length);
  g_ack_char->notify();
  return true;
}

}  // namespace ble_server
