// S1 Day 7 push-to-talk translation screen. Wires:
//   AudioRecorder (Day 5) -> TranslatorWs (Day 6) -> BleTransport (S0).
//
// Lifecycle per PTT press:
//   1. On press down: ensure sessionId (POST /v1/sessions on first use),
//      open WS via TranslatorWs.connect(), start AudioRecorder, pipe each
//      4800-byte PCM16 chunk into ws.send().
//   2. On press up: stop recorder, ws.endUtterance(), wait for textStream.
//   3. On TextDelta.partial: append text to the on-screen subtitle buffer.
//   4. On TextDelta.final: push translatedText into BleTransport.sendSubtitle()
//      so the ESP32-S3 renders it on the OLED.
//
// BLE connect is initiated separately by the user via the "Connect glasses"
// button. Translation still works without BLE - the OLED leg is just absent
// (text shows only on the phone).

import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../audio/recorder.dart';
import '../ble/ble_transport.dart';
import '../services/device_id.dart';
import '../services/session_client.dart';
import '../services/translator_ws.dart';

class TranslateScreen extends StatefulWidget {
  const TranslateScreen({super.key});

  @override
  State<TranslateScreen> createState() => _TranslateScreenState();
}

class _TranslateScreenState extends State<TranslateScreen> {
  final AudioRecorder _recorder = AudioRecorder();
  final TranslatorWs _ws = TranslatorWs();
  final SessionClient _sessionClient = SessionClient();
  final BleTransport _ble = BleTransport();

  String? _deviceId;
  String? _sessionId;
  bool _isHolding = false;
  bool _isBleConnected = false;
  bool _isWsConnected = false;
  int _bleSeq = 0;

  String _partialBuffer = '';
  String _lastFinal = '';
  final List<String> _logLines = <String>[];

