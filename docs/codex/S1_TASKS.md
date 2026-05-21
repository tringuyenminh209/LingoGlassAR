# S1 Sprint Task Division — Claude (lead) + Codex (assist)

**Sprint window**: 2026-05-21 to ~2026-06-04 (10 working days).
**Sprint goal**: end-to-end audio -> backend -> OpenAI Realtime ->
translated text -> BLE -> OLED. p95 < 2.5 s, cost < $1/session.

## Split rationale

- **Claude** handles work that requires: cross-file integration, BLE
  protocol changes, multi-step debugging, contract design, sprint
  decisions, latency analysis, code review of Codex output.
- **Codex** handles work that fits in: one file or one small package,
  pure scaffolding from a spec, isolated function implementation,
  boilerplate (Dockerfiles, CI config, repetitive test fixtures).

Codex submits a draft PR or diff; Claude (or the user) reviews before
merge. Codex never pushes to `main` directly.

## How Codex receives a task

For each task below:
1. Read `docs/codex/PROJECT_BRIEFING.md` first (one-time).
2. Read the linked source files referenced in the task.
3. Implement in a feature branch (`feat/s1-day-N-<slug>`).
4. Run the task's "verify" command before declaring done.
5. Open a PR with the conventional-commit subject given.
6. **No `Co-Authored-By: Claude/OpenAI` trailers** on commits.

## Day 1 — Backend scaffold [DONE 2026-05-20]

PR #1 merged at commit `538eae1`. backend/CLAUDE.md added in follow-up
(see "Notes" below).

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Codex** | Create `backend/` Python 3.12 project. `pyproject.toml` (uv or poetry), FastAPI + uvicorn + websockets + redis + openai SDK deps. Layout: `app/main.py` (entry), `app/api/` (routers), `app/services/` (translator placeholder), `app/core/config.py` (pydantic-settings reading .env). `/healthz` returns `{"status":"ok","version":"0.1.0"}`. | `uvicorn app.main:app` listens on :8000, curl returns 200. | DONE |
| **Codex** | `backend/Dockerfile` multi-stage (builder + runtime), `python:3.12-slim` base, non-root user, healthcheck on /healthz. | `docker build -t lg-backend .` succeeds. | DONE |
| **Codex** | `backend/docker-compose.yml`: services `api` (build from Dockerfile, port 8000) + `redis` (redis:7-alpine, no expose). `.env.example` listing `OPENAI_API_KEY=`. | `docker compose up` brings both up, healthcheck green. | DONE |
| **Claude** | Code review Codex PR. Add `backend/CLAUDE.md` with sprint hooks + conventions (mirror `mobile/CLAUDE.md` structure). | Commit, push. | DONE |

Commit subject: `feat(backend): S1 Day 1 FastAPI scaffold + Docker Compose`.

**Notes from review (deferred follow-ups for Day 3+)**:
- `_redis_state` creates a fresh redis client per `/healthz` call. Pool
  the client in app lifespan when Day 3 adds session WS endpoint that
  needs redis more frequently.
- No CORS middleware yet. Add in Day 3 when mobile starts hitting the API.
- `LOG_LEVEL` env is present in settings but not wired to uvicorn yet.
  Wire when Day 3 adds structured logs.
- `/healthz` extended beyond spec: returns redis state too. Acceptable —
  serves as a smoke probe for the Day 3 redis integration. Mobile health
  poll (S1 Day 7) can read this field.

## Day 2 — OpenAI Realtime integration

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Claude** | Design the translator service interface. Decide: streaming generator yielding `TextDelta` events, vs callback-based. Write the interface stub in `app/services/translator.py` with docstring describing the contract. | n/a (design). | DONE 2026-05-21, commit `812bc63` |
| **Codex** | Implement `app/services/translator.py` against the stub. WebSocket client to `wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview`. System prompt: "You are a JP<->VN translator. When you receive Japanese audio, output Vietnamese text only. When you receive Vietnamese audio, output Japanese text only. No commentary, no romanization." Forward incoming audio frames (PCM16 16kHz). Parse `response.text.delta` events. Expose `async def translate_stream(audio_frames: AsyncIterator[bytes]) -> AsyncIterator[TextDelta]`. | Unit test mocks the OpenAI WS, feeds 3 audio chunks, asserts text deltas emitted. | DONE PR #2, `ab22deb` |
| **Codex** | `backend/tests/test_translator.py` with the mock above. Use `pytest-asyncio`. Add to `pyproject.toml` dev deps. | `pytest backend/tests/` passes. | DONE PR #2, `ab22deb` (3/3 pass) |

