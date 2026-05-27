import 'dart:async';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';

import '../ocr/ocr_scanner.dart';

/// Captures a still image for on-device OCR and shows the recognised text.
///
/// Translation and BLE forwarding are intentionally left for the next step.
class OcrScreen extends StatefulWidget {
  const OcrScreen({super.key});

  @override
  State<OcrScreen> createState() => _OcrScreenState();
}

class _OcrScreenState extends State<OcrScreen> {
  final OcrScanner _scanner = OcrScanner();

  CameraController? _controller;
  bool _isLoading = true;
  bool _permissionDenied = false;
  bool _isRecognising = false;
  String? _recognisedText;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _initialiseCamera();
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

  Future<void> _captureAndRecognise() async {
    final controller = _controller;
    if (_isRecognising ||
        controller == null ||
        !controller.value.isInitialized) {
      return;
    }

    setState(() {
      _isRecognising = true;
      _errorMessage = null;
    });

    try {
      final image = await controller.takePicture();
      final text = await _scanner.recognise(image.path);
      if (!mounted) return;
      setState(() => _recognisedText = text);
    } on OcrError {
      if (!mounted) return;
      setState(() {
        _errorMessage = 'Text recognition failed. Please try again.';
      });
    } on Object {
      if (!mounted) return;
      setState(() {
        _errorMessage = 'Could not capture an image. Please try again.';
      });
    } finally {
      if (mounted) {
        setState(() => _isRecognising = false);
      }
    }
  }

  @override
  void dispose() {
    final controller = _controller;
    if (controller != null) {
      unawaited(controller.dispose());
    }
    unawaited(_scanner.dispose());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Scan text')),
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
                  Text(
                    'Recognised text',
                    style: Theme.of(context).textTheme.labelLarge,
                  ),
                  const SizedBox(height: 8),
                  Container(
                    constraints: const BoxConstraints(minHeight: 72),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color:
                          Theme.of(context).colorScheme.surfaceContainerHighest,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      _recognisedText == null
                          ? 'Capture an image to recognise text.'
                          : _recognisedText!.isEmpty
                              ? 'No text detected.'
                              : _recognisedText!,
                    ),
                  ),
                  const SizedBox(height: 16),
                  FilledButton.icon(
                    onPressed: _canCapture ? _captureAndRecognise : null,
                    icon: _isRecognising
                        ? const SizedBox.square(
                            dimension: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.camera_alt),
                    label: Text(
                      _isRecognising ? 'Recognising...' : 'Capture text',
                    ),
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
      !_isRecognising && (_controller?.value.isInitialized ?? false);

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
