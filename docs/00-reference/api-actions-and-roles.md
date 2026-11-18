# API actions and roles (Ismail → Mark)

**Source of truth:** `GET /api/v1/meta/actions` on a running API, and
`web/lib/case-actions.ts` (must stay aligned).

| Action | Role | Notes |
| --- | --- | --- |
| `record_contact_preference` | coordinator | Does not send contact |
| `approve_pathway` | clinical_reviewer | Blocked when `flag_status=needs_review` |
| `send_invitation` | coordinator | Simulated; requires preference |
| `record_decline` | coordinator | Disposition only; stays in denominator |
| `record_unreachable` | coordinator | Not a decline or completion |
| `book_appointment` | coordinator | Simulated; not attendance |
| `record_attendance` | coordinator | DNA does not complete care |
| `record_referral_outcome` | coordinator | Rejection creates reassignment work |
| `reassign_owner` | coordinator | Clears overdue flag |
| `defer_with_recall` | coordinator | Disposition `deferred` |
| `close_as_completed` | clinical_reviewer | Requires evidence + attestation |
| `close_other` | clinical_reviewer | `clinically_closed_other` — not completed |
| `reopen` | clinical_reviewer | Returns to `follow_up/active` |

Headers:

- `X-Namaa-Session` — guest workspace id (required)
- `X-Namaa-Role` — simulated role for the action (default `coordinator`)