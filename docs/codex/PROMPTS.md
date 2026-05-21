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

## 3. Day-N task prompt — TEMPLATE (use for Day 7-10)

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
