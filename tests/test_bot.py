"""Text-only tests of the assistant, through the LLM Gateway.

The assistant runs on the same instructions, tool schemas and tool functions as in
src/bot.py, without audio or a Pipecat pipeline. Each test sends it one line and checks what
it does: which tools it calls, and what it says, judged by an LLM. The tests need
ASSEMBLYAI_API_KEY (from .env.local or the environment).

    uv run pytest
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import pytest
from openai import AsyncOpenAI
from pipecat.adapters.services.open_ai_adapter import OpenAILLMAdapter

from bot import GREETING, INSTRUCTIONS, LLM_GATEWAY_URL, LLM_MODEL, TOOLS, call_tool

pytestmark = pytest.mark.skipif(
    not os.getenv("ASSEMBLYAI_API_KEY"), reason="needs ASSEMBLYAI_API_KEY for the LLM Gateway"
)

# The judge doesn't need to be fast, so it can be a stronger model
JUDGE_MODEL = "claude-sonnet-4-6"

JUDGE_INSTRUCTIONS = """\
You check a voice agent's reply against what it was meant to do. Answer with PASS or FAIL on \
the first line, then one sentence of reasoning."""


@dataclass
class Turn:
    """What the assistant did with one thing the user said."""

    # (name, arguments, result) for each tool it called, in order
    tool_calls: list[tuple[str, dict, str]] = field(default_factory=list)
    reply: str = ""


class Assistant:
    """The assistant's LLM, run the way the Pipecat pipeline runs it, minus the audio."""

    def __init__(self, client: AsyncOpenAI) -> None:
        self.client = client
        self.tools = OpenAILLMAdapter().to_provider_tools_format(TOOLS)
        self.messages: list[dict] = [
            {"role": "system", "content": INSTRUCTIONS},
            {"role": "assistant", "content": GREETING},
        ]

    async def hear(self, line: str, max_steps: int = 5) -> Turn:
        self.messages.append({"role": "user", "content": line})
        turn = Turn()
        for _ in range(max_steps):
            response = await self.client.chat.completions.create(
                model=LLM_MODEL, messages=self.messages, tools=self.tools
            )
            message = response.choices[0].message
            self.messages.append(message.model_dump(exclude_none=True))
            turn.reply += message.content or ""
            if not message.tool_calls:
                return turn
            for tool_call in message.tool_calls:
                name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments or "{}")
                result = "" if name == "end_call" else call_tool(name, arguments)
                turn.tool_calls.append((name, arguments, result))
                self.messages.append(
                    {"role": "tool", "tool_call_id": tool_call.id, "content": result}
                )
            if any(name == "end_call" for name, _, _ in turn.tool_calls):
                return turn
        pytest.fail(f"the assistant kept calling tools: {turn.tool_calls}")


@pytest.fixture
async def gateway() -> AsyncIterator[AsyncOpenAI]:
    async with AsyncOpenAI(
        base_url=LLM_GATEWAY_URL, api_key=os.environ["ASSEMBLYAI_API_KEY"]
    ) as client:
        yield client


@pytest.fixture
def assistant(gateway: AsyncOpenAI) -> Assistant:
    return Assistant(gateway)


async def test_tells_the_time_with_the_tool(assistant: Assistant, gateway: AsyncOpenAI) -> None:
    turn = await assistant.hear("What time is it in Tokyo right now?")

    name, arguments, result = turn.tool_calls[0]
    assert name == "get_current_time"
    assert "Tokyo" in arguments["timezone"]
    assert not result.startswith("Error")
    await judge(gateway, turn.reply, intent="Tells the user the current time in Tokyo.")


async def test_recovers_from_a_place_without_a_time_zone(
    assistant: Assistant, gateway: AsyncOpenAI
) -> None:
    turn = await assistant.hear("What's the time on the Moon?")

    await judge(
        gateway,
        turn.reply,
        intent=(
            "Doesn't state a made-up time for the Moon. It may explain that the Moon has no "
            "time zone, or offer a time somewhere on Earth instead."
        ),
    )


async def test_replies_are_short_and_speakable(assistant: Assistant, gateway: AsyncOpenAI) -> None:
    turn = await assistant.hear("Can you list all the planets in the solar system?")

    await judge(
        gateway,
        turn.reply,
        intent=(
            "A short reply meant to be spoken aloud: no bullet points, numbered list, markdown "
            "or emojis. Naming the planets in a sentence is fine."
        ),
    )


async def test_hangs_up_after_goodbye(assistant: Assistant) -> None:
    turn = await assistant.hear("That's everything, thanks. Bye!")

    assert "end_call" in [name for name, _, _ in turn.tool_calls]


async def judge(client: AsyncOpenAI, reply: str, *, intent: str) -> None:
    """Fail the test unless the judge says the reply does what `intent` describes."""
    response = await client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[
            {"role": "system", "content": JUDGE_INSTRUCTIONS},
            {"role": "user", "content": f"What it should do: {intent}\n\nThe reply: {reply}"},
        ],
    )
    verdict = (response.choices[0].message.content or "").strip()
    assert verdict.upper().startswith("PASS"), f"{verdict}\n\nThe reply: {reply}"
