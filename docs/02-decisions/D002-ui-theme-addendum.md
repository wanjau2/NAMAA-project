# D002 — UI theme addendum: corrected tokens and missing layers

**Date:** 2026-11-17
**Status:** Proposed — needs Mark's agreement; items 7 and 8 need Ismail and Alfred
**Decided by:** pending
**Supersedes:** specific token values in [namaa_ui_theme_prompt.md](../00-reference/namaa_ui_theme_prompt.md) §2, §3, §6
**Partially resolves:** OPEN-QUESTIONS Q2 (the implementation half — logical properties and bidi
apply regardless of whether Arabic copy ships)
**Raises:** OPEN-QUESTIONS Q8 (small-cell suppression must be server-side)

> D001 is reserved for the stack decision (Q1). This addendum assumes a Next.js + Tailwind +
> shadcn/ui frontend as the UI prompt specifies. If Q1 lands on plain React, everything here
> still applies except the shadcn mapping in §4.

## Context

The theme document's semantic model is sound and should be kept: five epistemic states that
separate *who asserted something* from *how urgent it is*, color never used alone, equal visual
weight for uncertainty, logical CSS properties, light mode only. Those decisions are the
reason the UI can carry the design specification's clinical safety boundary at all.

What it does not yet have is the layer underneath: contrast-verified border values, the states
that are not status (disabled, loading, empty, hover, selected), a type and spacing scale, a
token bridge to shadcn, and bidi handling for technical strings. Each of those is cheap now and
expensive after twenty components exist.

## Decision

Adopt the eight corrections below before building the first component, in the order given.

---

## 1. Status borders must carry the state's foreground color

**Problem.** The specified borders fail WCAG 1.4.11 (non-text contrast, ≥3:1) against their own
card backgrounds:

| Border on background | Specified | Ratio | Verdict |
| --- | --- | --- | --- |
| `#86EFAC` on `#F0FDF4` | green-300 | ≈1.33:1 | fails |
| `#C4B5FD` on `#F5F3FF` | violet-300 | ≈1.7:1 | fails |
| `#FCD34D` on `#FFFBEB` | amber-300 | ≈1.6:1 | fails |
| `#FCA5A5` on `#FEF2F2` | red-300 | ≈1.8:1 | fails |

This matters more here than in a typical app, because the theme deliberately uses **border
style** (dashed vs solid) as a meaning-bearing channel for unreviewed AI proposals. A channel
nobody can perceive is not a channel.

**Fix.** Set each status border to that state's **foreground** hex. One rule, three fewer
tokens, and every pair clears 3:1 with room to spare:

| State | Foreground / border | Background | Ratio | Border style |
| --- | --- | --- | --- | --- |
| Verified / authorized / completed | `#15803D` | `#F0FDF4` | ≈4.8:1 | `1px solid` |
| Proposed / unreviewed AI | `#6D28D9` | `#F5F3FF` | ≈6.5:1 | `1px dashed` |
| Needs review / missing / uncertain | `#B45309` | `#FFFBEB` | ≈4.8:1 | `1px solid` |
| Overdue / escalated / conflict | `#B91C1C` | `#FEF2F2` | ≈5.9:1 | `1px solid` |

Keep the original pale values only as optional decorative tints (`--status-*-edge-soft`) for
things like table row separators, never as the indicator itself.

**On cards, add a start-edge spine.** `border-s-4` in the foreground color, in place of a
uniform saturated outline. It reads as a status spine, raises contrast further, and mirrors
correctly under `dir="rtl"` for free because it is a logical property.

**Already verified as passing — do not change:**

- `#FFFFFF` on `--brand-primary #0F5C5C` ≈ 7.8:1
- `--brand-focus #0D9488` on canvas ≈ 3.6:1, and on the `#1E293B` simulation bar ≈ 3.9:1 — both
  clear the 3:1 non-text threshold, so the single global `*:focus-visible` rule is fine as
  written. Optional: `--brand-focus-on-dark: #5EEAD4` gives far more headroom on the dark bar
  if it feels tight in practice.
- Status foreground text on its own background clears AA for normal text, but with little
  headroom (green is the tightest at ≈4.8:1). Keep badge text at **≥12px and weight 500+**.

## 2. Role-gated controls: `aria-disabled`, never `disabled`

The theme requires actions belonging to another role to render disabled with an explanation.
A native `disabled` button is **removed from the focus order**, so a keyboard or screen-reader
user can never reach that explanation — and "all controls are keyboard accessible" is in the
work plan's definition of done.

**Pattern:**

