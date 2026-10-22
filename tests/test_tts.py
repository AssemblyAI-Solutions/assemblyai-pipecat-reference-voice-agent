"""Live tests of AssemblyAITTSService against AssemblyAI Streaming TTS.

They need ASSEMBLYAI_API_KEY (from .env.local or the environment).

    uv run pytest tests/test_tts.py
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from pipecat.frames.frames import (
    InterruptionFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
    TTSTextFrame,
)
from pipecat.tests.utils import SleepFrame, run_test

from assemblyai_tts import AssemblyAITTSService

load_dotenv(Path(__file__).parents[1] / ".env.local")

pytestmark = pytest.mark.skipif(
    not os.getenv("ASSEMBLYAI_API_KEY"), reason="needs ASSEMBLYAI_API_KEY for AssemblyAI TTS"
)

SAMPLE_RATE = 24000


def reply(*sentences: str) -> list:
    """The frames an LLM reply arrives as."""
    return [
        LLMFullResponseStartFrame(),
        *(LLMTextFrame(text=s) for s in sentences),
        LLMFullResponseEndFrame(),
    ]


async def test_speaks_a_reply_with_word_timings() -> None:
    frames, errors = await run_test(
        AssemblyAITTSService(sample_rate=SAMPLE_RATE),
        frames_to_send=[
            *reply("Thanks for calling Riverside Family Medicine. ", "How can I help? "),
            SleepFrame(sleep=5),
        ],
    )

    assert not errors
    assert any(isinstance(f, TTSStartedFrame) for f in frames)
    assert any(isinstance(f, TTSStoppedFrame) for f in frames)
    audio = b"".join(f.audio for f in frames if isinstance(f, TTSAudioRawFrame))
    assert len(audio) / (SAMPLE_RATE * 2) > 2  # seconds

    # Each word arrives as its own frame, timed from the word timings, in order
    words = [f for f in frames if isinstance(f, TTSTextFrame)]
    assert " ".join(w.text for w in words) == (
        "Thanks for calling Riverside Family Medicine. How can I help?"
    )
    times = [w.pts for w in words]
    assert times == sorted(times)


async def test_an_interruption_cancels_the_reply() -> None:
    long_reply = reply(
        "When you come in, please bring your insurance card, a photo ID and a list of every "
        "medication you take, with the doses, so the doctor can review them with you. "
    )
    frames, errors = await run_test(
        AssemblyAITTSService(sample_rate=SAMPLE_RATE),
        frames_to_send=[
            *long_reply,
            # Synthesis runs faster than real time, so interrupt while it's still going
            SleepFrame(sleep=0.4),
            InterruptionFrame(),
            *reply("Sure, go ahead. "),
            SleepFrame(sleep=3),
        ],
    )

    assert not errors
    first, second = [f.context_id for f in frames if isinstance(f, TTSStartedFrame)]
    first_audio = [f for f in frames if isinstance(f, TTSAudioRawFrame) and f.context_id == first]
    second_audio = [f for f in frames if isinstance(f, TTSAudioRawFrame) and f.context_id == second]

    # The long reply, about nine seconds in full, stops partway...
    assert sum(len(f.audio) for f in first_audio) / (SAMPLE_RATE * 2) < 6
    # ...none of it comes after the next reply starts...
    assert frames.index(first_audio[-1]) < frames.index(second_audio[0])
    # ...and the same session speaks the next reply in full
    spoken = " ".join(
        f.text for f in frames if isinstance(f, TTSTextFrame) and f.context_id == second
    )
    assert spoken == "Sure, go ahead."
