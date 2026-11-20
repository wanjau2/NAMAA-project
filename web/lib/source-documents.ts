/**
 * Resolving a case to its source note.
 *
 * `GET /api/v1/cases/{id}/documents` is authoritative. Factor citations are
 * not probed, and a hardcoded fallback map is not used: a 401/403/429 or
 * transport failure must surface as that failure, not as "no note".
 *
 * 403 and 404 stay indistinguishable. Listed identifiers from a failed
 * request are never shown.
 */

import { api, errorHttpStatus } from "@/lib/api";
import type { CaseOut, DocumentOut, Role } from "@/lib/api-types";
import {
  describeSecurityOutcome,
  type SecurityOutcome,
} from "@/lib/security-states";

export type ResolvedDocument =
  | { status: "found"; document: DocumentOut }
  | { status: "empty" }
  | { status: "unavailable"; outcome: SecurityOutcome; httpStatus: number };

export async function resolveCaseDocument(
  session: string,
  role: Role,
  caseOut: CaseOut,
  signal?: AbortSignal,
): Promise<ResolvedDocument> {
  let listed;
  try {
    listed = await api.listCaseDocuments(session, role, caseOut.id, signal);
  } catch (caught) {
    const httpStatus = errorHttpStatus(caught);
    return {
      status: "unavailable",
      httpStatus,
      outcome: describeSecurityOutcome(httpStatus, "note_retrieve"),
    };
  }

  const first = listed[0];
  if (!first) return { status: "empty" };

  try {
    const document = await api.getDocument(session, role, first.id, signal);
    if (document.case_id && document.case_id !== caseOut.id) {
      return { status: "empty" };
    }
    return { status: "found", document };
  } catch (caught) {
    const httpStatus = errorHttpStatus(caught);
    return {
      status: "unavailable",
      httpStatus,
      outcome: describeSecurityOutcome(httpStatus, "note_retrieve"),
    };
  }
}