- `aria-disabled="true"`, control stays focusable, handler returns early.
- The reason goes in **visible helper text** beneath the control, not a tooltip only.
- Associate it with `aria-describedby` so it is announced on focus.
- Because these controls are read, not inert, their label keeps `--text-secondary #475569`
  (≈6.9:1 on `#F1F5F9`) — **do not** wash it out to a conventional disabled grey.

Example copy, already in the theme: *"Requires Clinical Reviewer role to authorize care plan"*,
*"Booking alone does not complete preventive care."*

## 3. Bidi isolation for technical strings

Rule IDs, FHIR logical IDs, UTC timestamps, revisions and denominators will render scrambled
when embedded in Arabic text. The theme never mentions this. Bake it into the existing utility:

```css
.font-mono-tech {
  font-family: 'JetBrains Mono', monospace;
  direction: ltr;
  unicode-bidi: isolate;
  font-variant-numeric: tabular-nums;
}
```

Apply `.font-mono-tech` to every `DEMO_WCV_01`, `rev 3`, `2026-11-17T09:30Z`, FHIR id and
`n = 42` — in both language modes, not just RTL. `tabular-nums` additionally keeps numerator /
denominator columns aligned in the metrics view.

Also extend the RTL block, which currently sets only `body`:

```css
html[dir="rtl"] h1,
html[dir="rtl"] h2,
html[dir="rtl"] h3 { font-family: 'IBM Plex Sans Arabic', sans-serif; font-weight: 600; }
```

## 4. Token bridge to shadcn/ui

shadcn components read `--background`, `--foreground`, `--card`, `--primary`, `--muted`,
`--destructive`, `--border`, `--input`, `--ring`. They will **ignore** the Namaa variable names
entirely, so without a bridge every shadcn primitive renders in default shadcn colors while the
Namaa palette is hand-written into `className`. Two competing systems, and the theme loses.

Keep the Namaa tokens as the single source of truth and alias shadcn's names onto them.

**Implementation note (2026-11-17):** this section originally specified a
`tailwind.config.ts`. The installed stack is **Tailwind 4.3.3**, which is CSS-first and ships
**no config file at all** — theme values live in `@theme` inside `globals.css`. The approach is
unchanged; the mechanism is different. What was actually built:

```css
/* app/globals.css */
:root {
  /* Namaa tokens - the source of truth */
  --bg-canvas: #f8fafc;
  --brand-primary: #0f5c5c;
  /* ... */

  /* shadcn bridge: alias, never duplicate */
  --background: var(--bg-canvas);
  --primary: var(--brand-primary);
  --muted-foreground: var(--text-secondary);
  --destructive: var(--status-overdue-fg);
  --ring: var(--brand-focus);
}

@theme inline {
  /* generates bg-surface, text-ink-muted, border-status-proposed, ... */
  --color-surface: var(--bg-surface);
  --color-ink-muted: var(--text-secondary);
  --color-status-proposed: var(--status-proposed-fg);
  /* and re-exports shadcn's names so its components resolve */
  --color-background: var(--background);
  --color-primary: var(--primary);
}
```

`@theme inline` matters: it makes the generated utilities reference `var(...)` at runtime rather
than copying values at build time, which is what lets one `:root` change repaint everything.

**Version traps, revised for what is installed:**

- Tailwind v4 has **no `tailwind.config.ts`**. Adding one does nothing; edit `@theme`.
- The `hsl()` wrapper problem does not arise - shadcn's v4 output uses bare `oklch()` values, so
  plain hex aliases work. The trap it replaces: shadcn init writes a full `.dark` block and a
  `@custom-variant dark`, both of which were **removed** per the light-only guardrail.
- `shadow-xs` **does** exist in v4 (4.3.3), so the earlier v3 warning does not apply here.
- shadcn init leaves `--font-sans: var(--font-sans)` in `@theme inline` - a self-reference that
  silently breaks fonts until the layout defines the real variables.
- lucide-react v1 renamed the icons the theme names. `CheckCircle2`, `AlertTriangle` and
  `AlertOctagon` still resolve as deprecated aliases and are what the code uses; the canonical
  v1 names are `CircleCheckBig` and friends.

## 5. The states the theme does not define

| State | Treatment |
| --- | --- |
| Disabled (role-gated) | `--bg-subtle` fill, label at `--text-secondary`, visible helper text — see §2 |
| Loading / skeleton | `#E2E8F0` block on `--bg-surface`, gentle pulse; **plus** elapsed text, e.g. `Extracting… 12s (90s timeout)` — the spec polls every 2s against a 90s timeout, so a bare spinner hides a stall |
| Timeout / retry | Overdue tokens, explicit `Retry extraction`; never render a failure as "no gap found" |
| Empty | `--bg-subtle` panel, icon, one plain sentence, and a control to clear the filters that caused it |
| Row hover | `--bg-canvas` on a white row |
| Row / nav selected | `border-s-[3px]` in `--brand-primary` + `--bg-subtle` fill |
| Reset Demo confirm | Two-step, overdue tokens, and state the consequence: *"Retires this synthetic workspace and starts a new one."* |

