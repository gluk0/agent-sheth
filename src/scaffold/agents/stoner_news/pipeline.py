"""Pipeline assembly: harvest -> curate -> write -> direct -> package."""

from __future__ import annotations

from google.adk.agents import BaseAgent, LlmAgent, SequentialAgent
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.google_search_tool import google_search

from scaffold.agents.registry import load_prompt, register
from scaffold.agents.stoner_news.models import ContentJob
from scaffold.agents.stoner_news.packager import PackagerAgent
from scaffold.agents.stoner_news.tools import build_rss_tool
from scaffold.config import Settings
from scaffold.video import create_backend


def _build_searcher(settings: Settings) -> LlmAgent:
    """google_search is a built-in tool, so it needs its own agent wrapper."""
    return LlmAgent(
        name="news_searcher",
        model=settings.gemini_model,
        description="Searches the web for fresh news stories on a given topic.",
        instruction=(
            "Search the web for current news on the requested topic. "
            "Return the most recent, notable stories as a list with title, "
            "one-line summary, source, and URL. Only report real stories."
        ),
        tools=[google_search],
    )


@register(
    "stoner_pipeline",
    "Creates a stoner-style Instagram news reel end to end: harvests current "
    "news, picks a story, writes a script, and renders a vertical video. Use "
    "for any request to make content, brew a reel, or turn news into a video.",
)
def build_pipeline(settings: Settings) -> BaseAgent:
    harvester = LlmAgent(
        name="news_harvester",
        model=settings.gemini_model,
        description="Gathers current headlines from RSS and web search.",
        instruction=load_prompt(__file__, "harvester.md"),
        tools=[build_rss_tool(settings.rss_feeds), AgentTool(agent=_build_searcher(settings))],
        output_key="news_digest",
    )
    curator = LlmAgent(
        name="vibe_curator",
        model=settings.gemini_model,
        description="Picks the story with the most stoner resonance.",
        instruction=load_prompt(__file__, "curator.md"),
        output_key="curated_story",
    )
    scriptwriter = LlmAgent(
        name="script_writer",
        model=settings.gemini_model,
        description="Writes the reel script in the channel persona.",
        instruction=load_prompt(__file__, "scriptwriter.md"),
        output_key="reel_script",
    )
    visual_director = LlmAgent(
        name="visual_director",
        model=settings.gemini_model,
        description="Turns the script into a render-ready content job.",
        instruction=load_prompt(__file__, "visual_director.md"),
        output_schema=ContentJob,
        output_key="content_job",
    )
    packager = PackagerAgent(
        name="packager",
        description="Renders the content job into the final reel.",
        backend=create_backend(settings),
        output_dir=settings.output_dir,
    )
    # Note: ADK 2.x deprecates SequentialAgent in favor of Workflow, but
    # Workflow cannot yet be used as an LlmAgent sub-agent - which is exactly
    # how this pipeline hangs off the root router. Revisit when ADK allows it.
    return SequentialAgent(
        name="stoner_pipeline",
        description=(
            "End-to-end content pipeline: news to finished stoner-style "
            "Instagram reel with caption and hashtags."
        ),
        sub_agents=[harvester, curator, scriptwriter, visual_director, packager],
    )
