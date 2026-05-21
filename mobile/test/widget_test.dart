// Smoke test: the app pumps without throwing and shows the translate UI.
// SpikeScreen now lives behind the debug drawer (route '/spike').

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:lingoglass_mobile/main.dart';

void main() {
  testWidgets('LingoGlassApp renders TranslateScreen scaffold', (tester) async {
    await tester.pumpWidget(const LingoGlassApp());
    expect(find.text('LingoGlass Translate'), findsOneWidget);
    expect(find.text('HOLD TO TALK'), findsOneWidget);
    expect(find.text('BACKEND'), findsOneWidget);
    expect(find.text('BLE'), findsOneWidget);
  });
}
