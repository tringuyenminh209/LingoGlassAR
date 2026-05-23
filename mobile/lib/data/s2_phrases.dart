// S2 Day 5 translation-accuracy bench catalog.
//
// 60 short travel-domain utterances: 30 Japanese (sourceLang 'ja',
// translated to Vietnamese) + 30 Vietnamese (sourceLang 'vi', translated
// to Japanese). Six domains x 5 phrases x 2 directions. The operator
// reads each displayed phrase into the phone mic during S2-Run-30; the
// pipeline transcribes + translates and the operator scores the result
// 1-5 by eye (see docs/codex/S2_TASKS.md Day 6).
//
// Kept short (one clause each) to match the S1 catalog so STT latency
// and the accuracy axis are measured on comparable inputs. No profanity.
//
// `targetLang` is derived, never stored: every JP phrase targets VN and
// vice versa, so the run covers both directions from one flat list.

/// One bench phrase. `sourceLang` is 'ja' or 'vi'; `domain` is one of the
/// six travel domains below (string, not enum, so it lands verbatim in a
/// future CSV grouping without a lookup table).
class S2Phrase {
  const S2Phrase({
    required this.id,
    required this.text,
    required this.sourceLang,
    required this.domain,
  });

  final String id;
  final String text;
  final String sourceLang;
  final String domain;

  /// Opposite of [sourceLang] — the only two languages in the MVP.
  String get targetLang => sourceLang == 'ja' ? 'vi' : 'ja';
}

