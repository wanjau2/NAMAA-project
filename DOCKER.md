# Docker — Namaa demo stack

Synthetic demonstration only. **Not for clinical use.**

The web UI talks to the live API (workflow, extraction, review, evaluations,
analytics). Extraction uses an offline fixture; FHIR commit uses the gateway
stub. This is not a labelled-mock frontend.

## Services

| Service | URL | Notes |
| --- | --- | --- |
| Web (Next.js standalone) | http://localhost:3000 | `node server.js` from the standalone build |
| API (FastAPI) | http://localhost:8000 | Authoritative workflow; OpenAPI at `/docs` |

## Start

```bash
# from repo root
docker compose up --build
```

Optional: copy `.env.example` to `.env` and adjust ports or CORS.

## Browser API URL (build-time)

`NEXT_PUBLIC_API_BASE_URL` is compiled into the web bundle at image build. Set
it to a URL the **browser** can reach (typically `http://localhost:8000` when
Compose publishes the API on host port 8000). Rebuild the `web` service after
changing it; a runtime env var on the running container does not retarget
existing JavaScript.

Deprecated alias: `NEXT_PUBLIC_API_URL` is still accepted by Compose if
`NEXT_PUBLIC_API_BASE_URL` is unset.

## CORS

`NAMAA_CORS_ORIGINS` must include the exact browser origin (scheme, host, and
port). Defaults cover `http://localhost:3000` and `http://127.0.0.1:3000`.
Playwright serves the UI on port 3200 and sets this itself.

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

Then open http://localhost:3000, start a guest session, and open a case.

## Local (non-Docker) fallback

- API: see [api/README.md](api/README.md)
- Web, development: `cd web && npm ci && npm run dev` (expects the API at
  `http://127.0.0.1:8000`; add the UI origin to `NAMAA_CORS_ORIGINS` if it is
  not on port 3000)
- Web, production-like standalone:

```bash
cd web
npm ci
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 npm run build
npm start
```

`npm start` copies `.next/static` and `public` next to the standalone
`server.js` and runs it. Playwright uses `npx next start` via `start:next`.
