import { diffLines, diffWordsWithSpace } from "diff";
import type { DiffSegment } from "@/lib/api/schemas";

const LARGE = 40_000;

/** Client-side preview diff (jsdiff) as the same `DiffSegment[]` DiffView renders. */
export function previewSegments(before: string, after: string): DiffSegment[] {
  if (before === after) return before ? [{ op: "equal", text: before }] : [];
  const parts =
    before.length + after.length > LARGE ? diffLines(before, after) : diffWordsWithSpace(before, after);
  const out: DiffSegment[] = [];
  for (const p of parts) {
    const op = p.added ? "insert" : p.removed ? "delete" : "equal";
    const last = out[out.length - 1];
    if (last && last.op === op) last.text += p.value;
    else out.push({ op, text: p.value });
  }
  return out;
}

/** True when the segments contain at least one insert or delete. */
export function hasChanges(segments: readonly DiffSegment[]): boolean {
  return segments.some((s) => s.op !== "equal");
}
