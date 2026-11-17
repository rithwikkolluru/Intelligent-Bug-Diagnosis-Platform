from __future__ import annotations

import argparse
from time import perf_counter

from app.rag.clean import clean_records
from app.rag.config import get_settings
from app.rag.embedding import EmbeddingModel
from app.rag.indexer import Indexer
from app.rag.loaders import iter_all_sources
from app.rag.standardise import standardise_records
from app.rag.chunking import chunk_records


def run_pipeline(sample_size: int | None = None, *, full: bool = False, model: str | None = None, rebuild: bool = False, sources: list[str] | None = None) -> dict[str, object]:
    settings = get_settings()
    if model is not None:
        settings = settings.__class__(**{**settings.__dict__, "model_name": model})
    sample_limit = None if full else (sample_size or settings.sample_size)
    source_names = sources or ["mozilla", "eclipse", "apache"]
    records_by_source: dict[str, list[dict[str, object]]] = {}
    start = perf_counter()

    for source in source_names:
        rows = iter_all_sources(sample_size=sample_limit, seed=settings.seed).get(source, [])
        records_by_source[source] = rows
    load_elapsed = perf_counter() - start

    records_loaded = sum(len(v) for v in records_by_source.values())
    if records_loaded == 0:
        return {
            "sources": source_names,
            "records_loaded": 0,
            "records_cleaned": 0,
            "defects": 0,
            "chunks": 0,
            "embedding_time": 0.0,
            "total_time": perf_counter() - start,
            "index_count": 0,
            "warning": "No raw defect files were found under data/raw/. Add the Mozilla, Eclipse, and Apache datasets to run the full pipeline.",
        }

    cleaned: list[dict[str, object]] = []
    for source_rows in records_by_source.values():
        source_clean, _ = clean_records(source_rows)
        cleaned.extend(source_clean)
    clean_elapsed = perf_counter() - load_elapsed - start

    defects = standardise_records(cleaned)
    standardise_elapsed = perf_counter() - clean_elapsed - start

    chunks = chunk_records(defects, max_tokens=settings.chunk_size, overlap=settings.chunk_overlap, min_comment_length=settings.min_comment_length)
    chunk_elapsed = perf_counter() - standardise_elapsed - start

    model_obj = EmbeddingModel(model_name=settings.model_name)
    texts = [chunk["text"] for chunk in chunks]
    embeddings = model_obj.embed_batch(texts, normalize_embeddings=True, batch_size=settings.batch_size)
    embed_elapsed = perf_counter() - chunk_elapsed - start

    indexer = Indexer(collection_name=settings.collection_name, chroma_path=settings.chroma_path)
    indexer.upsert(chunks, embeddings)
    total_elapsed = perf_counter() - start

    return {
        "sources": source_names,
        "records_loaded": records_loaded,
        "records_cleaned": len(cleaned),
        "defects": len(defects),
        "chunks": len(chunks),
        "embedding_time": embed_elapsed,
        "total_time": total_elapsed,
        "index_count": indexer.get_count(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the historical defect vector index.")
    parser.add_argument("--sample-size", type=int, default=None)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--model", default=None)
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--sources", nargs="*", default=["mozilla", "eclipse", "apache"])
    args = parser.parse_args()
    summary = run_pipeline(sample_size=args.sample_size, full=args.full, model=args.model, rebuild=args.rebuild, sources=args.sources)
    print(summary)


if __name__ == "__main__":
    main()
