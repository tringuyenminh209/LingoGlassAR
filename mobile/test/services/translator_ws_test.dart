import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:lingoglass_mobile/services/translator_ws.dart';

const String _sessionId = 'a88aac9d-d5f6-45c5-bf91-44b7e29b56db';

void main() {
  group('TranslatorWs', () {
    test('connect sends session.start and waits for session.opened', () async {
      final socket = _FakeTranslatorWsSocket();
      final ws = _translatorWs(socket);

      final connect = ws.connect(
        _sessionId,
        deviceId: '49b2e46b-2848-473d-a804-2f0b7a7c2fb4',
      );
      await pumpEventQueue();

      expect(ws.isConnected, isFalse);
      expect(
        socket.connectedUrl.toString(),
        'ws://fake.test/v1/sessions/$_sessionId/stream',
      );
      expect(socket.sentFrames, hasLength(1));
      expect(socket.sentFrames.single, containsPair('type', 'session.start'));
      expect(socket.sentFrames.single, containsPair('sourceLang', 'ja'));
      expect(socket.sentFrames.single, containsPair('targetLang', 'vi'));
      expect(socket.sentFrames.single, containsPair('retainText', false));

      socket.serverFrame(<String, Object?>{
        'type': 'session.opened',
        'sessionId': _sessionId,
        'serverTs': '2026-05-22T01:23:45Z',
      });
      await connect;

      expect(ws.isConnected, isTrue);
      await ws.disconnect();
    });

    test('send and endUtterance encode the audio wire frames', () async {
      final socket = _FakeTranslatorWsSocket();
      final ws = await _connectedTranslatorWs(socket);
      final audio = Uint8List.fromList(List<int>.filled(4800, 7));

      ws.send(audio);
      ws.endUtterance();

      final chunk = socket.sentFrames[1];
      expect(chunk, containsPair('type', 'audio.chunk'));
      expect(chunk, containsPair('sessionId', _sessionId));
      expect(chunk, containsPair('seq', 0));
      expect(chunk, containsPair('codec', 'pcm16'));
      expect(chunk, containsPair('sampleRateHz', 24000));
      expect(base64Decode(chunk['dataBase64'] as String), audio);
      expect((chunk['dataBase64'] as String).length, 6400);

      final end = socket.sentFrames[2];
      expect(end, containsPair('type', 'audio.end'));
      expect(end, containsPair('sessionId', _sessionId));
      expect(end, containsPair('seq', 1));

      await ws.disconnect();
    });

    test('partial then final yields TextDelta events and closes stream',
        () async {
      final socket = _FakeTranslatorWsSocket();
      final ws = await _connectedTranslatorWs(socket);
      final deltas = <TextDelta>[];
      final done = Completer<void>();
      ws.textStream.listen(deltas.add, onDone: done.complete);

      socket.serverFrame(<String, Object?>{
        'type': 'translation.partial',
        'sessionId': _sessionId,
        'text': 'Xin ',
        'serverTs': '2026-05-22T01:23:46Z',
      });
      socket.serverFrame(<String, Object?>{
        'type': 'translation.final',
        'sessionId': _sessionId,
        'translatedText': 'Xin chao',
        'sourceText': 'source phrase',
        'durationMs': 420,
        'serverTs': '2026-05-22T01:23:47Z',
      });
      await done.future;

      expect(deltas, hasLength(2));
      expect(deltas.first.text, 'Xin ');
      expect(deltas.first.isFinal, isFalse);
      expect(deltas.last.text, 'Xin chao');
      expect(deltas.last.isFinal, isTrue);
      expect(deltas.last.sourceText, 'source phrase');
      expect(ws.isConnected, isFalse);
    });

    test('wire error becomes TranslatorWsError on textStream', () async {
      final socket = _FakeTranslatorWsSocket();
      final ws = await _connectedTranslatorWs(socket);
      final error = Completer<Object>();
      final done = Completer<void>();
      ws.textStream.listen(
        (_) {},
        onError: error.complete,
        onDone: done.complete,
      );

      socket.serverFrame(<String, Object?>{
        'type': 'error',
        'sessionId': _sessionId,
        'code': 'translator_error',
        'message': 'OpenAI failed',
        'retryable': true,
        'serverTs': '2026-05-22T01:23:46Z',
      });

      final received = await error.future;
      await done.future;
      expect(received, isA<TranslatorWsError>());
      expect((received as TranslatorWsError).code, 'translator_error');
      expect(received.retryable, isTrue);
    });

    test('send rejects audio chunks that are not 4800 bytes', () async {
      final socket = _FakeTranslatorWsSocket();
      final ws = await _connectedTranslatorWs(socket);

      expect(() => ws.send(Uint8List(4799)), throwsArgumentError);

      await ws.disconnect();
    });
  });
}

TranslatorWs _translatorWs(_FakeTranslatorWsSocket socket) {
  return TranslatorWs.withConnector(
    wsBase: Uri.parse('ws://fake.test'),
    connector: _FakeTranslatorWsConnector(socket),
    delay: (_) async {},
  );
}

Future<TranslatorWs> _connectedTranslatorWs(
  _FakeTranslatorWsSocket socket,
) async {
  final ws = _translatorWs(socket);
  final connect = ws.connect(_sessionId);
  await pumpEventQueue();
  socket.serverFrame(<String, Object?>{
    'type': 'session.opened',
    'sessionId': _sessionId,
    'serverTs': '2026-05-22T01:23:45Z',
  });
  await connect;
  return ws;
}

class _FakeTranslatorWsConnector implements TranslatorWsConnector {
  _FakeTranslatorWsConnector(this.socket);

  final _FakeTranslatorWsSocket socket;

  @override
  Future<TranslatorWsSocket> connect(Uri url) async {
    socket.connectedUrl = url;
    return socket;
  }
}

class _FakeTranslatorWsSocket implements TranslatorWsSocket {
  final StreamController<Object?> _server = StreamController<Object?>();
  final List<Map<String, Object?>> sentFrames = <Map<String, Object?>>[];
  Uri? connectedUrl;

  @override
  Future<void> get ready async {}

  @override
  Stream<Object?> get stream => _server.stream;

  @override
  void addJson(Map<String, Object?> frame) {
    sentFrames.add(Map<String, Object?>.from(frame));
  }

  @override
  Future<void> close() async {
    if (!_server.isClosed) {
      await _server.close();
    }
  }

  void serverFrame(Map<String, Object?> frame) {
    _server.add(jsonEncode(frame));
  }
}
