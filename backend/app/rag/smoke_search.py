from __future__ import annotations

from typing import Any

from app.rag.indexer import Indexer


def search(query_text: str, k: int = 5, where: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    indexer = Indexer()
    result = indexer.query(query_text=query_text, k=k, where=where)
    docs = result.get("documents", [[]])[0] if result.get("documents") else []
    ids = result.get("ids", [[]])[0] if result.get("ids") else []
    metas = result.get("metadatas", [[]])[0] if result.get("metadatas") else []
    dists = result.get("distances", [[]])[0] if result.get("distances") else []
    ranked: list[dict[str, Any]] = []
    for idx, doc in enumerate(docs):
        dist = dists[idx] if idx < len(dists) else 0.3
        sim = max(0.0, min(1.0, 1.0 - (dist if dist is not None else 0.3)))
        ranked.append({
            "chunk_id": ids[idx] if idx < len(ids) else None,
            "text": doc,
            "metadata": metas[idx] if idx < len(metas) else {},
            "similarity": round(sim, 2),
        })
    return ranked
