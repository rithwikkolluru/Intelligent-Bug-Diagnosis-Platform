# Daily Log

## Day 1

### Done
- Scaffolded the project structure for the bug diagnosis platform.
- Implemented the backend foundation with FastAPI, SQLAlchemy, config, and route scaffolding.
- Added submission logic for paste and file upload processing.
- Wrote initial tests for validation, parsing, redaction, and API behavior.

### Evidence
- Backend app starts with uvicorn and exposes health and submission endpoints.
- pytest confirms the targeted bug submission flow works.

### Learned
- Keep validation and redaction close to the submission service to avoid insecure data handling.
- Using a temporary SQLite override makes API tests isolated and repeatable.

### Blockers
- No blockers at this stage.

### Next
- Finish frontend UI integration and connect it to the FastAPI API.
- Expand CI and documentation placeholders.

## Day 2

### Done
- Added the historical defect pipeline scaffolding: source loaders, cleaning, standardisation, chunking, embeddings, and indexing utilities.
- Documented the current dataset-inspection state, which shows that `data/raw/` is empty in this environment.
- Added test coverage for cleaning, standardisation, chunking, and loader fixture reads.

### Evidence
- `pytest -q tests` passes with the project’s existing suite plus the new RAG-focused coverage.
- The build-index CLI entry point exists and is wired into the backend app package.

### Learned
- The most reliable approach for this project is to keep source-specific logic isolated and preserve stack traces through the full pipeline.
- Because the raw history datasets are absent, the pipeline is designed to work correctly once the files are added, while documenting the current limitation honestly.

### Blockers
- No Mozilla, Eclipse, or Apache raw datasets are present in the repository.

### Next
- Populate `data/raw/` with the actual datasets and run the index build end-to-end.
- Extend the smoke search and evaluation split once real historical defect data is available.
