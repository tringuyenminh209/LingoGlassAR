# Codex Prompts — Ready-to-Copy Templates

Three prompt families:
1. **Session opener** — paste once at the start of a Codex session so the
   agent reads the briefing before doing anything.
2. **Day-N task prompt** — paste each day to assign that day's Codex
   rows from `S1_TASKS.md`.
3. **PR-ready prompt** — paste when Codex says it's done, to enforce
   the PR template + verification output.

All prompts assume Codex has shell access in the repo root and can read
files. Adapt slightly for ChatGPT-without-shell (paste file contents
manually) or Cursor agent mode (let it auto-read).

---

## 1. Session opener (paste ONCE per session)

```
You are Codex, assisting on the LingoGlass AR project. Before doing
ANY task, read these files in order:

1. docs/codex/PROJECT_BRIEFING.md
2. docs/codex/S1_TASKS.md
3. CLAUDE.md (repo root)

After reading, summarise back to me in 5-10 bullets:
- The product in one line.
- Which sprint phase we are in and what's next.
- The top 5 hard rules you must not break.
- The BLE protocol packet layout in one line.
- Anything in the briefing you want me to clarify before you start.

DO NOT start writing code yet. Wait for my next message that assigns
a specific Day-N task.
```

---

## Status log

| Day | PR | Verdict | Commit |
|---:|---|---|---|
| 1 | #1 | MERGED 2026-05-20 (clean) | `538eae1` + follow-up `3ff139c` |
| 2 | #2 | MERGED 2026-05-21 (clean) | stub `812bc63`, impl `ab22deb` |
| 3 | #3 | MERGED 2026-05-21 (clean) | contract `c2f8377`, impl `6bc9ce1` |
| 4 | #4 | MERGED 2026-05-21 (clean) | runbook `6345efa`, CFN+drawio `37d31ef`, scripts `2b2e2bb` |
| 5 | #5 | MERGED 2026-05-22 (clean, 1 minor deviation) | audit `a6ba46d`, impl `c5de0ff` |
| 6 | #6 | MERGED 2026-05-22 (clean) | design `297b53e`, impl `10c768a` |
| 7a | (Claude PTT screen on main, manual device test pending) | wire-up `94ba294` | - |
| 7-codex | (Claude prompt ready, awaiting Codex PR) | Server-status widget | - |

## 2. Day-N task prompt — Day 1 (ready to copy)

```
Your task: S1 Day 1 — Backend scaffold. Implement only the rows marked
"Codex" in the Day 1 table of docs/codex/S1_TASKS.md. The "Claude" row
(adding backend/CLAUDE.md) is NOT your task; skip it.

## Concrete deliverables (your rows)

1. Create backend/ Python 3.12 project.
   - Layout:
     backend/
       pyproject.toml         (use uv-style PEP 621; project name lingoglass-backend)
       app/
         __init__.py
         main.py              (FastAPI app factory, mounts /healthz router)
         api/
           __init__.py
           health.py          (router with GET /healthz)
         core/
           __init__.py
           config.py          (pydantic-settings, reads .env)
         services/
           __init__.py        (placeholder for Day 2)
       tests/
         __init__.py
         test_health.py       (httpx asgi client, asserts /healthz returns 200)
       .env.example
       .gitignore             (Python defaults + .env, NOT .env.example)
       README.md              (1-paragraph: what it is, how to run)
   - Dependencies (pin major versions, no betas):
     fastapi >= 0.115, < 1.0
     uvicorn[standard] >= 0.30, < 1.0
     websockets >= 13, < 14
     redis[hiredis] >= 5, < 6
     openai >= 1.50, < 2.0
     pydantic-settings >= 2.5, < 3.0
   - Dev dependencies:
     pytest >= 8, < 9
     pytest-asyncio >= 0.24, < 1.0
     httpx >= 0.27, < 1.0
     ruff >= 0.6, < 1.0
   - /healthz returns: {"status":"ok","version":"0.1.0","redis":"<up|down>"}
     The redis field tries a PING and reports its state without crashing
     when redis is unreachable.

2. backend/Dockerfile (multi-stage):
   - Stage 1 "builder": python:3.12-slim, install uv, build wheel.
   - Stage 2 "runtime": python:3.12-slim, copy wheel + entrypoint,
     create non-root user "app" (uid 10001), HEALTHCHECK CMD curl on /healthz.
   - Final image < 200 MB.

3. backend/docker-compose.yml:
   - Service "api": build from Dockerfile, env_file .env, depends_on redis,
     ports "8000:8000".
   - Service "redis": image redis:7-alpine, no ports exposed to host,
     volume redis-data:/data, healthcheck redis-cli ping.
   - Top-level volumes: redis-data.

4. backend/.env.example:
   OPENAI_API_KEY=
   REDIS_URL=redis://redis:6379/0
   APP_ENV=dev
   LOG_LEVEL=info

## Hard constraints (DO NOT VIOLATE)

- Branch from main: feat/s1-day-1-backend-scaffold
- NEVER push to main. NEVER force-push. NEVER add Co-Authored-By trailers.
- Conventional commit subject: feat(backend): S1 Day 1 FastAPI scaffold + Docker Compose
- DO NOT add any dependency not listed above without asking first.
- DO NOT touch any file outside backend/ except for nothing else.
  (Specifically: do not edit firmware/, mobile/, .claude/, docs/, tests/.)
- Code in English. Comments only when the WHY is non-obvious.

## Verification (run before opening PR; paste raw output into PR body)

cd backend
docker compose up -d --build
sleep 5
curl -s http://localhost:8000/healthz
docker compose ps
docker compose down -v
pytest

All five commands must succeed (exit 0 and sensible output).

## When done

Push the branch and open a PR with this exact body, filled in:

---
## Summary
S1 Day 1 backend scaffold: FastAPI app factory, /healthz with optional
Redis check, multi-stage Dockerfile (non-root, < 200 MB), Docker Compose
with api + redis, pytest harness with one passing test.

## Files added
- backend/pyproject.toml
- backend/Dockerfile
- backend/docker-compose.yml
- backend/.env.example
- backend/.gitignore
- backend/README.md
- backend/app/{__init__.py, main.py}
- backend/app/api/{__init__.py, health.py}
- backend/app/core/{__init__.py, config.py}
- backend/app/services/__init__.py
- backend/tests/{__init__.py, test_health.py}

## Verification output

$ docker compose up -d --build
<paste>

$ curl -s http://localhost:8000/healthz
<paste>

$ docker compose ps
<paste>

$ docker compose down -v
<paste>

$ pytest
<paste>

## Open questions for review
- (list anything you decided without clear guidance)

## Time spent
- ~X hours
---

Then post the PR URL here and STOP. Do not start Day 2.
```

---

## 2b. Day 2 — OpenAI Realtime integration (ready to copy)

**Precondition**: Claude must commit the interface stub at
`backend/app/services/translator.py` first. Do not start Day 2 until
that file exists on `main` with a class signature and docstring contract.

```
Your task: S1 Day 2 — OpenAI Realtime translator service. Implement only
the rows marked "Codex" in the Day 2 table of docs/codex/S1_TASKS.md.
The "Claude" row (interface stub at backend/app/services/translator.py)
is already on main - read it first; your job is the implementation
plus the pytest mock.

## Concrete deliverables (your rows)

1. Implement backend/app/services/translator.py against the existing
   stub on main. Do NOT rewrite the public interface or rename methods.
   Internals:
   - Open an async WebSocket to wss://api.openai.com/v1/realtime
     ?model=gpt-4o-realtime-preview using the openai SDK (preferred) or
     a raw `websockets` client if the SDK does not expose the Realtime
     WS at the time of writing.
   - Send a `session.update` event with instructions:
     "You are a JP<->VN translator. When you receive Japanese audio,
     output Vietnamese text only. When you receive Vietnamese audio,
     output Japanese text only. No commentary, no romanization."
   - Set input_audio_format = pcm16, input_audio_transcription enabled
     so we get the source text for the cost logger later.
   - Forward incoming audio bytes via `input_audio_buffer.append` events.
   - On `response.text.delta` yield a TextDelta(text=<chunk>) on the
     output stream. On `response.text.done` yield TextDelta(final=True).
   - On any OpenAI error event, raise TranslatorError with the message;
     do not swallow.
   - Reuse a single WS connection per translator instance; the caller
     is responsible for lifecycle.

2. backend/tests/test_translator.py:
   - Mock the OpenAI WS using a fake async iterator that emits a fixed
     sequence of server events.
   - Feed 3 audio chunks (any 16-byte payloads) and assert:
     a) text deltas emitted in order
     b) text.done produces TextDelta(final=True)
     c) error event raises TranslatorError
   - Use pytest-asyncio (already a dev dep). asyncio_mode is auto.

## Hard constraints (always apply)

- Branch from main: feat/s1-day-2-translator-service
- NEVER push to main. NEVER force-push. NEVER add Co-Authored-By trailers.
- Conventional commit subject: feat(backend): S1 Day 2 OpenAI Realtime translator service
- Do not add any dependency not already in backend/pyproject.toml without
  asking. If the openai SDK does not yet expose Realtime over WS at the
  version pinned (>= 1.50, < 2.0), use the raw `websockets` library that
  is already a dependency.
- Do not touch firmware/, mobile/, .claude/, tests/ble_vectors.json,
  platformio.ini, or any BLE protocol file.
- Do not touch backend/app/api/ or app/main.py in this PR. Day 3 wires
  the WS endpoint.

## Verification (paste raw output into PR)

cd backend
docker compose up -d --build
sleep 5
docker compose logs api --tail 30
docker compose down -v
pytest -v tests/test_translator.py

The docker run is a smoke check that import does not crash. The pytest
run is the actual verification.

## PR description template

## Summary
<one paragraph: what changed and why>

## Files added / modified
<bullet list>

## Verification output
<paste raw command output, one block per command>

## Open questions for review
<things you decided without explicit guidance>

## Time spent
~X hours

After opening the PR, post the URL here and STOP. Do not start Day 3.
```

## 2c. Day 3 — Session API + WS bridge (ready to copy)

**Precondition**: Claude has locked the wire contract on `main`. Read these
files BEFORE coding:
- `docs/api-contract/ws-events.schema.json`  (JSON Schema, 8 variants)
- `docs/api-contract/ws-events.samples.json` (one canonical payload per variant)
- `docs/api-contract/openapi.yaml`           (POST /v1/sessions + WS doc)
- `backend/app/services/translator.py`       (Translator interface you call)

