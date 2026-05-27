import 'package:flutter_test/flutter_test.dart';
import 'package:lingoglass_mobile/ocr/ocr_scanner.dart';

void main() {
  group('OcrScanner', () {
    test('returns driver text and deletes the captured image once', () async {
      final driver = _FakeOcrDriver(text: 'sample-result');
      final scanner = OcrScanner.withDriver(driver);

      final result = await scanner.recognise('/capture/input.jpg');

      expect(result, 'sample-result');
      expect(driver.recognisePaths, ['/capture/input.jpg']);
      expect(driver.deletedPaths, ['/capture/input.jpg']);
    });

    test('deletes the captured image when recognition fails', () async {
      final driver = _FakeOcrDriver(error: StateError('recognition failed'));
      final scanner = OcrScanner.withDriver(driver);

      await expectLater(
        scanner.recognise('/capture/failure.jpg'),
        throwsA(isA<OcrError>()),
      );

      expect(driver.deletedPaths, ['/capture/failure.jpg']);
    });

    test('wraps non-OcrError and rethrows OcrError unchanged', () async {
      final wrappedDriver = _FakeOcrDriver(error: ArgumentError('invalid'));
      final wrappedScanner = OcrScanner.withDriver(wrappedDriver);
      await expectLater(
        wrappedScanner.recognise('/capture/wrapped.jpg'),
        throwsA(isA<OcrError>()),
      );

      final originalError = OcrError('driver error');
      final rethrownDriver = _FakeOcrDriver(error: originalError);
      final rethrownScanner = OcrScanner.withDriver(rethrownDriver);
      await expectLater(
        rethrownScanner.recognise('/capture/rethrown.jpg'),
        throwsA(same(originalError)),
      );
    });

    test('dispose forwards to the driver', () async {
      final driver = _FakeOcrDriver();
      final scanner = OcrScanner.withDriver(driver);

      await scanner.dispose();

      expect(driver.disposeCalls, 1);
    });
  });
}

class _FakeOcrDriver implements OcrDriver {
  _FakeOcrDriver({this.text = '', this.error});

  final String text;
  final Object? error;
  final List<String> recognisePaths = <String>[];
  final List<String> deletedPaths = <String>[];
  int disposeCalls = 0;

  @override
  Future<String> recognise(String imagePath) async {
    recognisePaths.add(imagePath);
    final failure = error;
    if (failure != null) {
      throw failure;
    }
    return text;
  }

  @override
  Future<void> deleteImage(String imagePath) async {
    deletedPaths.add(imagePath);
  }

  @override
  Future<void> dispose() async {
    disposeCalls++;
  }
}
