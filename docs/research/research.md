# Research Notes

## Observed repository state

The project includes the FastAPI bug submission app and supporting tests, but the historical defect data folders are empty. At the moment, `data/raw/` contains only `.gitkeep`; no raw Mozilla, Eclipse, or Apache dataset files are available in this workspace.

## Implication for the RAG pipeline

The Historical Defect Knowledge Base is scaffolded with a source-oriented loader pattern so it can ingest CSV, JSONL, JSON and Parquet inputs when the raw datasets are added. The standardisation layer normalises project IDs, severity and status vocabulary, preserves stack traces, and keeps track of duplicate references.

## Data quality expectations

Once real datasets are available, the most important quality checks are:

- whether summary/description fields are populated,
- whether duplicate links resolve to real defects,
- whether stack traces are preserved without being dropped during cleaning,
- whether severity and status vocabularies are consistent across sources.

## Design decisions

- Keep cleaning conservative: strip HTML and boilerplate but do not delete stack traces.
- Maintain source-specific loaders so project-specific parsing stays isolated.
- Use deterministic sampling and a fixed seed for reproducible experiments.
- Encourage a small, testable sample first and then allow a full dataset run via configuration.
