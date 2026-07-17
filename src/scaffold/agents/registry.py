"""Agent registry.

New agents are added by decorating a factory with :func:`register`::

    from scaffold.agents.registry import register

    @register("my_agent", "What this agent is good at (used by the router)")
    def build(settings: Settings) -> BaseAgent:
        return LlmAgent(name="my_agent", ...)

The package containing the factory must be imported from
``scaffold/agents/__init__.py`` so registration runs at startup.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from google.adk.agents import BaseAgent

from scaffold.config import Settings

AgentFactory = Callable[[Settings], BaseAgent]


@dataclass(frozen=True, slots=True)
class AgentSpec:
    """A registered agent: its routing metadata plus a factory to build it."""

    name: str
    description: str
    factory: AgentFactory


_REGISTRY: dict[str, AgentSpec] = {}


def register(name: str, description: str) -> Callable[[AgentFactory], AgentFactory]:
    """Class/function decorator that registers an agent factory under ``name``."""

    def decorator(factory: AgentFactory) -> AgentFactory:
        if name in _REGISTRY:
            msg = f"Agent {name!r} is already registered"
            raise ValueError(msg)
        _REGISTRY[name] = AgentSpec(name=name, description=description, factory=factory)
        return factory

    return decorator


def specs() -> tuple[AgentSpec, ...]:
    """All registered agents, in registration order."""
    return tuple(_REGISTRY.values())


def get_spec(name: str) -> AgentSpec | None:
    """Look up a single registered agent by name."""
    return _REGISTRY.get(name)


def build_sub_agents(settings: Settings) -> list[BaseAgent]:
    """Instantiate every registered agent."""
    return [spec.factory(settings) for spec in _REGISTRY.values()]


def load_prompt(anchor: str | Path, name: str) -> str:
    """Load a prompt file that lives next to an agent module.

    Usage: ``load_prompt(__file__, "instruction.md")``.
    """
    return (Path(anchor).parent / "prompts" / name).read_text(encoding="utf-8").strip()
