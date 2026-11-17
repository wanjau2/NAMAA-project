# MNN — <milestone name>

**Date:** YYYY-MM-DD
**Owner:** Ismail | Alfred | Mark
**Status:** Done | Partial | Mocked | Blocked
**Gate:** which delivery gate this closes (or part of)

## What changed

Two or three sentences. What the product can do now that it could not do before.

## Scope delivered

| Item | Built | Mocked | Not started | Note |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |

State this honestly — the submission must describe the real level of integration,
including any remaining mocks.

## Acceptance checks

| Scenario | Expected | Observed | Pass | Evidence |
| --- | --- | --- | --- | --- |
|  |  |  |  | [../03-evidence/...](../03-evidence/) |

## Non-negotiables re-verified

Tick only what was actually re-checked at this milestone.

- [ ] Synthetic-data notice present on every screen
- [ ] Server rejects invalid transitions (UI cannot force state)
- [ ] Stage and disposition remain separate; no silent relabel to completed
- [ ] Completion requires evidence plus reviewer authorization
- [ ] Missing data produces needs-review with equal visual weight
- [ ] No unreviewed AI output influences rules
- [ ] No unsupported clinical performance claims in UI, deck or pitch
- [ ] Small-cell suppression (n < 10) including complementary totals

## Contract changes

Any change to records, status names, action names, response fields or rule versions.
Fixtures updated before consumers changed? Who was told?

## Known limitations

What a reviewer would reasonably expect that is not there, and why.

## Next

The immediate next action, its owner and its due point.
