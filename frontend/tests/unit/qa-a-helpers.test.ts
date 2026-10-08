import { describe, expect, it } from "vitest";
import { cleanRationale, firstSentence } from "@/components/engine/findingLine";
import { refineRawDiff } from "@/components/changes/logic";
import { OVERVIEW_LINKS } from "@/components/overview/Funnel";

describe("findingLine helpers", () => {
  it("cleans a double full stop and keeps first sentence", () => {
    expect(cleanRationale("Stale citation..")).toBe("Stale citation.");
    expect(firstSentence("It is stale.. Second sentence.")).toBe("It is stale.");
  });
});

describe("refineRawDiff", () => {
  it("splits a single-paragraph replace into sentences with unchanged ones kept", () => {
    const out = refineRawDiff([
      { op: "delete", line: "One stays. Two old." },
      { op: "insert", line: "One stays. Two new." },
    ])!;
    expect(out.find((l) => l.op === "equal")?.line).toBe("One stays.");
    expect(out.filter((l) => l.op !== "equal")).toHaveLength(2);
  });
  it("leaves diffs that already have unchanged lines alone", () => {
    const lines = [{ op: "equal" as const, line: "a" }, { op: "delete" as const, line: "b" }];
    expect(refineRawDiff(lines)).toEqual(lines);
  });
});

describe("overview links use real filter keys", () => {
  it("only uses nuqs keys of changes and documents", () => {
    for (const href of Object.values(OVERVIEW_LINKS)) {
      const keys = [...new URLSearchParams(href.split("?")[1]).keys()];
      expect(keys.every((k) => ["rpl", "sub", "noise", "cls", "disp", "q", "status"].includes(k))).toBe(true);
    }
  });
});
