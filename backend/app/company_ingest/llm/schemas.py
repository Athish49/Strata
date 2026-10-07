"""Task 5.1.1 — Pydantic v2 schemas for LLM clause enrichment."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.company_ingest.constants import ClauseRole, DocClass


class SemanticParam(BaseModel):
    kind: Literal[
        "condition",
        "exception",
        "party",
        "channel",
        "content_element",
        "applicability",
    ]
    name: str
    value_text: str  # must be copied verbatim from clause text


class CitationLink(BaseModel):
    parameter_index: int  # index into the parameters list this is linked to
    citation_raw: str  # raw citation text


class ClauseEnrichment(BaseModel):
    clause_role: ClauseRole | None = None
    normalized_statement: str | None = None  # ≤ 80 words, active voice
    topic_terms: list[str] = Field(default_factory=list)  # ≤ 6 terms
    parameters: list[SemanticParam] = Field(default_factory=list)
    citation_links: list[CitationLink] = Field(default_factory=list)

    @field_validator("topic_terms")
    @classmethod
    def cap_topic_terms(cls, v: list[str]) -> list[str]:
        return v[:6]


class DocClassification(BaseModel):
    doc_class: DocClass
    reasoning: str | None = None
