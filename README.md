# agent-scaffold

Telegram-first AI agent scaffold built on [Google ADK](https://google.github.io/adk-docs/).

Talk to a root router agent over Telegram; it delegates to registered
specialist agents. Ships with two: general chat, and a content pipeline that
turns current news into stoner-style Instagram reels (video + caption +
hashtags), rendered via fal.ai or a free local stub.

## Quick start

```sh
cp .env.example .env   # fill in TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USER_IDS, GOOGLE_API_KEY
uv sync
uv run scaffold
```

Message your bot on Telegram. Only allowlisted user IDs get a response.

- `/brew` — pick the best current story and make a reel
- `/brew ufo hearings` — make a reel about a topic
- `/jobs`, `/job <id>` — browse finished content jobs
- or just talk to it in natural language

### Video rendering

`VIDEO_BACKEND=stub` (default) renders free ffmpeg test-pattern clips so the
whole pipeline can be exercised end to end at zero cost. Set
`VIDEO_BACKEND=fal` plus `FAL_KEY` and `FAL_VIDEO_MODEL` to render real AI
video. Requires `ffmpeg` on PATH for clip stitching.

## The content pipeline

`SequentialAgent` of five stages; each stage's output feeds the next via
session state:

1. **news_harvester** — pulls RSS feeds (`RSS_FEEDS`) + Google Search
2. **vibe_curator** — picks the story with the most stoner resonance
3. **script_writer** — persona-voiced 24-40s reel script
4. **visual_director** — shot-by-shot text-to-video prompts (structured `ContentJob`)
5. **packager** — deterministic: renders clips, stitches `final.mp4`, saves
   everything under `data/output/<job_id>/`

The `ContentJob` manifest (`job.json`) is the contract between the creative
stages and rendering — a job can be re-rendered on a different backend
without re-running the LLM stages.

## Layout

```
src/scaffold/
├── config.py            # pydantic-settings, all env config
├── logging.py           # structlog setup
├── runtime.py           # ADK Runner + session/artifact services (channel-agnostic seam)
├── jobs.py              # read-only access to finished jobs on disk
├── agents/
│   ├── registry.py      # @register decorator - how new agents plug in
│   ├── root.py          # router LlmAgent, delegates to registered sub-agents
│   ├── chat/            # default conversational agent
│   └── stoner_news/     # the content pipeline (prompts live in prompts/)
├── video/               # VideoBackend protocol, stub + fal.ai backends, stitcher
└── channels/
    └── telegram/        # aiogram 3 gateway: allowlist, handlers, video delivery
```

## Adding an agent

1. Create `src/scaffold/agents/<name>/agent.py` with a factory decorated by
   `@register("<name>", "description used for routing")`.
2. Import the package from `src/scaffold/agents/__init__.py`.

The root agent picks it up automatically.

## Deployment (Docker)

```sh
docker compose up -d --build
```

Long polling — no inbound ports or TLS needed. State persists in `./data`.

## Development

```sh
uv run ruff format . && uv run ruff check .   # format + lint
uv run mypy                                   # strict type-check
uv run pytest                                 # tests (no API keys needed)
```
