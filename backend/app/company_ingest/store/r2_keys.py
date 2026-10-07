"""
Pure functions for building R2 object key paths.

Key layout (company_id defaults to "rpl"):
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


def raw_dataset_key(company_id: str, doc_id: str, version: str, name: str) -> str:
    """Key for a raw dataset CSV under a document version."""
    v = sanitize_version(version)
    return f"company/{company_id}/raw/{doc_id}/{v}/data/{name}.csv"


def raw_render_key(company_id: str, doc_id: str, version: str, filename: str) -> str:
    """Key for a rendered artefact under a document version."""
    v = sanitize_version(version)
    return f"company/{company_id}/raw/{doc_id}/{v}/render/{filename}"


def global_file_key(company_id: str, run_id: str, filename: str) -> str:
    """Key for a global ingest-run file."""
    return f"company/{company_id}/global/{run_id}/{filename}"


def derived_clauses_key(company_id: str, doc_id: str, version: str) -> str:
    """Key for the derived clauses JSONL file."""
    v = sanitize_version(version)
    return f"company/{company_id}/derived/{doc_id}/{v}/clauses.jsonl"


def parquet_key(company_id: str, doc_id: str, version: str, name: str) -> str:
    """Key for a per-document derived dataset parquet file."""
    v = sanitize_version(version)
    return f"company/{company_id}/derived/{doc_id}/{v}/datasets/{name}.parquet"


def global_parquet_key(company_id: str, name: str) -> str:
    """Key for a global ops parquet file."""
    return f"company/{company_id}/derived/global/ops/{name}.parquet"


def report_key(company_id: str, run_id: str) -> str:
    """Key for an ingest run report JSON."""
    return f"company/{company_id}/ingest_runs/{run_id}/report.json"


def llm_key(company_id: str, run_id: str, stage: str, unit_id: str) -> str:
    """Key for an LLM stage output JSON."""
    return f"company/{company_id}/ingest_runs/{run_id}/llm/{stage}/{unit_id}.json"
