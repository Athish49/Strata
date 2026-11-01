"""
Pure functions for building R2 object key paths.

Key layout (company_id is always a required argument; "rpl" below is an
example value used for illustration):
  company/{company_id}/raw/{doc_id}/{version}/{doc_id}_v{version}.md
  company/{company_id}/raw/{doc_id}/{version}/data/{name}.csv
  company/{company_id}/raw/{doc_id}/{version}/render/{filename}
  company/{company_id}/global/{ingest_run_id}/{filename}
  company/{company_id}/derived/{doc_id}/{version}/clauses.jsonl
  company/{company_id}/derived/{doc_id}/{version}/datasets/{name}.parquet
  company/{company_id}/derived/global/ops/{name}.parquet
  company/{company_id}/ingest_runs/{run_id}/report.json
  company/{company_id}/ingest_runs/{run_id}/llm/{stage}/{unit_id}.json
"""


def sanitize_version(version: str) -> str:
    """Replace spaces with underscores in a version string."""
    return version.replace(" ", "_")


def raw_doc_key(company_id: str, doc_id: str, version: str, filename: str) -> str:
    """Key for a raw document file (e.g. the main .md file)."""
    v = sanitize_version(version)
    return f"company/{company_id}/raw/{doc_id}/{v}/{filename}"


def derived_clauses_key(company_id: str, doc_id: str, version: str) -> str:
    """Key for the derived clauses JSONL file."""
    v = sanitize_version(version)
    return f"company/{company_id}/derived/{doc_id}/{v}/clauses.jsonl"


def report_key(company_id: str, run_id: str) -> str:
    """Key for an ingest run report JSON."""
    return f"company/{company_id}/ingest_runs/{run_id}/report.json"


def llm_key(company_id: str, run_id: str, stage: str, unit_id: str) -> str:
    """Key for an LLM stage output JSON."""
    return f"company/{company_id}/ingest_runs/{run_id}/llm/{stage}/{unit_id}.json"
