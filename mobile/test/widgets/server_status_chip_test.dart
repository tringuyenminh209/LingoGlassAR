import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:lingoglass_mobile/widgets/server_status_chip.dart';

void main() {
  testWidgets('polls healthz and displays API status transitions',
      (tester) async {
    final firstResponse = Completer<http.Response>();
    final timeoutResponse = Completer<http.Response>();
    final requestedUris = <Uri>[];
    var callCount = 0;
    final client = MockClient((request) {
      requestedUris.add(request.url);
      return switch (callCount++) {
        0 => firstResponse.future,
        1 => Future.value(http.Response('{"redis":"down"}', 200)),
        2 => Future.value(http.Response('', 500)),
        _ => timeoutResponse.future,
      };
    });

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          appBar: AppBar(
            actions: [
              ServerStatusChip(
                apiBase: Uri.parse('https://test.lingoglass.invalid'),
                client: client,
              ),
            ],
          ),
        ),
      ),
    );

    expect(find.text('API'), findsOneWidget);
    expect(_chip(tester).backgroundColor, Colors.grey.shade300);

    firstResponse.complete(http.Response('{"redis":"up"}', 200));
    await tester.pump();
    expect(_chip(tester).backgroundColor, Colors.green.shade100);

    await tester.pump(const Duration(seconds: 10));
    await tester.pump();
    expect(_chip(tester).backgroundColor, Colors.yellow.shade100);

    await tester.pump(const Duration(seconds: 10));
    await tester.pump();
    expect(_chip(tester).backgroundColor, Colors.red.shade100);

    await tester.pump(const Duration(seconds: 10));
    expect(callCount, 4);
    await tester.pump(const Duration(seconds: 5));
    await tester.pump();
    expect(_chip(tester).backgroundColor, Colors.red.shade100);
    expect(
      requestedUris,
      everyElement(Uri.parse('https://test.lingoglass.invalid/healthz')),
    );

    await tester.pumpWidget(const SizedBox.shrink());
  });
}

Chip _chip(WidgetTester tester) =>
    tester.widget<Chip>(find.widgetWithText(Chip, 'API'));
