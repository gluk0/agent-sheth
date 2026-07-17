"""Tests for AgentRuntime using an in-memory session service and a stub agent."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.events import Event
from google.adk.sessions import InMemorySessionService
from google.genai import types

from scaffold.config import Settings
from scaffold.runtime import AgentRuntime


class EchoAgent(BaseAgent):
    """Deterministic agent: replies 'echo: <input>' without any LLM call."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        text = ""
        if ctx.user_content and ctx.user_content.parts:
            text = ctx.user_content.parts[0].text or ""
        yield Event(
            invocation_id=ctx.invocation_id,
            author=self.name,
            content=types.Content(role="model", parts=[types.Part(text=f"echo: {text}")]),
        )


def _runtime(settings: Settings) -> tuple[AgentRuntime, InMemorySessionService]:
    session_service = InMemorySessionService()
    runtime = AgentRuntime(
        settings,
        agent=EchoAgent(name="echo"),
        session_service=session_service,
        artifact_service=InMemoryArtifactService(),
    )
    return runtime, session_service


async def test_run_turn_yields_agent_reply(settings: Settings) -> None:
    runtime, _ = _runtime(settings)
    replies = [r async for r in runtime.run_turn(user_id="u1", session_id="c1", text="hi")]
    assert [r.text for r in replies] == ["echo: hi"]
    assert replies[0].video_path is None


async def test_session_created_once_and_reused(settings: Settings) -> None:
    runtime, session_service = _runtime(settings)
    async for _ in runtime.run_turn(user_id="u1", session_id="c1", text="one"):
        pass
    async for _ in runtime.run_turn(user_id="u1", session_id="c1", text="two"):
        pass

    session = await session_service.get_session(
        app_name=settings.app_name, user_id="u1", session_id="c1"
    )
    assert session is not None
    user_events = [e for e in session.events if e.author == "user"]
    assert len(user_events) == 2


async def test_separate_chats_get_separate_sessions(settings: Settings) -> None:
    runtime, session_service = _runtime(settings)
    async for _ in runtime.run_turn(user_id="u1", session_id="chat-a", text="a"):
        pass
    async for _ in runtime.run_turn(user_id="u2", session_id="chat-b", text="b"):
        pass

    a = await session_service.get_session(
        app_name=settings.app_name, user_id="u1", session_id="chat-a"
    )
    b = await session_service.get_session(
        app_name=settings.app_name, user_id="u2", session_id="chat-b"
    )
    assert a is not None and b is not None
    assert len(a.events) == 2  # user msg + echo reply
    assert len(b.events) == 2


def test_runtime_boots_full_agent_tree(settings: Settings) -> None:
    """Smoke test: the real root agent (router + chat + pipeline) constructs."""
    runtime = AgentRuntime(
        settings,
        session_service=InMemorySessionService(),
        artifact_service=InMemoryArtifactService(),
    )
    agent = runtime._runner.agent
    assert agent is not None and agent.name == "root"
    assert {a.name for a in agent.sub_agents} == {"chat", "stoner_pipeline"}


async def test_concurrent_turns_same_chat_do_not_race(settings: Settings) -> None:
    """Regression: simultaneous first messages must not double-create the
    session (hit as a sqlite UNIQUE violation with DatabaseSessionService)."""
    import asyncio

    from google.adk.sessions import DatabaseSessionService

    session_service = DatabaseSessionService(db_url=settings.session_db_url)
    runtime = AgentRuntime(
        settings,
        agent=EchoAgent(name="echo"),
        session_service=session_service,
        artifact_service=InMemoryArtifactService(),
    )

    async def one_turn(text: str) -> list[str]:
        return [r.text async for r in runtime.run_turn(user_id="u1", session_id="c1", text=text)]

    results = await asyncio.gather(one_turn("a"), one_turn("b"), one_turn("c"))
    assert sorted(r for batch in results for r in batch) == ["echo: a", "echo: b", "echo: c"]


async def test_direct_route_bypasses_root(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: /brew must run its agent directly, not via the LLM router
    (which can - and did - decide to answer instead of transferring)."""
    import scaffold.agents.registry as registry_module
    from scaffold.agents.registry import AgentSpec

    fresh: dict[str, AgentSpec] = {
        "direct_echo": AgentSpec(
            name="direct_echo",
            description="test agent",
            factory=lambda _settings: EchoAgent(name="direct_echo"),
        )
    }
    monkeypatch.setattr(registry_module, "_REGISTRY", fresh)

    runtime = AgentRuntime(
        settings,
        agent=EchoAgent(name="root_stub"),  # would answer if routing were used
        session_service=InMemorySessionService(),
        artifact_service=InMemoryArtifactService(),
    )
    replies = [
        r
        async for r in runtime.run_turn(
            user_id="u1", session_id="c1", text="hi", route="direct_echo"
        )
    ]
    assert replies[0].text == "echo: hi"


async def test_unknown_route_rejected(settings: Settings) -> None:
    runtime = AgentRuntime(
        settings,
        agent=EchoAgent(name="echo"),
        session_service=InMemorySessionService(),
        artifact_service=InMemoryArtifactService(),
    )
    with pytest.raises(ValueError, match="No registered agent"):
        async for _ in runtime.run_turn(user_id="u1", session_id="c1", text="x", route="missing"):
            pass
