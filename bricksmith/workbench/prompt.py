"""Canonical instructions for provider-specific BrickSmith agent runners."""
from pathlib import Path


SYSTEM_PROMPT_PATH = Path(__file__).with_name("system_prompt.md")


def load_system_prompt() -> str:
    """Return the exact system message that a new design-agent run should use."""
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
