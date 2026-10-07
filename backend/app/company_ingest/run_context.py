"""Task 1.1.2 — RunContext and Issue for a company ingestion run."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel


class Issue(BaseModel):
    severity: Literal["error", "warning", "info"]
    stage: str
    code: str
    message: str
    doc_id: str | None = None
    clause_id: str | None = None
    path: str | None = None
    details: dict = {}


@dataclass
class RunContext:
    run_id: uuid.UUID = field(default_factory=uuid.uuid4)
    company_id: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    no_llm: bool = False
    no_datasets: bool = False
    rebuild: bool = False
    stats: dict[str, int] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)
    llm_cache: dict = field(default_factory=dict)

    def issue(
        self,
        severity: Literal["error", "warning", "info"],
        stage: str,
        code: str,
        message: str,
        **kwargs: Any,
    ) -> None:
        """Append an Issue to the issues list."""
        self.issues.append(
            Issue(severity=severity, stage=stage, code=code, message=message, **kwargs)
        )

    def count(self, key: str, n: int = 1) -> None:
        """Increment stats[key] by n."""
        self.stats[key] = self.stats.get(key, 0) + n

    def to_report(self) -> dict:
        """Return a serialisable report dict.

        ``finished_at`` is set to None here; task 8.1.2 fills it at commit time.
        """
        return {
            "run_id": str(self.run_id),
            "company_id": self.company_id,
            "started_at": self.started_at.isoformat(),
            "no_llm": self.no_llm,
            "no_datasets": self.no_datasets,
            "rebuild": self.rebuild,
            "stats": dict(self.stats),
            "issues": [issue.model_dump() for issue in self.issues],
            "finished_at": None,
        }