**Stub design notes** (locked in `812bc63`):
- Public surface = `Translator` class + `TextDelta` dataclass +
  `TranslatorError` + `SYSTEM_INSTRUCTIONS` + `DEFAULT_MODEL` constants.
  Codex implements the body, does not rename or rewrite the surface.
- `TextDelta` has an optional `source_text` field for the Day 8 cost
  logger (carries the transcription of the source-language audio).
  BLE renderer ignores it.
- `Translator` is an async context manager. Single WS per instance.
  Concurrent `translate_stream()` calls on the same instance not
  supported (one utterance at a time).

**Notes from PR #2 review (deferred follow-ups)**:
- Test coverage gap: no test for the `source_text` path
  (`conversation.item.input_audio_transcription.completed`). Implementation
  is in place but unverified. Add when Day 8 cost logger lands so the
  cost-logging path has end-to-end test coverage.
- `websockets.connect(extra_headers=...)` is the legacy v13.x API. If we
  ever upgrade past `websockets >= 14`, switch to `additional_headers`
  on `websockets.asyncio.client.connect`. Pin stays at `>=13,<14` for now.
- `response.create` redundantly carries `instructions` already set in
  `session.update`. Harmless duplication. Strip in Day 3 cleanup pass.

Commit subject: `feat(backend): S1 Day 2 OpenAI Realtime translator service`.

## Day 3 — WebSocket session endpoint

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Claude** | Define the wire protocol between phone and backend. Document in `docs/api-contract/ws-events.schema.json` (already exists - extend). Events: `session.start`, `audio.chunk`, `text.delta`, `text.final`, `error`. | Schema validates against a sample payload. | DONE 2026-05-21, commit `c2f8377` (8/8 samples valid) |
| **Codex** | `app/api/sessions.py` with `POST /v1/sessions` (creates session_id, stores meta in Redis with 1h TTL) and `WS /v1/sessions/{id}/stream` (bridges client audio frames to translator service, relays text deltas back). | `curl POST` returns session_id. `wscat` connect, send dummy bytes, receive mock text. | DONE PR #3, `6bc9ce1` |
| **Codex** | `app/core/redis.py` thin wrapper with async client (`redis.asyncio`). Connection pool from settings. | Health check pings redis. | DONE PR #3, `6bc9ce1` (health.py refactored to use shared pool) |

**Wire contract notes** (locked in `c2f8377`):
- Wire variants on the WS = the 8 oneOf entries in `ws-events.schema.json`.
  Use the variant names verbatim (`session.start`, `session.opened`,
  `audio.chunk`, `audio.end`, `metrics`, `translation.partial`,
  `translation.final`, `error`). The spec text "text.delta / text.final"
  in the original task row mapped to `translation.partial / .final`.
- Audio is PCM16 mono 16 kHz. `audio.chunk.codec` is locked to `pcm16`
  and `sampleRateHz` to 16000.
- `error.code` is an enum: `translator_error`, `upstream_unavailable`,
  `session_not_found`, `daily_cap_exceeded`, `invalid_event`,
  `internal_error`.
- Canonical sample payloads in `docs/api-contract/ws-events.samples.json`;
  validator at `tools/validate_ws_schema.py`.
- HTTP contract for `POST /v1/sessions` + WS path in `openapi.yaml`.
- The Day 1 review follow-ups (redis pool in lifespan, CORS middleware)
  are folded into this Day 3 prompt.

