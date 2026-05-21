import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

const int _audioChunkBytes = 4800;
const int _sampleRateHz = 24000;
const int _maxConnectAttempts = 5;
const List<Duration> _connectBackoff = <Duration>[
  Duration(seconds: 1),
  Duration(seconds: 2),
  Duration(seconds: 4),
  Duration(seconds: 8),
  Duration(seconds: 30),
];

/// One incremental output decoded from the backend WS stream.
/// Mirrors backend `app/services/translator.py` TextDelta.
class TextDelta {
  const TextDelta({required this.text, this.isFinal = false, this.sourceText});

  final String text;
  final bool isFinal;
  final String? sourceText;
}

/// Thrown when the backend sends an `error` frame or the WS
/// transport fails non-recoverably mid-utterance.
class TranslatorWsError implements Exception {
  TranslatorWsError(this.code, this.message, {this.retryable = false});

  final String code;
  final String message;
  final bool retryable;

  @override
  String toString() => 'TranslatorWsError($code): $message';
}

/// One WS = one utterance. Caller creates the session via HTTP POST
/// elsewhere and passes the sessionId here. Each connect()/disconnect()
/// cycle covers a single push-to-talk gesture.
class TranslatorWs {
  TranslatorWs({Uri? wsBase})
      : this._(
          wsBase ?? Uri.parse('wss://api.lingoglass.online'),
          _WebSocketChannelConnector(),
          Future<void>.delayed,
        );

  @visibleForTesting
  TranslatorWs.withConnector({
    Uri? wsBase,
    required TranslatorWsConnector connector,
    Future<void> Function(Duration duration)? delay,
  }) : this._(
          wsBase ?? Uri.parse('wss://api.lingoglass.online'),
          connector,
          delay ?? Future<void>.delayed,
        );

  TranslatorWs._(this._wsBase, this._connector, this._delay);

  final TranslatorWsConnector _connector;
  final Future<void> Function(Duration duration) _delay;
  StreamController<TextDelta> _textController =
      StreamController<TextDelta>.broadcast();
  TranslatorWsSocket? _socket;
  StreamSubscription<Object?>? _socketSubscription;
  Completer<void>? _openedCompleter;
  String? _sessionId;
  int _nextSeq = 0;
  bool _isConnected = false;
  bool _closingCleanly = false;

  /// Open a WS to /v1/sessions/{sessionId}/stream, send session.start,
  /// wait for session.opened, then ready to send audio chunks.
  Future<void> connect(
    String sessionId, {
    String deviceId = '',
    String sourceLang = 'ja',
    String targetLang = 'vi',
  }) async {
    if (_isConnected || _openedCompleter != null) {
      throw StateError('TranslatorWs is already connected or connecting.');
    }

    _resetTextControllerIfClosed();
    _sessionId = sessionId;
    _nextSeq = 0;

    Object? lastError;
    for (var attempt = 0; attempt < _maxConnectAttempts; attempt++) {
      try {
        await _openOnce(
          sessionId,
          deviceId: deviceId,
          sourceLang: sourceLang,
          targetLang: targetLang,
        );
        return;
      } on TranslatorWsError {
        await _resetSocketForRetry();
        rethrow;
      } on _InitialTransportError catch (error) {
        lastError = error.cause;
        await _resetSocketForRetry();
        if (attempt == _maxConnectAttempts - 1) {
          break;
        }
        await _delay(_connectBackoff[attempt]);
      } on Object catch (error) {
        lastError = error;
        await _resetSocketForRetry();
        if (attempt == _maxConnectAttempts - 1) {
          break;
        }
        await _delay(_connectBackoff[attempt]);
      }
    }

    throw TranslatorWsError(
      'upstream_unavailable',
      'Could not open translator WebSocket after $_maxConnectAttempts '
          'attempts: $lastError',
    );
  }

