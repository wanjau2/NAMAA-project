/**
 * M14 — the browser, Docker, and env examples must agree on the API origin
 * variable, and `npm start` must launch the standalone server.
 *
 * Run: npm run verify:startup
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = join(webRoot, "..");

let pass = 0;
let fail = 0;

function check(name: string, condition: boolean, detail = "") {
  if (condition) {
    pass++;
    console.log(`PASS  ${name}`);
  } else {
    fail++;
    console.log(`FAIL  ${name} ${detail}`);
  }
}

function read(path: string) {
  return readFileSync(path, "utf8");
}

const apiClient = read(join(webRoot, "lib/api.ts"));
const dockerfile = read(join(webRoot, "Dockerfile"));
const compose = read(join(repoRoot, "docker-compose.yml"));
const envExample = read(join(repoRoot, ".env.example"));
const pkg = JSON.parse(read(join(webRoot, "package.json"))) as {
  scripts?: Record<string, string>;
};
const dockerMd = read(join(repoRoot, "DOCKER.md"));
const webReadme = read(join(webRoot, "README.md"));

check(
  "client canonical env is NEXT_PUBLIC_API_BASE_URL",
  apiClient.includes("process.env.NEXT_PUBLIC_API_BASE_URL"),
);
check(
  "client still accepts deprecated NEXT_PUBLIC_API_URL as a fallback alias",
  apiClient.includes("process.env.NEXT_PUBLIC_API_URL"),
);
check(
  "Dockerfile ARG is NEXT_PUBLIC_API_BASE_URL",
  /ARG NEXT_PUBLIC_API_BASE_URL=/.test(dockerfile),
);
check(
  "Compose passes NEXT_PUBLIC_API_BASE_URL into the web build",
  compose.includes("NEXT_PUBLIC_API_BASE_URL:"),
);
check(
  "Compose still maps the deprecated NEXT_PUBLIC_API_URL alias into BASE_URL",
  compose.includes("${NEXT_PUBLIC_API_BASE_URL:-${NEXT_PUBLIC_API_URL:-http://localhost:8000}}"),
);
check(
  ".env.example documents NEXT_PUBLIC_API_BASE_URL",
  /^NEXT_PUBLIC_API_BASE_URL=/m.test(envExample),
);
check(
  ".env.example documents NAMAA_CORS_ORIGINS",
  /^NAMAA_CORS_ORIGINS=/m.test(envExample),
);
check(
  "npm start launches the standalone server",
  pkg.scripts?.start === "node scripts/start-standalone.mjs",
);
check(
  "npm run start:next remains for Playwright / next start",
  pkg.scripts?.["start:next"] === "next start",
);
check(
  "DOCKER.md no longer claims the frontend is still on labelled mocks",
  !/Still on labelled mocks/i.test(dockerMd),
);
check(
  "DOCKER.md documents NEXT_PUBLIC_API_BASE_URL as build-time",
  dockerMd.includes("NEXT_PUBLIC_API_BASE_URL") &&
    /build/i.test(dockerMd),
);
check(
  "web README documents standalone start and CORS",
  webReadme.includes("npm start") &&
    webReadme.includes("NAMAA_CORS_ORIGINS") &&
    webReadme.includes("NEXT_PUBLIC_API_BASE_URL"),
);

console.log(`\n${pass} passed, ${fail} failed`);
if (fail > 0) process.exit(1);