**Notes from PR #3 review (deferred follow-ups)**:
- Docker image does not ship `docs/api-contract/`. Runtime falls back to
  the embedded `_WS_SCHEMA_FALLBACK` inside `app/api/sessions.py` which
  covers only the 4 client->server variants (correct for inbound
  validation, but a drift risk if the canonical schema diverges).
  Mitigation: vendor the schema into the wheel as a package data file
  before Day 4 deploy, or add a CI check that diffs the embedded
  fallback against the canonical schema.
- `session.start.sourceLang` and `targetLang` are required by the
  schema but the WS handler discards them — the translator is hard-locked
  to JP<->VN both directions. Either consume them on the backend
  (when we add lang-pair switching) or relax the schema to optional.
  Defer to Day 7 mobile integration where the real client surface
  will reveal which path is right.
- WS stays open in a dead state after `translation.final` — only viable
  client move is to disconnect. For S1 push-to-talk (one session = one
  utterance) this is fine; tighten in S2 by auto-closing the WS after
  final.

**Day 1 follow-ups all closed by PR #3**:
- redis client pool in lifespan: DONE (`app/core/redis.py` +
  `app/main.py` lifespan)
- CORS middleware: DONE (`app/main.py` + `settings.cors_origins`)
- `/healthz` reuses shared pool via Depends: DONE (`app/api/health.py`)
- LOG_LEVEL wiring to uvicorn: still pending — Day 4 deploy will wire
  this via `uvicorn --log-level $(LOG_LEVEL)` in the runtime CMD or via
  CLI args from `deploy.sh`.

Commit subject: `feat(backend): S1 Day 3 session API + WS bridge`.

## Day 4 — AWS Osaka deploy

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Claude (user-assisted)** | Provision EC2 t4g.small in `ap-northeast-3` via AWS console. Ubuntu 22.04 LTS. Allocate Elastic IP. Security group: 22/tcp from user IP, 80/tcp + 443/tcp from 0.0.0.0/0 (Cloudflare will front). | SSH in, `apt update` works. | runbook + CFN ready, user-execute |
| **Codex** | `infra/ec2/bootstrap.sh` (idempotent): install Docker engine + compose plugin + ufw, allow 22/80/443, enable ufw, create deploy user, set up `~/lingoglass/` clone path. | Run on fresh EC2: exit 0, docker --version, ufw status. | DONE PR #4, `2b2e2bb` (arm64 guard + idempotent docker.list extra) |
| **Codex** | `infra/ec2/deploy.sh`: pull from git, `docker compose pull && docker compose up -d --build`. | Re-run is no-op when no git changes. | DONE PR #4, `2b2e2bb` (60s health poll + log dump on fail) |
| **Claude (user-assisted)** | Cloudflare DNS: add A record `api` -> EC2 EIP, proxied (orange). SSL/TLS mode = "Full". | `curl https://api.lingoglass.online/healthz` returns 200. | runbook ready, user-execute |

**Manual runbook**: `docs/runbook/aws-osaka-deploy.md` (9 sections incl.
EC2 launch, EIP, SSH sanity, bootstrap, Cloudflare DNS, first deploy,
smoke test, cost watch, tear-down).

**Day 4 Codex prompt extends scope slightly**:
- `backend/Dockerfile` CMD wired to `LOG_LEVEL` env (closes the last
  Day 1 review follow-up).
- `backend/docker-compose.yml` gets `restart: unless-stopped` and
  log rotation (`max-size 10m, max-file 3`).
- `infra/ec2/README.md` documents operators' single-command redeploy.

Parallelism note: user can run runbook sections 1-5 while Codex writes
the scripts. The user pauses at section 4 ("bootstrap") until Codex's
PR is on main, then continues.

**Notes from PR #4 review (small follow-up)**:
- bootstrap.sh uses `systemctl enable` + `systemctl start` on separate
  lines. `systemctl enable --now docker.service` would be one line.
  Pure style nit; not worth a follow-up PR.
- Day 1 review follow-up #4 (LOG_LEVEL → uvicorn) is now closed by the
  Dockerfile shell-form CMD change. All Day 1 follow-ups are now
  resolved.