  /// Send one PCM16 24 kHz mono audio chunk.
  void send(Uint8List audioChunk) {
    if (audioChunk.length != _audioChunkBytes) {
      throw ArgumentError.value(
        audioChunk.length,
        'audioChunk.length',
        'must be $_audioChunkBytes bytes',
      );
    }

    final socket = _connectedSocket();
    socket.addJson(<String, Object?>{
      'type': 'audio.chunk',
      'sessionId': _sessionId,
      'seq': _nextSeq++,
      'codec': 'pcm16',
      'sampleRateHz': _sampleRateHz,
      'dataBase64': base64Encode(audioChunk),
      'clientTs': _clientTs(),
    });
  }

  /// Signal end-of-utterance.
  void endUtterance() {
    final socket = _connectedSocket();
    socket.addJson(<String, Object?>{
      'type': 'audio.end',
      'sessionId': _sessionId,
      'seq': _nextSeq++,
      'clientTs': _clientTs(),
    });
  }

  /// Stream of decoded TextDelta events.
  Stream<TextDelta> get textStream => _textController.stream;

  /// Close the WS cleanly. Idempotent.
  Future<void> disconnect() async {
    _closingCleanly = true;
    _isConnected = false;
    _openedCompleter = null;
    await _socketSubscription?.cancel();
    _socketSubscription = null;

    final socket = _socket;
    _socket = null;
    if (socket != null) {
      await socket.close();
    }

    await _closeTextController();
    _closingCleanly = false;
  }

  /// True between successful connect() and disconnect()/server-close.
  bool get isConnected => _isConnected;

  final Uri _wsBase;

  Future<void> _openOnce(
    String sessionId, {
    required String deviceId,
    required String sourceLang,
    required String targetLang,
  }) async {
    final socket = await _connector.connect(_streamUrl(sessionId));
    _socket = socket;
    _openedCompleter = Completer<void>();

    await socket.ready;
    _socketSubscription = socket.stream.listen(
      _handleMessage,
      onError: _handleSocketError,
      onDone: _handleSocketDone,
    );

    socket.addJson(<String, Object?>{
      'type': 'session.start',
      'deviceId': deviceId,
      'sourceLang': sourceLang,
      'targetLang': targetLang,
      'retainText': false,
      'clientTs': _clientTs(),
    });

    await _openedCompleter!.future;
    _openedCompleter = null;
  }

  void _handleMessage(Object? message) {
    late final Map<String, Object?> frame;
    try {
      frame = _decodeFrame(message);
    } on Object catch (error) {
      _failProtocol(
        TranslatorWsError(
          'internal_error',
          'Invalid translator WebSocket frame: $error',
        ),
      );
      return;
    }

    final type = frame['type'];
    switch (type) {
      case 'session.opened':
        _isConnected = true;
        _completeOpened();
      case 'translation.partial':
        _textController.add(TextDelta(text: frame['text'] as String));
      case 'translation.final':
        _textController.add(
          TextDelta(
            text: frame['translatedText'] as String,
            isFinal: true,
            sourceText: frame['sourceText'] as String?,
          ),
        );
        unawaited(_finishStreamCleanly());
      case 'error':
        final error = TranslatorWsError(
          frame['code'] as String,
          frame['message'] as String,
          retryable: frame['retryable'] as bool,
        );
        _failProtocol(error);
      default:
        _failProtocol(
          TranslatorWsError(
            'internal_error',
            'Unexpected translator WebSocket frame: $type',
          ),
        );
    }
  }

  Map<String, Object?> _decodeFrame(Object? message) {
    final decoded = jsonDecode(message as String);
    return Map<String, Object?>.from(decoded as Map);
  }

  void _handleSocketError(Object error) {
    if (_closingCleanly) {
      return;
    }
    if (!_isConnected) {
      _completeOpeningTransportError(error);
      return;
    }
    _failMidUtterance(error);
  }