## 6. Type and spacing scale

Four font families are named with no sizes. For a dense worklist this is what decides whether it
reads like Medplum or like a default template.

| Role | Size / line height | Family and weight |
| --- | --- | --- |
| Page title | 28 / 34 | Plus Jakarta Sans 700 |
| Section heading | 22 / 28 | Plus Jakarta Sans 600 |
| Card title | 18 / 26 | Plus Jakarta Sans 600 |
| Body, explanations | 16 / 24 | Inter 400 |
| Dense UI, table cells, labels | 14 / 20 | Inter 400, labels 500 |
| Metadata, timestamps, badges | 12 / 16 | Inter 500 — floor, never smaller |
| Technical strings | 13 in 14 contexts | JetBrains Mono 400, tabular |

Buttons and badges: Inter 600. Spacing on a 4px base — `4 / 8 / 12 / 16 / 24 / 32 / 48`. Card
padding 16 (20 on case detail), section gap 24, page gutter 16 mobile / 24 desktop, table row
height 44 to stay a valid touch target, simulation bar 44, filter row 48.

**Load fonts with `next/font`, not the `@import` in `globals.css`.** The import is a
render-blocking serial request and causes layout shift — both work against the release gate
requirement that a fresh browser can enter the demo cleanly. Subset to `latin` plus `arabic`.

## 7. One component owns status rendering

The "never rely on color alone" rule needs enforcement, not goodwill. Build exactly one
component and make it the only sanctioned way to show state:

```tsx
<StatusBadge state="proposed" /> // → dashed border + Sparkles icon + "Proposed — not yet reviewed"
```

It always emits **token + icon + plain-language text** together, so a bare colored dot is not
reachable through the API. Same for `<SuppressedCell />`. Review rule: a raw hex or a lone
colored element in a PR is a blocker.

## 8. Small-cell suppression must come from the server

**This one is not a theme issue and needs Ismail and Alfred.** If the frontend decides what
`n < 10` means, the true counts are still sitting in the network response — the suppression is
cosmetic and a reviewer can open DevTools and read the hidden group.

Required contract: `/metrics` (or `/analytics/*`) returns the cell already suppressed, with the
value omitted:

```json
{ "segment": "age_band_0_4", "suppressed": true, "reason": "small_cell", "threshold": 10 }
```

The UI renders the hatch, the lock icon and the monospace `Suppressed (n < 10)` label, plus
screen-reader text — and nothing else, because it has nothing else. Complementary suppression
(where a visible total would reveal the hidden cell) is a cohort calculation and belongs with
the metric definitions, not in CSS.

Cosmetic note: the `-45deg` hatch gradient does not mirror under `dir="rtl"`. Acceptable — it
carries no meaning on its own.

## 9. Simulation bar at phone width

44px holding an amber badge, three role options, a language toggle and Reset Demo will not fit a
phone, and 44px is simultaneously the minimum touch target. Below ~640px: keep the badge, collapse
role switcher / language / reset into one overflow menu. Both journeys must work at mobile width.

---

## Consequences

**Easier.** Components get built once against real tokens. shadcn primitives inherit the theme
instead of fighting it. RTL works from the first component rather than needing a sweep. The
accessibility claims in the definition of done become checkable rather than aspirational.

**Harder.** Roughly 2–3 hours of setup before the first screen exists, which comes out of F1.
Saturated status borders are visually heavier than the original pastels; the start-edge spine is
there to keep cards calm.

**What we can claim.** Contrast ratios in §1 are computed, not estimated, so WCAG AA contrast
and non-text contrast are defensible for the token set. **Not** a general claim of accessibility
conformance — that needs the keyboard, screen-reader and RTL passes below.

## Verification

Add to the F5 / M06 acceptance evidence:

- axe-core via Playwright on each screen, zero critical violations
- the full badge set screenshotted and contrast-checked, including the dashed proposal border
- keyboard-only completion of both journeys, with every `aria-disabled` control reachable and
  its reason announced
- RTL snapshot of case detail with a timestamp, a rule ID and a denominator visible, confirming
  no scrambled technical strings
- a suppressed segment confirmed suppressed **in the network response**, not just on screen

## Revisit when

Q1 lands on plain React (drop §4), Q2 decides Arabic copy does not ship (§3 still applies to
`tabular-nums` and future-proofing), or usability testing says the saturated borders are too loud.
