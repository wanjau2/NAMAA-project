# Docker — Namaa demo stack

Synthetic demonstration only. **Not for clinical use.**

## Services

| Service | URL | Notes |
| --- | --- | --- |
| Web (Next.js) | http://localhost:3000 | Still on labelled mocks until Mark’s F4 / Phase C |
| API (FastAPI) | http://localhost:8000 | Authoritative workflow; OpenAPI at `/docs` |

## Start

```bash
# from repo root
docker compose up --build
```

Optional: copy `.env.example` to `.env` and adjust ports or CORS.

## Stop

```bash
docker compose down
# also wipe SQLite volume:
docker compose down -v
```

## Smoke checks

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/v1/demo/sessions
```

## Local (non-Docker) fallback

- API: see [api/README.md](api/README.md)
- Web: `cd web && npm ci && npm run dev`
