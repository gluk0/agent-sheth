"""ADK runtime: owns the Runner, session service, and artifact service.

This is the single seam between channels (Telegram, CLI, ...) and the agent
layer. Channels call :meth:`AgentRuntime.run_turn` and receive the agent's
final text responses.
"""

from __future__ import annotations

import asyncio
import os
from collections import defaultdict
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

from google.adk.agents import BaseAgent
from google.adk.artifacts import BaseArtifactService
from google.adk.artifacts.file_artifact_service import FileArtifactService
from google.adk.runners import Runner
from google.adk.sessions import BaseSessionService, DatabaseSessionService
from google.genai import types

from scaffold.agents import build_root_agent
from scaffold.agents.registry import get_spec
from scaffold.agents.stoner_news.packager import STATE_VIDEO_PATH
from scaffold.config import Settings
from scaffold.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class AgentReply:
    """One outbound reply from the agent: text, optionally with a video."""

    text: str
    video_path: Path | None = None


class AgentRuntime:
    """Wraps an ADK Runner with session bootstrapping and a simple text API."""

    def __init__(
        self,
        settings: Settings,
        *,
        agent: BaseAgent | None = None,
        session_service: BaseSessionService | None = None,
        artifact_service: BaseArtifactService | None = None,
    ) -> None:
        # google-genai reads the key from the environment.
        if settings.google_api_key:
            os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)

        self._settings = settings
        self._session_service = session_service or DatabaseSessionService(
            db_url=settings.session_db_url
        )
        self._artifact_service = artifact_service or FileArtifactService(settings.artifact_dir)
        self._runner = Runner(
            app_name=settings.app_name,
            agent=agent or build_root_agent(settings),
            session_service=self._session_service,
            artifact_service=self._artifact_service,
        )
        # Runners for direct (non-LLM-routed) invocation of registered agents,
        # built lazily. Explicit commands like /brew use these so dispatch is
        # deterministic instead of relying on the router model to transfer.
        self._direct_runners: dict[str, Runner] = {}
        # One turn at a time per session: prevents create_session races when
        # several updates arrive at once and keeps conversation history linear.
        self._turn_locks: defaultdict[tuple[str, str], asyncio.Lock] = defaultdict(asyncio.Lock)

    def _runner_for(self, route: str | None) -> Runner:
        if route is None:
            return self._runner
        if route not in self._direct_runners:
            spec = get_spec(route)
            if spec is None:
                msg = f"No registered agent named {route!r}"
                raise ValueError(msg)
            self._direct_runners[route] = Runner(
                app_name=self._settings.app_name,
                agent=spec.factory(self._settings),
                session_service=self._session_service,
                artifact_service=self._artifact_service,
            )
        return self._direct_runners[route]

    async def run_turn(
        self, *, user_id: str, session_id: str, text: str, route: str | None = None
    ) -> AsyncIterator[AgentReply]:
        """Send one user message and yield final replies.

        ``route`` bypasses the LLM router and runs a registered agent
        directly (shared session, so context is preserved either way).
        """
        runner = self._runner_for(route)
        async with self._turn_locks[(user_id, session_id)]:
            await self._ensure_session(user_id=user_id, session_id=session_id)
            message = types.Content(role="user", parts=[types.Part(text=text)])
            log = logger.bind(user_id=user_id, session_id=session_id, route=route)
            log.info("turn.start", chars=len(text))

            async for event in runner.run_async(
                user_id=user_id, session_id=session_id, new_message=message
            ):
                if not event.is_final_response() or event.content is None:
                    continue
                reply = "".join(part.text for part in event.content.parts or [] if part.text)

                video_path: Path | None = None
                delta = event.actions.state_delta if event.actions else {}
                raw_path = delta.get(STATE_VIDEO_PATH)
                if isinstance(raw_path, str) and raw_path:
                    video_path = Path(raw_path)

                if reply.strip() or video_path is not None:
                    log.info(
                        "turn.response",
                        agent=event.author,
                        chars=len(reply),
                        video=str(video_path) if video_path else None,
                    )
                    yield AgentReply(text=reply, video_path=video_path)

            log.info("turn.done")

    async def close(self) -> None:
        await self._runner.close()  # type: ignore[no-untyped-call]
        for runner in self._direct_runners.values():
            await runner.close()  # type: ignore[no-untyped-call]

    async def _ensure_session(self, *, user_id: str, session_id: str) -> None:
        existing = await self._session_service.get_session(
            app_name=self._settings.app_name, user_id=user_id, session_id=session_id
        )
        if existing is None:
            await self._session_service.create_session(
                app_name=self._settings.app_name, user_id=user_id, session_id=session_id
            )
            logger.info("session.created", user_id=user_id, session_id=session_id)