```
Your task: S1 Day 3 - Session API + WS bridge. Implement only the rows
marked "Codex" in the Day 3 table of docs/codex/S1_TASKS.md. The
"Claude" row (wire contract in docs/api-contract/) is already on main -
read it first; your job is the FastAPI endpoints + redis client wrapper.

## Concrete deliverables (your rows)

1. backend/app/core/redis.py
   - Thin async wrapper around `redis.asyncio`.
   - Single connection pool created on FastAPI startup (lifespan event)
     and torn down on shutdown. Pool size from settings (default 10).
   - Expose `async def get_redis() -> Redis` for handler injection
     (FastAPI Depends). Reuse the pool; do not create a fresh client
     per call (Day 1 follow-up requested this).
   - Reuse the existing `Settings.redis_url` from app/core/config.py.
     Do not add a new env var.

2. backend/app/api/sessions.py
   - `POST /v1/sessions` -> 201 with SessionCreateResponse from
     docs/api-contract/openapi.yaml. Generates a UUID v4 session_id,
     writes `session:{id}` hash to Redis with fields
     {created_at, device_id?, status="open"} and 3600 s TTL.
     Returns {success: true, data: {sessionId, wsUrl, expiresAt}}
     where wsUrl is the absolute wss:// URL the client should open
     (compose from request.url_for or settings.public_base_url; pick
     one and document the choice).
     On daily-cap breach return 429 with ApiFail{code:"daily_cap_exceeded"}.
     For Day 3 the cap is NOT yet enforced - leave a clearly-marked TODO
     hook where the check will live; do not add the cap logic itself
     (that is Day 8).

   - `WS /v1/sessions/{id}/stream`
     a) On connect: look up `session:{id}` in Redis; if missing, accept
        then immediately close with code 4404 and a single `error` frame
        with code `session_not_found`, retryable=false.
     b) Validate every incoming frame against the schema. Frames that
        fail validation -> respond with `error` code `invalid_event`,
        retryable=true, do not close.
     c) Expected client frame order: `session.start` first, then
        repeated `audio.chunk`, terminated by `audio.end`. `metrics`
        frames may interleave at any time.
     d) On `session.start`: instantiate a Translator (api_key from
        settings.openai_api_key) inside `async with`. Reply with
        `session.opened` carrying serverTs.
     e) On each `audio.chunk`: base64-decode dataBase64 and push the
        bytes into a private asyncio.Queue feeding the translator's
        audio_frames AsyncIterator.
     f) On `audio.end`: close the queue (sentinel). The translator
        then emits TextDelta items.
     g) Map TextDelta -> wire:
          delta.text non-empty, final=False  -> `translation.partial`
          delta.final=True                   -> `translation.final`
            (translatedText is the running concatenation of every
             non-empty delta.text emitted in this utterance;
             durationMs = serverTs(final) - serverTs(session.opened))
          delta.source_text not None         -> attach to the upcoming
             translation.final as `sourceText` (privacy: see
             docs/api-contract/ws-events.schema.json description).
     h) On TranslatorError: emit `error` frame with code
        `translator_error`, retryable=true, message=str(exc), then
        close ws with 1011.
     i) On client disconnect mid-utterance: close the translator
        cleanly; do NOT mark the session record as errored - mobile
        may reopen with a new WS for a new utterance under the same
        session_id (S1 push-to-talk model: one session = one utterance,
        but be lenient).
   - Privacy: never log dataBase64, never log delta.text content,
     never log sourceText. Counts/timings only. (See backend/CLAUDE.md.)

3. backend/app/main.py - wire the new router and the redis lifespan.
   - Add `app.include_router(sessions.router)` next to health.
   - Use FastAPI lifespan context to open/close the redis pool.
   - Add CORS middleware: allow_origins from a new settings field
     `cors_origins` (default `["*"]` for dev, comma-split env var
     `CORS_ORIGINS`). allow_methods = ["*"], allow_headers = ["*"],
     allow_credentials = False.

4. backend/tests/test_sessions.py
   - Use ASGITransport, no real redis required. Mock the redis client
     via a fake that records HSET/EXPIRE/HGETALL calls in memory.
   - Tests:
     a) POST /v1/sessions returns 201 with sessionId UUID + wsUrl
        starting with wss:// or ws:// + expiresAt in ISO-8601.
     b) WS connect to an unknown sessionId closes with 4404 and an
        error frame code=session_not_found.
     c) WS happy path: session.start -> session.opened. Send 2
        audio.chunk frames + 1 audio.end. The translator is patched
        to a fake that yields TextDelta("Xin "), TextDelta("chao"),
        TextDelta(final=True). Assert that the client receives, in
        order: session.opened, translation.partial("Xin "),
        translation.partial("chao"), translation.final with
        translatedText="Xin chao".
     d) Invalid frame (missing required field) -> error frame
        code=invalid_event, ws stays open.
   - All four tests pass on pytest -v.

5. backend/app/core/config.py - add:
   - cors_origins: list[str] = ["*"]  (parse from env CORS_ORIGINS)
   - public_base_url: str = "ws://localhost:8000"  (used to compose
     wsUrl in POST /v1/sessions). Document override in .env.example.

6. backend/.env.example - add:
   CORS_ORIGINS=*
   PUBLIC_BASE_URL=ws://localhost:8000

## Hard constraints (always apply)

- Branch from main: feat/s1-day-3-sessions-ws
- NEVER push to main. NEVER force-push. NEVER add Co-Authored-By trailers.
- Conventional commit subject: feat(backend): S1 Day 3 session API + WS bridge
- Do not edit docs/api-contract/*.json or *.yaml - the contract is
  locked. If you find a real bug in the schema, raise it as an open
  question in the PR and STOP that work; do not patch the schema
  yourself.
- Do not edit backend/app/services/translator.py - the interface is
  locked. Use it via `async with Translator(...)`.
- Do not touch firmware/, mobile/, .claude/, tests/ble_vectors.json,
  platformio.ini, or any BLE protocol file.
- New dependencies: you may add `jsonschema >= 4.23, < 5.0` (for
  invalid_event validation). Do not add anything else without asking.
- Privacy: never log frame payloads or translated text content.
  Counts/timings only.

## Verification (paste raw output into PR)

cd backend
docker compose up -d --build
sleep 5
curl -s -X POST http://localhost:8000/v1/sessions
curl -s http://localhost:8000/healthz
docker compose logs api --tail 30
docker compose down -v
pytest -v tests/test_sessions.py tests/test_translator.py tests/test_health.py

The docker step is a smoke check that import + POST work. The pytest
run is the authoritative verification.

## PR description template

## Summary
<one paragraph: what changed and why>

## Files added / modified
<bullet list>

## Verification output
<paste raw output of each command separately>

## Open questions for review
<things you decided without explicit guidance>

## Time spent
~X hours

After opening the PR, post the URL here and STOP. Do not start Day 4.
```

---

## 2d. Day 4 — EC2 bootstrap + deploy scripts (ready to copy)

**Precondition**: Claude has written the manual runbook at
`docs/runbook/aws-osaka-deploy.md`. Read it before coding — it explains
what the human is doing on the AWS console + Cloudflare, which determines
what your scripts can assume (Ubuntu 22.04 ARM, ufw not yet installed,
deploy user not yet created, etc.).

```
Your task: S1 Day 4 - EC2 bootstrap + deploy scripts. Implement only the
rows marked "Codex" in the Day 4 table of docs/codex/S1_TASKS.md. The
"Claude (user-assisted)" rows (EC2 launch + EIP + Cloudflare DNS) are
manual steps in docs/runbook/aws-osaka-deploy.md and are NOT your task.

## Concrete deliverables (your rows)

1. infra/ec2/bootstrap.sh
   - Idempotent provisioning script for a fresh Ubuntu 22.04 LTS ARM
     instance. Re-running on a fully-bootstrapped box must exit 0 and
     change nothing.
   - Must be runnable as: `sudo bash bootstrap.sh`. Aborts if not root.
   - Steps in order:
     a) `apt-get update -y` and `apt-get upgrade -y` (non-interactive,
        `DEBIAN_FRONTEND=noninteractive`).
     b) Install required base packages: ca-certificates, curl, gnupg,
        lsb-release, ufw, git.
     c) Install Docker Engine + compose plugin via the official Docker
        APT repository (NOT docker.io from Ubuntu archive). Architecture
        must be `arm64`. Use the official keyring at
        /etc/apt/keyrings/docker.gpg. Install packages: docker-ce,
        docker-ce-cli, containerd.io, docker-buildx-plugin,
        docker-compose-plugin.
     d) Create system user `deploy` with home `/home/deploy`, shell
        /bin/bash, and add to the `docker` group. Skip if user already
        exists.
     e) Ensure `/home/deploy/lingoglass` exists, owned by `deploy:deploy`,
        mode 755. Do NOT clone the repo (manual step in runbook).
     f) Configure ufw: default deny incoming, default allow outgoing,
        allow 22/tcp, 80/tcp, 443/tcp. Enable ufw with `--force` to
        avoid the interactive prompt.
     g) Enable + start docker.service.
     h) Print a verification summary: `docker --version`,
        `docker compose version`, `ufw status verbose`, `id deploy`.
   - Use `set -euo pipefail` at the top. All paths absolute. No relative
     paths to `pwd`. Comment each step block with a short why.
   - The script is committed as executable (`chmod +x` in git).

2. infra/ec2/deploy.sh
   - Runs as the `deploy` user (the runbook does `sudo -u deploy -i`).
     Aborts if invoked as root (`[[ $EUID -ne 0 ]]` check).
   - Assumes the repo is cloned at `/home/deploy/lingoglass`.
   - Steps in order:
     a) cd into `/home/deploy/lingoglass`.
     b) `git fetch origin --prune`
     c) `git checkout main`
     d) `git pull --ff-only origin main` — fail loud if non-fast-forward
        (do not auto-merge; surface the conflict to the operator).
     e) cd into `backend/`.
     f) Require `.env` to exist. If missing, print a clear error
        pointing to the runbook section "First deploy" and exit 1.
     g) `docker compose pull --quiet` (no-op when images are built
        locally; useful later if we move to a registry).
     h) `docker compose up -d --build --remove-orphans`.
     i) Wait up to 60 s for the api container to be healthy. Poll
        `docker inspect --format '{{.State.Health.Status}}' <api container>`
        every 2 s. On timeout, dump `docker compose logs api --tail 60`
        and exit 1.
     j) `curl -fsS http://localhost:8000/healthz` to confirm the app
        responds. Print the response body. Exit 1 on non-2xx.
   - Use `set -euo pipefail`. Logging: print timestamped step headers
     `[deploy 2026-05-22T01:23:45Z] step name`. Helps when operators
     come back to logs later.
   - Idempotent: a second invocation with no git changes should be a
     fast no-op (compose recognises images, up -d is idempotent).

3. infra/ec2/README.md
   - One paragraph: what these scripts are for.
   - "First time" section: pointer to docs/runbook/aws-osaka-deploy.md.
   - "Redeploy" section: the single command operators will run
     (`bash infra/ec2/deploy.sh`).
   - "Troubleshooting" section: 4-5 common failures from the runbook
     (ufw blocking, env missing, redis unhealthy, etc.) with the
     command to diagnose each.

4. backend/Dockerfile - wire LOG_LEVEL env to uvicorn.
   - Day 1 review left this as a follow-up. The current CMD is
     `["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`
     which ignores LOG_LEVEL. Change to use sh -c so the env is
     expanded, with a sensible default:
     `CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level ${LOG_LEVEL:-info}"]`
   - Verify with `LOG_LEVEL=debug docker compose up -d --build` followed
     by `docker compose logs api --tail 5` — the debug lines should
     appear.

5. backend/docker-compose.yml - small production-readiness tweaks.
   - Add `restart: unless-stopped` to both `api` and `redis` services.
   - Add `logging.driver: json-file` with `options.max-size: "10m"` and
     `options.max-file: "3"` to both services. Keeps log disk usage
     bounded.
   - Do NOT change ports, volumes, healthcheck cadence, or env_file
     wiring.

## Hard constraints (always apply)

