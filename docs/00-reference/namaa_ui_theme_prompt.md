# Namaa UI Design System & Implementation Prompt

> **How to use this file:** Copy everything below the horizontal rule and paste it as the system prompt or initial context in your AI coding assistant (Cursor, Windsurf, v0, Lovable, or Claude/Gemini) when generating React/Next.js components for Namaa.

---

## 1. Role & Project Context

You are building the frontend interface for **Namaa**, a FHIR-first precision prevention and care-coordination platform prototype (Population Health Challenge 04).

* **Tech Stack:** React / Next.js with TypeScript, Tailwind CSS, and `shadcn/ui` primitives.
* **Reference Aesthetic:** Model the layout density, clarity, and clinical trust cues after **OpenMRS 3 (O3)** and **Medplum**.
* **Core Constraint:** Every screen operates in a synthetic demonstration environment. The UI must strictly enforce clinical safety boundaries—visually separating unverified proposals and missing records from clinician-authorized facts, and clearly labeling simulated actions.
* **Scope Guardrail:** Build a single high-contrast **light mode only**. Do not implement dark mode or heavy third-party charting libraries.

## 2. Visual Aesthetic & Color Tokens ("Clinical Desert Calm")

Use a calm, low-glare clinical palette pairing warm alabaster surfaces with deep clinical teal, crisp slate typography, and explicit semantic borders. Never rely on color alone to convey clinical or workflow status—always pair background/border tokens with an explicit icon and plain-language text badge.

### Surface & Brand Tokens

* **Canvas Background (`--bg-canvas`):** `#F8FAFC` (main application background)
* **Elevated Card Surface (`--bg-surface`):** `#FFFFFF` with `1px solid #E2E8F0` border and subtle `shadow-xs`
* **Subtle / Read-Only Pane (`--bg-subtle`):** `#F1F5F9` (clinical notes, FHIR JSON viewer, chronological timeline background)
* **Primary Brand / CTA (`--brand-primary`):** `#0F5C5C` (hover `#0B4646`) with `#FFFFFF` text for primary authorized actions (`Approve Pathway`, `Record Attendance`)
* **Interactive Focus Ring (`--brand-focus`):** `#0D9488` (`2px` solid outline with `2px` offset on `:focus-visible`)
* **Primary Ink (`--text-primary`):** `#0F172A` (headings and primary clinical data)
* **Secondary / Muted Ink (`--text-secondary`):** `#475569` (metadata labels, timestamps, helper text)

### Epistemic & Workflow Status Tokens

Map every state badge, alert banner, and status card to these exact semantic tokens:

1. **Verified / Authorized / Completed:**
   * Text: `#15803D` | Background: `#F0FDF4` | Border: `1px solid #86EFAC`
   * Icon: Checkmark (`CheckCircle2`)
   * Usage: Active `CarePlan`, verified `Observation`, completed `Procedure` with evidence.
2. **Proposed / Unreviewed AI Flag:**
   * Text: `#6D28D9` | Background: `#F5F3FF` | Border: `1px dashed #C4B5FD` (must use a **dashed** border)
   * Icon: Sparkles (`Sparkles`)
   * Usage: Staged extraction proposals or unreviewed rule flags prior to clinician sign-off.
3. **Needs Review / Missing / Uncertain:**
   * Text: `#B45309` | Background: `#FFFBEB` | Border: `1px solid #FCD34D`
   * Icon: Alert Triangle (`AlertTriangle`)
   * Usage: `needs_review` status, unknown last visit dates, conflicting history, or missing inputs.
4. **Overdue / Escalated / Conflict:**
   * Text: `#B91C1C` | Background: `#FEF2F2` | Border: `1px solid #FCA5A5`
   * Icon: Octagon Alert / Clock (`AlertOctagon`)
   * Usage: Missed `Task` deadlines, rejected referrals, or `409` stale revision errors.
5. **Persistent Simulation Header:**
   * Bar Background: `#1E293B` | Warning Badge Background: `#F59E0B` with `#0F172A` bold text.

## 3. Typography & Bilingual RTL Layout Rules

Namaa supports instant switching between **English (`dir="ltr"`)** and **Arabic (`dir="rtl"`)**.

* **English Headings:** `Plus Jakarta Sans` (weights 600, 700)
* **English Body & Controls:** `Inter` (weights 400, 500, 600)
* **Arabic UI (when `dir="rtl"` is active):** `IBM Plex Sans Arabic` (weights 400, 500, 600)
* **Technical Monospace:** `JetBrains Mono` (weights 400, 500) for rule IDs (`DEMO_WCV_01`, `DEMO_ADULT_01`), UTC timestamps, FHIR logical IDs, case revisions (`rev 3`), and cohort denominators (`n = 42`).
* **Mandatory Logical CSS Properties:** Use Tailwind logical utilities exclusively (`ms-*`, `me-*`, `ps-*`, `pe-*`, `start-0`, `end-0`, `text-start`, `border-s-*`, `rounded-s-*`). Never use physical directional classes (`ml-*`, `mr-*`, `pl-*`, `pr-*`, `left-*`, `right-*`, `text-left`) so the entire layout mirrors cleanly when toggling `dir="rtl"`.
* **Translation Labels:** Any unreviewed Arabic demo copy must include a subtle inline badge: `Unreviewed demo translation`.

## 4. Core Component & Safety Patterns

