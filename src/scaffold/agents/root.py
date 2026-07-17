"""Root router agent: delegates each user turn to the best-suited sub-agent."""

from __future__ import annotations

from google.adk.agents import LlmAgent

from scaffold.agents.registry import build_sub_agents, load_prompt, specs
from scaffold.config import Settings


def build_root_agent(settings: Settings) -> LlmAgent:
    """Build the root agent with every registered agent attached as a sub-agent."""
    roster = "\n".join(f"- `{spec.name}`: {spec.description}" for spec in specs())
    instruction = load_prompt(__file__, "root.md").format(roster=roster)
    return LlmAgent(
        name="root",
        model=settings.gemini_model,
        description="Front door: routes user requests to specialist agents.",
        instruction=instruction,
        sub_agents=build_sub_agents(settings),
    )
