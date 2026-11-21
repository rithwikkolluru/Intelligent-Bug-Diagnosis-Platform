from __future__ import annotations

from pathlib import Path


class PromptRegistry:
    """Loads and caches versioned system and task prompts from the filesystem."""

    def __init__(self, base_dir: Path | None = None):
        if base_dir is None:
            # Default to backend/app/agents/prompts
            base_dir = Path(__file__).resolve().parent / "prompts"
        self.base_dir = base_dir
        self._cache: dict[str, str] = {}

    def get_prompt(self, agent_name: str, version: str = "v1") -> str:
        cache_key = f"{agent_name}:{version}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        target_file = self.base_dir / agent_name / f"{version}.md"
        if not target_file.exists():
            target_file_txt = self.base_dir / agent_name / f"{version}.txt"
            if target_file_txt.exists():
                target_file = target_file_txt
            else:
                raise FileNotFoundError(
                    f"Prompt '{version}' for agent '{agent_name}' not found under {self.base_dir / agent_name}."
                )

        content = target_file.read_text(encoding="utf-8").strip()
        self._cache[cache_key] = content
        return content

    def clear(self) -> None:
        self._cache.clear()


_GLOBAL_PROMPT_REGISTRY: PromptRegistry | None = None


def get_prompt_registry() -> PromptRegistry:
    global _GLOBAL_PROMPT_REGISTRY
    if _GLOBAL_PROMPT_REGISTRY is None:
        _GLOBAL_PROMPT_REGISTRY = PromptRegistry()
    return _GLOBAL_PROMPT_REGISTRY
