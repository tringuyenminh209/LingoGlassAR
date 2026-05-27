// HTTP client for the backend translate-only API (S3 OCR path).
//
// Maps directly to docs/api-contract/openapi.yaml:
//   POST /v1/translate -> 200 {success: true, data: {translatedText, durationMs}}
//   429 daily_cap_exceeded -> TranslateClientError(code: 'daily_cap_exceeded')
//   502 translator_error   -> TranslateClientError(code: 'translator_error')
//
// Why a separate one-shot client (not the WS path): OCR already holds the full
// recognised text, so it needs a single text->text request, not the audio WS
// state machine. See docs/codex/S3_TASKS.md Day 2.
//
// Privacy: the request `text` (OCR'd source) and the response `translatedText`
// are NEVER logged here, and never put into an error message — same hard rule
// as the audio path. Only HTTP status codes surface on failure.
//
// One TranslateClient instance is reusable across calls; the caller owns the
// lifecycle and should not close the underlying http.Client mid-flight.

import 'dart:convert';

import 'package:http/http.dart' as http;

class TranslateResult {
  const TranslateResult({
    required this.translatedText,
    required this.durationMs,
  });

  /// JP<->VN translation of the input text.
  final String translatedText;

  /// Backend-measured translate round-trip in ms (connect + OpenAI translate).
  /// Informational; the device-side OCR latency record times its own legs.
  final int durationMs;
}

class TranslateClientError implements Exception {
  TranslateClientError(this.code, this.message, {this.retryable = false});

  final String code;
  final String message;
  final bool retryable;

  @override
  String toString() => 'TranslateClientError($code): $message';
}

class TranslateClient {
  TranslateClient({Uri? apiBase, http.Client? httpClient})
      : _apiBase = apiBase ?? Uri.parse('https://api.lingoglass.online'),
        _http = httpClient ?? http.Client();

  final Uri _apiBase;
  final http.Client _http;

  /// POST /v1/translate with the OCR'd text. Returns the parsed
  /// [TranslateResult] on 200; throws [TranslateClientError] on 429 (cap),
  /// 502 (translator upstream), or any other non-success status.
  ///
  /// Note: error messages never include the response body — a 200 body
  /// carries `translatedText`, which must not leak into logs.
  Future<TranslateResult> translate({
    required String deviceId,
    required String text,
    String sourceLang = 'ja',
    String targetLang = 'vi',
  }) async {
    final url = _apiBase.resolve('/v1/translate');
    final response = await _http.post(
      url,
      headers: const {'content-type': 'application/json'},
      body: jsonEncode({
        'deviceId': deviceId,
        'sourceLang': sourceLang,
        'targetLang': targetLang,
        'text': text,
      }),
    );

    if (response.statusCode == 429) {
      throw TranslateClientError(
        'daily_cap_exceeded',
        'Daily spend cap exceeded',
      );
    }
    if (response.statusCode == 502) {
      throw TranslateClientError(
        'translator_error',
        'Translator upstream failed',
        retryable: true,
      );
    }
    if (response.statusCode != 200) {
      throw TranslateClientError(
        'upstream_unavailable',
        'translate HTTP ${response.statusCode}',
        retryable: true,
      );
    }

    final body = jsonDecode(response.body) as Map<String, Object?>;
    if (body['success'] != true) {
      throw TranslateClientError(
        'internal_error',
        'translate response not successful',
      );
    }
    final data = body['data'] as Map<String, Object?>;
    return TranslateResult(
      translatedText: data['translatedText'] as String,
      durationMs: data['durationMs'] as int,
    );
  }

  /// Close the underlying HTTP client. After this the TranslateClient is
  /// unusable. Safe to call multiple times.
  void close() => _http.close();
}
