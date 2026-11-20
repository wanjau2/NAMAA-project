/**
 * Relate discovery is a hint index only.
 *
 * Candidates never authorize access, imply caregiver authority, or establish
 * eligibility. Convert supporting references into the hint shape the verified-
 * context endpoint accepts; do not invent assembly metadata.
 */

import type { RelateBatch, RelateHint } from "@/lib/api-types";

export function hintsFromRelate(
  ...batches: Array<RelateBatch | null | undefined>
): RelateHint[] {
  const hints: RelateHint[] = [];
  const seen = new Set<string>();
  for (const batch of batches) {
    for (const candidate of batch?.candidates ?? []) {
      for (const reference of candidate.supporting_references ?? []) {
        const slash = reference.indexOf("/");
        if (slash <= 0) continue;
        const resource_type = reference.slice(0, slash);
        const logical_id = reference.slice(slash + 1);
        if (!resource_type || !logical_id) continue;
        const key = `${resource_type}/${logical_id}`;
        if (seen.has(key)) continue;
        seen.add(key);
        hints.push({ resource_type, logical_id });
      }
    }
  }
  return hints;
}

export function relateCandidateCount(
  ...batches: Array<RelateBatch | null | undefined>
): number {
  return batches.reduce(
    (sum, batch) => sum + (batch?.candidates?.length ?? 0),
    0,
  );
}
