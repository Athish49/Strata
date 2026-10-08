import { describe, expect, it } from "vitest";
import * as lucide from "lucide-react";
import { MATCH_PATH_ICONS, VERDICT_SEVERITY_ORDER, VERDICT_TOKENS, verdictToken } from "@/lib/verdict-tokens";

describe("verdict tokens", () => {
  it("covers all verdicts, cleared and noise", () => {
    expect(Object.keys(VERDICT_TOKENS).sort()).toEqual(["action_required", "cleared", "info", "noise", "optional_relaxed", "review", "update_citation"]);
    expect(verdictToken("review").cssVar).toBe("--verdict-review");
  });
  it("uses only red / amber / green / ink-family variables", () => {
    const allowed = /^--(verdict-[a-z-]+|state-cleared|noise|red|red-soft|red-line|green|green-soft|amber|amber-soft|ink(-[2-4])?|surface|surface-muted|border|border-strong)$/;
    for (const [k, tok] of Object.entries(VERDICT_TOKENS)) {
      for (const cls of [tok.text, tok.soft, tok.border, tok.dot, tok.tick]) {
        for (const m of cls.matchAll(/var\((--[a-z0-9-]+)\)/g)) expect(m[1], `${k}: ${cls}`).toMatch(allowed);
      }
    }
  });
  it("icons per spec and real lucide exports", () => {
    expect(VERDICT_TOKENS.update_citation.icon).toBe("Quote");
    expect(VERDICT_TOKENS.optional_relaxed.icon).toBe("ArrowDownRight");
    expect(VERDICT_TOKENS.info.icon).toBe("Info");
    expect(MATCH_PATH_ICONS).toEqual({ direct_section: "Link", direct_rule: "Book", register_hop: "GitBranch", value_echo: "Repeat" });
    for (const icon of [...Object.values(MATCH_PATH_ICONS), ...Object.values(VERDICT_TOKENS).map((t) => t.icon)]) {
      expect((lucide as Record<string, unknown>)[icon], icon).toBeTruthy();
    }
  });
  it("noise is hatched, never a solid fill", () => {
    expect(VERDICT_TOKENS.noise.pill).toBe("hatch");
    expect(VERDICT_TOKENS.noise.soft).not.toMatch(/^bg-/);
  });
  it("severity order lists every verdict once", () => {
    expect([...VERDICT_SEVERITY_ORDER].sort()).toEqual(["action_required", "info", "optional_relaxed", "review", "update_citation"]);
  });
});
