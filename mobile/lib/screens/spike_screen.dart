// LingoGlass AR S0 spike screen.
// Phase A: scaffolded UI shell. Functional BLE scan/connect/send + latency log
// land in Phase C-F. The widget tree is laid out now so Phase C just fills the
// callbacks.

import 'package:flutter/material.dart';

class SpikeScreen extends StatefulWidget {
  const SpikeScreen({super.key});

  @override
  State<SpikeScreen> createState() => _SpikeScreenState();
}

class _SpikeScreenState extends State<SpikeScreen> {
  final List<String> _log = <String>[];

  void _onScanPressed() {
    // TODO Phase C: trigger flutter_blue_plus scan for service UUID.
    setState(() => _log.add('Scan not implemented yet (Phase C).'));
  }

  void _onSendPressed() {
    // TODO Phase D: encode subtitle via ble_protocol, write characteristic.
    setState(() => _log.add('Send not implemented yet (Phase D).'));
  }

  void _onRun20Pressed() {
    // TODO Phase F: send 20 subtitles, log latency, export CSV.
    setState(
      () => _log.add('Run-20 latency test not implemented yet (Phase F).'),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('LingoGlass S0 spike')),
      body: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: FilledButton(
                    onPressed: _onScanPressed,
                    child: const Text('Scan'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: FilledButton(
                    onPressed: _onSendPressed,
                    child: const Text('Send Hello'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: FilledButton(
                    onPressed: _onRun20Pressed,
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
                itemCount: _log.length,
                itemBuilder: (_, i) => Text(
                  _log[i],
                  style: const TextStyle(fontFamily: 'monospace'),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
