from __future__ import annotations

from typing import Any

from app.rag.indexer import Indexer


def search(query_text: str, k: int = 5, where: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    indexer = Indexer()
    result = indexer.query(query_text=query_text, k=k, where=where)
    docs = result.get("documents", [[]])[0]
    ids = result.get("ids", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    ranked: list[dict[str, Any]] = []
    for idx, doc in enumerate(docs):
        ranked.append({
            "chunk_id": ids[idx] if idx < len(ids) else None,
            "text": doc,
            "metadata": metas[idx] if idx < len(metas) else {},
        })
    return ranked
