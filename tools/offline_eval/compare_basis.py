"""Offline quality evaluation — compare ingest engine output against basis files.

INFORMATION BARRIER
-------------------
This is the ONLY file in this repository that may read *.basis.json files.
It must never be imported by anything under backend/app/.
Run this tool manually after a full ingest run; never call it from the pipeline.

Usage
-----
python tools/offline_eval/compare_basis.py \\
    --run-id <uuid> \\
    --corpus-root /path/to/corpus \\
    --clauses-jsonl-dir /path/to/derived/clauses
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Types (plain dicts to keep this file dependency-free)
# ---------------------------------------------------------------------------

BasisClause = dict[str, Any]   # from *.basis.json
EngineClause = dict[str, Any]  # from clauses.jsonl


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def load_basis_docs(corpus_root: Path) -> dict[str, list[BasisClause]]:
    """Return {doc_id: [basis_clause, ...]} for every *.basis.json found."""
    result: dict[str, list[BasisClause]] = {}
    docs_dir = corpus_root / "docs"
    if not docs_dir.is_dir():
        return result
    for doc_dir in sorted(docs_dir.iterdir()):
        if not doc_dir.is_dir():
            continue
        basis_file = doc_dir / f"{doc_dir.name}.basis.json"
        if basis_file.exists():
            data = json.loads(basis_file.read_text(encoding="utf-8"))
            doc_id = data.get("doc_id", doc_dir.name)
            result[doc_id] = data.get("clauses", [])
    return result


def load_engine_clauses(clauses_jsonl_dir: Path) -> dict[str, EngineClause]:
    """Return {clause_id: engine_clause} by scanning all clauses.jsonl under the dir."""
    result: dict[str, EngineClause] = {}
    for jsonl_path in sorted(clauses_jsonl_dir.rglob("clauses.jsonl")):
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            cid = obj.get("clause_id")
            if cid:
                result[cid] = obj
    return result


# ---------------------------------------------------------------------------
# Pure computation helpers
# ---------------------------------------------------------------------------


def _normalize_value(text: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation for loose matching."""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)
    return text


def _spans_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """Return True if [a_start, a_end) overlaps [b_start, b_end)."""
    return a_start < b_end and b_start < a_end


def _engine_cited_sections(engine_clause: EngineClause) -> list[str]:
    """Extract cited section keys from an engine clause's citations list."""
    sections: list[str] = []
    for c in engine_clause.get("citations", []):
        nk = c.get("normalized_key") or c.get("code_section_id")
        if nk:
            sections.append(nk)
    return sections


# ---------------------------------------------------------------------------
# Role agreement
# ---------------------------------------------------------------------------


def compute_role_agreement(
    basis_clauses: list[BasisClause],
    engine_by_id: dict[str, EngineClause],
) -> dict[str, Any]:
    """Compare basis clause_type to engine role for every matched clause.

    Returns:
        {
            "total": int,
            "matched": int,
            "agreement_pct": float,
            "misses": [(clause_id, basis_type, engine_role), ...],
        }
    """
    total = 0
    matched = 0
    misses: list[tuple[str, str, str]] = []

    for bc in basis_clauses:
        basis_type = bc.get("clause_type")
        if not basis_type:
            continue
        cid = bc.get("clause_id", "")
        ec = engine_by_id.get(cid)
        engine_role = ec.get("role") if ec else None
        total += 1
        if engine_role and engine_role == basis_type:
            matched += 1
        else:
            misses.append((cid, basis_type, engine_role or "MISSING"))

    pct = (matched / total * 100) if total else 0.0
    return {
        "total": total,
        "matched": matched,
        "agreement_pct": round(pct, 1),
        "misses": misses,
    }


# ---------------------------------------------------------------------------
# Confusion matrix
# ---------------------------------------------------------------------------


def build_confusion_matrix(
    basis_clauses: list[BasisClause],
    engine_by_id: dict[str, EngineClause],
) -> dict[tuple[str, str], int]:
    """Build a {(basis_type, engine_role): count} confusion matrix."""
    matrix: dict[tuple[str, str], int] = defaultdict(int)
    for bc in basis_clauses:
        basis_type = bc.get("clause_type")
        if not basis_type:
            continue
        cid = bc.get("clause_id", "")
        ec = engine_by_id.get(cid)
        engine_role = (ec.get("role") if ec else None) or "MISSING"
        matrix[(basis_type, engine_role)] += 1
    return dict(matrix)


