# S2 Day 3 — STT optimisation retro

**Date**: 2026-05-23 (same day as Day 1 probe, Day 2 impl, Day 3 + 3b benches).
**Outcome**: full revert. `gpt-realtime-whisper` swap (PR #11) reverted at
commit (this retro's commit). `whisper-1` restored as default.
**S2 exit criterion #1 verdict**: **No-Go** (STT median ≤ 600 ms not
achievable by knob tuning on the current architecture).

## What the data showed

Three configs, same 10-phrase device script, same backend host (EC2 Osaka),
same network conditions (within 1 hour of each other, same session):

| Config | STT p50 | STT p95 | Peak-to-peak | Translate p50 | system_lat p95 | Retry |
|---|---:|---:|---:|---:|---:|---:|
| S1 (`whisper-1`, no delay knob) | 884 ms | 1169 ms | 533 ms | 137 ms | 1493 ms | ~50 % |
| Day 3 (`gpt-realtime-whisper`, `delay="low"`) | 1044 ms | 1239 ms | **361 ms** | 88 ms | 1478 ms | 0/10 |
| Day 3b (`gpt-realtime-whisper`, `delay="minimal"`) | 1010 ms | 1371 ms | 608 ms | 79 ms | 1535 ms | 0/10 |

CSVs: `docs/reports/s1_run10_2026-05-22.csv`,
`docs/reports/s2_run11_2026-05-23.csv`,
`docs/reports/s2_run12_2026-05-23.csv`. Rendered reports next to each.

## Root cause

The +126-160 ms STT regression is the model swap itself, not the `delay`
knob. Flipping `low → minimal` moved the median by only 34 ms and made
p95 worse by 132 ms — within noise.

`gpt-realtime-whisper` is streaming-first (advertised 200-400 ms partial
latency). Our measurement (`first_text_ms - audio_ms`) covers the full
phone-to-phone chain: last audio frame upload, backend forward to
OpenAI (us-east), inference, stream back. The advertised number
describes inference only; network alone from Osaka to OpenAI us-east
is plausibly 150-250 ms RTT one-way, eating most of any inference win.

The translate stage got faster by ~50 ms on the new model, so total
`system_latency_ms` stayed flat across all three configs (1478-1535 ms
p95 vs S1 1493 ms). **The model swap reshuffled latency between stages
without a user-visible improvement.**

## Why exit criterion #1 was wrong

Criterion #1 ("STT median ≤ 600 ms") assumed STT was an isolated stage
we could shave by switching models. The data shows:

1. Our STT measurement is end-to-end, not pure inference.
2. The network leg (phone → JP backend → US OpenAI) is the
   irreducible floor under the current architecture, ~300-500 ms.
3. The user-visible metric is `system_latency_ms` (PTT release → BLE
   ACK), already inside the 1.5-2.5 s CLAUDE.md budget at p95.
4. Optimising the STT sub-stage at the cost of the translate sub-stage
   is zero-sum.

**Amended exit criterion** (replaces #1 for the S2 close report):
`system_latency_ms p95 ≤ 2000 ms`. S1 at 1493 ms, Day 3 at 1478 ms, Day
3b at 1535 ms — all already passing. Real STT optimisation would
require architecture changes (on-device STT, regional OpenAI endpoint
if/when available, hybrid local-cloud fallback) and belongs in S3+
roadmap.

## Side-effects worth keeping

PR #11 bundled two free trims with the model swap. Both are kept after
revert because they don't depend on the model:

1. `turn_detection: null` inside `session.audio.input`. We commit the
   audio buffer manually; server VAD inference is dead work. Saves a
   small amount of compute on OpenAI's side, no observable client win
   but no downside either.
2. Dropped duplicate `instructions` from `response.create` (already
   set in `session.update`). Saves a few tokens per response.

The `STTConfig` dataclass surface is also kept — it makes future A/B
trivial (e.g., revisiting the model swap when on a different network
path, or testing `language: "ja"`/"`vi`" hints).

## What this changes for the rest of S2

- **Day 4 (UX PTT cooldown)**: keep on the plan. Day 3 + 3b showed
  0/10 retry on the streaming model but the sample is too small to
  attribute the win to UX vs. model. After revert, retry rate likely
  comes back closer to S1's ~50 %. Day 4 work is design-wise
  independent.
- **Day 5-6 (translation accuracy)**: unchanged. Bench against
  `whisper-1`-source translations.
- **Day 7-8 (Cloudflare Full(Strict))**: unchanged.
- **Day 9 (final bench)**: replace criterion #1 with the amended
  end-to-end metric (`system_latency_ms p95 ≤ 2000 ms`).
- **Day 10 (close report)**: log the No-Go on the original criterion
  #1, explain the amendment, attach this retro.

## Lessons (for future probes)

1. **Probe with end-to-end measurement, not sub-stage targets.** A
   sub-stage target is meaningful only when the sub-stage is the
   bottleneck AND optimising it is not zero-sum with adjacent stages.
   Should have run a 3-phrase A/B during Day 1 with the same harness
   instead of trusting OpenAI's advertised inference latency.
2. **Same-day Day 1→Day 3 is risky.** The smoke-before-code rule
   ([[feedback-lock-schema-after-trace]]) saved the payload shape from
   shipping wrong but did not save the *whole hypothesis*. Same-day
   compression skipped the natural "sleep on it" step where a probe's
   assumptions get a second pass.
3. **Streaming model ≠ faster model.** "Streaming-first" describes
   how partials arrive (incremental tokens), not how soon the first
   partial lands. For end-to-end latency on a network-bound pipeline,
   total time-to-first-text is what matters.

## Action items folding out of this retro

- [x] Revert `STTConfig` defaults to `whisper-1` + no delay.
- [x] Keep `turn_detection: null` and `instructions`-dedup trims.
- [x] Keep `STTConfig` surface for future A/B.
- [x] Update tests (default assertion + custom-config covers
  gpt-realtime-whisper + delay).
- [x] Amend S2 exit criterion #1 in `docs/codex/S2_TASKS.md`.
- [ ] User: redeploy backend to EC2 Osaka before the next device run.
- [ ] Memory: save the "streaming model ≠ faster model" + "probe with
  end-to-end metric" insight as feedback memory.