1. **Persistent Top Simulation & Role Bar (`44px` height, sticky top):**
   * Dark slate (`#1E293B`) full-width strip visible on every screen.
   * Left/Start: Amber badge reading `SYNTHETIC DEMO DATA — NOT FOR CLINICAL USE`.
   * Center/End:
     * Interactive **Guest Role Switcher** (`Coordinator` | `Clinical Reviewer` | `Population Analyst`).
     * **Language Toggle** (`EN` / `عربي`).
     * **Reset Demo** button (`POST /demo/reset`) with confirmation state.
2. **Role-Gated Action Controls:**
   * Do not hide actions that belong to another role; render them in a visually disabled state with an explicit helper caption or tooltip explaining the boundary (e.g., *"Requires Clinical Reviewer role to authorize care plan"* or *"Booking alone does not complete preventive care"*).
3. **Equal-Weight Uncertainty Layout:**
   * On the Case Detail screen, display a dedicated **"Missing & Unverified Information"** card (`#FFFBEB` amber token) side-by-side with equal visual weight next to the **"Suggested Pathway"** card. Never imply that missing history equals low risk.
4. **Non-Destructive Conflict & Error Handling:**
   * When an action fails (such as a `409` stale revision conflict or rule evaluator timeout), display an inline `#FEF2F2` alert banner at the top of the action panel with a **Reload Latest State** button. **Preserve all user-entered form inputs** so work is never lost.
5. **Small-Cell Cohort Suppression ($n < 10$):**
   * In the Population Analytics view, render any segment with $n < 10$ (or complementary cells that could reveal a hidden count) using a diagonal hatched `#F1F5F9` pattern, a lock icon, and the monospace label `Suppressed (n < 10)`.

## 5. Screen-Specific UI Requirements

* **Guest Entry / Welcome:** Clean centered card on `#F8FAFC` with a clear synthetic-data notice and a single primary CTA (`Start Synthetic Demo Session`)—no credentials required.
* **Coordinator Worklist (`/cases`):** Filter pills for Pathway (`Child Well-Child`, `Adult Screening`), Stage (`identified`, `reviewed`, `invited`, `booked`, `attended`, `follow_up`, `closed`), and an `Overdue Only` toggle. Table/card rows must highlight the **Current Stage**, **Disposition** (distinct from stage), **Assigned Owner**, **Next Action**, and **Due Time**.
* **Case Detail & Source Review (`/cases/[id]`):**
  * Top patient header showing age band, preferred contact channel/language, and caregiver authority status (kept distinct from relationship).
  * Two-column body:
    * **Start Column:** Rule explanation card (`DEMO_WCV_01` / `DEMO_ADULT_01`), contributing source observations with dates, side-by-side **Missing/Conflicting Information** callout, and chronological audit event timeline.
    * **End Column:** Contextual **Action Panel** exposing valid lifecycle transitions (clinician review/approval, outreach invitation, simulated booking, attendance confirmation, referral tracking, and evidence-backed closure) plus a collapsible **FHIR / Audit Inspector** drawer (`#F1F5F9`).
* **Population Dashboard (`/metrics`):** Separate Child and Adult cohort cards displaying explicit numerators and denominators (`Verified Completed / Eligible Due`), separate funnel counts for Invited, Booked, Attended, and Follow-Up, a `Synthetic Demo Metrics` banner, and suppressed small-cell blocks.

## 6. Drop-In CSS Variables (`globals.css`)

```css
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;500;600&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&family=Plus+Jakarta+Sans:wght@600;700&display=swap');

:root {
  --bg-canvas: #f8fafc;
  --bg-surface: #ffffff;
  --bg-subtle: #f1f5f9;
  --border-default: #e2e8f0;

  --brand-primary: #0f5c5c;
  --brand-primary-hover: #0b4646;
  --brand-focus: #0d9488;

  --text-primary: #0f172a;
  --text-secondary: #475569;

  /* Epistemic & Workflow States */
  --status-verified-fg: #15803d;
  --status-verified-bg: #f0fdf4;
  --status-verified-border: #86efac;

  --status-proposed-fg: #6d28d9;
  --status-proposed-bg: #f5f3ff;
  --status-proposed-border: #c4b5fd;

  --status-review-fg: #b45309;
  --status-review-bg: #fffbeb;
  --status-review-border: #fcd34d;

  --status-overdue-fg: #b91c1c;
  --status-overdue-bg: #fef2f2;
  --status-overdue-border: #fca5a5;

  --sim-bar-bg: #1e293b;
  --sim-badge-bg: #f59e0b;
}

html[dir="ltr"] body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  background-color: var(--bg-canvas);
  color: var(--text-primary);
}

html[dir="ltr"] h1,
html[dir="ltr"] h2,
html[dir="ltr"] h3 {
  font-family: 'Plus Jakarta Sans', sans-serif;
}

html[dir="rtl"] body {
  font-family: 'IBM Plex Sans Arabic', sans-serif;
  background-color: var(--bg-canvas);
  color: var(--text-primary);
}

.font-mono-tech {
  font-family: 'JetBrains Mono', monospace;
}

*:focus-visible {
  outline: 2px solid var(--brand-focus);
  outline-offset: 2px;
}

.suppressed-cell {
  background: repeating-linear-gradient(
    -45deg,
    #f1f5f9,
    #f1f5f9 6px,
    #e2e8f0 6px,
    #e2e8f0 12px
  );
}
```