# ---------------------------------------------------------------------------
# Parameter recall
# ---------------------------------------------------------------------------


def compute_parameter_recall(
    basis_clauses: list[BasisClause],
    engine_by_id: dict[str, EngineClause],
) -> dict[str, Any]:
    """For regulatory_restatement clauses: how many basis parameters are recalled.

    A basis parameter matches an engine parameter in the same clause if:
    - Their spans overlap, OR
    - Their value_text is equal after normalization.

    Returns:
        {
            "total": int,   # basis parameters across qualifying clauses
            "found": int,   # matched by engine
            "recall_pct": float,
            "misses": [(clause_id, basis_param_value, basis_param_span), ...],
        }
    """
    total = 0
    found = 0
    misses: list[tuple[str, str, Any]] = []

    for bc in basis_clauses:
        if bc.get("clause_type") != "regulatory_restatement":
            continue
        cid = bc.get("clause_id", "")
        ec = engine_by_id.get(cid)
        engine_params = ec.get("parameters", []) if ec else []

        for bp in bc.get("parameters", []):
            total += 1
            b_span = bp.get("span", [0, 0])
            b_start, b_end = (b_span[0], b_span[1]) if len(b_span) >= 2 else (0, 0)
            b_value = _normalize_value(bp.get("value_text", ""))

            hit = False
            for ep in engine_params:
                e_start = ep.get("span_start", 0)
                e_end = ep.get("span_end", 0)
                e_value = _normalize_value(ep.get("value_text", ""))

                if _spans_overlap(b_start, b_end, e_start, e_end):
                    hit = True
                    break
                if b_value and e_value and b_value == e_value:
                    hit = True
                    break

            if hit:
                found += 1
            else:
                misses.append((cid, bp.get("value_text", ""), b_span))

    pct = (found / total * 100) if total else 0.0
    return {
        "total": total,
        "found": found,
        "recall_pct": round(pct, 1),
        "misses": misses,
    }


# ---------------------------------------------------------------------------
# Citation agreement
# ---------------------------------------------------------------------------


