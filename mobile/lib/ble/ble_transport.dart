// LingoGlass AR BLE transport for the spike sender.
//
// Wraps flutter_blue_plus to: scan filtered by service UUID, connect to the
// LingoGlass-S0 device, negotiate MTU, write subtitle fragments encoded by
// ble_protocol, and subscribe to ACK notifications.
//
// Phase D: single-fragment Hello round-trip.
// Phase E: multi-fragment send with sequence_id stepping.

import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_blue_plus/flutter_blue_plus.dart';

import 'ble_protocol.dart';

// Locked UUIDs. Mirror of firmware/CLAUDE.md.
const String _serviceUuid = '7c3d8b00-9e8a-4f15-b6c3-1d2e3f4a5b6c';
const String _subtitleWriteUuid = '7c3d8b01-9e8a-4f15-b6c3-1d2e3f4a5b6c';
const String _ackNotifyUuid = '7c3d8b02-9e8a-4f15-b6c3-1d2e3f4a5b6c';

const String deviceNameFilter = 'LingoGlass-S0';

/// Result of decoding an ACK packet received over the notify characteristic.
class AckEvent {
  const AckEvent({
    required this.sequenceId,
    required this.status,
    required this.receivedAtMicros,
  });

  /// sequence_id of the subtitle being acknowledged.
  final int sequenceId;

  /// Payload byte 0: 0x01 = ok, anything else = error code.
  final int status;

  /// Monotonic timestamp when the ACK arrived on the phone (for latency calc).
  final int receivedAtMicros;

  bool get isOk => status == 0x01;
}

class BleTransport {
  BleTransport({void Function(String)? log}) : _log = log ?? _noopLog;

  static void _noopLog(String _) {}

  final void Function(String) _log;

  BluetoothDevice? _device;
  BluetoothCharacteristic? _subtitleChar;
  BluetoothCharacteristic? _ackChar;
  StreamSubscription<List<int>>? _ackSub;
  StreamSubscription<BluetoothConnectionState>? _connSub;

  // BLE minimum ATT MTU is 23. We update this after requestMtu returns.
  // sendSubtitle uses this when the caller does not pass an explicit mtu.
  int _negotiatedMtu = 23;

  /// Actual MTU negotiated with the peripheral, or 23 (BLE minimum) until a
  /// successful requestMtu has run.
  int get negotiatedMtu => _negotiatedMtu;

  final StreamController<AckEvent> _ackController =
      StreamController<AckEvent>.broadcast();

  final StreamController<bool> _connController =
      StreamController<bool>.broadcast();

  /// Fires for every ACK packet received from the firmware.
  Stream<AckEvent> get acks => _ackController.stream;

  /// Fires `true` when a connection is established and `false` when the OS or
  /// peer drops the link. Listen and rebuild UI so the connection chip and
  /// `isConnected` checks stay honest after an external disconnect.
  Stream<bool> get connectionChanges => _connController.stream;

  bool get isConnected => _device != null && _subtitleChar != null;

  /// Scans for ~5 seconds, connects to the first LingoGlass-S0 found,
  /// negotiates MTU 247, and resolves to the connected device.
  Future<void> scanAndConnect({
    Duration scanTimeout = const Duration(seconds: 5),
  }) async {
    if (isConnected) {
      _log('already connected');
      return;
    }

    _log('scan start (filter: $deviceNameFilter)');
    final completer = Completer<BluetoothDevice>();
    late StreamSubscription<List<ScanResult>> sub;
    sub = FlutterBluePlus.scanResults.listen((results) {
      for (final r in results) {
        if (r.device.platformName == deviceNameFilter) {
          if (!completer.isCompleted) completer.complete(r.device);
          sub.cancel();
          FlutterBluePlus.stopScan();
          return;
        }
      }
    });

    await FlutterBluePlus.startScan(
      withServices: [Guid(_serviceUuid)],
      timeout: scanTimeout,
    );
    final device = await completer.future.timeout(
      scanTimeout + const Duration(seconds: 1),
      onTimeout: () => throw TimeoutException('device not found'),
    );
    await sub.cancel();
    await FlutterBluePlus.stopScan();

    _log('connecting to ${device.platformName} (${device.remoteId})');
    await device.connect(timeout: const Duration(seconds: 10));

    // Watch for OS / peer-side disconnects (BT toggle, range, power cycle).
    // Without this, cached refs lie about connection state and the next write
    // throws "device is not connected" while the UI still says CONN.
    await _connSub?.cancel();
    _connSub = device.connectionState.listen((state) {
      if (state == BluetoothConnectionState.disconnected) {
        _handleExternalDisconnect();
      }
    });

    // Android-only MTU request. iOS negotiates automatically; on iOS we leave
    // _negotiatedMtu at the BLE minimum until the first ACK comes back so we
    // never over-fragment.
    try {
      final mtu = await device.requestMtu(247);
      _negotiatedMtu = mtu;
      _log('mtu=$mtu (negotiated)');
    } on Exception catch (e) {
      _log('requestMtu failed: $e (iOS auto-negotiates, leaving mtu=23)');
    }

    final services = await device.discoverServices();
    final svc = services.firstWhere(
      (s) => s.uuid.toString().toLowerCase() == _serviceUuid,
      orElse: () => throw StateError('service $_serviceUuid not found'),
    );
    final writeChar = svc.characteristics.firstWhere(
      (c) => c.uuid.toString().toLowerCase() == _subtitleWriteUuid,
      orElse: () => throw StateError('subtitle write char not found'),
    );
    final notifyChar = svc.characteristics.firstWhere(
      (c) => c.uuid.toString().toLowerCase() == _ackNotifyUuid,
      orElse: () => throw StateError('ack notify char not found'),
    );

    await notifyChar.setNotifyValue(true);
    _ackSub = notifyChar.onValueReceived.listen(_handleAck);

    _device = device;
    _subtitleChar = writeChar;
    _ackChar = notifyChar;
    _log('connected, write+notify wired');
    if (!_connController.isClosed) _connController.add(true);
  }

