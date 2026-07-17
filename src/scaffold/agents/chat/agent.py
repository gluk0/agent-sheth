"""Chat agent definition."""

from __future__ import annotations

from google.adk.agents import BaseAgent, LlmAgent

from scaffold.agents.registry import load_prompt, register
from scaffold.config import Settings


@register(
    "chat",
    "General conversation, questions, status queries, and anything that no "
    "other specialist covers.",
)
def build_chat_agent(settings: Settings) -> BaseAgent:
    return LlmAgent(
        name="chat",
        model=settings.gemini_model,
        description="General-purpose assistant for conversation and questions.",
        instruction=load_prompt(__file__, "instruction.md"),
    )
