"""A voice agent starter where every model is AssemblyAI's, on one API key.

- Text-to-speech: AssemblyAI streaming TTS, with word-level timings (src/assemblyai_tts.py)
- Speech-to-text: Universal-3.6 Pro streaming, which also decides when the user has finished
  their turn
- LLM: LLM Gateway, an OpenAI-compatible API for models from Google, OpenAI, Anthropic and more

Each setting below names the skill in skills/ that explains when and how to change it.

    uv run src/bot.py               # talk to the agent in your browser at http://localhost:7860
    uv run src/bot.py -t daily      # or in a Daily room
    uv run src/bot.py -t twilio -x <your-ngrok-host>   # or on a phone number
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import EndWorkerFrame, FunctionCallResultProperties, TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.assemblyai.stt import AssemblyAISTTService
from pipecat.services.llm_service import FunctionCallParams
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.daily.transport import DailyParams
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams
from pipecat.workers.runner import WorkerRunner

from assemblyai_tts import AssemblyAITTSService

load_dotenv(Path(__file__).parents[1] / ".env.local")

# --- Voice: skills/tts-voice ---

# A voice id from https://www.assemblyai.com/docs/tts/voices, or one of your cloned voices
TTS_VOICE = "987db62e-a2c2-569a-9c4d-82460cdea1bd"  # Keegan

# The agent introduces itself by the voice's name; if you change one, change the other
ASSISTANT_NAME = "Keegan"

# --- Speech-to-text ---

# How quickly a turn ends versus how accurate the transcript is: "min_latency", "balanced"
# or "max_accuracy". See skills/turn-detection.
STT_MODE = "balanced"

# How loud speech must be to count, for transcription and for interrupting the agent. The
# STT and Silero use the same value. See skills/interruptions-and-vad.
VAD_THRESHOLD = 0.2

# Names and terms the STT should spell right. See skills/keyterms-and-prompt.
STT_KEYTERMS = [ASSISTANT_NAME]

# --- LLM: skills/llm-model ---

# Any model from https://llm-gateway.assemblyai.com/v1/models that supports tools
LLM_MODEL = "gemma-4-31b"
LLM_GATEWAY_URL = "https://llm-gateway.assemblyai.com/v1"

GREETING = f"Hi, I'm {ASSISTANT_NAME}. How can I help?"

INSTRUCTIONS = f"""\
You are {ASSISTANT_NAME}, a friendly voice assistant. You're talking with someone live, and \
everything you write is spoken aloud by a text-to-speech voice.

What you do: chat about anything and answer questions, and tell the time anywhere in the \
world with get_current_time.

How to talk:
- Keep each reply to one or two short sentences, and ask one question at a time.
- Don't use lists, markdown, emojis or abbreviations that sound odd aloud.
- When you read back a phone number, code or ID, separate every character with a space and \
group them with commas, like "5 1 2, 5 5 5, 0 1 3 4".
- If you didn't catch something, say so and ask again, rather than guessing.

Only state facts from your tools or that you're sure of. When the person has nothing else, \
say a short goodbye and call end_call."""


class ToolError(Exception):
    """A tool failed in a way the LLM can recover from; the message tells it how."""


# The tools. Each takes the LLM's arguments and returns what to tell the LLM. They don't
# depend on Pipecat, so tests can call them directly. See skills/add-a-tool.


def get_current_time(timezone: str) -> str:
    try:
        now = datetime.now(ZoneInfo(timezone))
    except (ZoneInfoNotFoundError, ValueError):
        raise ToolError(
            f"{timezone!r} isn't a time zone. Use an IANA name such as America/Chicago."
        ) from None
    hour = now.hour % 12 or 12
    meridiem = "AM" if now.hour < 12 else "PM"
    return f"It's {hour}:{now:%M} {meridiem} on {now:%A, %B} {now.day} in {timezone}."


TOOL_FUNCTIONS = {f.__name__: f for f in (get_current_time,)}


def call_tool(name: str, arguments: dict[str, Any]) -> str:
    """Run one of the tools, turning a ToolError into a message for the LLM."""
    try:
        return TOOL_FUNCTIONS[name](**arguments)
    except ToolError as e:
        return f"Error: {e}"


async def _run_tool(params: FunctionCallParams) -> None:
    await params.result_callback(call_tool(params.function_name, dict(params.arguments)))


async def _end_call(params: FunctionCallParams) -> None:
    # The goodbye is already queued ahead of this, so the call ends once it's been spoken
    await params.result_callback(None, properties=FunctionCallResultProperties(run_llm=False))
    await params.llm.push_frame(EndWorkerFrame(reason="the assistant ended the call"))


# What the LLM sees of the tools. Keep the descriptions accurate: they're the tools' docs.
TOOLS = ToolsSchema(
    standard_tools=[
        FunctionSchema(
            "get_current_time",
            "Get the current date and time somewhere in the world.",
            properties={
                "timezone": {
                    "type": "string",
                    "description": 'The place\'s IANA time zone, such as "Europe/London"',
                }
            },
            required=["timezone"],
            handler=_run_tool,
        ),
        FunctionSchema(
            "end_call",
            "Hang up, after you've said goodbye.",
            properties={},
            required=[],
            handler=_end_call,
        ),
    ]
)


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments) -> None:
    api_key = os.getenv("ASSEMBLYAI_API_KEY")
    if not api_key:
        raise ValueError("Set ASSEMBLYAI_API_KEY in .env.local or the environment")

    stt = AssemblyAISTTService(
        api_key=api_key,
        # Universal-3.6 Pro decides when the user has finished speaking
        vad_force_turn_endpoint=False,
        settings=AssemblyAISTTService.Settings(
            model="universal-3-6-pro",
            mode=STT_MODE,
            vad_threshold=VAD_THRESHOLD,
            keyterms_prompt=STT_KEYTERMS,
            # More building blocks, off by default. Each skill says when to use it.
            # voice_focus="near-field",     # background noise: skills/voice-focus
            # prompt="...",                 # what calls are about: skills/keyterms-and-prompt
            # language_codes=[Language.EN, Language.ES],  # expected languages: skills/languages
            # domain="medical-v1",          # medical vocabulary: skills/medical-mode
        ),
    )
    llm = OpenAILLMService(
        api_key=api_key,
        base_url=LLM_GATEWAY_URL,
        settings=OpenAILLMService.Settings(model=LLM_MODEL, system_instruction=INSTRUCTIONS),
    )
    tts = AssemblyAITTSService(api_key=api_key, voice=TTS_VOICE)

    context = LLMContext(tools=TOOLS)
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            # Silero catches the user starting to speak, so the agent stops quickly
            vad_analyzer=SileroVADAnalyzer(params=VADParams(confidence=VAD_THRESHOLD))
        ),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )
    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
    )
    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)
    await runner.add_workers(worker)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        # A fixed greeting is spoken right away, without waiting on the LLM
        await worker.queue_frames([TTSSpeakFrame(GREETING)])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        await runner.cancel()

    await runner.run()


async def bot(runner_args: RunnerArguments) -> None:
    """The entry point for Pipecat's runner and Pipecat Cloud."""
    transport = await create_transport(
        runner_args,
        {
            "daily": lambda: DailyParams(audio_in_enabled=True, audio_out_enabled=True),
            "twilio": lambda: FastAPIWebsocketParams(audio_in_enabled=True, audio_out_enabled=True),
            "webrtc": lambda: TransportParams(audio_in_enabled=True, audio_out_enabled=True),
        },
    )
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
