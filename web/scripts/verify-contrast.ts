import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { LANGUAGE_SCOPE } from "../lib/copy.ts";

/**
 * D7 — badge and brand contrast against the documented token pairs.
 *
 * Ratios are computed from the hex values in globals.css, not estimated.
 * WCAG 1.4.11 non-text contrast needs 3:1; text AA needs 4.5:1 (3:1 for large).
 *
 * Run: npm run verify:contrast
 */

const css = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../app/globals.css"),
  "utf8",
);

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

function cssHex(name: string): string {
  const match = css.match(new RegExp(`${name}:\\s*(#[0-9a-fA-F]{6})`));
  if (!match) {
    throw new Error(`token ${name} missing from globals.css`);
  }
  return match[1];
}

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  return [
    Number.parseInt(h.slice(0, 2), 16),
    Number.parseInt(h.slice(2, 4), 16),
    Number.parseInt(h.slice(4, 6), 16),
  ];
}

function channel(c: number): number {
  const s = c / 255;
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
}

function luminance(hex: string): number {
  const [r, g, b] = hexToRgb(hex);
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function contrast(fg: string, bg: string): number {
  const a = luminance(fg);
  const b = luminance(bg);
  const lighter = Math.max(a, b);
  const darker = Math.min(a, b);
  return (lighter + 0.05) / (darker + 0.05);
}

const tokens = {
  verifiedFg: cssHex("--status-verified-fg"),
  verifiedBg: cssHex("--status-verified-bg"),
  proposedFg: cssHex("--status-proposed-fg"),
  proposedBg: cssHex("--status-proposed-bg"),
  reviewFg: cssHex("--status-review-fg"),
  reviewBg: cssHex("--status-review-bg"),
  overdueFg: cssHex("--status-overdue-fg"),
  overdueBg: cssHex("--status-overdue-bg"),
  brand: cssHex("--brand-primary"),
  brandOnWhite: "#ffffff",
  ink: cssHex("--text-primary"),
  canvas: cssHex("--bg-canvas"),
  simBadge: cssHex("--sim-badge-bg"),
  simBadgeFg: cssHex("--sim-badge-fg"),
  focus: cssHex("--brand-focus"),
};

check(
  "verified badge text ≥ 4.5:1 on its background",
  contrast(tokens.verifiedFg, tokens.verifiedBg) >= 4.5,
  contrast(tokens.verifiedFg, tokens.verifiedBg).toFixed(2),
);
check(
  "proposed badge text ≥ 4.5:1 on its background",
  contrast(tokens.proposedFg, tokens.proposedBg) >= 4.5,
  contrast(tokens.proposedFg, tokens.proposedBg).toFixed(2),
);
check(
  "review badge text ≥ 4.5:1 on its background",
  contrast(tokens.reviewFg, tokens.reviewBg) >= 4.5,
  contrast(tokens.reviewFg, tokens.reviewBg).toFixed(2),
);
check(
  "overdue badge text ≥ 4.5:1 on its background",
  contrast(tokens.overdueFg, tokens.overdueBg) >= 4.5,
  contrast(tokens.overdueFg, tokens.overdueBg).toFixed(2),
);
check(
  "white on brand primary ≥ 4.5:1",
  contrast(tokens.brandOnWhite, tokens.brand) >= 4.5,
  contrast(tokens.brandOnWhite, tokens.brand).toFixed(2),
);
check(
  "ink on canvas ≥ 4.5:1",
  contrast(tokens.ink, tokens.canvas) >= 4.5,
  contrast(tokens.ink, tokens.canvas).toFixed(2),
);
check(
  "simulation badge text ≥ 4.5:1",
  contrast(tokens.simBadgeFg, tokens.simBadge) >= 4.5,
  contrast(tokens.simBadgeFg, tokens.simBadge).toFixed(2),
);
check(
  "focus ring on canvas ≥ 3:1 (non-text)",
  contrast(tokens.focus, tokens.canvas) >= 3,
  contrast(tokens.focus, tokens.canvas).toFixed(2),
);
check(
  "verified border colour against its background ≥ 3:1",
  contrast(tokens.verifiedFg, tokens.verifiedBg) >= 3,
);
check(
  "proposed dashed border against its background ≥ 3:1",
  contrast(tokens.proposedFg, tokens.proposedBg) >= 3,
);
check(
  "Arabic chrome is recorded as unreviewed demonstration copy",
  LANGUAGE_SCOPE.arabicChrome === "unreviewed_demo" &&
    LANGUAGE_SCOPE.clinicalCopy === "en" &&
    LANGUAGE_SCOPE.rtlMechanics === true,
);
check(
  "globals.css short-circuits animation under prefers-reduced-motion",
  /prefers-reduced-motion:\s*reduce/.test(css) &&
    /animation-duration:\s*0\.01ms/.test(css),
);

console.log(`\n${pass} passed, ${fail} failed`);
if (fail > 0) process.exit(1);
