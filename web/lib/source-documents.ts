/**
 * Resolving a case to its source note.
 *
 * The API has no documents-by-case listing, and the two available routes are
 * each incomplete:
 *
 *  - Case factors cite `DocumentReference/<id>`, but some cite documents that
 *    do not exist (case-0002 → doc-synthetic-01 returns 404), and case-0003
 *    cites none at all even though doc-synthetic-31 is linked to it.
 *  - `GET /api/v1/documents/{id}` returns the document's `case_id`, but there
 *    is no way to search from the other direction.
 *
 * So the resolver tries factor-cited ids first, then a small explicitly
 * labelled fallback map, and in BOTH paths verifies the returned document's
 * `case_id` before using it — a wrong guess can never show another patient's
 * note. Raised as Q11; delete the fallback once the API can list a case's
 * documents.
 */

import { api } from "@/lib/api";
import type { CaseOut, DocumentOut, Role } from "@/lib/api-types";

/** Known fixture links. Exists only because the API cannot be asked. */
const FALLBACK_CASE_DOCUMENTS: Record<string, string> = {
  "case-0001": "doc-synthetic-11",
  "case-0003": "doc-synthetic-31",
};

/** Document ids cited by this case's contributing records, in order. */
export function citedDocumentIds(caseOut: CaseOut): string[] {
  const ids = caseOut.detail.factors
    .map((fact) => fact.source)
    .filter((source) => source.startsWith("DocumentReference/"))
    .map((source) => source.slice("DocumentReference/".length));
  return [...new Set(ids)];
}

export function candidateDocumentIds(caseOut: CaseOut): string[] {
  const cited = citedDocumentIds(caseOut);
  const fallback = FALLBACK_CASE_DOCUMENTS[caseOut.id];
  return fallback && !cited.includes(fallback) ? [...cited, fallback] : cited;
}

export type ResolvedDocument =
  | { found: true; document: DocumentOut }
  | { found: false; tried: string[] };

/**
 * Returns the first candidate that exists AND belongs to this case.
 * A document whose `case_id` disagrees is rejected rather than displayed.
 */
export async function resolveCaseDocument(
  session: string,
  role: Role,
  caseOut: CaseOut,
): Promise<ResolvedDocument> {
  const tried = candidateDocumentIds(caseOut);
  for (const id of tried) {
    try {
      const document = await api.getDocument(session, role, id);
      if (document.case_id && document.case_id !== caseOut.id) continue;
      return { found: true, document };
    } catch {
      // 404 or policy denial: try the next candidate.
    }
  }
  return { found: false, tried };
}
