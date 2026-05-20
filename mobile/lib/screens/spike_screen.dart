// LingoGlass AR S0 spike screen.
// Phase D: Scan / Send Hello wired through BleTransport.
// Phase E: Send Japanese (multi-fragment) + MTU matrix (23/185/247).
// Phase F: Run 20 will add latency CSV export.

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../ble/ble_transport.dart';
import '../services/latency_logger.dart';

// ~100 character Japanese sample. UTF-8 ~ 300 bytes, multi-fragment at every
// supported MTU. Mix of hiragana, katakana, kanji, punctuation.
const String _japaneseSample = 'こんにちは、ヤマグチへようこそ。LingoGlassは旅行者のための'
    'リアルタイム字幕メガネです。話している言葉が目の前にすぐ表示されます。'
    '便利でしょう？';

const List<int> _mtuMatrix = [23, 185, 247];

// Phase F latency suite: 20 sends mixing MTUs and a short ASCII line so the
// CSV has a baseline (single-fragment) and stress points (multi-fragment at
// MTU 23). Same order each run for repeatability.
const String _shortSample = 'Hello LingoGlass';
const List<({String text, int mtu})> _latencyRunPlan = [
  // 4 warm-ups at the negotiated MTU
  (text: _shortSample, mtu: 247),
  (text: _shortSample, mtu: 247),
  (text: _shortSample, mtu: 247),
  (text: _shortSample, mtu: 247),
  // 8 JP samples cycling through MTU profiles
  (text: _japaneseSample, mtu: 23),
  (text: _japaneseSample, mtu: 185),
  (text: _japaneseSample, mtu: 247),
  (text: _japaneseSample, mtu: 23),
  (text: _japaneseSample, mtu: 185),
  (text: _japaneseSample, mtu: 247),
  (text: _japaneseSample, mtu: 23),
  (text: _japaneseSample, mtu: 185),
  // 8 short bursts at MTU 247 to measure best-case
  (text: _shortSample, mtu: 247),
  (text: _shortSample, mtu: 247),
  (text: _shortSample, mtu: 247),
  (text: _shortSample, mtu: 247),
  (text: _shortSample, mtu: 247),
  (text: _shortSample, mtu: 247),
  (text: _shortSample, mtu: 247),
  (text: _shortSample, mtu: 247),
];

class SpikeScreen extends StatefulWidget {
  const SpikeScreen({super.key});

  @override
  State<SpikeScreen> createState() => _SpikeScreenState();
}

class _SpikeScreenState extends State<SpikeScreen> {
  final List<String> _log = <String>[];
  late final BleTransport _transport;
  final LatencyLogger _latency = LatencyLogger();
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
      // Feed every ACK to the latency logger. Orphan ACKs (no pending send
      // for that sequence_id) are silently dropped by recordAck.
      final rec = _latency.recordAck(ack);
      if (rec != null) {
        _append(
            '  rtt=${rec.rttMs.toStringAsFixed(1)}ms fw_proc=${rec.fwProcMs ?? '-'}ms');
      }
    });
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
      final info = await _transport.sendSubtitle(
        text,
        seq,
        mtu: mtu,
        onSendStart: (bytes, frags, effMtu) {
          _latency.markSendStart(
            sequenceId: seq,
            mtu: effMtu,
            payloadBytes: bytes,
            fragments: frags,
          );
        },
      );
      _append(
          '> sent len=${text.length} seq=$seq $mtuLabel frags=${info.fragments}');
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

  // Phase F latency suite. Sends the 20-entry _latencyRunPlan, waits for
  // each ACK before issuing the next send (so RTTs don't pipeline together),
  // and prints a summary at the end. CSV is kept in _latency for copy.
  Future<void> _onRun20Pressed() async {
    if (_busy) return;
    if (!_transport.isConnected) {
      _append('not connected. tap Scan first.');
      return;
    }
    setState(() => _busy = true);
    try {
      _append('-- latency run start (${_latencyRunPlan.length} samples) --');
      _latency.clear();
      for (final step in _latencyRunPlan) {
        final seqBefore = _nextSeq;
        await _sendText(step.text, mtu: step.mtu);
        // Wait until this sequence_id is no longer pending (ACK matched) or
        // a short timeout elapses. _sendText incremented _nextSeq before
        // sending so seqBefore is the seq just used.
        final deadline = DateTime.now().add(const Duration(milliseconds: 800));
        while (_latency.records.length < seqBefore &&
            DateTime.now().isBefore(deadline)) {
          await Future<void>.delayed(const Duration(milliseconds: 10));
        }
        // Small inter-send gap so the firmware OLED settles between renders.
        await Future<void>.delayed(const Duration(milliseconds: 150));
      }
      final stats = _latency.summarise();
      if (stats != null) {
        _append('-- latency run done -- ${stats.toString()}');
      } else {
        _append('-- latency run done -- no OK samples recorded');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  // Copies the accumulated CSV to the clipboard. User pastes into a file on
  // the dev machine via adb / mac share for the Phase F report script.
  Future<void> _onCopyCsvPressed() async {
    final csv = _latency.toCsv();
    if (_latency.records.isEmpty) {
      _append('no latency records to copy. run "Run 20" first.');
      return;
    }
    await Clipboard.setData(ClipboardData(text: csv));
    _append('CSV copied to clipboard (${_latency.records.length} rows)');
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
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: _busy ? null : _onCopyCsvPressed,
                    child: const Text('Copy CSV'),
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
