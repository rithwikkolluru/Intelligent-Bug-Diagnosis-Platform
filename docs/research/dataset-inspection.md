# Dataset Inspection

## Phase 0 findings

This workspace does not currently contain any real Mozilla, Eclipse, or Apache defect files under `data/raw/`.

Observed directory state from the working tree:

- `data/raw/` contains only `.gitkeep`.
- No CSV, JSONL, Parquet, or compressed dataset files are present.
- Therefore, there are no dataset sizes, licences, or column statistics to report from actual files in this environment.

## Proposed mapping per source

Because the real data is missing, these mappings are documentation placeholders only and are not backed by observed file contents.

- Mozilla: `issue_id` -> original defect identifier; `summary`/`title` -> summary; `description`/`body` -> description; `comments` -> comments list; `status`, `resolution`, `severity`, `priority` -> taxonomy fields; `duplicate_of`/`duplicate` -> duplicate link; `url` -> source_url.
- Eclipse: `id` -> original defect identifier; `summary`/`title` -> summary; `description`, `body`, `details` -> description; `comments` -> comments list; `status`, `resolution`, `severity`, `priority` -> taxonomy fields; `duplicate_of` -> duplicate link; `url` -> source_url.
- Apache: `id` -> original defect identifier; `summary`, `title` -> summary; `description`, `body` -> description; `comments` -> comments list; `status`, `resolution`, `severity`, `priority` -> taxonomy fields; `duplicate_of` -> duplicate link; `url` -> source_url.

## Data quality concerns

- Missing raw datasets: no source directories are populated.
- No licence or provenance metadata could be verified from the repository.
- The pipeline is implemented to handle real data once the files are placed under `data/raw/<source>/`.

## Status

The inspection checkpoint is complete for the current repository state: the data is absent, and the project is ready to process real defect files when they are added.
