import 'package:flutter/material.dart';

import 'screens/spike_screen.dart';
import 'screens/translate_screen.dart';

void main() {
  runApp(const LingoGlassApp());
}

class LingoGlassApp extends StatelessWidget {
  const LingoGlassApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'LingoGlass AR',
      theme: ThemeData(colorSchemeSeed: Colors.indigo, useMaterial3: true),
      home: const TranslateScreen(),
      routes: {
        '/spike': (_) => const SpikeScreen(),
      },
    );
  }
}