- Branch from main: feat/s1-day-4-ec2-bootstrap-deploy
- NEVER push to main. NEVER force-push. NEVER add Co-Authored-By trailers.
- Conventional commit subject: feat(infra): S1 Day 4 EC2 Osaka bootstrap + deploy scripts
- Do not edit docs/runbook/* - the runbook is locked by Claude.
- Do not edit docs/api-contract/* or any BLE protocol file.
- Do not touch firmware/, mobile/, .claude/.
- No new dependencies. Bash + standard Ubuntu packages + Docker only.
- Make both .sh files executable in git (`git update-index --chmod=+x`).

## Verification (paste raw output into PR)

Local-only verification (no real EC2 needed for the PR):

# 1. Static checks
shellcheck infra/ec2/bootstrap.sh infra/ec2/deploy.sh
bash -n infra/ec2/bootstrap.sh
bash -n infra/ec2/deploy.sh

# 2. Confirm executable bit committed
git ls-files --stage infra/ec2/*.sh
# Expected output lines start with "100755"

# 3. Dockerfile change does not break the build
cd backend
docker compose up -d --build
sleep 5
curl -s http://localhost:8000/healthz
docker compose logs api --tail 5
docker compose down -v

# 4. Existing tests still pass
pytest -v

If shellcheck is not installed in your sandbox, note that in the PR
and run `bash -n` only. Do not skip the bash -n parse check.

## PR description template

## Summary
<one paragraph: what changed and why>

## Files added / modified
<bullet list>

## Verification output
<paste raw command output, one block per command>

## Open questions for review
<things you decided without explicit guidance>

## Time spent
~X hours

After opening the PR, post the URL here and STOP. Do not start Day 5.
```

---

## 2e. Day 5 — Flutter audio recorder (ready to copy)

**Precondition**: Claude has audited and locked the audio format on `main`.
**24 kHz PCM16 mono LE** (NOT 16 kHz) to match OpenAI Realtime exactly.
Schema (`docs/api-contract/ws-events.schema.json`) and translator docstring
already reflect this. Recorder must record at 24000 Hz natively.

```
Your task: S1 Day 5 - Flutter audio recorder. Implement only the rows
marked "Codex" in the Day 5 table of docs/codex/S1_TASKS.md. The "Claude"
row (chunking strategy review) was completed pre-task; the locked format
is 24 kHz PCM16 mono LE, ~100 ms chunks = 4800 bytes per chunk.

## Concrete deliverables (your rows)

1. mobile/pubspec.yaml: add `flutter_sound: ^9.2.13` to dependencies.
   Do not bump existing dep versions. Run `flutter pub get` locally to
   verify resolution; paste the output into the PR.

2. mobile/android/app/src/main/AndroidManifest.xml:
   - Add `<uses-permission android:name="android.permission.RECORD_AUDIO"/>`
     inside the manifest root, alongside the existing BLUETOOTH_*
     permissions. Do not touch existing entries.

3. mobile/ios/Runner/Info.plist:
   - Add `<key>NSMicrophoneUsageDescription</key>` with a one-line
     English string: "LingoGlass needs the microphone to translate
     speech in real time." Do not touch other keys.

4. mobile/lib/audio/recorder.dart - new file. Public API:

   ```dart
   class AudioRecorder {
     /// Start capturing PCM16 mono LE at 24 kHz.
     /// Emits ~100 ms chunks (4800 bytes each) on the returned stream.
     /// Throws RecorderError if the OS denies the mic permission or the
     /// platform recorder fails to start.
     Future<Stream<Uint8List>> start();

     /// Stop capturing. Closes the stream, releases the OS recorder.
     /// Safe to call multiple times.
     Future<void> stop();

     /// True between start() and stop().
     bool get isRecording;
   }

   class RecorderError implements Exception {
     RecorderError(this.message);
     final String message;
     @override String toString() => 'RecorderError: $message';
   }
   ```

   Implementation rules:
   - Use flutter_sound's `FlutterSoundRecorder.startRecorderToStream`
     with `codec: Codec.pcm16`, `sampleRate: 24000`, `numChannels: 1`.
   - flutter_sound delivers chunks of opaque size. Buffer the incoming
     bytes and emit fixed 4800-byte chunks via a StreamController so
     the consumer always sees ~100 ms slices. If start() is called
     while already recording, throw RecorderError.
   - On permission denial: call `permission_handler` to request
     `Permission.microphone` first; if denied, throw RecorderError.
   - Use `Uint8List` everywhere on the BLE-style boundary (no
     `List<int>`).
   - Idempotent close: stop() while not recording is a no-op.

5. mobile/test/audio/recorder_test.dart - unit test with a fake
   recorder driver. Verify:
   a) After start(), the returned stream emits at least one 4800-byte
      Uint8List chunk when the fake feeds 9600 bytes total.
   b) Partial trailing bytes (< 4800) are held in the buffer and NOT
      emitted (no short chunks on the wire).
   c) stop() closes the stream cleanly (listener gets onDone).
   d) Calling start() twice in a row throws RecorderError.
   You may need to abstract the platform recorder behind a small
   interface (e.g. `_PlatformRecorder`) so the test can inject a fake.
   Keep this abstraction in the same file or a sibling private file -
   do NOT add a new top-level package.

## Hard constraints (always apply)

- Branch from main: feat/s1-day-5-audio-recorder
- NEVER push to main. NEVER force-push. NEVER add Co-Authored-By trailers.
- Conventional commit subject: feat(mobile): S1 Day 5 PCM16 24 kHz audio recorder
- Do not edit firmware/, backend/, .claude/, docs/api-contract/,
  tests/ble_vectors.json, platformio.ini, or any BLE protocol file.
- Sample rate is locked at 24000 Hz. Do NOT change to 16 kHz or 48 kHz
  "for compatibility" — backend translator forwards bytes verbatim and
  expects exactly 24 kHz to match OpenAI Realtime pcm16.
- Chunk size is 4800 bytes (100 ms at 24 kHz, 16-bit, mono). Do NOT
  change to power-of-two sizes — the Day 9 latency budget assumes
  100 ms granularity.
- Do not add `axios`, `dio`, or any HTTP shim. Recorder is local-only
  for Day 5; WS sending is Day 6.
- No new dependencies beyond flutter_sound. Reuse existing
  permission_handler (^11.3.1) for mic permission.

## Verification (paste raw output into PR)

cd mobile
flutter pub get
flutter analyze
flutter test test/audio/recorder_test.dart
flutter test    # full suite must still pass

The first three commands prove the new code compiles + tests pass.
The fourth proves we did not break the existing Phase F BLE tests.

You do NOT need to flash this to a device for the PR — the unit test
with the fake recorder driver is sufficient. Device verification is
Claude's Day 7 work.

## PR description template

## Summary
<one paragraph: what changed and why>

## Files added / modified
<bullet list>

## Verification output
<paste raw command output, one block per command>

## Open questions for review
<things you decided without explicit guidance>

## Time spent
~X hours

After opening the PR, post the URL here and STOP. Do not start Day 6.
```

---

## 2f. Day 6 — Mobile WebSocket client (ready to copy)

**Precondition**: Claude has locked the lifecycle + reconnect semantics
in `docs/codex/S1_TASKS.md` Day 6 section. Read it first:
- 1 WS = 1 utterance (server tears down after translation.final)
- Reconnect with exponential backoff applies to INITIAL connect only
- Mid-utterance drop = ABORT, never silent reconnect
- session_id is supplied by caller (HTTP POST done elsewhere)

```
Your task: S1 Day 6 - Mobile WebSocket client. Implement only the rows
marked "Codex" in the Day 6 table of docs/codex/S1_TASKS.md. The
"Claude" row (reconnect semantics review) is in S1_TASKS.md.

## Concrete deliverables (your rows)

1. mobile/pubspec.yaml: add `web_socket_channel: ^3.0.1`. Do not bump
   existing deps.

2. mobile/lib/services/translator_ws.dart - new file. Public API:

   ```dart
   /// One incremental output decoded from the backend WS stream.
   /// Mirrors backend `app/services/translator.py` TextDelta.
   class TextDelta {
     const TextDelta({required this.text, this.isFinal = false, this.sourceText});
     final String text;
     final bool isFinal;
     final String? sourceText;
   }

   /// Thrown when the backend sends an `error` frame or the WS
   /// transport fails non-recoverably mid-utterance.
   class TranslatorWsError implements Exception {
     TranslatorWsError(this.code, this.message, {this.retryable = false});
     final String code;       // matches schema enum: translator_error, ...
     final String message;
     final bool retryable;
     @override String toString() => 'TranslatorWsError($code): $message';
   }

   /// One WS = one utterance. Caller creates the session via HTTP POST
   /// elsewhere and passes the sessionId here. Each connect()/disconnect()
   /// cycle covers a single push-to-talk gesture.
   class TranslatorWs {
     TranslatorWs({Uri? wsBase})
         : _wsBase = wsBase ?? Uri.parse('wss://api.lingoglass.online');

     /// Open a WS to /v1/sessions/{sessionId}/stream, send session.start,
     /// wait for session.opened, then ready to send audio chunks.
     ///
     /// Retries the underlying socket open with exponential backoff
     /// (1s, 2s, 4s, 8s, cap 30s, max 5 attempts) on transport-level
     /// failure (DNS, refused, 502). DOES NOT retry on protocol errors
     /// from the server (those raise TranslatorWsError immediately).
     ///
     /// Throws TranslatorWsError if all retries exhausted.
     Future<void> connect(String sessionId, {
       String deviceId = '',  // optional UUID; pass through to session.start
       String sourceLang = 'ja',
       String targetLang = 'vi',
     });

     /// Send one PCM16 24 kHz mono audio chunk. Must be 4800 bytes
     /// (validated). Throws StateError if not connected.
     /// Internally encodes as `audio.chunk` wire frame.
     void send(Uint8List audioChunk);

     /// Signal end-of-utterance. Backend will respond with translation
     /// deltas + one translation.final on textStream.
     void endUtterance();

     /// Stream of decoded TextDelta events. Closes (onDone) after
     /// receiving translation.final OR if WS disconnects.
     /// Errors are TranslatorWsError instances.
     Stream<TextDelta> get textStream;

     /// Close the WS cleanly. Idempotent.
     Future<void> disconnect();

     /// True between successful connect() and disconnect()/server-close.
     bool get isConnected;

     final Uri _wsBase;
   }
   ```

   Implementation rules:
   - Use `package:web_socket_channel/web_socket_channel.dart`. On
     mobile/desktop, use `IOWebSocketChannel.connect()`. Do NOT pull in
     `package:web_socket_channel/io.dart` directly if it doesn't expose
     a public Dart API in 3.0.1 - use the top-level connect helper.
   - URL composition: `${_wsBase}/v1/sessions/${sessionId}/stream`
     (`_wsBase` defaults to `wss://api.lingoglass.online`).
   - Reconnect/backoff applies to OPENING the socket only. Once
     session.opened arrives, no further auto-reconnect on this connect()
     call. Mid-utterance drop => emit TranslatorWsError on textStream
     then close.
   - Frame schema (lock from docs/api-contract/ws-events.schema.json):
     * Outgoing session.start: `{type, deviceId, sourceLang, targetLang,
       retainText=false, clientTs}` (ISO 8601 UTC).
     * Outgoing audio.chunk: `{type, sessionId, seq, codec="pcm16",
       sampleRateHz=24000, dataBase64, clientTs}`. seq starts at 0,
       increments per send().
     * Outgoing audio.end: `{type, sessionId, seq, clientTs}` (seq =
       last audio.chunk seq + 1).
     * Incoming session.opened: latch as "connected", emit nothing
       on textStream.
     * Incoming translation.partial: emit TextDelta(text, isFinal=false).
     * Incoming translation.final: emit TextDelta(text=translatedText,
       isFinal=true, sourceText=sourceText if present). Then close
       textStream cleanly.
     * Incoming error: raise TranslatorWsError on textStream with the
       wire code + message + retryable, then close.
   - Audio chunk size validation: `assert audioChunk.length == 4800`.
     Throw ArgumentError on mismatch (catches caller bugs early).
   - clientTs: `DateTime.now().toUtc().toIso8601String()`.
   - Use `dart:convert` `base64Encode` for the audio payload (not the
     web-only base64 codec).
   - No new packages beyond web_socket_channel. Reuse `dart:convert`
     for JSON + base64.

3. mobile/test/services/translator_ws_test.dart - unit test with a fake
   WS server (use the `MockWebSocketServer` pattern from
   web_socket_channel's testing examples, or roll a small fake
   StreamSink/Stream pair). Verify:
   a) connect() sends session.start then completes when fake server
      replies session.opened.
   b) send() emits one audio.chunk wire frame with correct fields
      (sessionId, seq, codec, sampleRateHz=24000, dataBase64 length).
   c) endUtterance() emits audio.end with seq = last chunk seq + 1.
   d) Receiving translation.partial then translation.final on the
      socket yields two TextDelta events on textStream, second with
      isFinal=true, then stream closes.
   e) Receiving an error frame raises TranslatorWsError on textStream
      with the wire code preserved.
   f) Chunk size != 4800 throws ArgumentError synchronously from send().

   The test must not open a real network socket. Use an injected fake
   transport or the same `@visibleForTesting` driver pattern Codex used
   in Day 5 recorder.dart.

## Hard constraints (always apply)

- Branch from main: feat/s1-day-6-translator-ws
- NEVER push to main. NEVER force-push. NEVER add Co-Authored-By trailers.
- Conventional commit subject: feat(mobile): S1 Day 6 backend WebSocket client
- Do not edit firmware/, backend/, .claude/, docs/api-contract/,
  tests/ble_vectors.json, platformio.ini, or any BLE protocol file.
- Audio frame size is locked at 4800 bytes. Do NOT add resampling or
  variable chunk support.
- Sample rate is locked at 24000 Hz. Do NOT write a sampleRateHz
  parameter; hard-code 24000 in the wire frame.
- Wire frame names are from ws-events.schema.json. Do not invent
  new event types.
- Reconnect/backoff applies to initial connect only. Mid-utterance
  drop => error + close, never silent recovery.
- No new dependencies beyond web_socket_channel ^3.0.1.

## Verification (paste raw output into PR)

cd mobile
flutter pub get
flutter analyze lib/services/translator_ws.dart test/services/translator_ws_test.dart
flutter test test/services/translator_ws_test.dart
flutter test    # full suite must still pass

If `flutter test` reports unrelated pre-existing warnings (BleTransport
_ackChar, latency_logger prefer_const_constructors, widget_test
unused-import), call those out in Open Questions; they are NOT yours
to fix in this PR.

## PR description template

## Summary
<one paragraph: what changed and why>

## Files added / modified
<bullet list>

## Verification output
<paste raw command output, one block per command>

## Open questions for review
<things you decided without explicit guidance>

## Time spent
~X hours

After opening the PR, post the URL here and STOP. Do not start Day 7.
```

---

## 2g. Day 7 (Codex row) — Server status widget (ready to copy)

**Precondition**: Phase 7a is merged on main. `TranslateScreen` exists at
`mobile/lib/screens/translate_screen.dart` with an AppBar `actions:` list
containing two `_chip(...)` widgets. Your task adds a third chip that
polls `/healthz` independently.

```
Your task: S1 Day 7 - Server status widget. Add a small widget that
polls https://api.lingoglass.online/healthz every 10 seconds and shows
an online/offline chip in TranslateScreen.

## Concrete deliverables

1. mobile/lib/widgets/server_status_chip.dart - new file.
   - StatefulWidget. On mount, poll /healthz every 10 s.
   - Display a Chip with label "API" and color:
     * Green: last poll returned HTTP 200 and body.redis == "up"
     * Yellow: last poll returned 200 but redis == "down"
     * Red: last poll failed (timeout, non-2xx, parse error)
     * Grey: no poll completed yet (initial state)
   - Use the existing `http` package (already in pubspec).
   - Use Timer.periodic for polling. Cancel in dispose().
   - Each poll has a 5-second timeout. On timeout, treat as red.
   - Do NOT crash the screen if /healthz is unreachable; the widget is
     decorative.
   - Accept an optional `Uri? apiBase` constructor param (default
     `https://api.lingoglass.online`). Useful for tests + dev override.

2. mobile/lib/screens/translate_screen.dart - small edit.
   - Add `import '../widgets/server_status_chip.dart';`
   - In the AppBar actions list, insert `const ServerStatusChip()` as
     the FIRST chip (before BACKEND and BLE). Do not modify other
     actions logic.

3. mobile/test/widgets/server_status_chip_test.dart - unit test.
   - Use a fake http.Client that returns a sequence of responses
     (200 redis:up, 200 redis:down, 500, timeout).
   - Verify the chip color/label transitions after each poll.
   - Use FakeAsync (from package:fake_async, NOT yet in deps - if you
     need it, prefer a different strategy: pass an injectable
     pollInterval and a manually-triggered poll method via
     @visibleForTesting, like Day 5 / Day 6 patterns).

## Hard constraints

- Branch: feat/s1-day-7-server-status-chip
- Commit subject: feat(mobile): S1 Day 7 server status chip
- No new dependencies. http + flutter SDK + flutter_test only.
- Do not touch translator_ws.dart, recorder.dart, ble_transport.dart,
  or any service in lib/services/. Polling stays self-contained in
  the widget.
- Do not touch backend/, firmware/, docs/api-contract/, .claude/.
- Idle CPU: timer fires once per 10 s. Do NOT poll more aggressively.

## Verification

cd mobile
flutter pub get
flutter analyze lib/widgets/server_status_chip.dart test/widgets/server_status_chip_test.dart
flutter test test/widgets/server_status_chip_test.dart
flutter test    # full suite must still pass (28 tests after this)

## PR description template

## Summary
<one paragraph>

## Files added / modified
<bullet list>

## Verification output
<paste raw>

## Open questions for review
<things you decided>

## Time spent
~X hours

After opening the PR, post the URL and STOP.
```

---

## 2h. Day 7 (Codex row) — OLED text density + paging for long subtitles

**Precondition**: `69245ba` is merged on main. `lib/oled_view/oled_view.cpp`
ships dual unifont (JP/VN) at 16 px with layout y=0, y=24, two-line.
Live JP+VN translation works but a typical translated sentence
("何か話してみようか？何でもいいんだよ、気軽に話してごらん…") only renders the
first ~7 CJK characters before running off the right edge. The rest is
lost. This task fixes that without losing the dual JP/VN font work.

Goal: a translated subtitle of up to ~120 codepoints is fully visible —
either by fitting more per screen (smaller font + word wrap) and/or by
auto-advancing through pages (paging). Final result must render the same
on JP and VN content; never garble script.

```
Your task: S1 Day 7 - OLED text density + paging. Make long JP/VN
subtitles fully visible on the SSD1306 128x64 OLED. Currently a long
sentence runs off the right edge after ~7 CJK or ~16 Latin characters
and is silently truncated.

## Concrete deliverables

1. firmware/esp32s3/lib/oled_view/oled_view.cpp + .h - rework.

   Smaller default font for JP (text density):
   - Switch the JP font from `u8g2_font_unifont_t_japanese2` (16 px) to
     `u8g2_font_b12_t_japanese2` (12 px). The b12 variant exists in
     this u8g2 build (see u8g2.h line 3315) and covers Hiragana,
     Katakana, and ~3000 Kanji.
   - VN keeps `u8g2_font_unifont_t_vietnamese1` (16 px) because u8g2
     ships no 12 px Vietnamese variant with precomposed diacritics.
     This is acceptable — VN diacritics need the height to stay legible
     on a 1.3 mm dot pitch.
   - Per-line script detection (the existing pick_font() at the byte
     0xE3-0xE9 boundary) keeps the right font per line. Variable
     line-height is fine: layout below uses each font's ascent.

   Word-wrap into a line buffer:
   - Add a helper that takes a UTF-8 string and the active font, and
     produces an ordered list of line slices that each fit within
     128 px width. Use `u8g2.getUTF8Width(slice)` to measure. Break at
     spaces / punctuation when possible; if no whitespace exists (long
     CJK run), fall back to per-codepoint splitting. NEVER cut inside a
     multi-byte UTF-8 codepoint — back the boundary up to the start of
     the leading byte (`(b & 0xC0) != 0x80`).
   - Cap the line buffer at 32 lines. Subtitles longer than that are
     truncated with a trailing `…` on the last line.

   Paging:
   - JP page: ceil(64 / 12) = 5 lines per page at y = 0, 12, 24, 36, 48.
   - VN page: ceil(64 / 16) = 4 lines per page at y = 0, 16, 32, 48.
   - If the wrapped line count <= one page, render as before — no
     paging, no timer.
   - If line count > one page, auto-advance pages every PAGE_HOLD_MS
     milliseconds (default 2500). When the last page is shown, hold it
     2x as long (5000 ms by default), then loop back to page 0.
   - The page advance is driven by the main-loop calling a new
     `oled_view::tick(uint32_t now_ms)` once per loop iteration. Do
     NOT use Arduino `delay()`, internal timers, or RTOS tasks — the
     existing main loop already calls `loop()` at >100 Hz and tick()
     is the cheapest integration point.

   Public surface (header) - keep existing functions, add two:
   - existing: `begin`, `is_ready`, `show_status`, `show_heartbeat`
   - new: `void tick(uint32_t now_ms)` — drives paging
   - new (optional, for tests): `size_t page_count()` — returns the
     number of pages the current subtitle wraps into. Useful for
     verifying the wrap math.

   Behavior detail:
   - `show_status(line1, line2)`: line1 is treated as a single short
     header (e.g. "LingoGlass S0") that stays at the top across all
     pages of line2. line2 is the long subtitle and gets wrapped /
     paged. If line2 is null/empty, behave as today.
   - `show_heartbeat(counter)`: unchanged — one screen, no paging.
   - When `show_status` is called again with a new line2, reset page
     state to page 0 immediately and re-wrap.

2. firmware/esp32s3/src/main.cpp - tiny edit.
   - Add a single call `oled_view::tick(millis())` inside `loop()`,
     near the existing display calls. Nothing else changes here.

3. firmware/esp32s3/test/test_oled_wrap/test_oled_wrap.cpp - new
   native unit test (host-side, no hardware) for the wrap algorithm.
   - Use the existing `pio test -e native` env.
   - The U8g2 width measurement requires the display object, so factor
     the wrap helper to take a `std::function<int(const char*)>` (or a
     plain function pointer) that returns the pixel width of a UTF-8
     slice. In production it wraps `g_display.getUTF8Width`; in tests
     it returns `strlen * char_width_constant`.
   - Test cases (minimum 6):
     * Empty string -> 0 lines.
     * Short JP that fits one line -> 1 line, no truncation.
     * Long JP with no spaces -> wraps at codepoint boundary, never
       mid-multi-byte.
     * Long VN with spaces -> wraps at word boundaries when possible.
     * Mixed JP+VN+ASCII -> still wraps cleanly.
     * Subtitle longer than 32-line cap -> last line ends with `…`.

## Hard constraints

- Branch: feat/s1-day-7-oled-paging
- Commit subject: feat(firmware): S1 Day 7 OLED text density + paging
- Do not touch backend/, mobile/, docs/api-contract/, .claude/.
- Do not change the BLE protocol or the subtitle assembler.
- Flash budget: total firmware.bin must stay under 1.2 MB. The b12 JP
  font is ~85 KB vs the unifont_t_japanese2 we drop (~110 KB), so net
  budget should improve. Report `Flash: [X bytes from 6553600 bytes]`
  from the build output in the PR.
- Latency budget (BLE leg): adding `tick()` to the main loop must not
  push the BLE-write -> render path above 200 ms. tick() is a cheap
  comparison + optional redraw; do not redraw if the current page
  hasn't changed.
- UTF-8 correctness: every wrap point must fall on a codepoint
  boundary. Test vector that exercises a Kanji at the 128-px edge is
  mandatory in test_oled_wrap.cpp.

## Verification

cd firmware/esp32s3
pio test -e native -f test_oled_wrap
pio run -e esp32s3
# capture and paste:
# - "Flash: [X bytes from 6553600 bytes]" from the build output
# - the 6 wrap test names that pass

After flashing on real hardware (user does this), record a 5-second
video of a long JP subtitle paging through. Attach to PR description
or describe it in words ("page 1 shows L1-L5 of N, page 2 shows
L6-L10, last page held 2x").

## PR description template

## Summary
<one paragraph: density + paging summary>

## Files added / modified
<bullet list>

## Verification output
<paste raw pio output>

## Open questions for review
<things you decided>
- Did you keep `show_status(null, null)` as a clear-screen? (Yes/No)
- How did you handle the case where line1 height + first page line2
  height exceeds 64 px? (Should not happen with current fonts, but
  document the safety net.)

## Time spent
~X hours

After opening the PR, post the URL and STOP.
```

---

## 2i. Day 8 (Codex rows) — Cost logger + daily cap (ready to copy)

**Precondition**: `f8dc457` is merged on main. `backend/app/services/cost_logger.py`
ships the locked public surface (`CostUsage`, `CostRecord`, `DailyStats`,
`DailyCapExceeded`, `compute_usd`, `CostLogger` skeleton with
`NotImplementedError` bodies, `enforce_daily_cap` stub). The
`response.done` usage shape was verified against `gpt-realtime` GA on
2026-05-22; the per-million-token pricing fields are already on
`Settings` and `.env.example`. `translator.Translator.translate_stream`
already yields the final `TextDelta` with `usage: CostUsage | None`
populated.

Codex job: fill the `NotImplementedError` bodies, wire the logger into
the WS session handler, expose `GET /v1/stats`, and enforce the daily
cap in `POST /v1/sessions`. **Do not change the locked interface** —
field names, method signatures, exception types, and the redis key
schema in the cost_logger.py module docstring are the contract.

```
Your task: S1 Day 8 — cost logger + daily cap. Implement the rows
marked "Codex" in the Day 8 table of docs/codex/S1_TASKS.md. The
interface in backend/app/services/cost_logger.py is LOCKED — fill the
NotImplementedError bodies, do not rename CostUsage / CostRecord /
DailyStats fields, the CostLogger method signatures, the
DailyCapExceeded exception, or the redis key schema documented in the
module docstring.

## Concrete deliverables

1. backend/app/services/cost_logger.py — implement bodies.

   CostLogger.__init__:
   - Store the redis client + the six per-million USD rates + the cap +
     session_ttl_seconds on self. Tighten the redis annotation from
     `object` to `redis.asyncio.Redis`.

   CostLogger.record(session_id, usage, *, now=None):
   - Compute `usd = compute_usd(usage, **rates)`.
   - Resolve `day = (now or datetime.now(UTC)).date()`.
   - One redis pipeline that issues, in order:
       HINCRBY session:{sid}:cost audio_input_tokens N
       HINCRBY session:{sid}:cost text_input_tokens N
       HINCRBY session:{sid}:cost cached_audio_input_tokens N
       HINCRBY session:{sid}:cost cached_text_input_tokens N
       HINCRBY session:{sid}:cost text_output_tokens N
       HINCRBY session:{sid}:cost audio_output_tokens N
       HINCRBYFLOAT session:{sid}:cost usd <usd>
       HSET session:{sid}:cost updated_at <iso>
       EXPIRE session:{sid}:cost (session_ttl_seconds + 600)
       (same six HINCRBYs + HINCRBYFLOAT against cost:daily:<YYYY-MM-DD>)
       EXPIRE cost:daily:<YYYY-MM-DD> 172800
       SADD cost:daily:<YYYY-MM-DD>:sessions <session_id>
       EXPIRE cost:daily:<YYYY-MM-DD>:sessions 172800
   - If SADD returned 1, issue a second pipeline with one HINCRBY
     `cost:daily:<YYYY-MM-DD> sessions 1`.
   - Return `CostRecord(session_id, usage, usd, day, now or
     datetime.now(UTC))`.

   CostLogger.session_cost(session_id):
   - HGETALL session:{sid}:cost. If empty, return None.
   - Rebuild CostUsage from the six token fields (default 0 each),
     CostRecord with usd from the `usd` field (parse float), recorded_at
     from `updated_at`. total_tokens = sum of the six token fields
     (the redis hash does not store total_tokens separately).
   - Day = recorded_at.date() (UTC).

   CostLogger.daily(day=None):
   - day defaults to today UTC. HGETALL cost:daily:<YYYY-MM-DD>.
   - Return DailyStats with all fields zero-filled when the hash is
     empty (so /v1/stats can be called before any session).

   enforce_daily_cap(cost_logger, *, cap_usd, now=None):
   - If cap_usd <= 0, return immediately.
   - Call `await cost_logger.daily(day=(now or now()).date())`.
   - If usd >= cap_usd, raise `DailyCapExceeded(current_usd=usd,
     cap_usd=cap_usd)`. Strictly `>=`, not `>`.

2. backend/app/api/sessions.py — wire it in.

   - Add a FastAPI dependency `get_cost_logger(redis: Redis = Depends(
     get_redis), settings: Settings = Depends(get_settings))` that
     constructs a CostLogger with all six rates + cap. Keep get_settings
     lru_cached as today.
   - In `create_session`, before allocating session_id:
       try:
           await enforce_daily_cap(cost_logger, cap_usd=settings.daily_usd_cap)
       except DailyCapExceeded as e:
           return JSONResponse(
               status_code=429,
               content=ApiFail(success=False, error=ApiError(
                   code="daily_cap_exceeded",
                   message=str(e),
               )).model_dump(),
           )
     (Use the existing ApiFail model. Update the response_model and the
     200 responses dict if needed to allow returning JSONResponse.)
   - In the WS handler `session_stream`, after the `if delta.final:`
     branch builds the translation.final payload and BEFORE breaking,
     call `await cost_logger.record(session_id, delta.usage)` IF
     `delta.usage is not None`. Do not raise if it is None (legacy
     fallback path). Pass the same cost_logger instance injected via
     Depends() (use `websocket.app.dependency_overrides` only if
     needed — prefer constructing it once per session from get_redis +
     get_settings inside the handler, matching the existing redis
     Depends pattern).

3. backend/app/api/stats.py — new router.

   - `GET /v1/stats?days=1` (int, default 1, max 2). Returns
     `{success: true, data: {days: [DailyStats, ...]}}` newest first.
     For days=1 the list has length 1; days=2 returns today + yesterday.
   - Use the same CostLogger dependency.
   - Pydantic response model. No new Pydantic v2 features beyond what
     sessions.py already uses.
   - Register the router in backend/app/main.py next to the other
     routers.

4. backend/tests/test_cost_logger.py — new pytest file.

   - Unit test for `compute_usd`: cover (a) all-non-cached input, (b)
     all-cached input (audio + text), (c) mixed cached/non-cached audio,
     (d) zero usage → 0 USD. Hand-compute expected values from the
     defaults in Settings.
   - Unit test for CostLogger.record(): inject a fake redis (in-memory
     dict-of-dicts is fine; mirror the FakeRedis pattern from
     test_sessions.py and extend it with hincrby / hincrbyfloat / sadd
     / pipeline()). Assert the six token HINCRBYs hit both the session
     hash and the daily hash; assert SADD-first-touch increments
     `sessions` exactly once across two record() calls with the same
     session_id.
   - Unit test for daily() returns zero-DailyStats when the bucket
     is absent.
   - Unit test for enforce_daily_cap: pre-seed daily hash usd, assert
     raises DailyCapExceeded with correct current_usd / cap_usd.

5. backend/tests/test_sessions.py — extend.

   - Use the extended FakeRedis from #4 so the WS happy-path test now
     also asserts that record() was called with the FakeTranslator's
     yielded usage. (FakeTranslator currently does not yield usage;
     update it to yield TextDelta(text="", final=True,
     usage=CostUsage(audio_input_tokens=10, text_input_tokens=46,
     cached_audio_input_tokens=0, cached_text_input_tokens=0,
     text_output_tokens=5, audio_output_tokens=0, total_tokens=61)) so
     the assertion has values.)
   - Add a new test_create_session_blocked_by_cap that monkeypatches
     `get_settings` to return daily_usd_cap=0.0001 and pre-seeds
     cost:daily:<today> usd=0.001, asserts 429 + code=daily_cap_exceeded.
   - Note: the existing test_ws_happy_path is failing on main with a
     fixture bug (sampleRateHz=16000 vs schema const 24000). Fix that
     fixture as part of this PR while you are in the file.

6. backend/tests/test_stats.py — new.

   - GET /v1/stats?days=1 with no traffic → success=True,
     data.days has 1 entry, usd=0.
   - After a record() call (using the same fake-redis pattern), days[0]
     reflects the recorded counts and USD.
   - days=3 → 422 (validation rejects out-of-range int).

## Hard constraints (always apply)

- Branch from main: feat/s1-day-8-cost-logger
- NEVER push to main. NEVER force-push. NEVER add Co-Authored-By
  trailers (hard rule for this repo).
- Conventional commit subject: `feat(backend): S1 Day 8 cost logging + daily cap`
- Do not add dependencies. The locked stub uses only stdlib + redis +
  pydantic + fastapi which are already present. If you find a need,
  STOP and ask.
- Do not modify firmware/, mobile/, .claude/, infra/ec2/, docs/.
  Backend + its tests + docs/codex/S1_TASKS.md (close your rows) only.
- Do not change the field names, method signatures, exception class, or
  the redis key schema documented in cost_logger.py. The probe sessions
  on EC2 fed those decisions; rewriting them invalidates Claude's
  pricing reconciliation work.
- Privacy boundary (from backend/CLAUDE.md): never log audio bytes,
  translated text, source transcripts, OpenAI tokens, or API keys.
  Counts and USD only, USD at DEBUG, session_id only when
  `settings.app_env == "dev"`. The translator's per-utterance
  `realtime.usage` INFO line is the established style — match it.

## Verification

cd backend
.venv/Scripts/python.exe -m pytest tests/ --no-header -q
# expect: all green, NO deselected. (Day 8 fixes the preexisting
# test_ws_happy_path_relays_translation 16k sample-rate bug.)

# end-to-end with running stack
docker compose up -d --build
curl -s http://localhost:8000/v1/stats?days=1 | jq
# expect: success=true, data.days[0].usd=0, all token counts 0

# fire one session from the mobile app (or a synthetic test you choose),
# then:
docker compose exec redis redis-cli HGETALL session:<id>:cost
docker compose exec redis redis-cli HGETALL cost:daily:$(date -u +%Y-%m-%d)
curl -s http://localhost:8000/v1/stats?days=1 | jq

# expect: six token fields + usd + updated_at present on the session
# hash, daily hash totals match, /v1/stats reflects the same numbers.

# cap test (transient)
DAILY_USD_CAP=0.0001 docker compose up -d --build api
# pre-seed daily bucket so cap is breached:
docker compose exec redis redis-cli HINCRBYFLOAT cost:daily:$(date -u +%Y-%m-%d) usd 0.001
curl -s -X POST http://localhost:8000/v1/sessions -H 'Content-Type: application/json' -d '{}' -o /tmp/r.json -w '%{http_code}\n'
cat /tmp/r.json | jq
# expect: 429, code="daily_cap_exceeded"

# reset cap after testing
docker compose exec redis redis-cli DEL cost:daily:$(date -u +%Y-%m-%d)

## PR description template

## Summary
<one paragraph: cost logger + cap + /v1/stats wired up>

## Files added / modified
<bullet list>

## Verification output
<paste raw command output for every command above, one block per command>

## Open questions for review
<things you decided without explicit guidance>
- Did the CostLogger dependency end up scoped per-request or per-app?
  Either is acceptable as long as redis is pooled.
- Any pricing edge case (e.g. negative cached delta) you noticed?

## Time spent
~X hours

After opening the PR, post the URL and STOP. Do not start Day 9.
```

---

## 2j. Day 9 (Codex rows) — End-to-end latency suite (ready to copy)

**Precondition**: Day 9 prep is on `main`. `E2eLatencyRecord` dataclass +
`E2eLatencyStats` dataclass + `LatencyLogger.e2e*` method signatures
are locked in `mobile/lib/services/latency_logger.dart` (all bodies
throw `UnimplementedError`). `tools/latency_report.py` ships the
`--s1` flag dispatch + `S1_TARGET_TOTAL_MS` + `S1_STAGES` constants;
`render_s1_markdown()` is a `NotImplementedError` stub with the output
spec in the block comment above it.

Codex job: fill the `UnimplementedError` bodies in `latency_logger.dart`,
add the 10-phrase catalog, wire the S1-Run-10 button into
`TranslateScreen`, implement `render_s1_markdown()`, and add tests on
both sides. **Do not change the locked contract** — `E2eLatencyRecord`
field names, `LatencyLogger.e2e*` method signatures, CSV header, and
`S1_STAGES` shape are frozen.

```
Your task: S1 Day 9 — end-to-end latency suite. Implement the rows
marked "Codex" in the Day 9 table of docs/codex/S1_TASKS.md. The
interfaces in mobile/lib/services/latency_logger.dart and
tools/latency_report.py are LOCKED — fill the UnimplementedError /
NotImplementedError bodies, do not rename E2eLatencyRecord /
E2eLatencyStats fields or LatencyLogger.e2e* method signatures, the
CSV header, or the S1_STAGES list.

## Concrete deliverables

1. mobile/lib/services/latency_logger.dart — fill bodies for the e2e
   methods.

   State model:
   - `_activeTrace` (an `_E2eTrace`) holds the in-progress utterance.
     A new `e2eStart` discards any prior unfinalised trace by
     finalising it with `errorCode='discarded'` first (so no data is
     lost; the operator sees the discard in the CSV).
   - All `e2eMark*` methods are no-ops when `_activeTrace == null`.
   - `e2eMarkSessionOpened` stores both `sessionOpenedTsMicros` and
     `sessionId` on the trace.
   - `e2eMarkBleAck` stores both `bleAckTsMicros` and `bleSequenceId`.
   - `e2eAbort('code')` sets `errorCode` then calls the same
     finalisation path used by `e2eFinalize` so the row still lands
     in `_e2eRecords`.
   - `e2eFinalize` computes `(ts - pressTsMicros) / 1000` rounded to
     nearest int for each delta. `audioMs` defaults to 0 when
     `releaseTsMicros` is null. `totalMs` = `bleAckMs` (null when
     bleAckMs is null).
   - `toE2eCsv` emits `E2eLatencyRecord.csvHeader` then one
     `toCsvRow()` per record, newline-terminated. Match the existing
     `toCsv` style.
   - `summariseE2e` filters by `isOk`, sorts by `totalMs`, returns
     `E2eLatencyStats` with p50/p90/p95/p99 via the same percentile
     formula `LatencyStats.summarise` uses (`((n-1)*p).round()`
     index).
   - `clearE2e` empties `_e2eRecords` and sets `_activeTrace=null`.
     Phase F state (`_records`, `_pending`) untouched.

   Privacy: never store or log the spoken text or any audio bytes
   in the trace. Only ids, counts, and timestamps.

2. mobile/lib/data/s1_phrases.dart — new file.

   ```dart
   class S1Phrase {
     const S1Phrase({required this.id, required this.text});
     final String id;   // kebab-case, unique
     final String text; // Japanese prompt the user reads
   }

   const List<S1Phrase> s1Phrases = <S1Phrase>[
     S1Phrase(id: 'greeting-01', text: 'おはようございます'),
     // ...9 more, 5-10 chars each, varied (greetings, weather,
     //   directions, food, time, numbers). No personal info, no
     //   long sentences — keep under ~10 chars so PTT is short and
     //   STT latency dominated by system overhead not audio length.
   ];
   ```

   Picks must be ids without collisions. Text must be plain JP, no
   emoji.

3. mobile/lib/screens/translate_screen.dart — add the runner.

   - One new IconButton or row of buttons near the existing PTT
     control:
       * "S1 Run 10" — starts the catalog loop
       * "Copy E2E CSV" — copies `logger.toE2eCsv()` to the
         clipboard (mirror the existing Copy CSV behaviour)
       * "Clear E2E" — `logger.clearE2e()` + on-screen log line
   - Runner state machine:
       For each phrase in s1Phrases:
         (a) Show the phrase text in a banner / overlay so the user
             reads it.
         (b) Wait up to 30 s for one full PTT cycle. If the user
             presses, the existing PTT flow fires; the runner is
             passive once PTT starts.
         (c) On PTT press, call `logger.e2eStart(phrase.id)`.
         (d) On PTT release, call `logger.e2eMarkPttRelease()`.
         (e) On `session.opened` in the WS callback, call
             `logger.e2eMarkSessionOpened(sessionId)`.
         (f) On first `translation.partial`, call
             `logger.e2eMarkFirstText()`.
         (g) On `translation.final`, call
             `logger.e2eMarkTranslationFinal()`.
         (h) On BLE ACK with `status==0x01`, call
             `logger.e2eMarkBleAck(sequenceId)` then
             `logger.e2eFinalize()`.
         (i) Wait 1.5 s for OLED clear, advance to next phrase.
       If 30 s elapses without a release, call
       `logger.e2eAbort('timeout')` and advance.
   - Do not break the existing single-press PTT flow. The S1 runner
     is additive: it just feeds phrase ids into the same hooks.

4. tools/latency_report.py — implement `render_s1_markdown()`.

   Follow the in-file spec block. Output sections in this exact
   order: title + target line, "Stacked-bar by stage (median ms)"
   table (one row per phrase id + a median row), "Overall total_ms"
   table, "Per-stage percentiles" table, verdict, failures (only if
   any). Excluded rows: any with non-empty `error` column or with
   missing required ms columns for the stage being computed.
   Clamp negative stage durations to 0 in display; if any
   appeared, add a "Clock skew: N rows had negative stage deltas"
   footer.

5. tools/test_latency_report.py — new pytest file (project root
   pytest is already configured; this lives in tools/ and runs via
   `python -m pytest tools/`).

   - `test_s1_render_happy_path`: 3-row fixture, asserts the output
     contains the verdict line "GO" and the right p95 number.
   - `test_s1_render_failure_section`: include 1 row with
     `error=ws_error`; assert "Failures" header appears and the
     row is excluded from percentiles.
   - `test_s1_render_clock_skew_footer`: include 1 row with
     `backend_ack_ms < audio_ms`; assert the footer is emitted.

6. mobile/test/latency_logger_test.dart — add e2e tests.

   - happy path: press → release → sessionOpened → firstText →
     final → bleAck → finalize → assert record fields populated.
   - abort path: start → abort('timeout') → finalize returns the
     aborted record with errorCode='timeout'.
   - discard on overlapping start: start('a') → start('b') (no
     finalize between) → assert `_e2eRecords` has the 'a' record
     with errorCode='discarded'.
   - markBleAck without active trace is a no-op.
   - clearE2e leaves Phase F records intact.

## Hard constraints (always apply)

- Branch from main: `feat/s1-day-9-latency-suite`.
- NEVER push to main. NEVER force-push. NEVER add Co-Authored-By
  trailers.
- Conventional commit subject: `feat(mobile): S1 Day 9 end-to-end latency suite`.
- Do not add dependencies in mobile or tools. Stdlib + flutter
  built-ins only. Clipboard already used via `services.dart`
  (`Clipboard.setData`).
- Do not change `E2eLatencyRecord.csvHeader`, the field names, or
  the `S1_STAGES` shape. The downstream report consumes the CSV
  by column name.
- Do not modify firmware/, backend/, infra/ec2/, .claude/, docs/
  (except `docs/codex/S1_TASKS.md` to mark your rows DONE).
- Privacy: never write the spoken prompt text into the CSV or any
  log line. The phrase_id is the only reference; the report tool
  joins back to the catalog if needed.
- Match the existing latency_logger.dart style: `microsecondsSinceEpoch`
  for clocks, `round()` for ms conversion, `List.unmodifiable` for
  the public records getter.

## Verification

cd mobile
flutter test test/latency_logger_test.dart
# expect: green, including the 5 new e2e cases

flutter test
# expect: all tests green (no regressions)

cd ../
python -m pytest tools/
# expect: tools/test_latency_report.py 3/3 green

# On device:
flutter run
# tap "S1 Run 10", read 10 prompts one by one. Tap "Copy E2E CSV"
# and paste the 10-row CSV into the PR description verification
# output. Capture a screenshot of the runner banner if practical.

python tools/latency_report.py --s1 the_pasted.csv > /tmp/r.md
# expect: markdown with stacked-bar table, verdict line, no
#         python tracebacks

## PR description template

## Summary
<one paragraph: e2e logger + runner + report wired end-to-end>

## Files added / modified
<bullet list>

## Verification output
<paste raw command output, one block per command, plus the 10-row
CSV from the device run>

## Open questions for review
<things you decided without explicit guidance>
- Catalog text: which 10 phrases did you choose, and how long
  is each in characters?
- Did the 30 s per-phrase timeout fire on any phrase during
  your manual run? (If yes, list which.)

## Time spent
~X hours

After opening the PR, post the URL and STOP. Do not start Day 10.
```

---

## 2k. Day 10 (Codex row) — Root README (ready to copy)

**Precondition**: S1 sprint closed with GO verdict (commit `5c30385`).
Day 9 report doc at `docs/reports/S1_Day9_report.md`. No root
`README.md` exists yet — this is a new-file task. The audience is a
future contributor (or future-Tri) landing on the GitHub repo for the
first time; the README is the entry point, not a comprehensive doc.

Codex job: create `README.md` at repo root, ~150-250 lines. Reuse the
high-level facts from `CLAUDE.md` (Project Overview, MVP architecture,
locked technical decisions) but rewrite for an external reader — no
Vietnamese mixed in the doc, English only since it is the
public-facing surface. Link out to the existing detailed docs rather
than duplicating them.

```
Your task: S1 Day 10 — create the root README.md. This is the only
Codex row in Day 10 (see docs/codex/S1_TASKS.md). It is a single new
file at the repo root, no other files touched.

## Concrete deliverables

1. README.md at the repo root (new file). Sections in this order:

   ### Header
   - Project name: "LingoGlass AR"
   - One-line tagline in English describing the product (real-time
     subtitle + translation eyewear for travel & multilingual
     communication).
   - Status badges (optional, only if you can write them without
     adding GitHub Actions config): replace with a plain line
     "Status: S1 sprint complete — see docs/reports/S1_Day9_report.md".

   ### Architecture (high-level)
   - One ASCII diagram showing the data flow:
       Phone (Flutter) -> Backend (FastAPI on AWS Osaka) ->
       OpenAI Realtime API -> Backend -> Phone (BLE central) ->
       ESP32-S3 (BLE peripheral) -> SSD1306 OLED
   - 3-5 sentences describing what runs where. Pull from
     CLAUDE.md "Project Overview" section. Mention:
       * Phone records audio (PCM16 24 kHz mono)
       * Backend bridges to OpenAI Realtime for STT + translation
       * Translated text goes back over WS, then via BLE to the
         ESP32-S3 controller
       * OLED renders the subtitle
   - Note the latency budget: p95 system_latency ≤ 2500 ms
     (measured 1493 ms on 2026-05-22, see Day 9 report).

   ### Repository layout
   - One-line description for each top-level directory:
       mobile/      Flutter app (Android + iOS)
       backend/     FastAPI service + WS bridge to OpenAI Realtime
       firmware/    ESP32-S3 ESP-IDF / PlatformIO firmware
       infra/       EC2 bootstrap + deploy scripts
       docs/        Architecture, API contract, runbooks, reports
       tools/       CSV report renderers (Phase F + S1)
       tests/       BLE protocol vectors (Dart + C++ shared)

   ### Quick start
   - Three subsections, one per component. Each shows the minimum
     commands a fresh clone needs to get the thing running. Pull
     command strings verbatim from the existing CLAUDE.md files
     (root, mobile/CLAUDE.md, backend/CLAUDE.md) — do not invent
     new commands.

     #### Backend (local docker)
     ```bash
     cd backend
     cp .env.example .env  # add OPENAI_API_KEY
     docker compose up
     # http://localhost:8000/healthz -> {"status":"ok",...}
     ```

     #### Mobile (Flutter)
     ```powershell
     cd mobile
     flutter pub get
     flutter test       # 33/33 tests
     flutter run        # device required
     ```

     #### Firmware (ESP32-S3)
     ```bash
     cd firmware/esp32s3
     pio run -t upload  # PlatformIO; ESPr Developer S3 + SSD1306
     ```

   ### Key technical decisions
   - Bullet list from CLAUDE.md "Quyết định kỹ thuật đã được lock"
     section, translated to English:
       * Audio source: phone mic (NOT a mic on the eyewear)
       * Camera (OCR future S3): phone camera
       * Subtitle transport: BLE first, Wi-Fi fallback only for debug
       * Controller: ESP32-S3 (ESP-IDF / Arduino)
       * Backend: FastAPI + WebSockets, no Kubernetes
       * Privacy LED: physical hardware LED required (S2+), not just
         an on-OLED icon

   ### Sprint progress
   - A small table:
     | Sprint | Status | Highlights |
     | ------ | ------ | ---------- |
     | S0     | DONE 2026-05-18 | BLE + OLED spike, MTU 23/185/247 verified |
     | S1     | DONE 2026-05-22 | Audio + WS + OpenAI Realtime + cost cap + e2e latency 1493ms p95 |
     | S2     | starting       | STT optimisation, Cloudflare Full(Strict), UX polish |
   - One sentence linking to docs/reports/S1_Day9_report.md.

   ### Documentation map
   - Bullet list with one-line descriptions:
       docs/LingoGlass_AR_Project_Plan.md — product spec, BOM, roadmap
       docs/LingoGlass_AR_Strategic_Analysis.md — market analysis
       docs/LingoGlass_AR_Development_Plan.md — V-model dev plan
       docs/api-contract/ — WS schema + samples + OpenAPI
       docs/codex/ — Codex briefing + per-day task table + prompts
       docs/runbook/ — AWS deploy runbook
       docs/reports/ — sprint reports
       docs/nippo/ — daily Japanese work reports
       CLAUDE.md (root) — high-level Claude Code rules for this repo
       mobile/CLAUDE.md, backend/CLAUDE.md, firmware/CLAUDE.md
         — per-component rules

   ### License
   - Just a placeholder: "All rights reserved. Contact: <email>".
     Do not add an OSS license, the project is private/founder-stage.

## Hard constraints

- Branch from main: feat/s1-day-10-readme
- NEVER push to main. NEVER force-push. NEVER add Co-Authored-By
  trailers (see [[feedback-no-claude-coauthor]] equivalent in this
  repo's commit history — search `git log --format=%B HEAD~20..HEAD
  | grep -i co-author` should return zero hits).
- Conventional commit subject: `docs: add root README with
  architecture + quick start`
- Single file change: README.md at repo root. Do not touch any
  other file. If you find a typo elsewhere, leave it.
- Do not add badges that link to services we have not configured
  (no codecov, no build badges from non-existent CI). Plain text
  status line only.
- ASCII diagrams only, no Mermaid blocks. The README must render
  cleanly on GitHub without enabling any extensions.
- No emoji.
- Length budget: 150-250 lines. If your draft exceeds 250 lines,
  trim by moving detail into linked docs.

## Verification

- Open `README.md` in a markdown previewer (VS Code Ctrl+Shift+V) and
  visually verify all sections render.
- `git diff --stat main..HEAD` should show exactly one file added.
- Run `wc -l README.md` and confirm 150 ≤ lines ≤ 250.
- `grep -i "co-author" $(git log --format=%H main..HEAD | xargs -I {} git
  show --format=%B {} -s)` returns nothing.

## PR description template

## Summary
<one paragraph: README created at repo root, links to existing docs,
no other files touched>

## Files added / modified
- README.md (new, NNN lines)

## Verification output
<paste `git diff --stat`, `wc -l README.md`, and a small excerpt of the
rendered preview if you can capture it>

## Open questions for review
<things you decided without explicit guidance>
- Tagline phrasing (you may have picked your own English wording)
- Whether to include the architecture ASCII diagram inline or punt
  to docs/

## Time spent
~X hours

After opening the PR, post the URL and STOP. Do not tag any release —
that is a Claude row.
```

---

## 3. Day-N task prompt — TEMPLATE (use for Day 8-10)

Replace `<N>` with the day number, fill `<TASK_TITLE>`, `<COMMIT_SUBJECT>`,
`<DELIVERABLES>`, `<VERIFICATION>` from `docs/codex/S1_TASKS.md`.

```
Your task: S1 Day <N> — <TASK_TITLE>. Implement only the rows marked
"Codex" in the Day <N> table of docs/codex/S1_TASKS.md. Skip "Claude" rows.

## Concrete deliverables (your rows)

<DELIVERABLES — paste the row contents verbatim from S1_TASKS.md>

## Hard constraints (always apply)

- Branch from main: feat/s1-day-<N>-<slug>
- NEVER push to main. NEVER force-push. NEVER add Co-Authored-By trailers.
- Conventional commit subject: <COMMIT_SUBJECT>
- Do not add dependencies not enumerated in the briefing or this prompt
  without asking first.
- Do not modify firmware/ or BLE protocol files (mobile/lib/ble/ble_protocol.dart,
  tests/ble_vectors.json, .claude/skills/ble-protocol/SKILL.md). Those are
  Claude-only territory per docs/codex/S1_TASKS.md.
- Do not touch platformio.ini or firmware/CLAUDE.md.

## Verification

<VERIFICATION — paste from S1_TASKS.md "Verify" column>

Run all verification commands. Paste raw output (not summary) into the
PR description.

## PR description template

## Summary
<one paragraph: what changed and why>

## Files added / modified
<bullet list>

## Verification output
<paste raw command output, one block per command>

## Open questions for review
<things you decided without explicit guidance>

## Time spent
~X hours

After opening the PR, post the URL here and STOP. Do not start the next day.
```

---

## 2l. S2 Day 2 (Codex row) — STT tuning gpt-realtime-whisper + delay=low (ready to copy)

**Tag**: implement bodies only. Do NOT add new public fields, rename the
`STTConfig` dataclass, or extend `Translator.__init__` beyond what
already exists. The contract surface is locked by Claude prep — your
job is the JSON payload wiring + tests.

**Precondition**: Claude prep landed on `main` at commit
`<paste from git log -1>`. That commit added `STTConfig`,
`DEFAULT_STT_CONFIG`, `TranscriptionDelay`, and the
`stt_config: STTConfig | None = None` parameter to
`Translator.__init__`. The body of `Translator.connect()` still sends
the S1 payload (whisper-1, no delay, default server_vad, duplicate
instructions in `response.create`). Your PR flips the body to the
S2 Day 1 probe target. Background in `docs/reports/S2_stt_probe.md`.

**Hypothesis** (Day 3 will measure): median `stt_ms` drops from
884 ms (S1) to ≤ 600 ms (S2 exit criterion #1).

```
Your task: S2 Day 2 — wire the locked STTConfig into the
session.update payload and trim two dead code paths. Single backend PR.

## Concrete deliverables

1. backend/app/services/translator.py — modify Translator.connect() ONLY:

   a. In the `session.update` payload sent on connect, replace the
      `audio.input.transcription` block:

         BEFORE:
            "transcription": {"model": "whisper-1"}

         AFTER:
            "transcription": {
              "model": self._stt_config.transcription_model,
              "delay": self._stt_config.transcription_delay,
            }

      Both fields come from self._stt_config (already stored by the
      __init__ change in Claude prep).

   b. Add "turn_detection": None INSIDE the "audio.input" object,
      right after the "transcription" block. The correct GA nesting is
      session.audio.input.turn_detection, not session.turn_detection
      at the top level — the latter was rejected by live GA smoke on
      2026-05-23 with "Unknown parameter: 'session.turn_detection'".
      Final shape of the audio.input block:

         "audio": {
           "input": {
             "format": {"type": "audio/pcm", "rate": 24000},
             "transcription": {
               "model": self._stt_config.transcription_model,
               "delay": self._stt_config.transcription_delay,
             },
             "turn_detection": None,
           }
         }

      This explicitly disables server VAD; we manually
      `input_audio_buffer.commit` and the server-side VAD inference is
      dead work in PTT mode.

   c. In Translator.translate_stream(), the `response.create` payload
      currently has both "output_modalities" and "instructions". DROP
      the "instructions" field. The instructions are already set in
      session.update; duplicating them in response.create costs
      tokenisation on every utterance (~50 ms). Keep
      "output_modalities".

   Do NOT change anything else in connect() or translate_stream() —
   no event-handler edits, no new fields, no docstring rewrites
   (Claude's docstring already describes the new behaviour).

2. backend/tests/test_translator.py — add or extend coverage:

   a. Existing test `test_translate_stream_emits_text_deltas_in_order`
      (or whatever it is called locally) must still pass with no
      change to its assertions. The FakeWebSocket only inspects sent
      events by type, so the payload edits should be transparent. If
      it breaks, your change is wrong — investigate before patching
      the test.

   b. New test `test_session_update_uses_stt_config_defaults`:
      instantiate `Translator(api_key="x")` with the default
      STTConfig, drive `__aenter__()` against a FakeWebSocket, then
      assert the FIRST sent payload is a session.update with:
        - session.audio.input.transcription.model == "gpt-realtime-whisper"
        - session.audio.input.transcription.delay == "low"
        - session.audio.input.turn_detection is None
          (the key MUST be present with a None/null value, not absent —
          omitting it would leave default server_vad enabled).
        - session.turn_detection key is NOT present at the top level
          (live GA rejects it as Unknown parameter).

   c. New test `test_session_update_honours_custom_stt_config`:
      instantiate `Translator(api_key="x",
      stt_config=STTConfig(transcription_delay="minimal"))`, drive
      __aenter__, assert the session.update has delay == "minimal".

   d. New test `test_response_create_omits_instructions`: drive a
      full translate_stream through a FakeWebSocket and assert the
      `response.create` payload sent contains "output_modalities" but
      NO "instructions" key.

3. Do NOT add a new dependency. Do NOT touch cost_logger.py,
   sessions.py, mobile/, firmware/, infra/, or docs/. The PR is
   strictly backend Translator + its test file.

## Smoke findings (already resolved 2026-05-23, log in PR body)

The S2 Day 1 probe (`docs/reports/S2_stt_probe.md` §7) flagged three
unknowns. Live smoke against `gpt-realtime-whisper` on 2026-05-23
resolved them. Quote these findings verbatim in the PR's "Open
questions for review" section:

A. **`turn_detection` location**: `session.turn_detection` (top level)
   is REJECTED by GA with `Unknown parameter: 'session.turn_detection'`.
   The correct nesting is `session.audio.input.turn_detection`. The
   payload spec in §1.b above already reflects this fix.

B. **Source transcript event**: `gpt-realtime-whisper` STILL emits
   `conversation.item.input_audio_transcription.completed` with a
   string `.transcript` field. No event-handler change needed;
   `TextDelta.source_text` capture path keeps working untouched.

C. **Usage shape**: `response.done.usage` still has the existing
   keys (`input_token_details.audio_tokens`,
   `input_token_details.text_tokens`,
   `input_token_details.cached_tokens_details`,
   `output_token_details.text_tokens`, etc.). The cost_logger reads
   the same fields, so no cost_logger change is needed in THIS PR.
   Pricing: OpenAI pricing page does not list a separate row for
   `gpt-realtime-whisper` (as of 2026-05-23); pricing constants
   follow-up is a separate Claude-prep task — do NOT touch
   cost_logger.py here.

If a fresh smoke contradicts any of A/B/C while you implement, STOP
and report — Claude will re-prep.

## Branch / commit / PR

- Branch: `feat/s2-day-2-stt-tuning`
- Commit subject: `feat(backend): S2 Day 2 STT tuning gpt-realtime-whisper + delay=low`
- PR title: same as commit subject
- No `Co-Authored-By: Claude/OpenAI` trailer (hard rule, see
  `docs/codex/S1_TASKS.md` "How Codex receives a task" §6).

## Verification commands to paste raw output for

  cd backend
  ../backend/.venv/Scripts/python.exe -m pytest tests/test_translator.py -v

Must show all tests pass (existing + 3 new). Paste the full pytest
output, not a summary.

## What this PR explicitly does NOT do

- It does NOT change the cost logger pricing constants.
- It does NOT touch mobile/, firmware/, or infra/.
- It does NOT update `docs/reports/S2_stt_probe.md` (Claude's doc).
- It does NOT add the Day 3 device bench (that is a Claude row).
- It does NOT introduce any new module.

After opening the PR, post the URL here and STOP. Do not start Day 3.
```

---

## 2m. S2 Day 4 (Codex row) — PTT cooldown + warnings UX (ready to copy)

**Tag**: implement bodies only. Do NOT change the locked tunables
(`_kPostFinalizeCooldown`, `_kShortPressMin`), do NOT rename
`_isInCooldown` / `_isShortPress` / `_showShortPressWarning` /
`_showDiscardBanner` / `_startPostFinalizeCooldown`, do NOT touch
`_PttState` enum, do NOT touch `LatencyLogger.e2eStart` signature.
The state-machine wiring is already done by Claude prep — your job is
the short-press time comparison + the two SnackBar bodies + widget
tests.

**Precondition**: Claude prep landed on `main` at commit
`<paste from git log -1>`. That commit:

- added `_kPostFinalizeCooldown` (500 ms) + `_kShortPressMin` (100 ms)
  as file-level constants in `mobile/lib/screens/translate_screen.dart`,
- added `_cooldownTimer` + `_pressDownTsMicros` state fields,
- implemented `_isInCooldown()` and `_startPostFinalizeCooldown()`
  in full (cooldown timer logic, no UI),
- wired `_isShortPress()` into `_onPressUp` as the FIRST check before
  any state mutation; the stub currently returns `false`,
- wired `_showShortPressWarning()` and `_showDiscardBanner()` call
  sites in `_onPressUp` and `_onPressDown`; both stubs are no-ops,
- changed `LatencyLogger.e2eStart` to return `E2eLatencyRecord?` so
  the discard banner has the discarded row to render,
- added 2 unit tests in `mobile/test/latency_logger_test.dart`
  covering the new return value (null on first call, non-null on
  back-to-back).

Background: S2 Day 9 retro of S1 showed retry rate ~50 % driven by the
PTT double-press pattern. The three behaviours are spec'd in
`docs/codex/S2_TASKS.md` Day 4 row.

```
Your task: S2 Day 4 — flip the short-press detection ON and fill the
two SnackBar bodies. Single mobile PR.

## Concrete deliverables

1. mobile/lib/screens/translate_screen.dart — three method bodies ONLY:

   a. `_isShortPress()` — replace the stub with:

        final pressed = _pressDownTsMicros;
        if (pressed == null) return false;
        final heldMicros =
            DateTime.now().microsecondsSinceEpoch - pressed;
        return heldMicros < _kShortPressMin.inMicroseconds;

      Do NOT change the signature or the early-null behaviour.

   b. `_showShortPressWarning()` — fill the body. Show a SnackBar via
      `ScaffoldMessenger.of(context)` with:

        - content: Text('Hold longer to record')
        - duration: Duration(milliseconds: 1500)
        - behavior: SnackBarBehavior.floating

      Guard on `mounted` before touching `ScaffoldMessenger`. Use
      `hideCurrentSnackBar()` before `showSnackBar()` so a quick burst
      of accidental taps does not pile up.

   c. `_showDiscardBanner(E2eLatencyRecord discarded)` — fill the
      body. Show a SnackBar with content
      `Text('Previous attempt (${discarded.phraseId}) discarded')`,
      duration 2 s, floating, same `mounted` + `hideCurrentSnackBar`
      pattern. Use the standard MaterialBanner only if you have a
      strong reason — SnackBar is preferred because it auto-dismisses.

   Do NOT touch any other method body, any state field, the build
   tree, the `_PttState` enum, or anything in `lib/ble/` /
   `lib/services/` / `lib/audio/`.

2. mobile/test/translate_screen_test.dart — NEW widget test file.
   Three test groups (one per behaviour):

   a. group 'cooldown blocks fast re-press' — pump the widget, fire a
      complete press/release cycle that drives the trace through to
      `_teardownPtt`, then fire a second press within 100 ms. Assert
      that the second press's `e2eStart` was NOT called (use a fake
      `LatencyLogger` or wrap with a key + tap counter on the press
      area). Acceptance: log line includes 'PTT cooldown'.

   b. group 'short press is rejected' — pump the widget, drive a
      press-down then release after < 100 ms. Assert that the
      `short_press` SnackBar text is in the tree, and `e2eAbort`
      received `'short_press'`. The trace must NOT contain
      `audioMs > 0`.

   c. group 'back-to-back discard shows banner' — pump the widget,
      seed `LatencyLogger` with an in-progress trace (call
      `e2eStart('a')` directly), then drive a fresh press. Assert
      the SnackBar text includes the discarded phraseId 'a'.

   The existing `mobile/test/widget_test.dart` may need adjustment if
   it tries to instantiate `TranslateScreen` directly — leave it
   alone if it does not import the screen.

3. Do NOT add new dependencies. Use `flutter_test` only.

## Verification commands to paste raw output for

- `cd mobile && flutter analyze --no-pub` — must show 0 issues.
- `cd mobile && flutter test test/translate_screen_test.dart` —
  must show all green.
- `cd mobile && flutter test test/latency_logger_test.dart` —
  must still show all green (regression check).

## Branch / commit / PR

Branch: `feat/s2-day-4-ptt-cooldown-ux`. Commit subject:
`feat(mobile): S2 Day 4 PTT cooldown + warnings`. PR title same.
Squash-merge.

## What this PR explicitly does NOT do

- It does NOT change the cooldown duration or short-press threshold
  (those are tunables Claude owns).
- It does NOT touch `LatencyLogger` or any service.
- It does NOT add a `provider` / `riverpod` / state-management package.
- It does NOT renumber the `_PttState` enum or add new states.
- It does NOT introduce manual scoring UI, accuracy harness, or
  Day 5+ features.

After opening the PR, post the URL here and STOP. Do not start Day 5.
```

---

## 2n. S2 Day 5 (Codex row) — translation accuracy harness tests (ready to copy)

**Tag**: tests only. Do NOT touch any `lib/` file. The catalog, the
generic run engine, the `S2 Run 30` button, and the `accuracy_score`
CSV column are ALL already implemented and merged by Claude prep — the
run works end-to-end on device. Your job is the missing test coverage.

**Why prep did the impl** (so you don't "fix" it): the S1-Run-10 engine
was live and used for benchmarks; turning it into a half-wired stub
would have broken S1. Generalising it into one catalog-driven engine
(`_startRun` / `_armRunPhrase` / `_scheduleRunAdvance` over a flat
`RunPhrase` list) was a non-stubbable refactor + the global no-duplicate
rule forbids a parallel S2 engine. Same decision axis as Day 4 cooldown.

**Precondition**: Claude prep landed on `main` at commit
`<paste from git log -1>`. That commit:

- added `mobile/lib/data/s2_phrases.dart` — 60 `S2Phrase` (30 `ja` +
  30 `vi`, 6 domains x 5 x 2 directions), with derived `targetLang`,
- added `accuracyScore` (nullable, default null, never auto-set) to
  `E2eLatencyRecord` + appended `accuracy_score` as the last CSV
  column in `csvHeader` / `toCsvRow`,
- replaced the S1-specific run fields/methods with a generic engine
  (`_runItems` / `_runLabel` / `_runActive` / `_runIndex`,
  `_currentRunPhrase`, `_startRun(items, label)`, `_armRunPhrase`,
  `_scheduleRunAdvance`) plus `_s1RunItems()` / `_s2RunItems()`
  builders and a `RunPhrase` typedef,
- added the `S2 Run 30` button next to `S1 Run 10`; both call
  `_startRun(...)` and are disabled while `_runActive`,
- wired `_onPressDown` to pass each phrase's `sourceLang`/`targetLang`
  into `_ws.connect` (manual PTT with no run still defaults ja->vi),
- updated the Day 4 short-press widget test to index the CSV `error`
  column by header (was `row.last`) now that `accuracy_score` is last.

```
Your task: S2 Day 5 — add test coverage for the accuracy harness.
Two NEW test files, zero lib changes. Single mobile PR.

## Concrete deliverables

1. mobile/test/data/s2_phrases_test.dart — pure data invariants on the
   exported `s2Phrases` const (no widgets, no async):

   - exactly 60 phrases,
   - exactly 30 with sourceLang == 'ja' and 30 with sourceLang == 'vi',
   - every one of the 6 domains ('greetings','directions','food',
     'transit','payment','emergencies') has exactly 5 ja + 5 vi,
   - every `targetLang` is the opposite of its `sourceLang`
     (ja->vi, vi->ja); sourceLang is only ever 'ja' or 'vi',
   - all `id` values are unique,
   - no `text` is empty / whitespace-only.

2. mobile/test/translate_screen_test.dart — ADD one group to the
   existing file (do not rewrite the Day 4 groups):

   group 'S2 Run 30':
     - pump the screen (reuse the existing `_pumpTranslateScreen`
       helper + `_SessionHttpOverrides` so the session POST hangs and
       no real WS/audio is needed),
     - tap `find.text('S2 Run 30')`, pump,
     - assert the phrase banner shows the first JP phrase
       'おはようございます' and the counter '1/60' is in the tree,
     - assert a log line 'phrase ja-greet-01 ready' appears.

   Do NOT try to assert the sourceLang reaches `_ws.connect` — the
   fake session hangs before WS connect, so that path is out of reach
   in a widget test. Catalog-direction coverage lives in deliverable 1.

3. Do NOT add dependencies. `flutter_test` only. Do NOT edit any file
   under mobile/lib/. Do NOT change the CSV schema or the button.

## Verification commands to paste raw output for

- `cd mobile && flutter analyze --no-pub` — 0 issues (the 2 pre-existing
  warnings in ble_transport.dart + widget_test.dart are allowed; do not
  touch them).
- `cd mobile && flutter test` — all green (currently 37 tests; you add
  ~7 catalog asserts + 1 widget group).

## Branch / commit / PR

Branch: `test/s2-day-5-accuracy-harness`. Commit subject:
`test(mobile): S2 Day 5 accuracy harness coverage`. PR title same.
Squash-merge.

## What this PR explicitly does NOT do

- It does NOT modify any `lib/` file — tests only.
- It does NOT add manual-scoring UI (scoring is a spreadsheet step in
  Day 6, the CSV column is intentionally export-empty).
- It does NOT touch the run engine, the button, or the CSV schema.
- It does NOT start Day 6 (device run + scoring).

After opening the PR, post the URL here and STOP.
```

---

## 4. PR-ready check (paste when Codex says "done")

```
Before I review your PR, verify these:

1. Branch name follows feat/s1-day-N-<slug>?
2. No commits to main? (`git log main..HEAD` shows your work)
3. No Co-Authored-By: trailers in any commit? (`git log --format=%B HEAD~3..HEAD`)
4. PR description has ALL of: Summary, Files, Verification output (raw,
   not summarised), Open questions, Time spent?
5. All verification commands actually ran (exit 0)?
6. No files modified outside the directories listed in the task?
   Run: `git diff --name-only main..HEAD` and confirm.

If any answer is "no", fix it before I look. If all "yes", post the
PR URL.
```

---

## 5. After-merge prompt (Claude uses this internally)

After the user reports a PR is merged, Claude updates the local checklist:

```
PR for S1 Day <N> merged at <commit>. Update:
- docs/codex/S1_TASKS.md: change the Day-N table to mark Codex rows
  as [DONE] inline.
- TaskUpdate the matching task #N to status=completed.
- If the merge revealed scope creep for Day N+1, edit Day N+1 row
  inline; flag in next 日報.
```

---

## Notes

- Codex tends to over-engineer. If a deliverable says "one file with X",
  resist when the agent proposes 4 files. Re-prompt with "Single file as
  specified."
- Codex sometimes wants to add fancy deps (typer, structlog, loguru,
  pydantic v1 shims). Reject anything not in the briefing without an
  explicit "yes" from Claude or user.
- Always demand raw command output in PR. If the agent paraphrases
  ("tests pass"), reject and re-ask.
- If a task is genuinely too vague, Codex will ask. Better than guessing.
  Add answers back to S1_TASKS.md so the next agent run is unambiguous.

## Lessons from Day 1 (PR #1, merged 2026-05-20)

- The briefing + PR template approach worked: zero rewrite cycles, ~1.5h
  of Codex time, clean merge with one tiny follow-up (backend/CLAUDE.md
  which was always a Claude row).
- Codex shipped a small spec improvement on its own initiative: pytest
  accepts redis up OR down so CI does not need infra. Keep prompts
  prescriptive on the contract but permissive on internal quality
  improvements - that combination paid off.
- Commit author identity uses the local git config, so PRs show the
  user's name. That's fine; the "no Co-Authored-By Claude" rule is what
  matters for attribution policy.
- Codex respected scope completely - did not touch firmware, mobile, or
  .claude/. The explicit "do not touch X" list in the prompt is doing
  real work.
- One thing to copy forward: paste the FULL verification output, not a
  summary. The PR body for #1 included every container start line and
  it made review unambiguous.
