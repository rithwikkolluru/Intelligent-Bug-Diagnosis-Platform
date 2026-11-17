from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.rag.config import get_settings


def _normalise_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in metadata.items():
        if value is None:
            cleaned[key] = ""
        elif isinstance(value, (str, int, float, bool)):
            cleaned[key] = value
        else:
            cleaned[key] = str(value)
    return cleaned


class Indexer:
    def __init__(self, collection_name: str | None = None, chroma_path: str | Path | None = None):
        self.settings = get_settings()
        self.collection_name = collection_name or self.settings.collection_name
        self.chroma_path = Path(chroma_path) if chroma_path is not None else self.settings.chroma_path
        self.collection = None
        try:
            import chromadb
            client = chromadb.PersistentClient(path=str(self.chroma_path))
            self.collection = client.get_or_create_collection(name=self.collection_name, metadata={"hnsw:space": "cosine"})
        except Exception:
            self.collection = None

    def upsert(self, chunks: list[dict[str, Any]], embeddings: list[list[float]]) -> list[str]:
        if self.collection is None:
            return []
        ids = [chunk["chunk_id"] for chunk in chunks]
        documents = [chunk["text"] for chunk in chunks]
        metadata = [_normalise_metadata(chunk["metadata"]) for chunk in chunks]
        self.collection.upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadata)
        return ids

    def get_count(self) -> int:
        if self.collection is None:
            return 0
        return self.collection.count()

    def query(self, query_text: str, k: int = 5, where: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.collection is None or self.get_count() == 0:
            return {"documents": [[]], "ids": [[]], "metadatas": [[]], "distances": [[]]}
        from app.rag.embedding import EmbeddingModel
        model = EmbeddingModel()
        vector = model.embed_text(query_text)
        safe_k = min(max(1, k), self.get_count())
        return self.collection.query(query_embeddings=[vector], n_results=safe_k, where=where)

    def export_jsonl(self, path: str | Path, chunks: list[dict[str, Any]]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for chunk in chunks:
                handle.write(json.dumps({"chunk_id": chunk["chunk_id"], "text": chunk["text"], "metadata": chunk["metadata"]}) + "\n")