**Defensive code Codex added beyond spec**:
- arm64 architecture guard in bootstrap.sh — exits 1 if accidentally
  run on x86 instance.
- Idempotent docker.list write — only overwrites when content differs.
- `usermod --append` re-add if deploy user exists but is not in
  docker group.
- ISO 8601 UTC timestamps in log helper.

Commit subject: `feat(infra): S1 Day 4 EC2 Osaka bootstrap + deploy scripts`.

## Day 5 — Flutter audio recorder

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Codex** | Add `flutter_sound` dependency to `mobile/pubspec.yaml`. Update Android manifest for `RECORD_AUDIO` + iOS Info.plist for `NSMicrophoneUsageDescription`. | `flutter pub get` clean, app installs. | DONE PR #5, `c5de0ff` |
| **Codex** | `mobile/lib/audio/recorder.dart`: `AudioRecorder` class. `start()` begins capture at PCM16 **24 kHz** mono LE, emits `Stream<Uint8List>` of ~100 ms chunks (**4800 bytes**). `stop()` finalises stream. | Unit test with mock recorder driver passes. | DONE PR #5, `c5de0ff` (22/22 tests pass, AudioRecorderDriver DI pattern) |
| **Claude** | Review chunking strategy. Confirm 100 ms aligns with OpenAI Realtime input expectations. Adjust sample rate if needed. | n/a | DONE 2026-05-22 (see decision below) |

**Sample-rate decision (2026-05-22)**:
- OpenAI Realtime API's `pcm16` input format expects **24 kHz mono LE**
  verbatim. If we sent 16 kHz, OpenAI would play it back at 1.5x speed
  causing garbled transcription.
- Schema (`docs/api-contract/ws-events.schema.json`) updated:
  `audioChunk.sampleRateHz` const 16000 -> **24000**. samples.json
  updated to match. 8/8 samples still validate.
- Translator service docstring (`backend/app/services/translator.py`)
  updated: "24 kHz, 4800 bytes per ~100 ms chunk".
- Mobile recorder is the source: it must record natively at 24 kHz.
  flutter_sound supports this on Android (resampled from device native
  rate by the OS) and iOS (AVAudioRecorder accepts 24 kHz directly).
- Trade-off accepted: 50% more bandwidth vs 16 kHz, but zero backend
  resampling cost and matches OpenAI default. S2 may revisit if cellular
  bandwidth becomes a bottleneck for users.

**Notes from PR #5 review (deferred follow-ups)**:
- `start()` while already recording is **idempotent** (returns same
  stream) instead of throwing RecorderError as the prompt specified.
  Codex's choice is arguably safer for callers but deviates from spec.
  Document in `mobile/CLAUDE.md` sprint hooks when added. If we hit a
  real bug where caller expects throwing semantics, revisit.
- Test coverage gaps (low priority): (c) `stop()` closing stream and
  (d) start-twice-throws are not explicitly asserted. Day 7 integration
  test on device will cover the close path in practice.
- Test file path: `test/audio_recorder_test.dart` (flat) instead of
  `test/audio/recorder_test.dart` (nested). Acceptable while there's
  only one audio file.

Commit subject: `feat(mobile): S1 Day 5 audio recorder service`.

## Day 6 — Mobile WebSocket client

| Owner | Task | Verify | Status |
|---|---|---|---|
| **Codex** | `mobile/lib/services/translator_ws.dart`: connects to `wss://api.lingoglass.online/v1/sessions/.../stream`. API: `connect(sessionId)`, `send(Uint8List audioChunk)`, `Stream<TextDelta> get textStream`, `disconnect()`. Use `package:web_socket_channel`. Reconnect with exponential backoff (1s, 2s, 4s, 8s, cap 30s). | Mock WS server unit test. | DONE PR #6, `10c768a` (27/27 tests pass, TranslatorWsConnector DI + injectable delay) |
| **Claude** | Review reconnect semantics: ensure session_id stays stable across reconnects (or document that mid-session disconnect aborts the utterance). | n/a | DONE 2026-05-22 (decisions below) |