  Future<void> disconnect() async {
    await _connSub?.cancel();
    _connSub = null;
    await _ackSub?.cancel();
    _ackSub = null;
    await _device?.disconnect();
    _clearRefs();
    _log('disconnected');
    if (!_connController.isClosed) _connController.add(false);
  }

  void _clearRefs() {
    _device = null;
    _subtitleChar = null;
    _ackChar = null;
    _negotiatedMtu = 23;
  }

  // Called when the connectionState stream reports disconnected without the
  // app asking for it. Cleans cached refs so isConnected stops lying.
  void _handleExternalDisconnect() {
    if (_device == null && _subtitleChar == null) return; // already cleared
    _log('connection lost (external disconnect)');
    _ackSub?.cancel();
    _ackSub = null;
    _connSub?.cancel();
    _connSub = null;
    _clearRefs();
    if (!_connController.isClosed) _connController.add(false);
  }

  /// Encodes [text] as UTF-8, splits into fragments based on the negotiated
  /// MTU (or [mtu] override), and writes each fragment to the subtitle
  /// characteristic with write-without-response.
  ///
  /// If [mtu] is null, uses [negotiatedMtu] (default 23 = BLE minimum, updated
  /// after requestMtu returns at connect time).
  ///
  /// Returns the number of fragments sent.
  Future<int> sendSubtitle(String text, int sequenceId, {int? mtu}) async {
    final char = _subtitleChar;
    if (char == null) {
      throw StateError('not connected');
    }
    final bytes = Uint8List.fromList(utf8.encode(text));

    final effectiveMtu = mtu ?? _negotiatedMtu;
    final perFragment = effectiveMtu - 3 - packetOverhead;
    if (perFragment <= 0) {
      throw StateError(
        'mtu $effectiveMtu too small for protocol overhead $packetOverhead',
      );
    }
    final fragments = splitUtf8(bytes, perFragment);
    _log(
      'send seq=$sequenceId len=${bytes.length} '
      'frags=${fragments.length} max_payload=$perFragment',
    );

    for (var i = 0; i < fragments.length; i++) {
      final r = fragments[i];
      final payload = Uint8List.sublistView(
        bytes,
        r.offset,
        r.offset + r.length,
      );
      final packet = encodeFragment(
        type: MessageType.subtitle,
        sequenceId: sequenceId,
        fragmentIndex: i,
        fragmentCount: fragments.length,
        payload: payload,
      );
      await char.write(packet, withoutResponse: true);
      _log('  frag $i/${fragments.length} bytes=${packet.length}');
    }
    return fragments.length;
  }

  void _handleAck(List<int> bytes) {
    final data = Uint8List.fromList(bytes);
    final result = decodeFragment(data);
    if (!result.isOk || result.packet == null) {
      _log('ack decode FAILED status=${result.status}');
      return;
    }
    final p = result.packet!;
    final status = p.payload.isNotEmpty ? p.payload[0] : 0;
    final event = AckEvent(
      sequenceId: p.header.sequenceId,
      status: status,
      receivedAtMicros: DateTime.now().microsecondsSinceEpoch,
    );
    _log('ack seq=${event.sequenceId} status=0x${status.toRadixString(16)}');
    _ackController.add(event);
  }

  Future<void> dispose() async {
    await disconnect();
    await _ackController.close();
    await _connController.close();
  }
}
