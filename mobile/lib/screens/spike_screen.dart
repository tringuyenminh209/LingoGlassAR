// LingoGlass AR S0 spike screen.
// Phase D: Scan / Send Hello wired through BleTransport.
// Phase E: Send Japanese (multi-fragment) + MTU matrix (23/185/247).
// Phase F: Run 20 will add latency CSV export.

import 'dart:async';

import 'package:flutter/material.dart';

import '../ble/ble_transport.dart';

// ~100 character Japanese sample. UTF-8 ~ 300 bytes, multi-fragment at every
// supported MTU. Mix of hiragana, katakana, kanji, punctuation.
const String _japaneseSample = 'こんにちは、ヤマグチへようこそ。LingoGlassは旅行者のための'
    'リアルタイム字幕メガネです。話している言葉が目の前にすぐ表示されます。'
    '便利でしょう？';

const List<int> _mtuMatrix = [23, 185, 247];

class SpikeScreen extends StatefulWidget {
  const SpikeScreen({super.key});

  @override
  State<SpikeScreen> createState() => _SpikeScreenState();
}

class _SpikeScreenState extends State<SpikeScreen> {
  final List<String> _log = <String>[];
  late final BleTransport _transport;
  StreamSubscription<AckEvent>? _ackSub;
  StreamSubscription<bool>? _connSub;
  int _nextSeq = 1;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _transport = BleTransport(log: _append);
    _ackSub = _transport.acks.listen((ack) {
      _append(
          '< ACK seq=${ack.sequenceId} status=0x${ack.status.toRadixString(16).padLeft(2, '0')} ok=${ack.isOk}');
    });
    // Rebuild the CONN/idle chip when the link goes up or down so the UI
    // stops lying after an external disconnect (BT toggle, range, etc.).
    _connSub = _transport.connectionChanges.listen((_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _ackSub?.cancel();
    _connSub?.cancel();
    _transport.dispose();
    super.dispose();
  }

  void _append(String line) {
    if (!mounted) return;
    setState(() => _log.add(line));
  }

  Future<void> _onScanPressed() async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      await _transport.scanAndConnect();
    } on Exception catch (e) {
      _append('scan/connect FAILED: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _sendText(String text, {int? mtu}) async {
    if (!_transport.isConnected) {
      _append('not connected. tap Scan first.');
      return;
    }
    final seq = _nextSeq++;
    final mtuLabel =
        mtu == null ? 'mtu=auto(${_transport.negotiatedMtu})' : 'mtu=$mtu';
    try {
      final frags = await _transport.sendSubtitle(text, seq, mtu: mtu);
      _append('> sent len=${text.length} seq=$seq $mtuLabel frags=$frags');
    } on Exception catch (e) {
      _append('send FAILED ($mtuLabel): $e');
    } on StateError catch (e) {
      _append('send FAILED ($mtuLabel): $e');
    }
  }

  Future<void> _onSendHelloPressed() async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      await _sendText('Hello');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _onSendJapanesePressed() async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      await _sendText(_japaneseSample);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  // Sends the Japanese sample once per MTU in the matrix, with a small gap
  // so the firmware can finish assembling + ACK before the next sequence.
  Future<void> _onMtuMatrixPressed() async {
    if (_busy) return;
    if (!_transport.isConnected) {
      _append('not connected. tap Scan first.');
      return;
    }
    setState(() => _busy = true);
    try {
      _append('-- MTU matrix start --');
      for (final mtu in _mtuMatrix) {
        await _sendText(_japaneseSample, mtu: mtu);
        await Future<void>.delayed(const Duration(milliseconds: 1500));
      }
      _append('-- MTU matrix done --');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _onRun20Pressed() {
    // TODO Phase F: send 20 subtitles, log latency, export CSV.
    _append('Run-20 latency test not implemented yet (Phase F).');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('LingoGlass S0 spike'),
        actions: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: Center(
              child: Text(
                _transport.isConnected
                    ? 'CONN mtu=${_transport.negotiatedMtu}'
                    : 'idle',
                style: TextStyle(
                  color: _transport.isConnected
                      ? Colors.greenAccent
                      : Colors.white70,
                ),
              ),
            ),
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: FilledButton(
                    onPressed: _busy ? null : _onScanPressed,
                    child: const Text('Scan'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: FilledButton(
                    onPressed: _busy ? null : _onSendHelloPressed,
                    child: const Text('Send Hello'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: FilledButton(
                    onPressed: _busy ? null : _onRun20Pressed,
                    child: const Text('Run 20'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: FilledButton.tonal(
                    onPressed: _busy ? null : _onSendJapanesePressed,
                    child: const Text('Send JA (auto MTU)'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: FilledButton.tonal(
                    onPressed: _busy ? null : _onMtuMatrixPressed,
                    child: const Text('MTU matrix 23/185/247'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            const Text('Log', style: TextStyle(fontWeight: FontWeight.bold)),
            const Divider(),
            Expanded(
              child: ListView.builder(
                reverse: true,
                itemCount: _log.length,
                itemBuilder: (_, i) => Text(
                  _log[_log.length - 1 - i],
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
