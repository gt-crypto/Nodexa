"""Prompts module for AI Investigation."""
from backend.agent.prompts.system_prompt import INVESTIGATOR_SYSTEM_PROMPT
from backend.agent.prompts.investigation_prompt import build_investigation_user_prompt

__all__ = [
    "INVESTIGATOR_SYSTEM_PROMPT",
    "build_investigation_user_prompt",
]
