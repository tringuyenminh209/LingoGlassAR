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
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:permission_handler/permission_handler.dart';

import '../audio/recorder.dart';
import '../ble/ble_transport.dart';
import '../data/s1_phrases.dart';
import '../services/device_id.dart';
import '../services/latency_logger.dart';
import '../services/session_client.dart';
import '../services/translator_ws.dart';

enum _PttState { idle, starting, recording, ending, aborting }

// S2 Day 4 — PTT UX tunables. Locked here (Claude prep) so Codex impl
// and any future tune touch only one place.
//
// `_kPostFinalizeCooldown`: time after a trace ends (success OR abort)
// during which a fresh PTT press is rejected. Prevents the S1 Day 9
// double-press pattern where the second press hit between
// `translation.final` and `e2eFinalize()`, discarding the prior trace
// and inflating retry rate. 500 ms is the initial setting from the S2
// open-questions lock; tune empirically in the Day 4 device run if
// retry rate is still > 20 %.
const Duration _kPostFinalizeCooldown = Duration(milliseconds: 500);

// `_kShortPressMin`: a release that happens within this window of press
// is treated as an accidental tap. The trace is aborted with
// `short_press` and the user sees a transient warning instead of an
// empty/garbled transcription row.
const Duration _kShortPressMin = Duration(milliseconds: 100);

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
  final LatencyLogger _latency = LatencyLogger();

  String? _deviceId;
  String? _sessionId;
  bool _isHolding = false;
  bool _isBleConnected = false;
  bool _isWsConnected = false;
  int _bleSeq = 0;

  // Single source of truth for PTT lifecycle. Prevents overlapping
  // press cycles that previously caused permission_handler races and
  // "TranslatorWs already connected" errors.
  _PttState _ptt = _PttState.idle;

  String _partialBuffer = '';
  String _lastFinal = '';
  final List<String> _logLines = <String>[];

  StreamSubscription<bool>? _bleConnSub;
  StreamSubscription<AckEvent>? _bleAckSub;
  StreamSubscription<TextDelta>? _wsTextSub;
  StreamSubscription<Uint8List>? _audioSub;
  Timer? _s1Timeout;
  Timer? _s1Advance;
  var _s1Running = false;
  var _s1Index = 0;

  // S2 Day 4 — PTT UX state (Codex impl fills bodies). All three pieces
  // share the same lifecycle: created on press, consulted on release,
  // cleared on teardown.
  Timer? _cooldownTimer;
  int? _pressDownTsMicros;

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
    _bleAckSub = _ble.acks.listen(_onBleAck);
    if (!mounted) return;
    setState(() => _deviceId = id);
    _log('Device ID ${id.substring(0, 8)}...');

    // Pre-warm mic permission once at startup. permission_handler does
    // not allow concurrent requests; doing this here means recorder.start()
    // later sees an already-granted state and never re-prompts.
    final perm = await Permission.microphone.request();
    if (!perm.isGranted) {
      _log('Mic permission denied - PTT will fail until granted');
    } else {
      _log('Mic permission granted');
    }
  }

  @override
  void dispose() {
    _bleConnSub?.cancel();
    _bleAckSub?.cancel();
    _wsTextSub?.cancel();
    _audioSub?.cancel();
    _s1Timeout?.cancel();
    _s1Advance?.cancel();
    _cooldownTimer?.cancel();
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
    if (_ptt != _PttState.idle) {
      _log('PTT busy (state=${_ptt.name}), press ignored');
      return;
    }
    // S2 Day 4 (a) — cooldown gate. Stub returns false; Codex makes it
    // honour `_cooldownTimer`.
    if (_isInCooldown()) {
      _log('PTT cooldown, press ignored');
      return;
    }
    if (_deviceId == null) {
      _log('Not ready (deviceId pending)');
      return;
    }
    _ptt = _PttState.starting;
    _pressDownTsMicros = DateTime.now().microsecondsSinceEpoch;
    final phrase = _currentS1Phrase;
    if (phrase != null) {
      // S2 Day 4 (c) — discard banner. e2eStart now returns the
      // discarded prior record (or null) — stub `_showDiscardBanner` is
      // a no-op until Codex wires the UI.
      final discarded = _latency.e2eStart(phrase.id);
      if (discarded != null) {
        _showDiscardBanner(discarded);
      }
    }
    setState(() {
      _isHolding = true;
      _partialBuffer = '';
    });

    try {
      _sessionId ??= (await _sessionClient.createSession(_deviceId!)).sessionId;
      if (_ptt != _PttState.starting) return; // aborted while creating session
      _log('Session ${_sessionId!.substring(0, 8)}...');

      await _ws.connect(_sessionId!, deviceId: _deviceId!);
      _latency.e2eMarkSessionOpened(_sessionId!);
      if (_ptt != _PttState.starting) {
        // User released during connect; clean up the now-orphaned socket.
        await _ws.disconnect();
        return;
      }
      _wsTextSub = _ws.textStream.listen(_onTextDelta, onError: _onWsError);
      setState(() => _isWsConnected = true);
      _log('WS connected');

      final audioStream = await _recorder.start();
      if (_ptt != _PttState.starting) {
        await _recorder.stop();
        await _ws.disconnect();
        return;
      }
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
      _ptt = _PttState.recording;
      _log('Recording...');
    } catch (e) {
      if (_latency.e2eAbort('start_error') != null) {
        _scheduleS1Advance();
      }
      _log('Start error: $e');
      await _teardownPtt();
    }
  }

  Future<void> _onPressUp() async {
    if (_ptt == _PttState.idle) return;

    // S2 Day 4 (b) — short-press detection. Must run BEFORE
    // `e2eMarkPttRelease` so a discarded short press doesn't leak a
    // bogus audio_ms into the CSV row. Stub `_isShortPress` is false
    // until Codex wires the press-down timestamp comparison.
    if (_isShortPress()) {
      _showShortPressWarning();
      _latency.e2eAbort('short_press');
      _s1Timeout?.cancel();
      _ptt = _PttState.aborting;
      setState(() => _isHolding = false);
      _log('Short press ignored (<${_kShortPressMin.inMilliseconds}ms)');
      await _teardownPtt();
      return;
    }

    _latency.e2eMarkPttRelease();
    _s1Timeout?.cancel();
    setState(() => _isHolding = false);

    if (_ptt == _PttState.starting) {
      // Released before connect/recorder fully spun up. Mark cancelled and
      // let _onPressDown's checkpoints unwind. As a safety net, also tear
      // down here in case the in-flight chain already passed all checkpoints.
      _ptt = _PttState.aborting;
      _log('Released before ready, aborting');
      await _teardownPtt();
      return;
    }

    if (_ptt != _PttState.recording) return;
    _ptt = _PttState.ending;

    await _audioSub?.cancel();
    _audioSub = null;
    await _recorder.stop();
    if (!_isWsConnected) {
      _log('WS not connected at end, aborting');
      await _teardownPtt();
      return;
    }
    try {
      _ws.endUtterance();
      _log('Audio ended, awaiting translation...');
    } catch (e) {
      _log('endUtterance error: $e');
      await _teardownPtt();
    }
  }

  Future<void> _teardownPtt() async {
    setState(() => _isHolding = false);
    await _audioSub?.cancel();
    _audioSub = null;
    await _recorder.stop();
    await _wsTextSub?.cancel();
    _wsTextSub = null;
    await _ws.disconnect();
    if (mounted) setState(() => _isWsConnected = false);
    _ptt = _PttState.idle;
    _pressDownTsMicros = null;
    // S2 Day 4 (a) — start cooldown after every terminal teardown so a
    // fast re-press is rejected by `_isInCooldown()`. Stub is a no-op
    // until Codex wires the timer.
    _startPostFinalizeCooldown();
  }

  // ------------------------------------------------------------------
  // S2 Day 4 — PTT UX (Claude prep + Codex impl split)
  //
  // (a) cooldown: state-machine only, no UI — fully implemented in
  //     prep. A press during cooldown is silently rejected; the user
  //     experiences "press did nothing", which is the intended
  //     feedback because the trace just ended.
  // (b) short-press: detection wired here returning `false` (stub);
  //     Codex flips it + adds SnackBar UI in [_showShortPressWarning]
  //     in the same PR so the user always sees feedback when the press
  //     is rejected.
  // (c) discard banner: detection already wired via the new
  //     [LatencyLogger.e2eStart] return value; Codex fills
  //     [_showDiscardBanner].
  // ------------------------------------------------------------------

  /// True iff a fresh PTT press should be rejected because a prior
  /// trace just ended (cooldown is active).
  bool _isInCooldown() => _cooldownTimer?.isActive ?? false;

  /// Schedule the post-finalize cooldown. Called from [_teardownPtt]
  /// at every terminal state (success + abort + error).
  void _startPostFinalizeCooldown() {
    _cooldownTimer?.cancel();
    _cooldownTimer = Timer(_kPostFinalizeCooldown, () {
      _cooldownTimer = null;
    });
  }

  /// True iff the PTT release happened within [_kShortPressMin] of
  /// press. Consulted by [_onPressUp] BEFORE any state mutation so a
  /// discarded short press leaves no side-effects.
  ///
  /// Codex (Day 4 body): replace the stub return with the real
  /// comparison:
  ///
  ///   final pressed = _pressDownTsMicros;
  ///   if (pressed == null) return false;
  ///   final held = DateTime.now().microsecondsSinceEpoch - pressed;
  ///   return held < _kShortPressMin.inMicroseconds;
  ///
  /// Until Codex flips this, short-press detection is OFF and existing
  /// S1 behaviour is preserved.
  bool _isShortPress() {
    final pressed = _pressDownTsMicros;
    if (pressed == null) return false;
    final heldMicros = DateTime.now().microsecondsSinceEpoch - pressed;
    return heldMicros < _kShortPressMin.inMicroseconds;
  }

  /// Show transient feedback when the user released too fast.
  ///
  /// Codex (Day 4 body): SnackBar (preferred — auto-dismisses) with a
  /// message such as "Hold longer to record". Theme/copy is yours, but
  /// keep the duration short (≤ 2 s) so it doesn't stack on a series
  /// of accidental taps.
  void _showShortPressWarning() {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        const SnackBar(
          content: Text('Hold longer to record'),
          duration: Duration(milliseconds: 1500),
          behavior: SnackBarBehavior.floating,
        ),
      );
  }

  /// Show transient feedback when a back-to-back press discarded the
  /// previous trace.
  ///
  /// Codex (Day 4 body): SnackBar (preferred) naming the discarded
  /// phrase id so the operator knows which row is now "discarded" in
  /// the CSV. Example copy: "Previous attempt (greeting-01) discarded".
  void _showDiscardBanner(E2eLatencyRecord discarded) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text('Previous attempt (${discarded.phraseId}) discarded'),
          duration: const Duration(seconds: 2),
          behavior: SnackBarBehavior.floating,
        ),
      );
  }

  void _onTextDelta(TextDelta delta) {
    if (delta.isFinal) {
      _latency.e2eMarkTranslationFinal();
      setState(() {
        _lastFinal = delta.text;
        _partialBuffer = '';
      });
      _log('Final: ${delta.text}');
      if (_isBleConnected) {
        unawaited(_sendToBle(delta.text));
      } else {
        if (_latency.e2eAbort('ble_unavailable') != null) {
          _scheduleS1Advance();
        }
        _log('(BLE not connected, OLED skipped)');
      }
      unawaited(_teardownPtt());
    } else {
      if (delta.text.isNotEmpty) {
        _latency.e2eMarkFirstText();
      }
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
    if (_latency.e2eAbort('ws_error') != null) {
      _scheduleS1Advance();
    }
    _log('WS error: $error');
    setState(() => _isWsConnected = false);
    unawaited(_teardownPtt());
  }

  void _onBleAck(AckEvent ack) {
    if (!ack.isOk || ack.sequenceId != _bleSeq) return;
    _latency.e2eMarkBleAck(ack.sequenceId);
    if (_latency.e2eFinalize() != null) {
      _log('E2E row complete id=${_currentS1Phrase?.id ?? '-'}');
      _scheduleS1Advance();
    }
  }

  S1Phrase? get _currentS1Phrase {
    if (!_s1Running || _s1Index >= s1Phrases.length) return null;
    return s1Phrases[_s1Index];
  }

  void _startS1Run() {
    if (_s1Running) return;
    _latency.clearE2e();
    setState(() {
      _s1Running = true;
      _s1Index = 0;
    });
    _log('S1 Run 10 started');
    _armS1Phrase();
  }

  void _armS1Phrase() {
    final phrase = _currentS1Phrase;
    _s1Timeout?.cancel();
    if (phrase == null) {
      setState(() => _s1Running = false);
      _log('S1 Run 10 finished');
      return;
    }
    _log('S1 phrase ${phrase.id} ready');
    _s1Timeout = Timer(const Duration(seconds: 30), () {
      if (_latency.e2eAbort('timeout') != null) {
        _log('S1 phrase ${phrase.id} timeout');
      }
      if (_ptt != _PttState.idle) {
        unawaited(_teardownPtt());
      }
      _scheduleS1Advance(delay: Duration.zero);
    });
  }

  void _scheduleS1Advance(
      {Duration delay = const Duration(milliseconds: 1500)}) {
    if (!_s1Running) return;
    _s1Timeout?.cancel();
    _s1Advance?.cancel();
    _s1Advance = Timer(delay, () {
      if (!mounted) return;
      setState(() => _s1Index += 1);
      _armS1Phrase();
    });
  }

  Future<void> _copyE2eCsv() async {
    await Clipboard.setData(ClipboardData(text: _latency.toE2eCsv()));
    _log('E2E CSV copied');
  }

  void _clearE2e() {
    _latency.clearE2e();
    _log('E2E rows cleared');
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
          if (_currentS1Phrase != null)
            MaterialBanner(
              content: Text(
                _currentS1Phrase!.text,
                style: theme.textTheme.headlineSmall,
              ),
              actions: [
                Text(
                  '${_s1Index + 1}/${s1Phrases.length}',
                  style: theme.textTheme.labelLarge,
                ),
              ],
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
          Wrap(
            alignment: WrapAlignment.center,
            spacing: 8,
            children: [
              TextButton.icon(
                onPressed: _s1Running ? null : _startS1Run,
                icon: const Icon(Icons.play_arrow),
                label: const Text('S1 Run 10'),
              ),
              TextButton.icon(
                onPressed: _copyE2eCsv,
                icon: const Icon(Icons.copy),
                label: const Text('Copy E2E CSV'),
              ),
              TextButton.icon(
                onPressed: _clearE2e,
                icon: const Icon(Icons.delete_outline),
                label: const Text('Clear E2E'),
              ),
            ],
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