def compute_citation_agreement(
    basis_clauses: list[BasisClause],
    engine_by_id: dict[str, EngineClause],
) -> dict[str, Any]:
    """For basis clauses with citations, check if all appear in engine cited_sections.

    Returns:
        {
            "total": int,   # total basis citations across all qualifying clauses
            "found": int,   # citations present in engine
            "agreement_pct": float,
            "misses": [(clause_id, missing_citation), ...],
        }
    """
    total = 0
    found = 0
    misses: list[tuple[str, str]] = []

    for bc in basis_clauses:
        basis_cites = bc.get("citations", [])
        if not basis_cites:
            continue
        cid = bc.get("clause_id", "")
        ec = engine_by_id.get(cid)
        engine_sections = set(_engine_cited_sections(ec) if ec else [])

        for cite in basis_cites:
            total += 1
            if cite in engine_sections:
                found += 1
            else:
                misses.append((cid, cite))

    pct = (found / total * 100) if total else 0.0
    return {
        "total": total,
        "found": found,
        "agreement_pct": round(pct, 1),
        "misses": misses,
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def _format_confusion_matrix(matrix: dict[tuple[str, str], int]) -> str:
    """Render confusion matrix as a Markdown table."""
    if not matrix:
        return "_No data_\n"

    basis_types = sorted({k[0] for k in matrix})
    engine_roles = sorted({k[1] for k in matrix})

    header = "| basis_type \\ engine_role | " + " | ".join(engine_roles) + " |"
    sep = "| --- | " + " | ".join(["---"] * len(engine_roles)) + " |"
    rows = [header, sep]
    for bt in basis_types:
        cells = [str(matrix.get((bt, er), 0)) for er in engine_roles]
        rows.append(f"| {bt} | " + " | ".join(cells) + " |")
    return "\n".join(rows) + "\n"


def generate_report(
    run_id: str,
    role_stats: dict[str, Any],
    param_stats: dict[str, Any],
    cite_stats: dict[str, Any],
    confusion_matrix: dict[tuple[str, str], int],
) -> str:
    """Render the evaluation report as a Markdown string."""
    lines: list[str] = []

    lines.append(f"# Offline Quality Evaluation Report")
    lines.append(f"")
    lines.append(f"**Run ID:** {run_id}")
    lines.append(f"")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value | Target |")
    lines.append("| --- | --- | --- |")
    lines.append(
        f"| Role agreement | {role_stats['agreement_pct']}% "
        f"({role_stats['matched']}/{role_stats['total']}) | ≥ 90% |"
    )
    lines.append(
        f"| Parameter recall | {param_stats['recall_pct']}% "
        f"({param_stats['found']}/{param_stats['total']}) | ≥ 95% |"
    )
    lines.append(
        f"| Citation agreement | {cite_stats['agreement_pct']}% "
        f"({cite_stats['found']}/{cite_stats['total']}) | — |"
    )
    lines.append("")
    lines.append(
        "> **Note:** targets: role agreement ≥ 90%, parameter recall ≥ 95%; "
        "these are tracked, not enforced."
    )
    lines.append("")

    # Confusion matrix
    lines.append("## Confusion Matrix (basis_type vs engine_role)")
    lines.append("")
    lines.append(_format_confusion_matrix(confusion_matrix))

    # Top 10 misses
    lines.append("## Top 10 Misses")
    lines.append("")

    lines.append("### Role misses")
    lines.append("")
    role_misses = role_stats.get("misses", [])[:10]
    if role_misses:
        lines.append("| clause_id | basis_type | engine_role |")
        lines.append("| --- | --- | --- |")
        for cid, bt, er in role_misses:
            lines.append(f"| {cid} | {bt} | {er} |")
    else:
        lines.append("_None_")
    lines.append("")

    lines.append("### Parameter recall misses")
    lines.append("")
    param_misses = param_stats.get("misses", [])[:10]
    if param_misses:
        lines.append("| clause_id | value_text | span |")
        lines.append("| --- | --- | --- |")
        for cid, vt, span in param_misses:
            lines.append(f"| {cid} | {vt} | {span} |")
    else:
        lines.append("_None_")
    lines.append("")

    lines.append("### Citation agreement misses")
    lines.append("")
    cite_misses = cite_stats.get("misses", [])[:10]
    if cite_misses:
        lines.append("| clause_id | missing_citation |")
        lines.append("| --- | --- |")
        for cid, cite in cite_misses:
            lines.append(f"| {cid} | {cite} |")
    else:
        lines.append("_None_")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare ingest engine output against synthetic corpus basis files.",
        epilog=(
            "INFORMATION BARRIER: this script is the only file that may read "
            "*.basis.json files. Never import it from backend/app/."
        ),
    )
    parser.add_argument("--run-id", required=True, help="UUID for this evaluation run")
    parser.add_argument(
        "--corpus-root", required=True, help="Root of the synthetic corpus"
    )
    parser.add_argument(
        "--clauses-jsonl-dir",
        required=True,
        help="Directory containing per-doc clauses.jsonl files",
    )
    parser.add_argument(
        "--output-dir",
        default="tools/offline_eval/out",
        help="Directory where the report will be written",
    )
    args = parser.parse_args()

    corpus_root = Path(args.corpus_root)
    clauses_dir = Path(args.clauses_jsonl_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading basis docs from {corpus_root} ...", file=sys.stderr)
    basis_by_doc = load_basis_docs(corpus_root)
    total_docs = len(basis_by_doc)
    print(f"  Found {total_docs} basis doc(s).", file=sys.stderr)

    print(f"Loading engine clauses from {clauses_dir} ...", file=sys.stderr)
    engine_by_id = load_engine_clauses(clauses_dir)
    print(f"  Found {len(engine_by_id)} engine clause(s).", file=sys.stderr)

    # Flatten all basis clauses
    all_basis: list[BasisClause] = []
    for clauses in basis_by_doc.values():
        all_basis.extend(clauses)

    print("Computing metrics ...", file=sys.stderr)
    role_stats = compute_role_agreement(all_basis, engine_by_id)
    confusion_matrix = build_confusion_matrix(all_basis, engine_by_id)
    param_stats = compute_parameter_recall(all_basis, engine_by_id)
    cite_stats = compute_citation_agreement(all_basis, engine_by_id)

    report = generate_report(
        args.run_id, role_stats, param_stats, cite_stats, confusion_matrix
    )

    out_path = output_dir / f"report_{args.run_id}.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"Report written to {out_path}", file=sys.stderr)

    # Print summary to stdout
    print(f"Role agreement:    {role_stats['agreement_pct']}%")
    print(f"Parameter recall:  {param_stats['recall_pct']}%")
    print(f"Citation agreement:{cite_stats['agreement_pct']}%")


if __name__ == "__main__":
    main()