  StreamSubscription<bool>? _bleConnSub;
  StreamSubscription<TextDelta>? _wsTextSub;
  StreamSubscription<Uint8List>? _audioSub;

  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    final id = await DeviceId.get();
    _bleConnSub = _ble.connectionChanges.listen((connected) {
      if (!mounted) return;
      setState(() => _isBleConnected = connected);
      _log(connected ? 'BLE connected' : 'BLE disconnected');
    });
    if (!mounted) return;
    setState(() => _deviceId = id);
    _log('Device ID ${id.substring(0, 8)}...');
  }

  @override
  void dispose() {
    _bleConnSub?.cancel();
    _wsTextSub?.cancel();
    _audioSub?.cancel();
    unawaited(_recorder.stop());
    unawaited(_ws.disconnect());
    _sessionClient.close();
    super.dispose();
  }

  void _log(String line) {
    if (!mounted) return;
    setState(() {
      _logLines.insert(
          0, '${DateTime.now().toIso8601String().substring(11, 19)}  $line');
      if (_logLines.length > 50) _logLines.removeLast();
    });
  }

  Future<void> _connectBle() async {
    if (_isBleConnected) return;
    _log('BLE scan + connect...');
    try {
      await _ble.scanAndConnect();
      _log('BLE link up, MTU=${_ble.negotiatedMtu}');
    } catch (e) {
      _log('BLE error: $e');
    }
  }

  Future<void> _onPressDown() async {
    if (_isHolding) return;
    if (_deviceId == null) {
      _log('Not ready (deviceId pending)');
      return;
    }
    setState(() {
      _isHolding = true;
      _partialBuffer = '';
    });

    try {
      _sessionId ??= (await _sessionClient.createSession(_deviceId!)).sessionId;
      _log('Session ${_sessionId!.substring(0, 8)}...');

      await _ws.connect(_sessionId!, deviceId: _deviceId!);
      _wsTextSub = _ws.textStream.listen(_onTextDelta, onError: _onWsError);
      setState(() => _isWsConnected = true);
      _log('WS connected');

      final audioStream = await _recorder.start();
      _audioSub = audioStream.listen(
        (chunk) {
          try {
            _ws.send(chunk);
          } catch (e) {
            _log('WS send error: $e');
          }
        },
        onError: (e) => _log('Recorder error: $e'),
      );
      _log('Recording...');
    } catch (e) {
      _log('Start error: $e');
      await _teardownPtt();
    }
  }

  Future<void> _onPressUp() async {
    if (!_isHolding) return;
    setState(() => _isHolding = false);

    await _audioSub?.cancel();
    _audioSub = null;
    await _recorder.stop();
    try {
      _ws.endUtterance();
    } catch (e) {
      _log('endUtterance error: $e');
    }
    _log('Audio ended, awaiting translation...');
  }

  Future<void> _teardownPtt() async {
    setState(() => _isHolding = false);
    await _audioSub?.cancel();
    _audioSub = null;
    await _recorder.stop();
    await _wsTextSub?.cancel();
    _wsTextSub = null;
    await _ws.disconnect();
    setState(() => _isWsConnected = false);
  }

  void _onTextDelta(TextDelta delta) {
    if (delta.isFinal) {
      setState(() {
        _lastFinal = delta.text;
        _partialBuffer = '';
      });
      _log('Final: ${delta.text}');
      if (_isBleConnected) {
        unawaited(_sendToBle(delta.text));
      } else {
        _log('(BLE not connected, OLED skipped)');
      }
      unawaited(_teardownPtt());
    } else {
      setState(() => _partialBuffer += delta.text);
    }
  }

  Future<void> _sendToBle(String text) async {
    _bleSeq = (_bleSeq + 1) & 0xFFFF;
    try {
      final info = await _ble.sendSubtitle(text, _bleSeq);
      _log(
          'BLE sent seq=$_bleSeq frags=${info.fragments} bytes=${info.payloadBytes}');
    } catch (e) {
      _log('BLE send error: $e');
    }
  }

  void _onWsError(Object error) {
    _log('WS error: $error');
    setState(() => _isWsConnected = false);
    unawaited(_teardownPtt());
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('LingoGlass Translate'),
        actions: [
          _chip('BACKEND', _isWsConnected, theme),
          _chip('BLE', _isBleConnected, theme),
          const SizedBox(width: 8),
        ],
      ),
      drawer: Drawer(
        child: ListView(
          children: [
            const DrawerHeader(
                child: Text('Debug', style: TextStyle(fontSize: 20))),
            ListTile(
              leading: const Icon(Icons.bluetooth),
              title: const Text('Connect glasses (BLE)'),
              onTap: () {
                Navigator.of(context).pop();
                _connectBle();
              },
            ),
            ListTile(
              leading: const Icon(Icons.science),
              title: const Text('S0 Spike screen'),
              onTap: () {
                Navigator.of(context).pop();
                Navigator.of(context).pushNamed('/spike');
              },
            ),
          ],
        ),
      ),
      body: Column(
        children: [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            color: theme.colorScheme.surfaceContainerHighest,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text('Partial', style: theme.textTheme.labelSmall),
                Text(
                  _partialBuffer.isEmpty ? '—' : _partialBuffer,
                  style: theme.textTheme.titleLarge,
                ),
                const SizedBox(height: 12),
                Text('Last final', style: theme.textTheme.labelSmall),
                Text(
                  _lastFinal.isEmpty ? '—' : _lastFinal,
                  style: theme.textTheme.titleMedium,
                ),
              ],
            ),
          ),
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              itemCount: _logLines.length,
              itemBuilder: (_, i) => Text(
                _logLines[i],
                style: const TextStyle(fontSize: 11, fontFamily: 'monospace'),
              ),
            ),
          ),
          GestureDetector(
            onTapDown: (_) => _onPressDown(),
            onTapUp: (_) => _onPressUp(),
            onTapCancel: _onPressUp,
            child: Container(
              height: 96,
              width: double.infinity,
              color: _isHolding ? Colors.redAccent : theme.colorScheme.primary,
              alignment: Alignment.center,
              child: Text(
                _isHolding ? 'RELEASE TO TRANSLATE' : 'HOLD TO TALK',
                style: const TextStyle(
                    color: Colors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.bold),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _chip(String label, bool ok, ThemeData theme) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: Chip(
        label: Text(label, style: const TextStyle(fontSize: 10)),
        backgroundColor: ok ? Colors.green.shade100 : Colors.grey.shade300,
        side: BorderSide(color: ok ? Colors.green : Colors.grey),
        padding: EdgeInsets.zero,
        visualDensity: VisualDensity.compact,
      ),
    );
  }
}
