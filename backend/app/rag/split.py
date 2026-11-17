from __future__ import annotations

import random
from typing import Any

from app.rag.standardise import HistoricalDefect


def build_eval_pairs(defects: list[HistoricalDefect], limit: int = 500, seed: int = 42) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    known_ids = {defect.defect_id for defect in defects}
    for defect in defects:
        dup = defect.duplicate_of
        if not dup or dup not in known_ids:
            continue
        candidates.append({
            "query_defect_id": defect.defect_id,
            "query_text_fields": [defect.summary, defect.description, defect.stack_trace or ""],
            "relevant_defect_ids": [dup],
            "source": defect.project,
        })
    if not candidates:
        return []
    rng = random.Random(seed)
    chosen = rng.sample(candidates, min(limit, len(candidates)))
    return chosen
