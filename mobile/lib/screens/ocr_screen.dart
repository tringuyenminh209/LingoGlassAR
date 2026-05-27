// S3 OCR capture -> translate -> BLE screen.
//
// Pipeline per capture (mirrors the speech path in translate_screen.dart, but
// anchored at capture, not PTT press):
//   1. ocrStart(captureId)             // latency anchor = capture instant
//   2. controller.takePicture()        // still image -> temp file
//   3. OcrScanner.recognise(path)      // on-device ML Kit; deletes the image
//   4. ocrMarkRecognised(charCount)    // count only, never the text
//   5. TranslateClient.translate(text) // POST /v1/translate (text -> text)
//   6. ocrMarkTranslated()
//   7. BleTransport.sendSubtitle(text) // OLED render, if glasses connected
//   8. on BLE ack 0x01: ocrMarkBleAck + ocrFinalize
//
// The captured image never leaves the phone (on-device OCR; temp file deleted
// in OcrScanner). Recognised + translated text are shown on screen only and
// are NEVER logged. The OCR latency record stores counts/durations only.
//
// BLE connect is initiated by the user via the app-bar button. Translation
// still works without BLE - the OLED leg is just absent (text shows on phone),
// and the latency row is aborted with `ble_unavailable` so the bench only
// scores complete captures.

import 'dart:async';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:permission_handler/permission_handler.dart';

import '../ble/ble_transport.dart';
import '../ocr/ocr_scanner.dart';
import '../services/device_id.dart';
import '../services/latency_logger.dart';
import '../services/translate_client.dart';

enum _OcrStage { idle, recognising, translating, sending }

class OcrScreen extends StatefulWidget {
  const OcrScreen({super.key});

  @override
  State<OcrScreen> createState() => _OcrScreenState();
}

class _OcrScreenState extends State<OcrScreen> {
  final OcrScanner _scanner = OcrScanner();
  final TranslateClient _translateClient = TranslateClient();
  final BleTransport _ble = BleTransport();
  final LatencyLogger _latency = LatencyLogger();

  CameraController? _controller;
  bool _isLoading = true;
  bool _permissionDenied = false;
  _OcrStage _stage = _OcrStage.idle;
  String? _recognisedText;
  String? _translatedText;
  String? _errorMessage;

  String? _deviceId;
  bool _isBleConnected = false;
  int _bleSeq = 0;
  int _captureCounter = 0;

  StreamSubscription<bool>? _bleConnSub;
  StreamSubscription<AckEvent>? _bleAckSub;

  @override
  void initState() {
    super.initState();
    _bootstrap();
    _initialiseCamera();
  }

  Future<void> _bootstrap() async {
    final id = await DeviceId.get();
    _bleConnSub = _ble.connectionChanges.listen((connected) {
      if (!mounted) return;
      setState(() => _isBleConnected = connected);
    });
    _bleAckSub = _ble.acks.listen(_onBleAck);
    if (!mounted) return;
    setState(() => _deviceId = id);
  }

