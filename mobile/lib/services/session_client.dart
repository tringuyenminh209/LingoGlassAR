// HTTP client for the backend session API.
//
// Maps directly to docs/api-contract/openapi.yaml:
//   POST /v1/sessions  -> 201 {success: true, data: {sessionId, wsUrl, expiresAt}}
//   429 daily_cap_exceeded -> SessionClientError(retryable: false, code: 'daily_cap_exceeded')
//
// One SessionClient instance is reusable across multiple createSession calls.
// Caller owns the lifecycle and should not close the underlying http.Client
// while requests are in flight.

import 'dart:convert';

import 'package:http/http.dart' as http;

class SessionInfo {
  const SessionInfo({
    required this.sessionId,
    required this.wsUrl,
    required this.expiresAt,
  });

  /// UUID returned by the backend; pass to TranslatorWs.connect().
  final String sessionId;

  /// Absolute WS URL composed by the backend from PUBLIC_BASE_URL.
  /// Informational - TranslatorWs builds its own URL from a base + sessionId.
  final Uri wsUrl;

  /// When the Redis session record expires (TTL 1h).
  final DateTime expiresAt;
}

class SessionClientError implements Exception {
  SessionClientError(this.code, this.message, {this.retryable = false});

  final String code;
  final String message;
  final bool retryable;

  @override
  String toString() => 'SessionClientError($code): $message';
}

class SessionClient {
  SessionClient({Uri? apiBase, http.Client? httpClient})
      : _apiBase = apiBase ?? Uri.parse('https://api.lingoglass.online'),
        _http = httpClient ?? http.Client();

  final Uri _apiBase;
  final http.Client _http;

  /// POST /v1/sessions with the deviceId. Returns the parsed SessionInfo on
  /// 201; throws SessionClientError on 429 (cap exceeded) or any other
  /// non-success status.
  Future<SessionInfo> createSession(String deviceId) async {
    final url = _apiBase.resolve('/v1/sessions');
    final response = await _http.post(
      url,
      headers: const {'content-type': 'application/json'},
      body: jsonEncode({'deviceId': deviceId}),
    );

    if (response.statusCode == 429) {
      throw SessionClientError(
        'daily_cap_exceeded',
        'Daily spend cap exceeded',
      );
    }
    if (response.statusCode != 201) {
      throw SessionClientError(
        'upstream_unavailable',
        'createSession HTTP ${response.statusCode}: ${response.body}',
        retryable: true,
      );
    }

    final body = jsonDecode(response.body) as Map<String, Object?>;
    if (body['success'] != true) {
      throw SessionClientError(
        'internal_error',
        'createSession not successful: ${response.body}',
      );
    }
    final data = body['data'] as Map<String, Object?>;
    return SessionInfo(
      sessionId: data['sessionId'] as String,
      wsUrl: Uri.parse(data['wsUrl'] as String),
      expiresAt: DateTime.parse(data['expiresAt'] as String),
    );
  }

  /// Close the underlying HTTP client. After this the SessionClient is
  /// unusable. Safe to call multiple times.
  void close() => _http.close();
}
