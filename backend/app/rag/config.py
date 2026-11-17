from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RAGSettings:
    project_root: Path = Path(__file__).resolve().parents[3]
    data_dir: Path = project_root / "data"
    raw_dir: Path = data_dir / "raw"
    processed_dir: Path = data_dir / "processed"
    samples_dir: Path = data_dir / "samples"
    chroma_path: Path = project_root / "chroma_db"
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    sample_size: int = 30000
    seed: int = 42
    chunk_size: int = 350
    chunk_overlap: int = 50
    min_comment_length: int = 30
    collection_name: str = "historical-defects"
    batch_size: int = 32
    top_k: int = 5

    @classmethod
    def from_env(cls) -> RAGSettings:
        project_root = Path(os.getenv("RAG_PROJECT_ROOT", str(Path(__file__).resolve().parents[3])))
        return cls(
            project_root=project_root,
            data_dir=project_root / "data",
            raw_dir=project_root / "data" / "raw",
            processed_dir=project_root / "data" / "processed",
            samples_dir=project_root / "data" / "samples",
            chroma_path=project_root / "chroma_db",
            model_name=os.getenv("RAG_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2"),
            sample_size=int(os.getenv("RAG_SAMPLE_SIZE", "30000")),
            seed=int(os.getenv("RAG_SEED", "42")),
            chunk_size=int(os.getenv("RAG_CHUNK_SIZE", "350")),
            chunk_overlap=int(os.getenv("RAG_CHUNK_OVERLAP", "50")),
            min_comment_length=int(os.getenv("RAG_MIN_COMMENT_LENGTH", "30")),
            collection_name=os.getenv("RAG_COLLECTION_NAME", "historical-defects"),
            batch_size=int(os.getenv("RAG_BATCH_SIZE", "32")),
            top_k=int(os.getenv("RAG_TOP_K", "5")),
        )


def get_settings() -> RAGSettings:
    return RAGSettings.from_env()