  Future<void> _initialiseCamera() async {
    setState(() {
      _isLoading = true;
      _permissionDenied = false;
      _errorMessage = null;
    });

    final status = await Permission.camera.request();
    if (!mounted) return;
    if (!status.isGranted) {
      setState(() {
        _isLoading = false;
        _permissionDenied = true;
      });
      return;
    }

    CameraController? controller;
    try {
      final cameras = await availableCameras();
      if (!mounted) return;
      if (cameras.isEmpty) {
        setState(() {
          _isLoading = false;
          _errorMessage = 'No camera is available on this device.';
        });
        return;
      }

      final camera = cameras.firstWhere(
        (description) => description.lensDirection == CameraLensDirection.back,
        orElse: () => cameras.first,
      );
      controller = CameraController(
        camera,
        ResolutionPreset.high,
        enableAudio: false,
      );
      await controller.initialize();
      if (!mounted) {
        await controller.dispose();
        return;
      }
      setState(() {
        _controller = controller;
        _isLoading = false;
      });
    } on Object {
      await controller?.dispose();
      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _errorMessage = 'Camera setup failed. Please try again.';
      });
    }
  }

  Future<void> _connectBle() async {
    if (_isBleConnected) return;
    try {
      await _ble.scanAndConnect();
    } catch (e) {
      if (!mounted) return;
      setState(() => _errorMessage = 'BLE connect failed. Try again.');
    }
  }

  /// Full capture pipeline: capture -> on-device OCR -> translate -> BLE.
  /// Each leg stamps the OCR latency record; any failure aborts the record
  /// with a stage-specific error code so the bench can see where it failed.
  Future<void> _captureTranslateSend() async {
    final controller = _controller;
    if (_stage != _OcrStage.idle ||
        controller == null ||
        !controller.value.isInitialized) {
      return;
    }
    final deviceId = _deviceId;
    if (deviceId == null) {
      setState(() => _errorMessage = 'Not ready yet, try again in a moment.');
      return;
    }

    _captureCounter += 1;
    final captureId = 'ocr-${_captureCounter.toString().padLeft(3, '0')}';
    _latency.ocrStart(captureId);

    setState(() {
      _stage = _OcrStage.recognising;
      _errorMessage = null;
      _translatedText = null;
    });

    final String recognised;
    try {
      final image = await controller.takePicture();
      recognised = await _scanner.recognise(image.path);
    } on OcrError {
      _latency.ocrAbort('ocr_error');
      _fail('Text recognition failed. Please try again.');
      return;
    } on Object {
      _latency.ocrAbort('capture_error');
      _fail('Could not capture an image. Please try again.');
      return;
    }
    _latency.ocrMarkRecognised(recognised.length);
    if (!mounted) return;
    setState(() => _recognisedText = recognised);

    if (recognised.trim().isEmpty) {
      _latency.ocrAbort('no_text');
      _setStage(_OcrStage.idle);
      return;
    }

    setState(() => _stage = _OcrStage.translating);
    final String translated;
    try {
      final result = await _translateClient.translate(
        deviceId: deviceId,
        text: recognised,
      );
      translated = result.translatedText;
    } on TranslateClientError {
      _latency.ocrAbort('translate_error');
      _fail('Translation failed. Please try again.');
      return;
    } on Object {
      _latency.ocrAbort('translate_error');
      _fail('Translation failed. Please try again.');
      return;
    }
    _latency.ocrMarkTranslated();
    if (!mounted) return;
    setState(() => _translatedText = translated);

    if (!_isBleConnected) {
      // Translation shows on the phone; the OLED leg is simply absent. The
      // latency row is aborted so the bench only scores complete captures.
      _latency.ocrAbort('ble_unavailable');
      _setStage(_OcrStage.idle);
      return;
    }

    setState(() => _stage = _OcrStage.sending);
    _bleSeq = (_bleSeq + 1) & 0xFFFF;
    try {
      await _ble.sendSubtitle(translated, _bleSeq);
      // ocrMarkBleAck + ocrFinalize happen in _onBleAck when the ESP32 acks.
    } catch (e) {
      _latency.ocrAbort('ble_error');
      _fail('Could not send to glasses. Please try again.');
      return;
    }
    _setStage(_OcrStage.idle);
  }

  void _onBleAck(AckEvent ack) {
    if (!ack.isOk || ack.sequenceId != _bleSeq) return;
    _latency.ocrMarkBleAck(ack.sequenceId);
    _latency.ocrFinalize();
  }

  void _fail(String message) {
    if (!mounted) return;
    setState(() {
      _errorMessage = message;
      _stage = _OcrStage.idle;
    });
  }

  void _setStage(_OcrStage stage) {
    if (!mounted) return;
    setState(() => _stage = stage);
  }

  Future<void> _copyOcrCsv() async {
    await Clipboard.setData(ClipboardData(text: _latency.toOcrCsv()));
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        const SnackBar(
          content: Text('OCR latency CSV copied'),
          duration: Duration(milliseconds: 1500),
          behavior: SnackBarBehavior.floating,
        ),
      );
  }

  @override
  void dispose() {
    _bleConnSub?.cancel();
    _bleAckSub?.cancel();
    final controller = _controller;
    if (controller != null) {
      unawaited(controller.dispose());
    }
    unawaited(_scanner.dispose());
    unawaited(_ble.dispose());
    _translateClient.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Scan text'),
        actions: [
          IconButton(
            tooltip: _isBleConnected ? 'Glasses connected' : 'Connect glasses',
            icon: Icon(
              _isBleConnected ? Icons.bluetooth_connected : Icons.bluetooth,
              color: _isBleConnected ? Colors.lightBlueAccent : null,
            ),
            onPressed: _isBleConnected ? null : _connectBle,
          ),
          IconButton(
            tooltip: 'Copy OCR latency CSV',
            icon: const Icon(Icons.copy),
            onPressed: _copyOcrCsv,
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(child: _buildCameraPanel()),
            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (_errorMessage != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: Text(
                        _errorMessage!,
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                    ),
                  _textPanel(
                    context,
                    label: 'Recognised text',
                    value: _recognisedText,
                    emptyHint: 'Capture an image to recognise text.',
                    noContentHint: 'No text detected.',
                  ),
                  const SizedBox(height: 12),
                  _textPanel(
                    context,
                    label: 'Translation',
                    value: _translatedText,
                    emptyHint: 'Translation appears here.',
                    noContentHint: '—',
                  ),
                  const SizedBox(height: 16),
                  FilledButton.icon(
                    onPressed: _canCapture ? _captureTranslateSend : null,
                    icon: _stage == _OcrStage.idle
                        ? const Icon(Icons.camera_alt)
                        : const SizedBox.square(
                            dimension: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          ),
                    label: Text(_captureButtonLabel),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  bool get _canCapture =>
      _stage == _OcrStage.idle && (_controller?.value.isInitialized ?? false);

  String get _captureButtonLabel {
    switch (_stage) {
      case _OcrStage.idle:
        return 'Capture text';
      case _OcrStage.recognising:
        return 'Recognising...';
      case _OcrStage.translating:
        return 'Translating...';
      case _OcrStage.sending:
        return 'Sending to glasses...';
    }
  }

  Widget _textPanel(
    BuildContext context, {
    required String label,
    required String? value,
    required String emptyHint,
    required String noContentHint,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(label, style: Theme.of(context).textTheme.labelLarge),
        const SizedBox(height: 8),
        Container(
          constraints: const BoxConstraints(minHeight: 56),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Text(
            value == null
                ? emptyHint
                : value.isEmpty
                    ? noContentHint
                    : value,
          ),
        ),
      ],
    );
  }

  Widget _buildCameraPanel() {
    if (_permissionDenied) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.no_photography_outlined, size: 48),
              const SizedBox(height: 12),
              const Text(
                'Camera permission denied. Allow camera access to capture text.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              OutlinedButton(
                onPressed: _initialiseCamera,
                child: const Text('Try again'),
              ),
            ],
          ),
        ),
      );
    }
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) {
      return const Center(child: Icon(Icons.camera_alt_outlined, size: 48));
    }
    return Center(
      child: AspectRatio(
        aspectRatio: controller.value.aspectRatio,
        child: CameraPreview(controller),
      ),
    );
  }
}
