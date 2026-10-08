import { describe, expect, it } from "vitest";
import * as lucide from "lucide-react";
import {
  FUTURE_FEATURES,
  MORE_SOURCES_ITEMS,
  OPTIONAL_PAGE_CUES,
  PAGE_CUES,
  SHELL_CUES,
  SHOW_FUTURE_CUES,
  TOOLTIP_MAX_LENGTH,
  countPageCues,
} from "@/lib/future-features";

describe("future features registry", () => {
  it("is on by default", () => {
    expect(SHOW_FUTURE_CUES).toBe(true);
  });
  it("contains the full catalog", () => {
    const ids = Object.keys(FUTURE_FEATURES);
    expect(ids).toHaveLength(42);
    for (const id of ["notifications", "watch", "upload-document", "track-docket", "comment-letter", "more-sources", "sync-directory"]) {
      expect(ids).toContain(id);
    }
    for (const [key, f] of Object.entries(FUTURE_FEATURES)) expect(f.id).toBe(key);
  });
  it("copy matches the spec for samples", () => {
    expect(FUTURE_FEATURES["notifications"]).toMatchObject({ label: "Alerts", variant: "icon", tooltip: "Get alerted the moment a rule your documents depend on changes." });
    expect(FUTURE_FEATURES["search-ask"].label).toBe('Ask Strata "‹query›"');
    expect(FUTURE_FEATURES["upload-document"].tooltip).toBe("Add a document; Strata splits it into clauses and files it in the right vertical.");
  });
  it("every tooltip is <= 90 chars and fields are non-empty", () => {
    for (const f of Object.values(FUTURE_FEATURES)) {
      expect(f.tooltip.length, f.id).toBeLessThanOrEqual(TOOLTIP_MAX_LENGTH);
      expect(f.label.length, f.id).toBeGreaterThan(0);
      expect(f.tooltip.length, f.id).toBeGreaterThan(0);
    }
    for (const m of MORE_SOURCES_ITEMS) expect(m.tooltip.length).toBeLessThanOrEqual(TOOLTIP_MAX_LENGTH);
  });
  it("icons are real lucide exports", () => {
    for (const f of Object.values(FUTURE_FEATURES)) {
      expect((lucide as Record<string, unknown>)[f.icon], `${f.id}:${f.icon}`).toBeTruthy();
    }
  });
  it("no page has more than 3 cues; all referenced ids exist", () => {
    for (const [page, ids] of Object.entries(PAGE_CUES)) {
      expect(countPageCues(page), page).toBeLessThanOrEqual(3);
      for (const id of ids) expect(FUTURE_FEATURES[id], `${page}:${id}`).toBeDefined();
    }
    for (const ids of Object.values(OPTIONAL_PAGE_CUES)) for (const id of ids) expect(FUTURE_FEATURES[id]).toBeDefined();
    for (const id of SHELL_CUES) expect(FUTURE_FEATURES[id]).toBeDefined();
  });
  it("shell cues are not placed on pages", () => {
    for (const ids of Object.values(PAGE_CUES)) for (const id of ids) expect(SHELL_CUES).not.toContain(id);
  });
  it("every non-shell registry entry is placed on some page", () => {
    const placed = new Set([...Object.values(PAGE_CUES).flat(), ...Object.values(OPTIONAL_PAGE_CUES).flat(), ...SHELL_CUES]);
    // continuous-monitoring etc. are all listed; nothing orphaned.
    for (const id of Object.keys(FUTURE_FEATURES)) expect(placed.has(id), id).toBe(true);
  });
});
