# backend/ — FastAPI audio translation gateway

Scope: server-side bridge between the mobile sender and the OpenAI Realtime
API. S1 goal is a single-tenant prototype; multi-user / scaling is S2+.

## Stack

- Python 3.12 (Dockerfile is the source of truth; local 3.13 is OK for `pytest` only).
- FastAPI 0.115.x + uvicorn 0.30.x.
- `redis[hiredis]` 5.x for session metadata + cost log. Single instance per host.
- `openai` 1.50+ SDK for Realtime WebSocket.
- `pydantic-settings` 2.x for env-driven config.
- `pytest` + `pytest-asyncio` + `httpx` (ASGI transport, no real network in unit tests).
- `ruff` for lint/format. No black, no isort.

Build / package: `uv` builds a wheel at Dockerfile builder stage; runtime image
installs the wheel and runs `uvicorn app.main:app`.

## Layout

```
backend/
├── pyproject.toml          # PEP 621 + hatchling backend, packages=["app"]
├── Dockerfile              # multi-stage builder + runtime, non-root uid 10001
├── docker-compose.yml      # api + redis, redis healthcheck gates api start
├── .env.example            # template; .env is gitignored
├── .gitignore
├── README.md               # one-paragraph run notes
├── app/
│   ├── main.py             # app factory create_app(), mounts routers
│   ├── api/                # one router per resource
│   │   └── health.py       # GET /healthz with redis PING probe
│   ├── core/
│   │   └── config.py       # Settings (pydantic-settings) + get_settings()
│   └── services/           # business logic; OpenAI translator lives here (Day 2+)
└── tests/                  # pytest, asyncio_mode=auto, ASGITransport client
    └── test_health.py
```

`app/api/` holds HTTP/WS routers. `app/services/` holds connectors to external
systems (OpenAI Realtime, audio buffers, cost logger). `app/core/` holds
config + cross-cutting infrastructure. Keep `main.py` to wiring only.

## Run / test

```powershell
# Local dev (no Docker, requires Python 3.12 venv)
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

```powershell
# Docker (preferred — matches prod)
cd backend
docker compose up -d --build
curl http://localhost:8000/healthz
docker compose down -v   # also drops redis volume
```

```powershell
# Unit tests (no docker needed; test accepts redis up OR down state)
cd backend
pytest
```

## Coding conventions

- Type-annotate every public function. `Literal` for narrow string enums.
- Pydantic models for request and response bodies. Never return raw dicts
  from a handler.
- `get_settings()` is cached via `@lru_cache`; do not call `Settings()`
  directly elsewhere.
- New deps must be added to `pyproject.toml` and announced in the PR
  description. Do not pip install at runtime.
- Logging: configure via uvicorn's `--log-level` from env. Use `logger =
  logging.getLogger(__name__)` per module. **Never log audio bytes or
  translated text content** — this is a hard privacy boundary that
  applies from Day 1.
- Async-first: all I/O is async. No `requests`; use `httpx.AsyncClient`
  for outbound HTTP (already a dev dep) or the openai SDK's async paths.

## Contracts

- HTTP / WebSocket wire contract lives in `docs/api-contract/`. Extend
  `openapi.yaml` and `ws-events.schema.json` in the same commit as any
  endpoint change. Mobile (`mobile/lib/services/translator_ws.dart`)
  mirrors the WS event shape; both sides must change together.
- The BLE protocol is **not** a backend concern. Subtitle text comes out
  of the backend as plain UTF-8; the mobile app encodes it into the BLE
  packet format. Backend does not need to know about CRC, MTU, or
  sequence_id.

## Sprint hooks

- S1 Day 1 (done 2026-05-20, commit 538eae1, PR #1): scaffold. FastAPI
  app factory, `/healthz` with optional redis PING (returns
  `{status, version, redis}`), pydantic-settings config, multi-stage
  Dockerfile (< 200 MB, non-root, curl-based healthcheck), Docker Compose
  with redis healthcheck gating api start, one ASGITransport pytest case
  that accepts redis up OR down so CI can run without infra. Local pytest
  may run on Python 3.13 but the Docker runtime is 3.12.
- S1 Day 2 (next): `app/services/translator.py` — async WebSocket client
  to OpenAI Realtime API. Streaming generator yielding `TextDelta`
  events. JP↔VN translation prompt locked in service instructions.
  Mock-based pytest using `pytest-asyncio`.
- S1 Day 3: `app/api/sessions.py` — `POST /v1/sessions` returns
  session_id, stores meta in redis (1h TTL). `WS /v1/sessions/{id}/stream`
  bridges mobile audio frames to translator service. Add CORS middleware
  for the mobile origin. Pool redis client in app lifespan.
- S1 Day 8: `app/services/cost_logger.py` — per-session `audio_seconds`,
  `tokens_in`, `tokens_out` to redis hash `session:{id}:cost`. `GET
  /v1/stats` aggregates last 24h. Daily spend cap env `DAILY_USD_CAP`
  enforced in session creation.

## Do not

- Persist user audio. Bytes flow through memory only and are not written
  to disk, redis, or logs.
- Log translated text content. Counts and durations only.
- Add Flask, Django, or any non-FastAPI HTTP framework.
- Add `axios` or any JS shim. Backend is pure Python.
- Run uvicorn with `--reload` in the runtime Docker image.
- Add a dependency without listing the candidate in the PR description.
