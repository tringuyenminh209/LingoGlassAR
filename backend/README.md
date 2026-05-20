# LingoGlass Backend

FastAPI backend scaffold for the S1 audio translation pipeline. Run locally with `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`, or use Docker Compose with `docker compose up -d --build`; `/healthz` returns app status, version, and whether Redis responds to `PING`.
