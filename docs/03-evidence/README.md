# Evidence

Proof behind the claims in the milestone records. A milestone is not `Done` until its
acceptance checks pass **in the integrated build** and the evidence sits here, linked.

## Layout

```
03-evidence/
  MNN-<slug>/
    checks.md          scenario / expected / observed / owner, one row per check
    screenshots/       UI states, including error, empty, conflict and suppressed cells
    test-output/       pytest, validator and Playwright output as captured, not summarized
    recordings/        demo recordings
```

## Rules

- Record **observed** output, not the output you expected. A failing check recorded honestly
  is worth more than a passing claim that nobody can reproduce.
- No real credentials, tokens or personal information in any screenshot or recording.
- All data shown must be synthetic, and the synthetic-data notice must be visible in frames
  that show clinical content.
- Fixture pass rates are **software evidence**. Never label them diagnostic accuracy,
  calibration or clinical effectiveness.
