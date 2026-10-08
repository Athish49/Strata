/** Marker for documents signed by two people by design (no approver). */
export function TwoSignatureTag() {
  return (
    <span className="inline-flex h-[18px] shrink-0 items-center rounded-[4px] border border-border-strong px-1.5 text-[11px] font-medium text-ink-3">
      Two-signature document
    </span>
  );
}
