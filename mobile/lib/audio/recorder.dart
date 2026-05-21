import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/foundation.dart';
import 'package:flutter_sound/flutter_sound.dart';
import 'package:permission_handler/permission_handler.dart';

const int _sampleRateHz = 24000;
const int _chunkBytes = 4800;

class AudioRecorder {
  AudioRecorder() : this._(_FlutterSoundRecorderDriver());

  @visibleForTesting
  AudioRecorder.withDriver(AudioRecorderDriver driver) : this._(driver);

  AudioRecorder._(this._driver);

  final AudioRecorderDriver _driver;
  StreamController<Uint8List>? _chunkController;
  StreamSubscription<Uint8List>? _inputSubscription;
  BytesBuilder _pending = BytesBuilder(copy: false);
  bool _isRecording = false;

  /// Start capturing PCM16 mono LE at 24 kHz.
  /// Emits ~100 ms chunks (4800 bytes each) on the returned stream.
  /// Throws RecorderError if the OS denies the mic permission or the
  /// platform recorder fails to start.
  Future<Stream<Uint8List>> start() async {
    if (_isRecording) {
      return _chunkController!.stream;
    }

    final controller = StreamController<Uint8List>();
    _chunkController = controller;
    _pending = BytesBuilder(copy: false);

    try {
      final input = await _driver.start();
      _inputSubscription = input.listen(
        _appendInput,
        onError: controller.addError,
        onDone: _closeFromInput,
      );
      _isRecording = true;
      return controller.stream;
    } on RecorderError {
      await _closeOutput();
      rethrow;
    } on Object catch (error) {
      await _closeOutput();
      throw RecorderError('Failed to start the platform recorder: $error');
    }
  }

  /// Stop capturing. Closes the stream, releases the OS recorder.
  /// Safe to call multiple times.
  Future<void> stop() async {
    if (!_isRecording && _chunkController == null) {
      return;
    }

    _isRecording = false;
    await _inputSubscription?.cancel();
    _inputSubscription = null;
    await _driver.stop();
    await _closeOutput();
  }

  /// True between start() and stop().
  bool get isRecording => _isRecording;

  void _appendInput(Uint8List data) {
    final controller = _chunkController;
    if (controller == null || controller.isClosed || data.isEmpty) {
      return;
    }

    _pending.add(data);
    while (_pending.length >= _chunkBytes) {
      final buffered = _pending.takeBytes();
      controller.add(Uint8List.sublistView(buffered, 0, _chunkBytes));
      if (buffered.length > _chunkBytes) {
        _pending.add(Uint8List.sublistView(buffered, _chunkBytes));
      }
    }
  }

  Future<void> _closeFromInput() async {
    _isRecording = false;
    _inputSubscription = null;
    await _closeOutput();
  }

  Future<void> _closeOutput() async {
    _pending = BytesBuilder(copy: false);
    final controller = _chunkController;
    _chunkController = null;
    if (controller != null && !controller.isClosed) {
      unawaited(controller.close());
    }
  }
}

@visibleForTesting
abstract interface class AudioRecorderDriver {
  Future<Stream<Uint8List>> start();

  Future<void> stop();
}

class _FlutterSoundRecorderDriver implements AudioRecorderDriver {
  FlutterSoundRecorder? _recorder;
  StreamController<Uint8List>? _inputController;

  @override
  Future<Stream<Uint8List>> start() async {
    final permission = await Permission.microphone.request();
    if (!permission.isGranted) {
      throw RecorderError('Microphone permission was denied.');
    }

    final recorder = FlutterSoundRecorder();
    // flutter_sound 9.30+ delivers raw PCM bytes directly via
    // StreamSink<Uint8List>. The old `Food` / `FoodData` envelope was
    // dropped, so no .where/.map filter is needed any more.
    final controller = StreamController<Uint8List>();
    _recorder = recorder;
    _inputController = controller;

    try {
      await recorder.openRecorder();
      await recorder.startRecorder(
        codec: Codec.pcm16,
        toStream: controller.sink,
        sampleRate: _sampleRateHz,
        numChannels: 1,
      );
      return controller.stream;
    } on Object {
      await stop();
      rethrow;
    }
  }

  @override
  Future<void> stop() async {
    final recorder = _recorder;
    _recorder = null;
    if (recorder != null) {
      await recorder.stopRecorder();
      await recorder.closeRecorder();
    }

    final controller = _inputController;
    _inputController = null;
    if (controller != null && !controller.isClosed) {
      await controller.close();
    }
  }
}

class RecorderError implements Exception {
  RecorderError(this.message);

  final String message;

  @override
  String toString() => 'RecorderError: $message';
}