  void _handleSocketDone() {
    if (_closingCleanly) {
      return;
    }
    if (!_isConnected) {
      _completeOpeningTransportError('socket closed before session.opened');
      return;
    }
    _failMidUtterance('socket closed mid-utterance');
  }

  void _failMidUtterance(Object error) {
    final wsError = TranslatorWsError(
      'upstream_unavailable',
      'Translator WebSocket disconnected: $error',
      retryable: true,
    );
    _isConnected = false;
    _addTextError(wsError);
    unawaited(_finishStreamCleanly());
  }

  void _failProtocol(TranslatorWsError error) {
    _isConnected = false;
    _addTextError(error);
    final completer = _openedCompleter;
    if (completer != null && !completer.isCompleted) {
      completer.completeError(error);
    }
    unawaited(_finishStreamCleanly());
  }

  void _completeOpened() {
    final completer = _openedCompleter;
    if (completer != null && !completer.isCompleted) {
      completer.complete();
    }
  }

  void _completeOpeningTransportError(Object error) {
    final completer = _openedCompleter;
    if (completer != null && !completer.isCompleted) {
      completer.completeError(_InitialTransportError(error));
    }
  }

  void _addTextError(TranslatorWsError error) {
    if (!_textController.isClosed) {
      _textController.addError(error);
    }
  }

  Future<void> _finishStreamCleanly() async {
    _closingCleanly = true;
    _isConnected = false;
    await _socketSubscription?.cancel();
    _socketSubscription = null;

    final socket = _socket;
    _socket = null;
    if (socket != null) {
      await socket.close();
    }

    await _closeTextController();
    _openedCompleter = null;
    _closingCleanly = false;
  }

  Future<void> _resetSocketForRetry() async {
    _isConnected = false;
    _openedCompleter = null;
    await _socketSubscription?.cancel();
    _socketSubscription = null;

    final socket = _socket;
    _socket = null;
    if (socket != null) {
      await socket.close();
    }
  }

  void _resetTextControllerIfClosed() {
    if (_textController.isClosed) {
      _textController = StreamController<TextDelta>.broadcast();
    }
  }

  Future<void> _closeTextController() async {
    if (!_textController.isClosed) {
      await _textController.close();
    }
  }

  TranslatorWsSocket _connectedSocket() {
    final socket = _socket;
    if (!_isConnected || socket == null) {
      throw StateError('TranslatorWs is not connected.');
    }
    return socket;
  }

  Uri _streamUrl(String sessionId) {
    final base = _wsBase.toString().replaceFirst(RegExp(r'/$'), '');
    return Uri.parse(
      '$base/v1/sessions/${Uri.encodeComponent(sessionId)}/stream',
    );
  }

  String _clientTs() => DateTime.now().toUtc().toIso8601String();
}

@visibleForTesting
abstract interface class TranslatorWsConnector {
  Future<TranslatorWsSocket> connect(Uri url);
}

@visibleForTesting
abstract interface class TranslatorWsSocket {
  Future<void> get ready;

  Stream<Object?> get stream;

  void addJson(Map<String, Object?> frame);

  Future<void> close();
}

class _WebSocketChannelConnector implements TranslatorWsConnector {
  @override
  Future<TranslatorWsSocket> connect(Uri url) async {
    return _WebSocketChannelSocket(WebSocketChannel.connect(url));
  }
}

class _WebSocketChannelSocket implements TranslatorWsSocket {
  _WebSocketChannelSocket(this._channel);

  final WebSocketChannel _channel;

  @override
  Future<void> get ready => _channel.ready;

  @override
  Stream<Object?> get stream => _channel.stream;

  @override
  void addJson(Map<String, Object?> frame) {
    _channel.sink.add(jsonEncode(frame));
  }

  @override
  Future<void> close() async {
    await _channel.sink.close();
  }
}

class _InitialTransportError {
  _InitialTransportError(this.cause);

  final Object cause;
}
