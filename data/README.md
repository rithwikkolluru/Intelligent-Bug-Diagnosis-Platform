# Data

This folder holds local data artifacts for the project.

- `raw/`: raw dataset files; keep this git-ignored and local-only
- `processed/`: cleaned and normalized data artifacts
- `samples/`: sample files used for tests and demos

## Expected raw-file layout

Place the historical defect files under:

- `data/raw/mozilla/`
- `data/raw/eclipse/`
- `data/raw/apache/`

The pipeline reads CSV, JSONL, JSON and Parquet files from these source directories.

## Build commands

```bash
cd backend
python -m app.rag.build_index --sample-size 2000
python -m app.rag.build_index --full --model sentence-transformers/all-MiniLM-L6-v2
```

## Current repository state

The raw dataset directories are currently empty in this workspace. The pipeline is prepared for real-source processing, but no Mozilla, Eclipse, or Apache file set is present to inspect or quantify from actual data.
