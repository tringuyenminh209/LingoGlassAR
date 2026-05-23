import 'package:flutter_test/flutter_test.dart';
import 'package:lingoglass_mobile/data/s2_phrases.dart';

void main() {
  const expectedDomains = <String>{
    'greetings',
    'directions',
    'food',
    'transit',
    'payment',
    'emergencies',
  };

  group('s2Phrases', () {
    test('contains exactly 60 phrases split evenly by source language', () {
      expect(s2Phrases, hasLength(60));
      expect(_countWhere((phrase) => phrase.sourceLang == 'ja'), 30);
      expect(_countWhere((phrase) => phrase.sourceLang == 'vi'), 30);
    });

    test('contains exactly five phrases per domain and language', () {
      expect(s2Phrases.map((phrase) => phrase.domain).toSet(), expectedDomains);

      for (final domain in expectedDomains) {
        expect(
          _countWhere(
            (phrase) => phrase.domain == domain && phrase.sourceLang == 'ja',
          ),
          5,
          reason: '$domain should have five Japanese prompts',
        );
        expect(
          _countWhere(
            (phrase) => phrase.domain == domain && phrase.sourceLang == 'vi',
          ),
          5,
          reason: '$domain should have five Vietnamese prompts',
        );
      }
    });

    test('derives target language from source language', () {
      for (final phrase in s2Phrases) {
        expect(phrase.sourceLang, isIn(<String>['ja', 'vi']));
        expect(phrase.targetLang, phrase.sourceLang == 'ja' ? 'vi' : 'ja');
      }
    });

    test('uses unique ids', () {
      final ids = s2Phrases.map((phrase) => phrase.id).toList();
      expect(ids.toSet(), hasLength(ids.length));
    });

    test('has no blank text', () {
      for (final phrase in s2Phrases) {
        expect(phrase.text.trim(), isNotEmpty, reason: phrase.id);
      }
    });
  });
}

int _countWhere(bool Function(S2Phrase phrase) predicate) =>
    s2Phrases.where(predicate).length;
