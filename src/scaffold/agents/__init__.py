"""Agent packages. Importing this package registers all built-in agents."""

from scaffold.agents import chat as chat  # re-export: registration side effect
from scaffold.agents import stoner_news as stoner_news  # re-export: registration side effect
from scaffold.agents.registry import build_sub_agents, register, specs
from scaffold.agents.root import build_root_agent

__all__ = ["build_root_agent", "build_sub_agents", "register", "specs"]
