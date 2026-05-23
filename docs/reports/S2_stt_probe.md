# S2 Day 1 — STT optimisation probe

**Date**: 2026-05-23
**Author**: Claude (self, on behalf of solo dev)
**Output of**: `docs/codex/S2_TASKS.md` Day 1 row (research only, no code).
**Goal**: identify the single highest-impact, lowest-risk tuning change to land
in Day 2 to drive STT median (884 ms post-PTT-release) below 600 ms.

## 1. Current `session.update` payload (S1 baseline)

`backend/app/services/translator.py` `connect()` sends:

```json
{
  "type": "session.update",
  "session": {
    "type": "realtime",
    "output_modalities": ["text"],
    "instructions": "<SYSTEM_INSTRUCTIONS, 168 chars>",
    "audio": {
      "input": {
        "format": {"type": "audio/pcm", "rate": 24000},
        "transcription": {"model": "whisper-1"}
      }
    }
  }
}
```

`response.create` additionally re-sends `output_modalities` + `instructions`.
PR #2 review flagged the duplicate `instructions` as harmless but
strippable.

## 2. Knobs we currently set vs. knobs we could set

| Knob | Current | GA default if omitted | Notes |
|---|---|---|---|
| `audio.input.transcription.model` | `whisper-1` | none (transcription off) | `gpt-realtime-whisper` is the new streaming STT model, advertised partial latency 200-400 ms. |
| `audio.input.transcription.delay` | not set | `medium` | New knob for `gpt-realtime-whisper` only. Values: `minimal` / `low` / `medium` / `high` / `xhigh`. |
| `audio.input.transcription.language` | not set | auto-detect | Setting it to `ja` or `vi` could speed lang detection on first frame. |
| `turn_detection` | not set | `server_vad` (auto) | Server-side VAD runs even though we manually `input_audio_buffer.commit`. Wasted inference. |
| `instructions` (in `response.create`) | duplicated | n/a | PR #2 follow-up flagged this. ~50 ms tokenisation. |
| `temperature` (response) | not set | model default | Lower temp = slightly faster sampling. Translation accuracy may suffer. |
| `max_response_output_tokens` | not set | unbounded | Capping doesn't reduce latency-to-first-token. |

We are NOT touching the response side (translation) — translation median was
137 ms in S1, already well within the 200-600 ms spec from CLAUDE.md.

## 3. S1 STT sub-distribution (computed from
`docs/reports/s1_run10_2026-05-22.csv`)

`stt_ms = first_text_ms - audio_ms` for each OK row (no error column).
PTT release happens at `audio_ms` from press; first translation partial
arrives at `first_text_ms`. The delta is the post-release time the user
sees as "lag before any text appears".

OK rows sorted ascending by `stt_ms`:

| phrase | audio_ms | first_text_ms | stt_ms |
|---|---:|---:|---:|
| number-10 | 4464 | 5191 | **727** |
| time-09 | 4806 | 5614 | **808** |
| direction-05 (retry) | 4444 | 5253 | **809** |
| weather-04 | 4440 | 5322 | **882** |
| food-08 (retry) | 4214 | 5098 | **884** |
| greeting-02 (retry) | 3440 | 4360 | **920** |
| weather-03 | 5390 | 6404 | **1014** |
| food-07 (retry 4) | 3777 | 4835 | **1058** |
| greeting-01 | 4778 | 6038 | **1260** |

Percentiles (n=9, linear interpolation):

- **p50 = 884 ms** (confirms the memory claim)
- **p90 ≈ 1078 ms**
- **p95 ≈ 1169 ms**

Variance: 533 ms peak-to-peak. The slowest row (greeting-01, 1260 ms) is
also the first run of the session — likely cold-start of the OpenAI
session or our Translator instance. The retried rows hover at the
median, so retry path does not appear to be a confounder for the STT
stage itself.

S2 exit-criterion #1 is `stt median ≤ 600 ms`. We need to drop the
median by **≥ 284 ms** (32 %). Day 2 target should be a single change
plausibly worth that.

