class S1Phrase {
  const S1Phrase({required this.id, required this.text});

  final String id;
  final String text;
}

const List<S1Phrase> s1Phrases = <S1Phrase>[
  S1Phrase(id: 'greeting-01', text: 'おはようございます'),
  S1Phrase(id: 'greeting-02', text: 'こんばんは'),
  S1Phrase(id: 'weather-03', text: '晴れですか'),
  S1Phrase(id: 'weather-04', text: '雨が降る'),
  S1Phrase(id: 'direction-05', text: '駅はどこ'),
  S1Phrase(id: 'direction-06', text: '右へ行く'),
  S1Phrase(id: 'food-07', text: '水ください'),
  S1Phrase(id: 'food-08', text: 'ご飯です'),
  S1Phrase(id: 'time-09', text: '今何時'),
  S1Phrase(id: 'number-10', text: '二つください'),
];