**Lifecycle + reconnect decisions (2026-05-22)**:

1. **1 WS = 1 utterance**. Backend (`backend/app/api/sessions.py`) rejects
   a second `session.start` on the same WS, and tears down after
   `translation.final`. So each push-to-talk gesture is its own WS open
   -> session.start -> audio.* -> translation.* -> close cycle.

2. **Reconnect with exponential backoff applies to INITIAL CONNECT
   ONLY**. Once `session.opened` arrives on this `connect()` call, no
   further auto-reconnect. Mid-utterance disconnect ABORTS the utterance
   (the backend cannot resume because audio frames are not checkpointed
   in OpenAI Realtime).

3. **Mid-utterance drop semantics**: emit `TranslatorWsError(retryable:
   true)` on textStream, close stream, set isConnected=false. The UI
   (Day 7 push-to-talk screen) decides whether to surface "press again"
   or retry automatically. The WS client itself does NOT retry mid-flight.

4. **Backoff schedule**: 1s, 2s, 4s, 8s, cap 30s, max 5 attempts. After
   5 failures, `connect()` throws `TranslatorWsError(retryable: false,
   code: 'upstream_unavailable')`.

5. **session_id management is out of scope for this class**. Caller
   creates the session via HTTP POST `/v1/sessions` and passes the
   returned sessionId in. Same sessionId can be reused for multiple
   sequential utterances until Redis TTL (1h) expires.

6. **TextDelta on mobile mirrors backend** (`app/services/translator.py`):
   - `translation.partial` -> `TextDelta(text, isFinal: false)`
   - `translation.final` -> `TextDelta(text: translatedText,
     isFinal: true, sourceText?)`
   - `error` -> `TranslatorWsError` raised on textStream

7. **session.start does not block on translator service creation**.
   Backend instantiates the OpenAI Translator inside the WS handler
   only after receiving session.start. Mobile's `connect()` waits for
   `session.opened` ack before returning so the caller knows the
   server-side translator is hot.

8. **audio.chunk frame size validation at the WS client boundary**.
   `send()` throws ArgumentError synchronously if chunk length != 4800
   bytes. This catches the bug class "AudioRecorder upstream emitted
   short chunk" before it hits the wire (where validation would only
   surface as `invalid_event` from the backend).

**Notes from PR #6 review (deferred follow-ups)**:
- `connect()` defaults `deviceId` to `''`. Schema declares deviceId as
  required UUID. Backend's `Draft202012Validator` does not strict-validate
  `format: uuid`, so this passes in practice, but conceptually wrong.
  **Day 7** must generate or cache a UUID v4 device ID (via
  `shared_preferences` or similar) and pass it on every connect().
- `textStream` is a broadcast `StreamController`. Broadcast streams do
  not buffer events, so a listener that attaches AFTER the first
  `translation.partial` arrives will miss it. For the push-to-talk
  pattern (connect -> listen -> send), Dart microtask ordering makes
  this safe in practice. Re-check during Day 7 device integration.

Commit subject: `feat(mobile): S1 Day 6 backend WebSocket client`.

## Day 7 — End-to-end wiring

| Owner | Task | Verify |
|---|---|---|
| **Claude** | `mobile/lib/screens/translate_screen.dart`: push-to-talk button + log + connection chip (similar to `spike_screen.dart`). Hold -> recorder.start + WS connect. Release -> recorder.stop + WS close. On `TextDelta` -> append to in-progress subtitle buffer. On `text.final` -> push to `BleTransport.sendSubtitle()`. | Manual: hold mic, say JP phrase, OLED shows VN translation within 2.5 s. |
| **Claude** | Switch `MaterialApp.home` to `TranslateScreen` by default; keep `SpikeScreen` accessible via a debug drawer. | Build + run on device. |
| **Codex** | Add a "Server status" widget that polls `/healthz` every 10 s and displays online/offline chip. | UI shows green when backend reachable. |

