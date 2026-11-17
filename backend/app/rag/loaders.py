from __future__ import annotations

import csv
import json
from pathlib import Path
from random import Random
from typing import Any, Iterator

from app.rag.config import get_settings


class BaseLoader:
    source_name: str = ""
    supported_extensions = {".csv", ".jsonl", ".json", ".parquet"}

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or get_settings().raw_dir

    def discover_files(self) -> list[Path]:
        if not self.base_dir.exists():
            return []
        files: list[Path] = []
        for p in sorted(self.base_dir.rglob("*")):
            if p.is_file() and p.suffix.lower() in self.supported_extensions:
                files.append(p)
        return files

    def iter_records(self, sample_size: int | None = None, seed: int = 42) -> Iterator[dict[str, Any]]:
        for path in self.discover_files():
            for row in self._read_path(path):
                yield row

    def _read_path(self, path: Path) -> list[dict[str, Any]]:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
                reader = csv.DictReader(handle)
                return [dict(row) for row in reader]
        if suffix in {".jsonl", ".json"}:
            records: list[dict[str, Any]] = []
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                if suffix == ".jsonl":
                    for line in handle:
                        line = line.strip()
                        if line:
                            records.append(json.loads(line))
                else:
                    payload = json.load(handle)
                    if isinstance(payload, list):
                        records.extend(item for item in payload if isinstance(item, dict))
                    elif isinstance(payload, dict):
                        records.append(payload)
            return records
        return []


class MozillaLoader(BaseLoader):
    source_name = "mozilla"


class EclipseLoader(BaseLoader):
    source_name = "eclipse"


class ApacheLoader(BaseLoader):
    source_name = "apache"


def iter_source_records(source: str, sample_size: int | None = None, seed: int = 42) -> list[dict[str, Any]]:
    loaders = {
        "mozilla": MozillaLoader,
        "eclipse": EclipseLoader,
        "apache": ApacheLoader,
    }
    loader_cls = loaders.get(source.lower())
    if loader_cls is None:
        raise ValueError(f"Unsupported source: {source}")
    base_dir = get_settings().raw_dir / source.lower()
    records = list(loader_cls(base_dir).iter_records(sample_size=sample_size, seed=seed))
    if sample_size is not None and sample_size > 0 and len(records) > sample_size:
        rng = Random(seed)
        records = rng.sample(records, sample_size)
    return records


def iter_all_sources(sample_size: int | None = None, seed: int = 42) -> dict[str, list[dict[str, Any]]]:
    return {
        source: iter_source_records(source, sample_size=sample_size, seed=seed)
        for source in ("mozilla", "eclipse", "apache")
    }
