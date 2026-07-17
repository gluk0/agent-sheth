"""Tests for the agent registry and root agent wiring."""

from __future__ import annotations

import pytest
from google.adk.agents import BaseAgent, LlmAgent

import scaffold.agents.registry as registry_module
from scaffold.agents import build_root_agent
from scaffold.agents.registry import AgentSpec, build_sub_agents, register, specs
from scaffold.config import Settings


@pytest.fixture
def clean_registry(monkeypatch: pytest.MonkeyPatch) -> dict[str, AgentSpec]:
    fresh: dict[str, AgentSpec] = {}
    monkeypatch.setattr(registry_module, "_REGISTRY", fresh)
    return fresh


def test_register_and_build(clean_registry: dict[str, AgentSpec], settings: Settings) -> None:
    @register("dummy", "A test agent")
    def build(settings: Settings) -> BaseAgent:
        return LlmAgent(name="dummy", model=settings.gemini_model)

    assert [s.name for s in specs()] == ["dummy"]
    agents = build_sub_agents(settings)
    assert len(agents) == 1
    assert agents[0].name == "dummy"


def test_duplicate_registration_rejected(clean_registry: dict[str, AgentSpec]) -> None:
    @register("dup", "first")
    def build_a(settings: Settings) -> BaseAgent:
        return LlmAgent(name="dup")

    with pytest.raises(ValueError, match="already registered"):

        @register("dup", "second")
        def build_b(settings: Settings) -> BaseAgent:
            return LlmAgent(name="dup")


def test_builtin_chat_agent_is_registered() -> None:
    assert "chat" in {s.name for s in specs()}


def test_root_agent_includes_registered_agents(settings: Settings) -> None:
    root = build_root_agent(settings)
    assert root.name == "root"
    assert "chat" in {a.name for a in root.sub_agents}
    assert "`chat`" in root.instruction