const List<S2Phrase> s2Phrases = <S2Phrase>[
  // --- Japanese -> Vietnamese (30) ---
  // greetings
  S2Phrase(
      id: 'ja-greet-01',
      text: 'おはようございます',
      sourceLang: 'ja',
      domain: 'greetings'),
  S2Phrase(
      id: 'ja-greet-02',
      text: 'ありがとうございます',
      sourceLang: 'ja',
      domain: 'greetings'),
  S2Phrase(
      id: 'ja-greet-03', text: 'はじめまして', sourceLang: 'ja', domain: 'greetings'),
  S2Phrase(
      id: 'ja-greet-04', text: 'すみません', sourceLang: 'ja', domain: 'greetings'),
  S2Phrase(
      id: 'ja-greet-05', text: 'お元気ですか', sourceLang: 'ja', domain: 'greetings'),
  // directions
  S2Phrase(
      id: 'ja-dir-01', text: '駅はどこですか', sourceLang: 'ja', domain: 'directions'),
  S2Phrase(
      id: 'ja-dir-02',
      text: 'まっすぐ行ってください',
      sourceLang: 'ja',
      domain: 'directions'),
  S2Phrase(
      id: 'ja-dir-03',
      text: '右に曲がってください',
      sourceLang: 'ja',
      domain: 'directions'),
  S2Phrase(
      id: 'ja-dir-04',
      text: 'ここはどこですか',
      sourceLang: 'ja',
      domain: 'directions'),
  S2Phrase(
      id: 'ja-dir-05', text: '近いですか', sourceLang: 'ja', domain: 'directions'),
  // food
  S2Phrase(id: 'ja-food-01', text: '水をください', sourceLang: 'ja', domain: 'food'),
  S2Phrase(
      id: 'ja-food-02', text: 'おすすめは何ですか', sourceLang: 'ja', domain: 'food'),
  S2Phrase(
      id: 'ja-food-03', text: 'メニューをください', sourceLang: 'ja', domain: 'food'),
  S2Phrase(id: 'ja-food-04', text: '辛いですか', sourceLang: 'ja', domain: 'food'),
  S2Phrase(id: 'ja-food-05', text: '美味しいです', sourceLang: 'ja', domain: 'food'),
  // transit
  S2Phrase(
      id: 'ja-transit-01',
      text: '切符はどこで買えますか',
      sourceLang: 'ja',
      domain: 'transit'),
  S2Phrase(
      id: 'ja-transit-02',
      text: '次の電車は何時ですか',
      sourceLang: 'ja',
      domain: 'transit'),
  S2Phrase(
      id: 'ja-transit-03',
      text: 'このバスは空港に行きますか',
      sourceLang: 'ja',
      domain: 'transit'),
  S2Phrase(
      id: 'ja-transit-04',
      text: 'タクシーを呼んでください',
      sourceLang: 'ja',
      domain: 'transit'),
  S2Phrase(
      id: 'ja-transit-05', text: '何番線ですか', sourceLang: 'ja', domain: 'transit'),
  // payment
  S2Phrase(
      id: 'ja-pay-01', text: 'いくらですか', sourceLang: 'ja', domain: 'payment'),
  S2Phrase(
      id: 'ja-pay-02', text: 'カードで払えますか', sourceLang: 'ja', domain: 'payment'),
  S2Phrase(
      id: 'ja-pay-03', text: '現金で払います', sourceLang: 'ja', domain: 'payment'),
  S2Phrase(
      id: 'ja-pay-04', text: '領収書をください', sourceLang: 'ja', domain: 'payment'),
  S2Phrase(id: 'ja-pay-05', text: '高すぎます', sourceLang: 'ja', domain: 'payment'),
  // emergencies
  S2Phrase(
      id: 'ja-emerg-01',
      text: '助けてください',
      sourceLang: 'ja',
      domain: 'emergencies'),
  S2Phrase(
      id: 'ja-emerg-02',
      text: '病院はどこですか',
      sourceLang: 'ja',
      domain: 'emergencies'),
  S2Phrase(
      id: 'ja-emerg-03',
      text: '警察を呼んでください',
      sourceLang: 'ja',
      domain: 'emergencies'),
  S2Phrase(
      id: 'ja-emerg-04',
      text: '道に迷いました',
      sourceLang: 'ja',
      domain: 'emergencies'),
  S2Phrase(
      id: 'ja-emerg-05',
      text: '気分が悪いです',
      sourceLang: 'ja',
      domain: 'emergencies'),

  // --- Vietnamese -> Japanese (30) ---
  // greetings
  S2Phrase(
      id: 'vi-greet-01',
      text: 'Xin chào',
      sourceLang: 'vi',
      domain: 'greetings'),
  S2Phrase(
      id: 'vi-greet-02',
      text: 'Cảm ơn rất nhiều',
      sourceLang: 'vi',
      domain: 'greetings'),
  S2Phrase(
      id: 'vi-greet-03',
      text: 'Rất vui được gặp bạn',
      sourceLang: 'vi',
      domain: 'greetings'),
  S2Phrase(
      id: 'vi-greet-04',
      text: 'Xin lỗi',
      sourceLang: 'vi',
      domain: 'greetings'),
  S2Phrase(
      id: 'vi-greet-05',
      text: 'Bạn khỏe không',
      sourceLang: 'vi',
      domain: 'greetings'),
  // directions
  S2Phrase(
      id: 'vi-dir-01',
      text: 'Nhà ga ở đâu',
      sourceLang: 'vi',
      domain: 'directions'),
  S2Phrase(
      id: 'vi-dir-02',
      text: 'Đi thẳng giúp tôi',
      sourceLang: 'vi',
      domain: 'directions'),
  S2Phrase(
      id: 'vi-dir-03',
      text: 'Rẽ phải giúp tôi',
      sourceLang: 'vi',
      domain: 'directions'),
  S2Phrase(
      id: 'vi-dir-04',
      text: 'Tôi đang ở đâu',
      sourceLang: 'vi',
      domain: 'directions'),
  S2Phrase(
      id: 'vi-dir-05',
      text: 'Có gần không',
      sourceLang: 'vi',
      domain: 'directions'),
  // food
  S2Phrase(
      id: 'vi-food-01', text: 'Cho tôi nước', sourceLang: 'vi', domain: 'food'),
  S2Phrase(
      id: 'vi-food-02',
      text: 'Bạn gợi ý món gì',
      sourceLang: 'vi',
      domain: 'food'),
  S2Phrase(
      id: 'vi-food-03',
      text: 'Cho tôi xem thực đơn',
      sourceLang: 'vi',
      domain: 'food'),
  S2Phrase(
      id: 'vi-food-04',
      text: 'Món này có cay không',
      sourceLang: 'vi',
      domain: 'food'),
  S2Phrase(
      id: 'vi-food-05', text: 'Rất ngon', sourceLang: 'vi', domain: 'food'),
  // transit
  S2Phrase(
      id: 'vi-transit-01',
      text: 'Mua vé ở đâu',
      sourceLang: 'vi',
      domain: 'transit'),
  S2Phrase(
      id: 'vi-transit-02',
      text: 'Mấy giờ có chuyến tàu tiếp theo',
      sourceLang: 'vi',
      domain: 'transit'),
  S2Phrase(
      id: 'vi-transit-03',
      text: 'Xe buýt này có đến sân bay không',
      sourceLang: 'vi',
      domain: 'transit'),
  S2Phrase(
      id: 'vi-transit-04',
      text: 'Gọi taxi giúp tôi',
      sourceLang: 'vi',
      domain: 'transit'),
  S2Phrase(
      id: 'vi-transit-05',
      text: 'Sân ga số mấy',
      sourceLang: 'vi',
      domain: 'transit'),
  // payment
  S2Phrase(
      id: 'vi-pay-01',
      text: 'Bao nhiêu tiền',
      sourceLang: 'vi',
      domain: 'payment'),
  S2Phrase(
      id: 'vi-pay-02',
      text: 'Tôi trả bằng thẻ được không',
      sourceLang: 'vi',
      domain: 'payment'),
  S2Phrase(
      id: 'vi-pay-03',
      text: 'Tôi trả tiền mặt',
      sourceLang: 'vi',
      domain: 'payment'),
  S2Phrase(
      id: 'vi-pay-04',
      text: 'Cho tôi hóa đơn',
      sourceLang: 'vi',
      domain: 'payment'),
  S2Phrase(
      id: 'vi-pay-05', text: 'Đắt quá', sourceLang: 'vi', domain: 'payment'),
  // emergencies
  S2Phrase(
      id: 'vi-emerg-01',
      text: 'Làm ơn giúp tôi',
      sourceLang: 'vi',
      domain: 'emergencies'),
  S2Phrase(
      id: 'vi-emerg-02',
      text: 'Bệnh viện ở đâu',
      sourceLang: 'vi',
      domain: 'emergencies'),
  S2Phrase(
      id: 'vi-emerg-03',
      text: 'Gọi cảnh sát giúp tôi',
      sourceLang: 'vi',
      domain: 'emergencies'),
  S2Phrase(
      id: 'vi-emerg-04',
      text: 'Tôi bị lạc đường',
      sourceLang: 'vi',
      domain: 'emergencies'),
  S2Phrase(
      id: 'vi-emerg-05',
      text: 'Tôi thấy không khỏe',
      sourceLang: 'vi',
      domain: 'emergencies'),
];
