# Document Change Detection

## Problem

Documents (1–50 pages) arrive continuously. Filenames may change. Content may or may not differ. An external API extracts document content — each call costs money. Goal: only call the API when content has actually changed.

## Solution

Hash the raw file bytes before any parsing. Compare against the stored hash. Call the extraction API only on mismatch.

- **Algorithm:** xxHash64 (non-cryptographic, ~20x faster than SHA-256)
- **Output:** 16 hex characters per document
- **Collision safety:** 1-in-18-quintillion per comparison; birthday-safe up to ~100M documents
- **No metadata dependency, no file size checks, no content parsing**

## Pipeline

```
Document arrives (raw bytes)
        │
        ▼
   xxHash64(raw bytes)  ←  stream 8KB chunks, no full load into memory
        │
        ▼
   Lookup doc_id in hash store
        │
   ┌────┴────┐
 MATCH     MISMATCH / NEW
   │         │
   ▼         ▼
 SKIP     Call extraction API → store new hash → process content
```

## Document Identity

Filenames are unreliable. Stable `doc_id` options:

| Strategy | When to use |
|---|---|
| Business ID (contract #, invoice #) | Documents have internal identifiers |
| Content-addressable (hash = ID) | Question is "have I seen this exact file?" |
| System-assigned ID | External system tracks document lineage |

## Storage Schema

Any KV store (Redis, DynamoDB, Postgres, SQLite):

```
doc_id        TEXT PRIMARY KEY
content_hash  CHAR(16)          -- xxHash64 hex
last_seen     TIMESTAMP
```

~100 bytes/row. 10M documents ≈ 1 GB.

## Core Implementation

```python
import xxhash

def has_changed(file_path: str, doc_id: str, store) -> bool:
    h = xxhash.xxh64()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    new_hash = h.hexdigest()

    if store.get(doc_id) == new_hash:
        return False

    store.set(doc_id, new_hash)
    return True
```

## Trade-offs

- **Accepted false positive:** a file re-saved with identical content but different bytes (re-export, different compression) triggers an unnecessary API call. This is rare and cheaper than building local parsers for every format.
- **No false negatives:** if bytes match, content is identical — mathematically guaranteed.
- **If adversarial collision resistance is needed:** swap xxHash64 for SHA-256 (64 hex chars, ~20x slower).
