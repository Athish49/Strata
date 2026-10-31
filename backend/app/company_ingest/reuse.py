"""Task 5.2 — clause-level reuse (TDD §4.2, architecture §8 "Gate 2").

When a new version of a document is ingested, a clause whose raw text is
byte-identical to a clause of the prior version inherits that clause's
**LLM-derived** enrichment and is marked ``unit._reused = True`` so the LLM
stage skips it.  A one-paragraph edit in a 200-clause policy then reaches the
LLM for one clause, not 200.

Matching
--------
``clauses.text_sha256`` is ``parse/text.py:sha256_text(text_raw)`` — the RAW,
unnormalised text, deliberately different from the document content hash
(task 4.1).  A prior clause is a match when its ``text_sha256`` equals the
unit's AND its ``unit_kind`` / ``section_kind`` are the same.  The structural
check matters because the deterministic role rules (``enrich/roles.py``)
depend on ``unit_kind`` and ``section_kind``, not only on text: an LLM role
was only ever assigned because those rules returned ``None`` for that
structure, so inheriting it is equivalent to re-running the pipeline only when
the structure is unchanged.

Duplicates (boilerplate repeated within one version) are resolved
deterministically: among matching prior clauses the lowest
``(ordinal, clause_id)`` wins, and every new unit with that hash inherits from
that one row.

Inherit vs recompute (the stage-4 double-append question)
--------------------------------------------------------
This runs as stage 3; stage 4 (``enrich_citations`` / ``enrich_parameters`` /
``enrich_roles`` / ...) runs AFTER it on every unit and *appends* to
``unit.citations`` / ``unit.parameters``.  The split chosen here:

* **Recomputed by stage 4, never inherited:** citations, regex parameters and
  deterministic roles (``role_method`` in marker / grammar / heuristic).  They
  are pure functions of the identical text + structure, so recomputing yields
  the same rows, is always consistent with the current regexes, and cannot be
  double-appended.  Citation resolution (stage 6) re-resolves them against the
  NEW version's ``law_as_of``, which is the correct behaviour anyway.
* **Inherited from the prior version:** ``normalized_statement``,
  ``topic_terms``, the ``method='llm'`` parameters, and — only when
  ``role_method == 'llm'`` — ``clause_role`` / ``role_method`` /
  ``assessable``.  These are what the LLM stage would have produced and stage
  4 never regenerates them.

No prior primary key is ever copied: inherited parameters are rebuilt as
in-memory ``ParameterEntry`` objects on the new unit, and
``store/neon.py:insert_clause_parameters`` derives their ``parameter_pk`` from
``stable_uuid(company_id, unit.version_id, ...)`` — the NEW version's id
(task 5.5).

Only clauses that show LLM output in the prior version are reused (an LLM
role, a ``normalized_statement``, ``topic_terms`` or an LLM parameter).
Otherwise a prior version ingested with ``no_llm`` would lock its clauses out
of LLM enrichment forever; such clauses fall through to stage 5, where the
persistent ``llm_extractions`` cache keeps them cheap.

Embedding
---------
The ingest service does no Qdrant embedding; promotion (task 5.6) does.
``units_needing_embedding`` is the filter for that step.  ``unit._reused_from``
holds the prior ``clause_pk`` — the promotion step must COPY the prior
version's vector for a reused unit (point id
``stable_uuid(company_id, prior_version_id, clause_id)``), never omit the
point, because Qdrant is delete-and-replace by ``doc_id``.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, Iterable

from sqlalchemy import text

from app.company_ingest.enrich.parameter_entry import ParameterEntry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.company_ingest.parse.models import ClauseUnit
    from app.company_ingest.run_context import RunContext

__all__ = [
    "is_reused",
    "reuse_from_prior_version",
    "units_needing_embedding",
]

_PRIOR_CLAUSES_SQL = text(
    """
    SELECT CAST(clause_pk AS text) AS clause_pk, clause_id, ordinal, text_sha256,
           unit_kind, section_kind, clause_role, role_method, assessable,
           normalized_statement, topic_terms
      FROM company.clauses
     WHERE company_id = :company_id
       AND doc_id = :doc_id
       AND version_id = CAST(:version_id AS uuid)
     ORDER BY ordinal, clause_id
    """
)

_PRIOR_LLM_PARAMS_SQL = text(
    """
    SELECT CAST(clause_pk AS text) AS clause_pk, kind, value_text, value_num, unit,
           qualifier, day_type, span_start, span_end, verified
      FROM company.clause_parameters
     WHERE clause_pk = ANY(CAST(:clause_pks AS uuid[]))
       AND method = 'llm'
     ORDER BY clause_pk, span_start, span_end, value_text
    """
)


def is_reused(unit: "ClauseUnit") -> bool:
    return bool(getattr(unit, "_reused", False))


def units_needing_embedding(units: Iterable["ClauseUnit"]) -> list["ClauseUnit"]:
    """Units whose vectors must be computed; reused units copy their prior vector."""
    return [u for u in units if not is_reused(u)]


def _ordinal_key(row: Any) -> tuple:
    ordinal = row["ordinal"]
    return (ordinal if ordinal is not None else 1 << 62, str(row["clause_id"]))


async def reuse_from_prior_version(
    session: "AsyncSession",
    company_id: str,
    doc_id: str,
    prior_version_id: str | None,
    units: list["ClauseUnit"],
    ctx: "RunContext | None" = None,
) -> int:
    """Copy LLM-derived enrichment onto units whose text_sha256 matches a prior
    clause.  Sets ``unit._reused = True`` so the LLM stage skips them.
    Returns the reuse count (0 for a first version)."""
    if not prior_version_id or not units:
        return 0
    prior_version_id = str(uuid.UUID(str(prior_version_id)))
    if any(str(u.version_id) == prior_version_id for u in units):
        return 0  # re-ingesting the prior version itself: nothing to inherit

    rows = (
        await session.execute(
            _PRIOR_CLAUSES_SQL,
            {"company_id": company_id, "doc_id": doc_id, "version_id": prior_version_id},
        )
    ).mappings().all()
    if not rows:
        return 0

    # (text_sha256, unit_kind, section_kind) -> first prior row by ordinal.
    best: dict[tuple, Any] = {}
    for row in sorted(rows, key=_ordinal_key):
        key = (row["text_sha256"], row["unit_kind"], row["section_kind"])
        best.setdefault(key, row)

    matches: list[tuple["ClauseUnit", Any]] = []
    for unit in units:
        if is_reused(unit) or not unit.text_sha256:
            continue
        row = best.get((unit.text_sha256, unit.unit_kind, unit.section_kind))
        if row is not None:
            matches.append((unit, row))
    if not matches:
        return 0

    pks = sorted({str(row["clause_pk"]) for _, row in matches})
    param_rows = (
        await session.execute(_PRIOR_LLM_PARAMS_SQL, {"clause_pks": pks})
    ).mappings().all()
    llm_params: dict[str, list[Any]] = {}
    for p in param_rows:
        llm_params.setdefault(str(p["clause_pk"]), []).append(p)

    reused = 0
    for unit, row in matches:
        pk = str(row["clause_pk"])
        params = llm_params.get(pk, [])
        llm_role = row["role_method"] == "llm" and row["clause_role"] is not None
        topic_terms = list(row["topic_terms"] or [])
        if not (llm_role or row["normalized_statement"] is not None or topic_terms or params):
            continue  # no LLM output to inherit (e.g. prior ran with no_llm)

        if llm_role:
            unit.role = row["clause_role"]
            unit.role_method = "llm"
            unit.assessable = row["assessable"]
        unit.normalized_statement = row["normalized_statement"]
        unit.topic_terms = topic_terms
        for p in params:
            unit.parameters.append(
                ParameterEntry(
                    kind=p["kind"],
                    unit=p["unit"],
                    value_text=p["value_text"],
                    value_num=float(p["value_num"]) if p["value_num"] is not None else None,
                    value_source=None,  # recomputed by finalize_parameters
                    qualifier=p["qualifier"],
                    day_type=p["day_type"] or "n_a",
                    span_start=p["span_start"],
                    span_end=p["span_end"],
                    method="llm",
                    verified=bool(p["verified"]) if p["verified"] is not None else True,
                )
            )
        unit._reused = True  # type: ignore[attr-defined]
        unit._reused_from = pk  # type: ignore[attr-defined]
        reused += 1

    if ctx is not None and reused:
        ctx.count("clauses_reused", reused)
    return reused
