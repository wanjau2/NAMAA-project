# Namaa web (synthetic demo)

**Not for clinical use.** The UI talks to the Namaa API. Extraction is an
offline fixture; FHIR commit is a gateway stub.

## Prerequisites

The API must be running on the origin baked into the browser build (default
`http://127.0.0.1:8000`). See [api/README.md](../api/README.md).

`NAMAA_CORS_ORIGINS` on the API must include this UI's origin (scheme, host,
and port). The API default allows ports 3000. Playwright uses 3200 and sets
CORS itself.

## Development

```bash
npm ci
npm run dev
```

Open http://localhost:3000. `NEXT_PUBLIC_API_BASE_URL` defaults to
`http://127.0.0.1:8000` when unset.

## Production-like standalone

This app builds with Next `output: "standalone"`. After `npm run build`:

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 npm run build
npm start
```

`npm start` copies `.next/static` and `public` into the standalone folder and
runs `node server.js` (same as Docker). The API origin is compiled in at
**build** time; changing the env var afterwards does not retarget the browser.

`npm run start:next` runs `next start` and is what Playwright uses. Prefer
`npm start` for a reviewer walkthrough.

Deprecated alias: `NEXT_PUBLIC_API_URL` is still read if
`NEXT_PUBLIC_API_BASE_URL` is unset.

## Checks

```bash
npm run lint
npm run verify
npm run verify:api   # API must already be on :8000
npx playwright test --project=desktop
```