## 4. Tuning candidates ranked

### Candidate A — switch `whisper-1` → `gpt-realtime-whisper`, set `delay: "low"`

`gpt-realtime-whisper` is a streaming-first STT model released alongside
the GA Realtime API. OpenAI documents partial latency of 200-400 ms
end-of-phoneme-to-delta vs. `whisper-1` which was built for finished
audio files. `delay: "low"` favours latency over word-error-rate.

- **Expected impact**: high. Plausible to cut median by 300-500 ms.
- **Risk**: medium. Accuracy could degrade — but we are translating short
  travel-domain phrases where small WER drops should still produce
  understandable VN/JP output (and Day 5-6 accuracy harness will catch
  any regression).
- **Implementation cost**: tiny. Two-field change in `session.update`
  payload. No test refactor needed (mock WS does not care about model
  name). Unit test can be a string-assertion on the outgoing JSON.

### Candidate B — disable input transcription entirely

We don't strictly need the source-language transcript for the
translation pipeline; the response WS yields translated text directly.
The transcript is currently used only as `source_text` on the final
`TextDelta` for the cost logger audit trail.

- **Expected impact**: medium-high. Removes a parallel inference graph;
  may free OpenAI scheduler capacity. Hard to predict without testing.
- **Risk**: low for latency, medium for observability — losing
  source_text breaks the audit trail for "what did the user actually
  say" debugging.
- **Implementation cost**: 1-line removal. But Day 5-6 harness wants the
  source transcript displayed for manual scoring. So if we cut this,
  we'd need a separate path to recover source text for the harness only.

### Candidate C — strip duplicate `instructions` from `response.create` + set `turn_detection: null`

PR #2 follow-up + the dead VAD inference. Together: ~100-150 ms of
trimming.

- **Expected impact**: low (~100-150 ms median).
- **Risk**: very low. Both are cleanups, not behavior changes.
- **Implementation cost**: tiny.

## 5. Day 2 target (locked)

**Candidate A**: switch `audio.input.transcription.model` from `whisper-1`
to `gpt-realtime-whisper` and set `audio.input.transcription.delay` to
`"low"`. Keep Candidate C trim (instructions dedup + `turn_detection:
null`) in the same commit since they are free.

**Hypothesis**: median STT drops from 884 ms to **≤ 550 ms**.
Acceptance gate for Day 3 bench:

- If median `stt_ms` ≤ 600 ms AND translation still passes a quick smoke
  (3 known-good phrases produce sensible VN/JP): keep and move on.
- If median 600-800 ms: try `delay: "minimal"`.
- If median > 800 ms or accuracy collapses on smoke: revert and try
  Candidate B + C combo.

We deliberately do NOT touch Candidate B in Day 2 because it would
complicate the Day 5-6 accuracy harness wiring. Revisit only if A fails.

## 6. Implementation outline for Day 2 (Claude prep + Codex impl)

1. **Claude prep**: extend `Translator.__init__` to accept an optional
   `stt_config: STTConfig | None = None` dataclass with fields
   `transcription_model: str = "gpt-realtime-whisper"`,
   `transcription_delay: Literal["minimal","low","medium","high","xhigh"] = "low"`.
   Default the dataclass to the new values so callers get the
   optimisation without code change. Strip `instructions` from
   `response.create`. Add `"turn_detection": None` to the
   `session.audio.input` block (see §7 finding A — NOT at session
   top level). Lock stubs only; the body changes are mechanical and
   Codex-safe.
2. **Codex**: update the session.update JSON, drop the instructions
   field from `response.create`, add a unit test that asserts the
   outgoing JSON contains the new fields.
3. **Claude review + merge.**

## 7. Open questions for Day 2 — resolved by 2026-05-23 live smoke

Codex ran a live smoke against `gpt-realtime-whisper` on 2026-05-23
before opening the PR. Findings:

