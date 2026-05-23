import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lingoglass_mobile/screens/translate_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  late String? clipboardText;
  const permissionChannel =
      MethodChannel('flutter.baseflow.com/permissions/methods');

  setUp(() {
    clipboardText = null;
    SharedPreferences.setMockInitialValues(
      <String, Object>{
        'lingoglass.device_id': '00000000-0000-4000-8000-000000000001',
      },
    );
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, (call) async {
      if (call.method == 'Clipboard.setData') {
        final data = call.arguments as Map<Object?, Object?>;
        clipboardText = data['text'] as String?;
      }
      return null;
    });
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(permissionChannel, (call) async {
      if (call.method == 'requestPermissions') {
        final permissions = call.arguments as List<Object?>;
        return <int, int>{for (final value in permissions) value! as int: 1};
      }
      if (call.method == 'checkPermissionStatus') {
        return 1;
      }
      return null;
    });
  });

  tearDown(() {
    HttpOverrides.global = null;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, null);
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(permissionChannel, null);
  });

  group('cooldown blocks fast re-press', () {
    testWidgets('logs cooldown and ignores the second press', (tester) async {
      HttpOverrides.global = _SessionHttpOverrides();
      await _pumpTranslateScreen(tester);
      await tester.tap(find.text('S1 Run 10'));
      await tester.pump();

      await _pressFor(tester, const Duration(milliseconds: 120));
      await tester.pump(const Duration(milliseconds: 10));
      await tester.pump();
      await _pressFor(tester, const Duration(milliseconds: 10));

      expect(find.textContaining('PTT cooldown'), findsOneWidget);
    });
  });

  group('short press is rejected', () {
    testWidgets('shows warning and records short_press without audioMs',
        (tester) async {
      HttpOverrides.global = _SessionHttpOverrides();
      await _pumpTranslateScreen(tester);
      await tester.tap(find.text('S1 Run 10'));
      await tester.pump();

      await tester.tap(find.text('HOLD TO TALK'));
      await tester.pump();

      expect(find.text('Hold longer to record'), findsOneWidget);
      await tester.pump(const Duration(milliseconds: 10));

      await tester.pump();
      await tester.tap(find.text('Copy E2E CSV'));
      await tester.pump();

      final lines = clipboardText!.trim().split('\n');
      final header = lines[0].split(',');
      final row = lines[1].split(',');
      int col(String name) => header.indexOf(name);
      expect(row[col('audio_ms')], '0');
      expect(row[col('error')], 'short_press');
      // S2 Day 5 added the manual-scoring column; it is always empty on
      // device export (operator fills it in a spreadsheet afterwards).
      expect(row[col('accuracy_score')], '');
    });
  });

  group('back-to-back discard shows banner', () {
    testWidgets('names the discarded phrase id', (tester) async {
      HttpOverrides.global = _SessionHttpOverrides();
      await _pumpTranslateScreen(tester);
      await tester.tap(find.text('S1 Run 10'));
      await tester.pump();

      await _pressFor(tester, const Duration(milliseconds: 120));
      await tester.pump(const Duration(milliseconds: 10));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 700));

      await _pressFor(tester, const Duration(milliseconds: 120));

      expect(
        find.text('Previous attempt (greeting-01) discarded'),
        findsOneWidget,
      );
    });
  });
}

Future<void> _pumpTranslateScreen(WidgetTester tester) async {
  await tester.pumpWidget(
    MaterialApp(
      theme: ThemeData(useMaterial3: true),
      home: const TranslateScreen(),
    ),
  );
  for (var i = 0; i < 5; i++) {
    await tester.pump(const Duration(milliseconds: 20));
  }
  expect(find.textContaining('Device ID'), findsOneWidget);
}

Future<void> _pressFor(WidgetTester tester, Duration duration) async {
  final target = find.text('HOLD TO TALK');
  final gesture = await tester.startGesture(tester.getCenter(target));
  await tester.pump();
  await tester.runAsync(() => Future<void>.delayed(duration));
  await gesture.up();
  await tester.pump();
}

class _SessionHttpOverrides extends HttpOverrides {
  final List<Completer<HttpClientResponse>> _pending =
      <Completer<HttpClientResponse>>[];

  @override
  HttpClient createHttpClient(SecurityContext? context) =>
      _FakeSessionHttpClient(pending: _pending);
}

class _FakeSessionHttpClient implements HttpClient {
  _FakeSessionHttpClient({required this.pending});

  final List<Completer<HttpClientResponse>> pending;

  @override
  Future<HttpClientRequest> openUrl(String method, Uri url) async =>
      _FakeSessionRequest(pending: pending);

  @override
  void close({bool force = false}) {}

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _FakeSessionRequest implements HttpClientRequest {
  _FakeSessionRequest({required this.pending});

  final List<Completer<HttpClientResponse>> pending;
  final BytesBuilder _body = BytesBuilder();
  final HttpHeaders _headers = _FakeHttpHeaders();

  @override
  bool bufferOutput = true;

  @override
  int contentLength = -1;

  @override
  Encoding encoding = utf8;

  @override
  bool followRedirects = true;

  @override
  int maxRedirects = 5;

  @override
  bool persistentConnection = true;

  @override
  HttpHeaders get headers => _headers;

  @override
  void add(List<int> data) => _body.add(data);

  @override
  Future<void> addStream(Stream<List<int>> stream) async {
    await for (final chunk in stream) {
      add(chunk);
    }
  }

  @override
  void write(Object? object) => add(encoding.encode('$object'));

  @override
  void writeAll(Iterable<Object?> objects, [String separator = '']) {
    write(objects.join(separator));
  }

  @override
  void writeCharCode(int charCode) => write(String.fromCharCode(charCode));

  @override
  void writeln([Object? object = '']) => write('$object\r\n');

  @override
  Future<HttpClientResponse> close() async {
    final completer = Completer<HttpClientResponse>();
    pending.add(completer);
    return completer.future;
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _FakeHttpHeaders implements HttpHeaders {
  @override
  List<String>? operator [](String name) => null;

  @override
  void add(String name, Object value, {bool preserveHeaderCase = false}) {}

  @override
  void set(String name, Object value, {bool preserveHeaderCase = false}) {}

  @override
  void remove(String name, Object value) {}

  @override
  void removeAll(String name) {}

  @override
  String? value(String name) => null;

  @override
  void forEach(void Function(String name, List<String> values) action) {}

  @override
  void noFolding(String name) {}

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}
