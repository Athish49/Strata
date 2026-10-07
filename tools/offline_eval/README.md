# Offline Quality Evaluation

This tool compares the ingest engine's outputs against the synthetic corpus basis files.

## Security note

`compare_basis.py` is the ONLY file in this repository that may read `*.basis.json` files.
It must never be imported by anything under `backend/app/`.
The information barrier exists to prevent basis data from entering any database.
Run this tool manually after a full ingest run; never call it from the ingest pipeline.

## Usage

```bash
python tools/offline_eval/compare_basis.py \
    --run-id <uuid> \
    --corpus-root /path/to/corpus \
    --clauses-jsonl-dir /path/to/derived/clauses
```

Output: `tools/offline_eval/out/report_<run_id>.md`
