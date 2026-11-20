#!/usr/bin/env node
/**
 * Run the Next.js `output: "standalone"` server the same way Docker does.
 *
 * `next start` warns (and can miss assets) when the app is built standalone.
 * This copies `.next/static` and `public` next to `server.js`, then runs it.
 *
 * NEXT_PUBLIC_API_BASE_URL is baked in at `npm run build`. Changing it here
 * does not retarget the browser; rebuild with the URL the browser can reach.
 */

import { cpSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const webRoot = join(dirname(fileURLToPath(import.meta.url)), "..");

function findStandalone() {
  const candidates = [
    join(webRoot, ".next/standalone"),
    join(webRoot, ".next/standalone/web"),
  ];
  for (const dir of candidates) {
    if (existsSync(join(dir, "server.js"))) return dir;
  }
  return null;
}

const standalone = findStandalone();
if (!standalone) {
  console.error(
    "No standalone server.js under .next/standalone. Run `npm run build` first.",
  );
  process.exit(1);
}

const staticSrc = join(webRoot, ".next/static");
const staticDest = join(standalone, ".next/static");
if (existsSync(staticSrc)) {
  mkdirSync(dirname(staticDest), { recursive: true });
  cpSync(staticSrc, staticDest, { recursive: true });
}

const publicSrc = join(webRoot, "public");
const publicDest = join(standalone, "public");
if (existsSync(publicSrc)) {
  cpSync(publicSrc, publicDest, { recursive: true });
}

const child = spawn(process.execPath, ["server.js"], {
  cwd: standalone,
  stdio: "inherit",
  env: {
    ...process.env,
    PORT: process.env.PORT ?? "3000",
    HOSTNAME: process.env.HOSTNAME ?? "0.0.0.0",
  },
});

const forward = (signal) => {
  if (!child.killed) child.kill(signal);
};

process.on("SIGINT", () => forward("SIGINT"));
process.on("SIGTERM", () => forward("SIGTERM"));

child.on("exit", (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  process.exit(code ?? 1);
});
