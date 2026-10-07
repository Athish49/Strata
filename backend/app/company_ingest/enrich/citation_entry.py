"""CitationEntry dataclass — enrichment output for task 4.1.1."""
from __future__ import annotations

from dataclasses import dataclass

from app.company_ingest.enrich.citations_grammar import ParsedCitation


@dataclass
class CitationEntry:
    """One resolved citation found in (or associated with) a ClauseUnit.

    Produced by enrich_citations() (task 4.1.1).
    Written to the database by 8.1.2.
    """

    parsed: ParsedCitation          # structured form from citations_grammar
    context: str                    # inline | regulatory_basis_table | register_column | front_matter
    span_start: int                 # character offset into ClauseUnit.text_raw
    span_end: int
    resolution_status: str          # resolved | repealed_at_s1 | not_found | external
    code_section_id: str | None     # PK of CodeSection row, if resolved
    in_knowledge_base: bool         # False for external / non-IAC
