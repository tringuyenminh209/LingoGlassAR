// LingoGlass AR S0 spike screen.
// Phase D: Scan / Send Hello wired through BleTransport.
// Phase F: Run 20 will add latency CSV export.

import 'package:flutter/material.dart';

import '../ble/ble_transport.dart';

class SpikeScreen extends StatefulWidget {
  const SpikeScreen({super.key});

  @override
  State<SpikeScreen> createState() => _SpikeScreenState();
}

class _SpikeScreenState extends State<SpikeScreen> {
  final List<String> _log = <String>[];
  late final BleTransport _transport;
  int _nextSeq = 1;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _transport = BleTransport(log: _append);
    _transport.acks.listen((ack) {
      _append('< ACK seq=${ack.sequenceId} ok=${ack.isOk}');
    });
  }

  @override
  void dispose() {
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

  Future<void> _onSendPressed() async {
    if (_busy) return;
    if (!_transport.isConnected) {
      _append('not connected. tap Scan first.');
      return;
    }
    setState(() => _busy = true);
    final seq = _nextSeq++;
    try {
      final frags = await _transport.sendSubtitle('Hello', seq);
      _append('> sent "Hello" seq=$seq frags=$frags');
    } on Exception catch (e) {
      _append('send FAILED: $e');
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
                _transport.isConnected ? 'CONN' : 'idle',
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
                    onPressed: _busy ? null : _onSendPressed,
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
