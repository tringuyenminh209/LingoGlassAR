// Smoke test: the spike app pumps without throwing and shows the app bar.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:lingoglass_mobile/main.dart';

void main() {
  testWidgets('LingoGlassApp renders SpikeScreen scaffold', (tester) async {
    await tester.pumpWidget(const LingoGlassApp());
    expect(find.text('LingoGlass S0 spike'), findsOneWidget);
    expect(find.text('Scan'), findsOneWidget);
    expect(find.text('Send Hello'), findsOneWidget);
    expect(find.text('Send JA (auto MTU)'), findsOneWidget);
  });
}
