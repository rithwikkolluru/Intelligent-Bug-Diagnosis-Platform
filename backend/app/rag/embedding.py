from __future__ import annotations

import hashlib
import os

import numpy as np

from app.rag.config import get_settings


class EmbeddingModel:
    def __init__(self, model_name: str | None = None, device: str | None = None):
        self.model_name = model_name or get_settings().model_name
        self.device = device or ("mps" if os.getenv("PYTORCH_MPS_AVAILABLE") == "1" else "cpu")
        self.model = None
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name, device=self.device)
        except Exception:
            self.model = None
        self.cache_dir = get_settings().project_root / "data" / "processed" / "embeddings"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _fallback_vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        rng = np.random.default_rng(int(digest[:8], 16))
        vector = rng.normal(0, 1, 384).astype(float)
        vector = vector / np.linalg.norm(vector)
        return vector.tolist()

    def count_tokens(self, text: str) -> int:
        if self.model is not None and hasattr(self.model, "tokenizer"):
            try:
                tokens = self.model.tokenizer(text, return_attention_mask=False, return_token_type_ids=False)["input_ids"]
                return len(tokens)
            except Exception:
                pass
        return max(1, len(text.split()))

    def embed_batch(self, texts: list[str], *, normalize_embeddings: bool = True, batch_size: int = 32) -> list[list[float]]:
        if not texts:
            return []
        if self.model is not None:
            embeddings = self.model.encode(list(texts), normalize_embeddings=normalize_embeddings, batch_size=batch_size, show_progress_bar=False)
            return np.asarray(embeddings).astype(float).tolist()
        return [self._fallback_vector(text) for text in texts]

    def embed_text(self, text: str) -> list[float]:
        return self.embed_batch([text], normalize_embeddings=True)[0]

    def cached_vectors(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            key = hashlib.sha256(f"{self.model_name}:{text}".encode()).hexdigest()
            path = self.cache_dir / f"{key}.npy"
            if path.exists():
                vectors.append(np.load(path).astype(float).tolist())
            else:
                vector = self.embed_text(text)
                np.save(path, np.asarray(vector, dtype=float))
                vectors.append(vector)
        return vectors
