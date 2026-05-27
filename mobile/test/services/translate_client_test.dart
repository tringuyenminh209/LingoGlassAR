import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:lingoglass_mobile/services/translate_client.dart';

void main() {
  group('TranslateClient', () {
    test('successful response returns result and sends contract payload',
        () async {
      late http.Request capturedRequest;
      final client = TranslateClient(
        apiBase: Uri.parse('https://backend.test'),
        httpClient: MockClient((request) async {
          capturedRequest = request;
          return http.Response(
            jsonEncode({
              'success': true,
              'data': {
                'translatedText': 'translated-output',
                'durationMs': 123,
              },
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        }),
      );

      final result = await client.translate(
        deviceId: 'device-1',
        sourceLang: 'ja',
        targetLang: 'vi',
        text: 'source-input',
      );

      expect(result.translatedText, 'translated-output');
      expect(result.durationMs, 123);
      expect(capturedRequest.method, 'POST');
      expect(
          capturedRequest.url, Uri.parse('https://backend.test/v1/translate'));
      expect(
        jsonDecode(capturedRequest.body),
        <String, Object?>{
          'deviceId': 'device-1',
          'sourceLang': 'ja',
          'targetLang': 'vi',
          'text': 'source-input',
        },
      );
    });

    test('429 maps to daily cap exceeded', () async {
      final error = await _translateErrorFor(http.Response('', 429));

      expect(error.code, 'daily_cap_exceeded');
      expect(error.retryable, false);
    });

    test('502 maps to retryable translator error', () async {
      final error = await _translateErrorFor(http.Response('', 502));

      expect(error.code, 'translator_error');
      expect(error.retryable, true);
    });

    test('other non-200 maps to retryable upstream unavailable', () async {
      final error = await _translateErrorFor(http.Response('', 500));

      expect(error.code, 'upstream_unavailable');
      expect(error.retryable, true);
    });

    test('success false maps to internal error', () async {
      final error = await _translateErrorFor(
        http.Response(jsonEncode({'success': false}), 200),
      );

      expect(error.code, 'internal_error');
      expect(error.retryable, false);
    });

    test('non-200 errors do not leak response body text', () async {
      const bodyMarker = 'DO_NOT_LEAK_TRANSLATED_BODY';

      final error = await _translateErrorFor(http.Response(bodyMarker, 500));

      expect(error.toString(), isNot(contains(bodyMarker)));
    });
  });
}

Future<TranslateClientError> _translateErrorFor(http.Response response) async {
  final client = TranslateClient(
    apiBase: Uri.parse('https://backend.test'),
    httpClient: MockClient((_) async => response),
  );

  try {
    await client.translate(
      deviceId: 'device-1',
      sourceLang: 'ja',
      targetLang: 'vi',
      text: 'source-input',
    );
  } on TranslateClientError catch (error) {
    return error;
  }

  fail('Expected TranslateClientError');
}
