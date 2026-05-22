import 'package:flutter_test/flutter_test.dart';
import 'package:lingoglass_mobile/data/s1_phrases.dart';

void main() {
  test('S1 phrase catalog has ten unique short prompts', () {
    expect(s1Phrases, hasLength(10));
    expect(s1Phrases.map((phrase) => phrase.id).toSet(), hasLength(10));
    for (final phrase in s1Phrases) {
      expect(phrase.id, matches(RegExp(r'^[a-z0-9]+(?:-[a-z0-9]+)+$')));
      expect(phrase.text.runes.length, lessThanOrEqualTo(10));
    }
  });
}