Commit subject: `feat(mobile): S1 Day 7 push-to-talk translation pipeline`.

## Day 8 — Cost + diagnostics

| Owner | Task | Verify |
|---|---|---|
| **Codex** | Backend `app/services/cost_logger.py`: log per-session `audio_seconds`, `tokens_in`, `tokens_out` to Redis hash `session:{id}:cost`. Use OpenAI usage events from Realtime API (`response.done` carries usage). **Never log audio bytes or translated text content** - this is a hard privacy boundary. | Run a session, check Redis: `HGETALL session:foo:cost`. |
| **Codex** | `GET /v1/stats` aggregates last 24 h: total cost, total sessions, p50 / p95 session length. Reads from Redis ZSET indexed by timestamp. | curl returns sane JSON. |
| **Claude** | Define hard daily spend cap (env: `DAILY_USD_CAP=5.0`). When exceeded, `/v1/sessions` returns 429. | Force cap to $0.01, attempt session, assert 429. |

Commit subject: `feat(backend): S1 Day 8 cost logging + daily cap`.

## Day 9 — Latency suite end-to-end

| Owner | Task | Verify |
|---|---|---|
| **Claude** | Design the e2e latency record shape: `phrase_id, audio_ms (push-to-talk duration), backend_ack_ms (first ack from WS), first_text_ms (first delta), full_text_ms (text.final), ble_ack_ms (Phase F ACK), total_ms`. | Document in `mobile/lib/services/latency_logger.dart` (extend or sibling file). |
| **Codex** | Extend `LatencyLogger` to handle the e2e record (or new `S1LatencyLogger`). Add S1-Run-10 button on `TranslateScreen`. 10 pre-recorded JP phrases (record once, replay from assets), each triggers a session. Export CSV via existing Copy CSV pattern. | Run 10 phrases, CSV has 10 rows with all 7 columns populated. |
| **Codex** | Extend `tools/latency_report.py`: add an `--s1` mode that summarises by stage (audio/backend/ble) instead of by MTU. | `py tools/latency_report.py --s1 out/s1_run.csv` produces stacked-bar markdown. |

Commit subject: `feat(mobile): S1 Day 9 end-to-end latency suite`.

## Day 10 — Report + Go/No-Go

| Owner | Task | Verify |
|---|---|---|
| **Claude** | Write `docs/s1_report.md` with results, anomalies, decision. Same structure as `phase_f_report.md`. Go = e2e p95 < 2.5 s + cost < $1/session at MTU 247. | File committed. |
| **Codex** | Update root `README.md` (create if missing) with the current high-level architecture diagram + how-to-run. | `gh repo view --web` shows updated README. |
| **Claude** | Tag release `v0.2.0-s1` after Go. Update `MEMORY.md` to mark S1 complete. | `git tag` listed. |

Commit subject: `docs(s1): Run 1 results + Go/No-Go verdict`.

## What Codex must NOT do

- Push to `main`. Always feature branches + PR.
- Touch BLE protocol files (`firmware/esp32s3/lib/ble_protocol/`,
  `mobile/lib/ble/ble_protocol.dart`, `tests/ble_vectors.json`,
  `.claude/skills/ble-protocol/SKILL.md`). Those are Claude-only territory.
- Touch `platformio.ini`, `firmware/CLAUDE.md`, or board hardware config.
- Add new dependencies without asking. List the candidate in the PR
  description and wait for review.
- Delete files unless the task explicitly says to.
- Edit `.claude/` for any reason except updating Codex briefings under
  `.claude/skills/` (only if asked).
- Run `git push --force`, `git reset --hard`, `rm -rf`, or any
  destructive command.

## Communication contract

Each day's PR description must include:
- Task list with checkboxes (`- [x] step done`).
- Verification command output (paste, not summarise).
- Open questions for Claude (if any).
- Files touched (summary).
- Estimated time spent.

Claude reviews within 24 h, leaves either "merge" or "needs work".
After merge, Claude updates this file marking the day complete and
adjusts subsequent days if scope shifted.
