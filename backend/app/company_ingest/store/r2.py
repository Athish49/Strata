"""
R2 storage client for the company ingest pipeline.

Write-once semantics:
  - put_* checks whether the key already exists and carries a `sha256` metadata entry.
  - Same sha256 → no-op, returns "unchanged".
  - Different sha256 → raises ValueError.
  - Missing sha256 in existing object metadata, or key absent → proceeds normally.

Every stored object must carry metadata keys:
  sha256, content_type, doc_id, version, profile
"""

import hashlib
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import settings


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------

def _get_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _existing_sha256(client, bucket: str, key: str) -> str | None:
    """
    Return the sha256 stored in the object's metadata, or None if the object
    does not exist or has no sha256 metadata entry.
    """
    try:
        head = client.head_object(Bucket=bucket, Key=key)
        return head.get("Metadata", {}).get("sha256")
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return None
        raise


def _check_write_once(client, bucket: str, key: str, new_sha256: str) -> bool:
    """
    Enforce write-once semantics.

    Returns True  → proceed with upload.
    Returns False → key exists with same sha256 (no-op / "unchanged").
    Raises ValueError → key exists with different sha256.
    """
    existing = _existing_sha256(client, bucket, key)
    if existing is None:
        return True  # key absent or no sha256 tag — proceed
    if existing == new_sha256:
        return False  # identical content — no-op
    raise ValueError(
        f"Key {key!r} exists with different sha256 "
        f"(stored={existing!r}, new={new_sha256!r})"
    )


def _sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def put_bytes(
    key: str,
    data: bytes,
    metadata: dict,
    content_type: str = "application/octet-stream",
    force: bool = False,
) -> str:
    """
    Upload *data* to *key*.

    *metadata* must include: sha256, content_type, doc_id, version, profile.
    If sha256 is absent from *metadata*, it is computed and injected.

    Returns "ok" on a successful upload, "unchanged" if the object already
    exists with the same sha256.

    If *force* is True the write-once guard is bypassed: an existing object
    with a different sha256 is overwritten rather than raising ValueError.
    """
    client = _get_client()
    bucket = settings.R2_BUCKET_NAME

    # Ensure sha256 is present in metadata
    if "sha256" not in metadata:
        metadata = {**metadata, "sha256": _sha256_of(data)}

    if force:
        # Skip write-once guard; still skip if content is identical
        existing = _existing_sha256(client, bucket, key)
        if existing == metadata["sha256"]:
            return "unchanged"
    elif not _check_write_once(client, bucket, key, metadata["sha256"]):
        return "unchanged"

    # boto3 requires all metadata values to be strings
    str_meta = {k: str(v) for k, v in metadata.items()}

    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
        Metadata=str_meta,
    )
    return "ok"


def put_file(key: str, path: Path, metadata: dict) -> str:
    """
    Upload the file at *path* to *key*.

    content_type is inferred from metadata["content_type"] if present,
    otherwise defaults to "application/octet-stream".

    Returns "ok" or "unchanged".
    """
    data = path.read_bytes()
    content_type = metadata.get("content_type", "application/octet-stream")
    return put_bytes(key, data, metadata, content_type)


def get_bytes(key: str) -> bytes:
    """Download and return the raw bytes for *key*."""
    client = _get_client()
    response = client.get_object(Bucket=settings.R2_BUCKET_NAME, Key=key)
    return response["Body"].read()


def exists(key: str) -> bool:
    """Return True if *key* exists in the bucket."""
    client = _get_client()
    try:
        client.head_object(Bucket=settings.R2_BUCKET_NAME, Key=key)
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        raise


def list_prefix(prefix: str) -> list[str]:
    """Return all keys under *prefix* (handles pagination)."""
    client = _get_client()
    bucket = settings.R2_BUCKET_NAME
    keys: list[str] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])
    return keys
