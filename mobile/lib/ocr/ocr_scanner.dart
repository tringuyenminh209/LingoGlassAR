import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart';

/// On-device OCR for the S3 camera path.
///
/// [recognise] runs Google ML Kit's Japanese text recogniser **on the phone**
/// against a still image the camera UI just captured, then deletes that image
/// before returning. The captured bytes never leave the device and never
/// persist past this call — only the recognised text is returned, which is the
/// only thing allowed to cross the WS to the backend (privacy boundary, see
/// root CLAUDE.md + docs/reports/S3_ocr_probe.md).
///
/// Mirrors the [AudioRecorder] shape: a thin orchestrator with an injectable
/// [OcrDriver] so the privacy-critical "always delete the image" logic is unit
/// testable with a fake driver (the ML Kit / file-system calls are not). The
/// camera capture + preview live in the capture UI (it owns the
/// `CameraController`); this class takes the resulting file path.
class OcrScanner {
  OcrScanner() : this._(_MlKitOcrDriver());

  @visibleForTesting
  OcrScanner.withDriver(OcrDriver driver) : this._(driver);

  OcrScanner._(this._driver);

  final OcrDriver _driver;

  /// Recognise Japanese text in the still image at [imagePath] using on-device
  /// ML Kit, then delete the file before returning.
  ///
  /// The image is deleted in a `finally` so it is removed even when
  /// recognition throws — the bytes must not survive a failure. Returns the
  /// recognised text (may be empty if nothing was found). Throws [OcrError]
  /// on recognition failure.
  Future<String> recognise(String imagePath) async {
    try {
      return await _driver.recognise(imagePath);
    } on OcrError {
      rethrow;
    } on Object catch (error) {
      throw OcrError('OCR recognition failed: $error');
    } finally {
      // Privacy: the captured image never persists, even on failure.
      await _driver.deleteImage(imagePath);
    }
  }

  /// Release the underlying recogniser. Safe to call multiple times.
  Future<void> dispose() => _driver.dispose();
}

@visibleForTesting
abstract interface class OcrDriver {
  /// Run on-device OCR on the image at [imagePath]; return recognised text.
  Future<String> recognise(String imagePath);

  /// Delete the captured image at [imagePath]. Must not throw if the file is
  /// already gone.
  Future<void> deleteImage(String imagePath);

  /// Release native resources.
  Future<void> dispose();
}

class _MlKitOcrDriver implements OcrDriver {
  // Japanese script model. The plugin runs recognition fully on-device and
  // offline; nothing is uploaded. arm64 only (Galaxy S10 OK).
  final TextRecognizer _recognizer = TextRecognizer(
    script: TextRecognitionScript.japanese,
  );

  @override
  Future<String> recognise(String imagePath) async {
    final inputImage = InputImage.fromFilePath(imagePath);
    final recognised = await _recognizer.processImage(inputImage);
    // `.text` is the full recognised text (blocks joined by newlines). The
    // operator scores the key line by eye (criterion #1); the text is never
    // logged or stored here.
    return recognised.text;
  }

  @override
  Future<void> deleteImage(String imagePath) async {
    final file = File(imagePath);
    if (await file.exists()) {
      await file.delete();
    }
  }

  @override
  Future<void> dispose() => _recognizer.close();
}

class OcrError implements Exception {
  OcrError(this.message);

  final String message;

  @override
  String toString() => 'OcrError: $message';
}
