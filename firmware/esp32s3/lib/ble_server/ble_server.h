// NimBLE GATT server for LingoGlass S0.
//
// GATT layout (locked, see firmware/CLAUDE.md):
//   Service        7c3d8b00-9e8a-4f15-b6c3-1d2e3f4a5b6c
//   Subtitle write 7c3d8b01-9e8a-4f15-b6c3-1d2e3f4a5b6c  (WRITE + WRITE_NR)
//   ACK notify     7c3d8b02-9e8a-4f15-b6c3-1d2e3f4a5b6c  (NOTIFY + READ)
//
// Phase C: skeleton. The write callback hands raw bytes back to the caller
// but this library does not decode them. Phase D wires ble_protocol::decode_fragment.

#pragma once

#include <stddef.h>
#include <stdint.h>

namespace ble_server {

// Receives one subtitle write payload. The buffer is owned by NimBLE and
// only valid for the duration of the callback - copy if you need to retain.
using SubtitleWriteCallback = void (*)(const uint8_t* data, size_t length);

// Fired once each time a central disconnects, after advertising has been
// restarted. Use this to reset per-connection state (e.g. SubtitleAssembler).
using DisconnectCallback = void (*)();

// Initializes NimBLE, registers the GATT service, and starts advertising.
// device_name is what shows up in a phone's BLE scanner. Returns false if
// the BLE stack failed to bring up.
bool begin(const char* device_name, SubtitleWriteCallback on_subtitle);

// Registers a hook called when the central disconnects. Pass nullptr to
// clear. Safe to call before or after begin().
void set_disconnect_callback(DisconnectCallback on_disconnect);

// True while a central is connected.
bool is_connected();

// Sends an ACK packet over the notify characteristic. data should be a
// complete ACK packet (header + payload + crc8 trailer). Returns false if
// no central is connected.
bool notify_ack(const uint8_t* data, size_t length);

}  // namespace ble_server