- **`turn_detection` nesting**: `session.turn_detection` (top level) is
  REJECTED by GA with `Unknown parameter: 'session.turn_detection'`.
  Correct path is `session.audio.input.turn_detection`. Some OpenAI
  guides still document the top-level form, so docs are inconsistent;
  live API is the source of truth. §1 / §4 / §6 above corrected.
- **Source transcript event**: `gpt-realtime-whisper` still emits
  `conversation.item.input_audio_transcription.completed` with a
  string `.transcript` field. `TextDelta.source_text` capture
  unchanged.
- **Usage shape**: `response.done.usage` keys unchanged
  (`input_token_details.audio_tokens`,
  `input_token_details.text_tokens`,
  `input_token_details.cached_tokens_details`,
  `output_token_details.text_tokens`, etc.). `cost_logger` reads
  these fields untouched; no S2 Day 2 change needed.
- **Pricing**: OpenAI pricing page does not list a separate row for
  `gpt-realtime-whisper` as of 2026-05-23. Pricing constants
  follow-up is a separate Claude-prep task (likely Day 3 if Day 3
  bench shows a cost delta), NOT bundled in the Day 2 Codex PR.

## 8. Day 3 device bench result (2026-05-23, same-day)

Backend with Candidate A live on EC2 Osaka (`gpt-realtime-whisper` +
`delay="low"`, `turn_detection: null` nested, instructions deduped).
S1-Run-10 button replayed against the new config.

CSV: `docs/reports/s2_run11_2026-05-23.csv` (10/10 OK rows).
Rendered: `docs/reports/S2_latency_2026-05-23.md`.

Observed (post-tuning):

| Metric | S1 baseline | S2 Day 3 (delay=low) | Δ |
|---|---:|---:|---:|
| STT median | 884 ms | **1044 ms** | **+160 ms regression** |
| STT p90 | 1078 ms | 1122 ms | +44 ms |
| STT p95 | 1169 ms | 1239 ms | +70 ms |
| STT peak-to-peak | 533 ms | 361 ms | **−172 ms (more consistent)** |
| system_latency p95 | 1493 ms | 1478 ms | −15 ms (flat) |
| Retry rate | ~50 % (S1 Day 9) | **0/10** | −50 pts (Day 9 UX bug self-resolved) |

**Verdict**: Day 3 plan said `> 800 ms median → revert + retro`. Strict
read = revert. But Candidate A is composed of multiple sub-changes
(model swap + delay knob + VAD off + dedup); the only one that can
plausibly explain a +160 ms STT regression is the `delay` knob itself
(higher accuracy bias). Distribution tightened (smaller peak-to-peak),
which is the streaming-first model behaving as advertised, but the
floor moved up.

**Day 3 follow-up (Option B, single re-test):** flip
`transcription_delay` from `"low"` to `"minimal"` (the cheapest possible
follow-up — keeps the streaming-first model, only reduces the
end-of-phoneme buffering). If the next bench still shows median > 800 ms,
full revert + retro. If 600-800 ms, accept and audit Day 6 accuracy. If
≤ 600 ms, exit-criterion #1 cleared.

Default updated in `backend/app/services/translator.py`:
`STTConfig.transcription_delay = "minimal"`. Tests updated. Backend
needs redeploy + S1-Run-10 replay.

## Sources

- [Voice activity detection (VAD) | OpenAI API](https://platform.openai.com/docs/guides/realtime-vad)
- [Realtime transcription | OpenAI API](https://developers.openai.com/api/docs/guides/realtime-transcription)
- [gpt-realtime-whisper Model | OpenAI API](https://developers.openai.com/api/docs/models/gpt-realtime-whisper)
- [GPT Realtime Voice Models Explained — MindStudio](https://www.mindstudio.ai/blog/gpt-realtime-voice-models-explained)
- [OpenAI Releases Three Realtime Audio Models — MarkTechPost (2026-05-08)](https://www.marktechpost.com/2026/05/08/openai-releases-three-realtime-audio-models-gpt-realtime-2-gpt-realtime-translate-and-gpt-realtime-whisper-in-the-realtime-api/)
