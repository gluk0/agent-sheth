"""Telegram message handlers."""

from __future__ import annotations

from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import FSInputFile, Message
from aiogram.utils.chat_action import ChatActionSender

from scaffold.config import Settings
from scaffold.custom_video import create_custom_video
from scaffold.jobs import get_job, list_jobs
from scaffold.logging import get_logger
from scaffold.runtime import AgentReply, AgentRuntime
from scaffold.video import create_backend
from scaffold.video.base import RenderError

logger = get_logger(__name__)
router = Router(name="core")

_TELEGRAM_MAX_LEN = 4096
_CAPTION_MAX_LEN = 1024

_START_TEXT = (
    "Hey. I'm your agent scaffold.\n\n"
    "Just talk to me in plain language - I'll route your request to the "
    "right specialist agent.\n\n"
    "Commands:\n"
    "/brew [topic] - make a stoner news reel (optionally about a topic)\n"
    "/custom - send a photo + caption to turn it into a video\n"
    "/jobs - recent content jobs\n"
    "/job <id> - details for one job\n"
    "/help - what I can do"
)

_HELP_TEXT = (
    "Talk to me in natural language and I'll route the request.\n\n"
    "Available:\n"
    "- General chat and questions\n"
    "- Content pipeline: news -> stoner-style Instagram reel\n"
    "- Custom videos from your own image + text\n\n"
    "Commands:\n"
    "/brew - pick the best current story and make a reel\n"
    "/brew ufo hearings - make a reel about a specific topic\n"
    "/custom - send a photo with caption '/custom <prompt>' to animate it\n"
    "/jobs - list recent content jobs\n"
    "/job <id> - resend a job's video and caption"
)

_CUSTOM_USAGE = (
    "Make a custom video two ways:\n\n"
    "1. Text only:\n/custom neon smoke swirling, slow cosmic zoom, vhs grain\n\n"
    "2. Or send a photo with that as its caption - your image seeds the "
    "video and the text drives the motion.\n\n"
    "The text is also used as the caption."
)


def brew_prompt(topic: str | None) -> str:
    """The message sent to the agent when /brew is used."""
    if topic:
        return f"Run the stoner news content pipeline and produce a reel about this topic: {topic}"
    return (
        "Run the stoner news content pipeline. Pick the best current story "
        "yourself and produce a reel."
    )


def parse_custom_caption(caption: str | None) -> str | None:
    """Extract the prompt from a '/custom <text>' photo caption."""
    if caption is None:
        return None
    stripped = caption.strip()
    if not stripped.startswith("/custom"):
        return None
    return stripped.removeprefix("/custom").strip() or None


def _chunks(text: str, size: int = _TELEGRAM_MAX_LEN) -> list[str]:
    """Split a reply into Telegram-sized chunks, preferring newline boundaries."""
    parts: list[str] = []
    remaining = text
    while len(remaining) > size:
        cut = remaining.rfind("\n", 0, size)
        if cut <= 0:
            cut = size
        parts.append(remaining[:cut])
        remaining = remaining[cut:].lstrip("\n")
    if remaining:
        parts.append(remaining)
    return parts


async def _send_reply(message: Message, reply: AgentReply) -> None:
    if reply.video_path is not None and reply.video_path.is_file():
        await message.answer_video(FSInputFile(reply.video_path))
    for chunk in _chunks(reply.text):
        await message.answer(chunk)


async def _run_and_reply(
    message: Message, runtime: AgentRuntime, text: str, route: str | None = None
) -> None:
    if message.from_user is None or message.bot is None:
        return
    user_id = str(message.from_user.id)
    session_id = str(message.chat.id)
    try:
        async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
            async for reply in runtime.run_turn(
                user_id=user_id, session_id=session_id, text=text, route=route
            ):
                await _send_reply(message, reply)
    except Exception:
        logger.exception("turn.failed", user_id=user_id, session_id=session_id)
        await message.answer("Something went wrong handling that - check the logs.")


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    await message.answer(_START_TEXT)


@router.message(Command("help"))
async def on_help(message: Message) -> None:
    await message.answer(_HELP_TEXT)


@router.message(Command("brew"))
async def on_brew(message: Message, command: CommandObject, runtime: AgentRuntime) -> None:
    await message.answer("Brewing... this takes a few minutes.")
    # Explicit command: run the pipeline directly, no LLM routing involved.
    await _run_and_reply(message, runtime, brew_prompt(command.args), route="stoner_pipeline")


@router.message(Command("jobs"))
async def on_jobs(message: Message, settings: Settings) -> None:
    jobs = list_jobs(settings.output_dir)
    if not jobs:
        await message.answer("No content jobs yet. Try /brew.")
        return
    lines = [
        f"{'[video] ' if j.video_path else ''}{j.job_id} - {j.headline} ({j.shots} shots)"
        for j in jobs
    ]
    await message.answer("Recent jobs:\n" + "\n".join(lines) + "\n\nUse /job <id> for details.")


@router.message(Command("job"))
async def on_job(message: Message, command: CommandObject, settings: Settings) -> None:
    if not command.args:
        await message.answer("Usage: /job <id> (see /jobs)")
        return
    job = get_job(settings.output_dir, command.args.strip())
    if job is None:
        await message.answer("No job with that id. See /jobs.")
        return
    if job.video_path is not None:
        await message.answer_video(
            FSInputFile(job.video_path), caption=job.headline[:_CAPTION_MAX_LEN]
        )
    for chunk in _chunks(job.caption_block or "(no caption saved)"):
        await message.answer(chunk)


async def _render_custom(
    message: Message, settings: Settings, prompt: str, image_path: Path | None = None
) -> None:
    if message.bot is None:
        return
    await message.answer("Rendering your custom video...")
    try:
        async with ChatActionSender.upload_video(bot=message.bot, chat_id=message.chat.id):
            result = await create_custom_video(
                prompt=prompt,
                image_path=image_path,
                backend=create_backend(settings),
                output_dir=settings.output_dir,
            )
    except RenderError as exc:
        logger.exception("custom.failed")
        await message.answer(f"Rendering failed: {exc}")
        return
    except Exception:
        logger.exception("custom.failed")
        await message.answer("Something went wrong rendering that - check the logs.")
        return

    await message.answer_video(FSInputFile(result.video_path))
    for chunk in _chunks(f"{result.caption}\n\nJob: {result.job_id}"):
        await message.answer(chunk)


@router.message(Command("custom"))
async def on_custom_text(message: Message, command: CommandObject, settings: Settings) -> None:
    if not command.args:
        await message.answer(_CUSTOM_USAGE)
        return
    await _render_custom(message, settings, command.args.strip())


@router.message(F.photo)
async def on_photo(message: Message, settings: Settings) -> None:
    if message.bot is None or not message.photo:
        return
    prompt = parse_custom_caption(message.caption)
    if prompt is None:
        await message.answer(_CUSTOM_USAGE)
        return

    photo = message.photo[-1]  # largest resolution
    uploads_dir = settings.data_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    image_path = uploads_dir / f"{photo.file_unique_id}.jpg"
    await message.bot.download(photo, destination=image_path)
    await _render_custom(message, settings, prompt, image_path)


@router.message(F.text)
async def on_text(message: Message, runtime: AgentRuntime) -> None:
    if message.text is None:
        return
    await _run_and_reply(message, runtime, message.text)


@router.message()
async def on_unsupported(message: Message) -> None:
    await message.answer("I can only handle text messages for now.")
