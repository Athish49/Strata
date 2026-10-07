"""
T91 Scoring Engine — Strata Corpus Expected-Findings Evaluator

Usage:
    python scoring.py <system_findings_json> [--verbose] [--snapshot S1|S2]

Inputs:
    system_findings_json: Path to a JSON file produced by the Strata engine.
                          Expected schema: {"documents": [{"doc_id": str,
                          "findings": [{"clause_id": str, "citation": str,
                          "finding_type": str, "route_to": {...}}]}]}

Outputs (stdout):
    - Per-document match table
    - Precision / Recall / False-positive rate
    - Routing accuracy
    - Baseline check (if --snapshot S1, asserts zero non-informational findings)
    - Cohen's kappa on finding_type (annotator agreement proxy)

Corpus SHA-256:
    a7adf93afef12d7a7c58008efbca265b3d4dea2f5a27bd18c29eeeeca66937f0
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

EXPECTED_FILE = Path(__file__).parent / "expected_findings.json"
CORPUS_SHA256 = "a7adf93afef12d7a7c58008efbca265b3d4dea2f5a27bd18c29eeeeca66937f0"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_expected() -> dict:
    with open(EXPECTED_FILE) as f:
        return json.load(f)


def is_informational(finding: dict) -> bool:
    return finding.get("finding_type", "") == "informational"


def _strip_subsection(cit: str) -> str:
    """Return citation with trailing subsection designator removed: '170 IAC 1-6-3(2)' → '170 IAC 1-6-3'."""
    import re
    return re.sub(r'\([^)]*\)$', '', cit.strip()).rstrip()


def citation_matches(system_cit: str, expected_cit: str) -> bool:
    """
    Citations match at the section level: strip trailing subsection designators
    from both sides, then require equality. A system detection on a subsection
    of the expected section (or vice versa) counts as a match; a system detection
    on a *different* section does not.
    """
    return _strip_subsection(system_cit) == _strip_subsection(expected_cit)


def clause_matches(system_clause: str, acceptable: list[str], parent_tolerance: bool) -> bool:
    """
    Clause matches when:
      - system_clause is in acceptable_clause_ids, OR
      - parent_tolerance is true and the system_clause is a PARENT of an acceptable
        clause (i.e. an acceptable clause starts with system_clause + '.').
    The spec says a detection on the immediate parent clause is acceptable when
    parent_tolerance is true; a detection on a child does NOT substitute.
    """
    if system_clause in acceptable:
        return True
    if not parent_tolerance:
        return False
    # Parent check: system_clause is a parent when some acceptable id starts with it
    prefix = system_clause + "."
    return any(a.startswith(prefix) for a in acceptable)


def route_matches(system_route: dict, expected_route: dict) -> bool:
    if not system_route or not expected_route:
        return False
    return (
        system_route.get("owner") == expected_route.get("owner")
        and system_route.get("approver") == expected_route.get("approver")
    )


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score(system_file: Path, snapshot: str = "S2", verbose: bool = False) -> None:
    expected_data = load_expected()

    # Verify corpus SHA-256 (informational — does not fail)
    if expected_data.get("corpus_sha256") != CORPUS_SHA256:
        print("WARNING: corpus SHA-256 mismatch in expected_findings.json", file=sys.stderr)

    with open(system_file) as f:
        system_data = json.load(f)

    # Build lookup: doc_id → system findings
    sys_by_doc: dict[str, list[dict]] = defaultdict(list)
    for doc in system_data.get("documents", []):
        for finding in doc.get("findings", []):
            sys_by_doc[doc["doc_id"]].append(finding)

    # -------------------------------------------------------------------------
    # Baseline check
    # -------------------------------------------------------------------------
    if snapshot.upper() == "S1":
        non_info_count = sum(
            1
            for findings in sys_by_doc.values()
            for f in findings
            if not is_informational(f)
        )
        print(f"=== BASELINE CHECK (S1) ===")
        if non_info_count == 0:
            print("PASS — zero non-informational findings on S1 corpus.")
        else:
            print(f"FAIL — {non_info_count} non-informational finding(s) found on S1 corpus (expected 0).")
        return

    # -------------------------------------------------------------------------
    # S2 scoring
    # -------------------------------------------------------------------------

    # Collect expected non-informational findings and must_not_flag sets
    expected_findings_flat: list[dict] = []
    must_not_flag_all: dict[str, set[str]] = defaultdict(set)

    for doc in expected_data["documents"]:
        doc_id = doc["doc_id"]
        for ef in doc.get("findings", []):
            entry = {
                "doc_id": doc_id,
                **ef,
            }
            expected_findings_flat.append(entry)
        for clause in doc.get("must_not_flag", []):
            must_not_flag_all[doc_id].add(clause)

    # Match system findings to expected findings (greedy, order-preserving)
    # Each system finding may satisfy at most one expected finding.
    matched_ids: set[str] = set()          # expected finding_ids already matched
    used_system_ids: set[int] = set()      # system finding object ids already used
    matched_pairs: list[tuple[dict, dict]] = []  # (expected, system)
    unmatched_expected: list[dict] = []

    # For each expected non-informational finding, try to find a system match
    for ef in expected_findings_flat:
        if is_informational(ef):
            continue
        matched = False
        for sf in sys_by_doc.get(ef["doc_id"], []):
            if is_informational(sf):
                continue
            if id(sf) in used_system_ids:
                continue
            if citation_matches(sf.get("citation", ""), ef["citation"]) and \
               clause_matches(sf.get("clause_id", ""), ef["acceptable_clause_ids"], ef["parent_tolerance"]):
                matched_pairs.append((ef, sf))
                matched_ids.add(ef["finding_id"])
                used_system_ids.add(id(sf))
                matched = True
                break
        if not matched:
            unmatched_expected.append(ef)

    # False positives: system non-informational findings that didn't match any expected
    false_positives_non_info: list[dict] = []
    for doc in system_data.get("documents", []):
        doc_id = doc["doc_id"]
        for sf in doc.get("findings", []):
            if is_informational(sf):
                continue
            if id(sf) not in used_system_ids:
                false_positives_non_info.append({"doc_id": doc_id, **sf})

    # False positives on must_not_flag
    false_pos_neg_set: list[dict] = []
    for doc in system_data.get("documents", []):
        doc_id = doc["doc_id"]
        mnf = must_not_flag_all.get(doc_id, set())
        for sf in doc.get("findings", []):
            if sf.get("clause_id", "") in mnf and not is_informational(sf):
                false_pos_neg_set.append({"doc_id": doc_id, **sf})

    # Routing accuracy
    route_correct = sum(
        1 for (ef, sf) in matched_pairs
        if route_matches(sf.get("route_to", {}), ef.get("route_to", {}))
    )

    # Counts
    total_expected_non_info = sum(1 for ef in expected_findings_flat if not is_informational(ef))
    total_system_non_info = sum(
        1
        for findings in sys_by_doc.values()
        for sf in findings
        if not is_informational(sf)
    )
    matched_count = len(matched_pairs)
    # Unique system findings that matched (extra detections on same expected finding are excluded)
    unique_matched_system = len(used_system_ids)

    precision = unique_matched_system / total_system_non_info if total_system_non_info else 0.0
    recall = matched_count / total_expected_non_info if total_expected_non_info else 0.0
    total_mnf_clauses = sum(len(v) for v in must_not_flag_all.values())
    fp_rate = len(false_pos_neg_set) / total_mnf_clauses if total_mnf_clauses else 0.0
    routing_acc = route_correct / matched_count if matched_count else 0.0

    # -------------------------------------------------------------------------
    # Print results
    # -------------------------------------------------------------------------
    print("=" * 70)
    print("STRATA CORPUS SCORING REPORT — T91 Answer Key")
    print(f"Corpus SHA-256: {CORPUS_SHA256[:16]}...")
    print(f"System file:    {system_file}")
    print(f"Snapshot:       {snapshot.upper()}")
    print("=" * 70)

    print(f"\n{'Metric':<40} {'Value':>10}")
    print("-" * 52)
    print(f"{'Expected non-informational findings':<40} {total_expected_non_info:>10}")
    print(f"{'  — medium':<40} {sum(1 for ef in expected_findings_flat if not is_informational(ef) and ef.get('severity')=='medium'):>10}")
    print(f"{'  — low':<40} {sum(1 for ef in expected_findings_flat if not is_informational(ef) and ef.get('severity')=='low'):>10}")
    print(f"{'System non-informational findings':<40} {total_system_non_info:>10}")
    print(f"{'Matched':<40} {matched_count:>10}")
    print(f"{'Recall (overall)':<40} {recall:>10.3f}")
    recall_med = sum(1 for (ef,_) in matched_pairs if ef.get('severity')=='medium')
    exp_med = sum(1 for ef in expected_findings_flat if not is_informational(ef) and ef.get('severity')=='medium')
    recall_low = sum(1 for (ef,_) in matched_pairs if ef.get('severity')=='low')
    exp_low = sum(1 for ef in expected_findings_flat if not is_informational(ef) and ef.get('severity')=='low')
    print(f"{'Recall (medium severity)':<40} {(recall_med/exp_med if exp_med else 0.0):>10.3f}")
    print(f"{'Recall (low severity)':<40} {(recall_low/exp_low if exp_low else 0.0):>10.3f}")
    print(f"{'Precision':<40} {precision:>10.3f}")
    print(f"{'FP rate on negative set':<40} {fp_rate:>10.3f}")
    print(f"{'Routing accuracy (matched)':<40} {routing_acc:>10.3f}")

    print("\n--- Per-Document Status ---")
    expected_by_doc = defaultdict(list)
    for ef in expected_findings_flat:
        expected_by_doc[ef["doc_id"]].append(ef)

    for doc in expected_data["documents"]:
        doc_id = doc["doc_id"]
        exp_status = doc["expected_status"]
        exp_non_info = [ef for ef in expected_by_doc.get(doc_id, []) if not is_informational(ef)]
        sys_non_info = [sf for sf in sys_by_doc.get(doc_id, []) if not is_informational(sf)]
        matched_doc = [p for p in matched_pairs if p[0]["doc_id"] == doc_id]
        sys_status = "flagged" if sys_non_info else "cleared"
        status_ok = "✓" if sys_status == exp_status else "✗"
        print(
            f"  {status_ok} {doc_id:<30} expected={exp_status:<8} "
            f"system={sys_status:<8} "
            f"exp={len(exp_non_info)} sys={len(sys_non_info)} matched={len(matched_doc)}"
        )

    if verbose:
        if unmatched_expected:
            print("\n--- Unmatched Expected Non-Informational Findings ---")
            for ef in unmatched_expected:
                print(f"  {ef['finding_id']} [{ef['doc_id']}] {ef['citation']} "
                      f"({ef['finding_type']}/{ef['severity']})")

        if false_positives_non_info:
            print("\n--- System False Positives (non-informational, no match) ---")
            for sf in false_positives_non_info:
                print(f"  [{sf['doc_id']}] {sf.get('clause_id','')} {sf.get('citation','')} "
                      f"({sf.get('finding_type','')})")

        if false_pos_neg_set:
            print("\n--- False Positives on Negative Set (must_not_flag clauses flagged) ---")
            for sf in false_pos_neg_set:
                print(f"  [{sf['doc_id']}] {sf.get('clause_id','')} {sf.get('citation','')}")

    print()
    # Pass/fail targets
    targets = [
        ("Recall ≥ 0.83", recall >= 0.83),
        ("Precision ≥ 0.80", precision >= 0.80),
        ("FP rate on negative set = 0", fp_rate == 0.0),
        ("Routing accuracy ≥ 0.80", routing_acc >= 0.80 or matched_count == 0),
    ]
    all_pass = True
    for label, result in targets:
        icon = "PASS" if result else "FAIL"
        if not result:
            all_pass = False
        print(f"  [{icon}] {label}")

    print()
    print("Overall:", "PASS" if all_pass else "FAIL")
    print("=" * 70)


# ---------------------------------------------------------------------------
# Finding-type Cohen's kappa helper (for adjudication use)
# ---------------------------------------------------------------------------

def kappa(annotations_a: list[str], annotations_b: list[str]) -> float:
    """
    Compute Cohen's kappa between two annotation lists of equal length.
    Items are finding_type strings.
    """
    if len(annotations_a) != len(annotations_b):
        raise ValueError("Annotation lists must have equal length")
    n = len(annotations_a)
    if n == 0:
        return 1.0
    categories = sorted(set(annotations_a) | set(annotations_b))
    # Observed agreement
    po = sum(1 for a, b in zip(annotations_a, annotations_b) if a == b) / n
    # Expected agreement
    pe = sum(
        (annotations_a.count(c) / n) * (annotations_b.count(c) / n)
        for c in categories
    )
    if pe == 1.0:
        return 1.0
    return (po - pe) / (1.0 - pe)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="T91 Strata corpus scoring engine")
    parser.add_argument("system_findings", help="Path to system findings JSON")
    parser.add_argument("--verbose", action="store_true", help="Show unmatched and FP details")
    parser.add_argument(
        "--snapshot", default="S2", choices=["S1", "S2"],
        help="S1 = baseline check (expect zero non-informational findings); S2 = full scoring"
    )
    args = parser.parse_args()

    score(Path(args.system_findings), snapshot=args.snapshot, verbose=args.verbose)


if __name__ == "__main__":
    main()
