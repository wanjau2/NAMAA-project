/**
 * Source offsets are Unicode CODE POINTS, not JavaScript string indices.
 *
 * Alfred's contract (ai/docs/CONTRACTS.md) states it plainly: offsets are
 * zero-based, end-exclusive Unicode code points, and JavaScript must use
 * `Array.from(text).slice(start, end).join("")` or convert explicitly.
 *
 * Python indexes strings by code point; JavaScript by UTF-16 code unit. For
 * ASCII and for Arabic — both inside the BMP — the two agree, which is why
 * this was not visibly broken. They diverge for any astral character (emoji,
 * rarer scripts), and the failure is SILENT: the excerpt stops matching its
 * offsets, the proposal is marked untraceable, and a correct extraction
 * becomes unreviewable.
 *
 * Null offsets mean the source match failed or was ambiguous. The UI must then
 * highlight NOTHING — never the first occurrence of the excerpt, which would
 * invent a provenance the extractor did not claim.
 */

/** Code-point slice. Half-open [start, end). */
export function sliceCodePoints(
  text: string,
  start: number,
  end: number,
): string {
  return Array.from(text).slice(start, end).join("");
}

/** Number of Unicode code points, not UTF-16 code units. */
export function codePointLength(text: string): number {
  return Array.from(text).length;
}

export type OffsetSpan = {
  offset_start: number | null;
  offset_end: number | null;
  excerpt: string;
};

export type Traceability =
  /** The excerpt matches the note at its stated offsets. */
  | { state: "verified"; before: string; match: string; after: string }
  /** The extractor could not locate the excerpt; nothing may be highlighted. */
  | { state: "no_offsets" }
  /** Offsets fall outside the note. */
  | { state: "out_of_range" }
  /** Offsets are inside the note but name different text. */
  | { state: "mismatch"; found: string };

/**
 * Verify a proposal's excerpt against the note it claims to come from, and
 * split the note for highlighting.
 *
 * A matching quote establishes TRACEABILITY, not correctness.
 */
export function traceability(text: string, span: OffsetSpan): Traceability {
  const { offset_start: start, offset_end: end, excerpt } = span;

  if (start === null || end === null) return { state: "no_offsets" };

  const points = Array.from(text);
  if (start < 0 || end > points.length || end <= start) {
    return { state: "out_of_range" };
  }

  const match = points.slice(start, end).join("");
  if (match !== excerpt) return { state: "mismatch", found: match };

  return {
    state: "verified",
    before: points.slice(0, start).join(""),
    match,
    after: points.slice(end).join(""),
  };
}

/** True only when the excerpt is verified against the source. */
export function isTraceable(text: string, span: OffsetSpan): boolean {
  return traceability(text, span).state === "verified";
}
