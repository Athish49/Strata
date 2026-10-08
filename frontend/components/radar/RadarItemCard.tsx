import { AppLink } from "@/lib/app-link";
import { AttributeChip } from "@/components/common/AttributeChip";
import { CitationText } from "@/components/common/CitationText";
import { DocChip } from "@/components/common/DocChip";
import { FutureCue } from "@/components/common/FutureCue";
import type { RadarItem } from "@/lib/api/schemas";
import { formatBasisValue, humanizeKey, screenedLine } from "./logic";

export function BasisChips({ item }: { item: RadarItem }) {
  if (item.attribute_basis.length === 0) return null;
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="Company attributes this was screened against">
      {item.attribute_basis.map((a) => (
        <li key={a.key}>
          <AppLink href={`/app/company#${encodeURIComponent(a.key)}`} className="rounded-[6px] hover:ring-1 hover:ring-border-strong">
            <AttributeChip label={humanizeKey(a.key)}>{formatBasisValue(a.value)}</AttributeChip>
          </AppLink>
        </li>
      ))}
    </ul>
  );
}

export function RadarItemCard({ item, agencyName }: { item: RadarItem; agencyName?: string }) {
  const yes = item.applicable === "yes";
  const unclear = item.applicable === "unclear";
  return (
    <li className="rounded-[12px] border border-border bg-surface p-5" data-testid="radar-item">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <AppLink href={`/app/changes/${encodeURIComponent(item.change_id)}`} className="hover:underline">
          <CitationText className="text-[13px] font-medium">{item.citation}</CitationText>
        </AppLink>
        {item.heading && <span className="text-[15px] font-medium leading-5 text-ink">{item.heading}</span>}
        {agencyName && <span className="ml-auto text-[13px] text-ink-3">{agencyName}</span>}
      </div>

      {item.affected_activity.trim() && (
        <p className="mt-2 text-[14px] leading-5 text-ink-2">
          <span className="text-ink-3">Affects: </span>
          {item.affected_activity.trim()}
        </p>
      )}

      {item.applicable === "no" ? (
        <p className="mt-2 text-[14px] leading-5 text-ink-2">{screenedLine(item)}</p>
      ) : (
        item.reason.trim() && <p className="mt-1.5 text-[14px] leading-5 text-ink-2">{item.reason.trim()}</p>
      )}

      {item.quote.trim() && (
        <blockquote className="mt-3 border-l-2 border-border-strong pl-3 font-serif text-[15px] leading-6 text-ink-2">
          {item.quote.trim()}
        </blockquote>
      )}

      {item.attribute_basis.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-[12px] text-ink-3">{item.applicable === "no" ? "Screened out by" : "Based on"}</span>
          <BasisChips item={item} />
        </div>
      )}

      {item.docs_covering_same_rule.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="text-[12px] text-ink-3">Docs covering the same rule</span>
          {item.docs_covering_same_rule.map((d) => (
            <DocChip key={d} docId={d} href={`/app/documents/${encodeURIComponent(d)}`} />
          ))}
        </div>
      )}

      {(yes || unclear) && (
        <div className="mt-3 flex flex-wrap items-center gap-4">
          {yes && <FutureCue id="map-document" />}
          <FutureCue id="assign-review" />
        </div>
      )}
    </li>
  );
}
