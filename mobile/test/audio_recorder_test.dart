import 'dart:async';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:lingoglass_mobile/audio/recorder.dart';

void main() {
  group('AudioRecorder', () {
    test('re-chunks platform input into 4800-byte frames', () async {
      final driver = _FakeAudioRecorderDriver();
      final recorder = AudioRecorder.withDriver(driver);
      final chunks = <Uint8List>[];
      final stream = await recorder.start();
      final subscription = stream.listen(chunks.add);

      driver.add(Uint8List(2000));
      driver.add(Uint8List(3500));
      driver.add(Uint8List(4100));
      await pumpEventQueue();

      expect(recorder.isRecording, isTrue);
      expect(chunks.map((chunk) => chunk.length), [4800, 4800]);

      await recorder.stop();
      await recorder.stop();
      await subscription.cancel();

      expect(recorder.isRecording, isFalse);
      expect(driver.stopCalls, 1);
    });

    test('propagates RecorderError when the driver cannot start', () async {
      final recorder = AudioRecorder.withDriver(
        _FakeAudioRecorderDriver(startError: RecorderError('denied')),
      );

      await expectLater(recorder.start(), throwsA(isA<RecorderError>()));
      expect(recorder.isRecording, isFalse);
    });
  });
}

class _FakeAudioRecorderDriver implements AudioRecorderDriver {
  _FakeAudioRecorderDriver({this.startError});

  final RecorderError? startError;
  final StreamController<Uint8List> _controller = StreamController<Uint8List>();
  int stopCalls = 0;

  @override
  Future<Stream<Uint8List>> start() async {
    final error = startError;
    if (error != null) {
      throw error;
    }
    return _controller.stream;
  }

  @override
  Future<void> stop() async {
    stopCalls++;
    if (!_controller.isClosed) {
      await _controller.close();
    }
  }

  void add(Uint8List bytes) {
    _controller.add(bytes);
  }
}
