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
| **Codex** | `app/api/sessions.py` with `POST /v1/sessions` (creates session_id, stores meta in Redis with 1h TTL) and `WS /v1/sessions/{id}/stream` (bridges client audio frames to translator service, relays text deltas back). | `curl POST` returns session_id. `wscat` connect, send dummy bytes, receive mock text. | pending Codex |
| **Codex** | `app/core/redis.py` thin wrapper with async client (`redis.asyncio`). Connection pool from settings. | Health check pings redis. | pending Codex |

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

Commit subject: `feat(backend): S1 Day 3 session API + WS bridge`.

## Day 4 — AWS Osaka deploy

| Owner | Task | Verify |
|---|---|---|
| **Claude (user-assisted)** | Provision EC2 t4g.small in `ap-northeast-3` via AWS console. Ubuntu 22.04 LTS. Allocate Elastic IP. Security group: 22/tcp from user IP, 80/tcp + 443/tcp from 0.0.0.0/0 (Cloudflare will front). | SSH in, `apt update` works. |
| **Codex** | `infra/ec2/bootstrap.sh` (idempotent): install Docker engine + compose plugin + ufw, allow 22/80/443, enable ufw, create deploy user, set up `~/lingoglass/` clone path. | Run on fresh EC2: exit 0, docker --version, ufw status. |
| **Codex** | `infra/ec2/deploy.sh`: pull from git, `docker compose pull && docker compose up -d --build`. | Re-run is no-op when no git changes. |
| **Claude (user-assisted)** | Cloudflare DNS: add A record `api` -> EC2 EIP, proxied (orange). SSL/TLS mode = "Full". | `curl https://api.lingoglass.online/healthz` returns 200. |

Commit subject: `feat(infra): S1 Day 4 EC2 Osaka bootstrap + deploy scripts`.

## Day 5 — Flutter audio recorder

| Owner | Task | Verify |
|---|---|---|
| **Codex** | Add `flutter_sound` dependency to `mobile/pubspec.yaml`. Update Android manifest for `RECORD_AUDIO` + iOS Info.plist for `NSMicrophoneUsageDescription`. | `flutter pub get` clean, app installs. |
| **Codex** | `mobile/lib/audio/recorder.dart`: `AudioRecorder` class. `start()` begins capture at PCM16 16 kHz mono, emits `Stream<Uint8List>` of ~100 ms chunks (1600 samples = 3200 bytes). `stop()` finalises stream. | Unit test with mock recorder driver passes. |
| **Claude** | Review chunking strategy. Confirm 100 ms aligns with OpenAI Realtime input expectations (which want 24 kHz PCM16 or 16 kHz). Adjust sample rate if needed. | n/a |

Commit subject: `feat(mobile): S1 Day 5 audio recorder service`.

## Day 6 — Mobile WebSocket client

| Owner | Task | Verify |
|---|---|---|
| **Codex** | `mobile/lib/services/translator_ws.dart`: connects to `wss://api.lingoglass.online/v1/sessions/.../stream`. API: `connect(sessionId)`, `send(Uint8List audioChunk)`, `Stream<TextDelta> get textStream`, `disconnect()`. Use `package:web_socket_channel`. Reconnect with exponential backoff (1s, 2s, 4s, 8s, cap 30s). | Mock WS server unit test. |
| **Claude** | Review reconnect semantics: ensure session_id stays stable across reconnects (or document that mid-session disconnect aborts the utterance). | n/a |

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
