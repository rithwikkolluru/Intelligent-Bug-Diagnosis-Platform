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


## Day 3

### Done
- Audited and resolved critical security vulnerabilities: enforced streaming 5MB upload size limits (`MAX_UPLOAD_MB`), filename path-traversal sanitization, extension whitelisting, and migrated to modern FastAPI lifespan handlers.
- Integrated Google Gemini AI (`gemini-2.5-flash`) for real-time root-cause analysis, step-by-step fix recommendations, executable before/after code patches, and verification checklists.
- Engineered a zero-downtime dual-engine architecture: built an intelligent heuristic diagnosis fallback that runs seamlessly if an API key is unconfigured.
- Populated the RAG knowledge base by indexing 36 historical defect chunks across Mozilla, Apache, and Eclipse into ChromaDB using local Sentence Transformers (`all-MiniLM-L6-v2`).
- Re-architected the frontend UI with React + Vite: introduced 1-click demo presets (Java NPE, Python KeyError, JS TypeError, C++ Segfault), clickable recent submissions, interactive Diagnosis Dashboard with 1-click code copying, and an in-app Gemini API Key settings modal.
- Expanded test coverage to 53 comprehensive unit and integration tests (all passing).

### Evidence
- `pytest tests` passes 53/53 tests in ~8 seconds.
- `smoke_search` returns verified cosine similarity defect matches from ChromaDB.
- `POST /api/diagnose` creates bug reports and generates structured diagnoses with historical citations.
- Frontend builds cleanly via `npm run build` in 250ms.

### Learned
- Structuring strict JSON response schemas with LLMs ensures deterministic UI rendering.
- Keeping an automated heuristic fallback alongside the live LLM eliminates demo failures during API outages or quota limits.

### Blockers
- None. The system is end-to-end operational and ready for presentation and evaluation.
