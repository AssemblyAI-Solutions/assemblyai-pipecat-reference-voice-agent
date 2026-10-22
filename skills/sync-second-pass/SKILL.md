---
name: sync-second-pass
description: Make the transcription of phone numbers, member IDs, dates of birth and spelled names more accurate with a second pass through AssemblyAI's Sync API, uploaded live from the pipeline's audio while the caller speaks. Use when the user wants higher accuracy on numbers, IDs or entities, mentions the Sync API, "second pass", re-transcription or tapping the STT, or the agent mishears IDs that the caller reads out.
---

# Sync second pass

Universal-3.6 Pro streaming transcribes every turn as the caller speaks, which is what lets the agent answer quickly. For the few turns where one wrong character is costly, such as a phone number or member ID, this adds a second transcript of the same audio from the [Sync API](https://www.assemblyai.com/docs/sync-stt/getting-started/transcribe-live-audio) and uses it instead.

A `FrameProcessor` right after the STT sees the caller's audio (the STT passes it through), the start of each turn, and its final transcript. It uploads the turn's audio to the Sync API *while the caller is still talking*, so when the turn ends the Sync transcript is nearly ready. In testing it arrived 80 to 150 ms after the streaming one, and those milliseconds are added only to the turns that get a second pass.

Tested against the live API in a Pipecat pipeline: a member ID read as "W, eight seven three, four five one, two six" came back from streaming as "W873-451-26" and from the Sync API as "W87345126".

Pipecat also has `AssemblyAISyncSTTService`, which transcribes *every* turn with the Sync API instead of streaming. This skill keeps streaming, and its turn detection, and adds the Sync API only where it pays off.

## Before you start

**Apply the [wait-longer-for-numbers skill](../wait-longer-for-numbers/SKILL.md) first.** This skill uses its `ASKS_FOR_DETAILS` pattern to choose which turns get a second pass. It also keeps a number in one turn: given half a number, cut off by a pause, the Sync API was seen to complete it ("415-555" became "415-555-5555"). It needs the whole answer.

Each second pass is billed as Sync transcription, on top of the streaming transcription of the same audio, for those turns only.

## Steps

### 1. Install the AssemblyAI SDK

```console
uv add "assemblyai>=1.6.5"
```

### 2. Create `src/sync_second_pass.py`

```python
"""A second, more accurate transcript of the turns that matter, from AssemblyAI's Sync API.

Universal-3.6 Pro streaming transcribes the caller as they speak. For a turn where one wrong
character is costly, such as a phone number, member ID or date of birth, `SyncSecondPass` also
uploads the same audio to the Sync API while the caller is still talking, and when the turn
ends it swaps the streaming transcript for the Sync one. Because the upload happens live, the
Sync transcript is ready shortly after the caller stops.

It goes in the pipeline right after the STT, which passes the caller's audio through.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections import deque
from collections.abc import Callable

import assemblyai as aai
from loguru import logger
from pipecat.frames.frames import (
    Frame,
    InputAudioRawFrame,
    ProposedUserStartedSpeakingFrame,
    TranscriptionFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

# The Sync API takes at most 120 s of audio per request
MAX_TURN_SECONDS = 100


class SyncSecondPass(FrameProcessor):
    def __init__(
        self,
        *,
        wanted: Callable[[], bool],
        context: Callable[[], list[str]] = list,
        prompt: str | None = None,
        keyterms: list[str] | None = None,
        model: str = "universal-3-6-pro",
        timeout: float = 2.0,
        preroll: float = 1.0,
    ) -> None:
        """
        Args:
            wanted: Called as each turn starts; True if the turn should get a second pass,
                for example because the agent just asked for a phone number.
            context: Called as each turn starts; the conversation so far, oldest first, sent
                as `conversation_context` so the Sync API knows what the caller is answering.
            prompt: What the call is about, as for the streaming STT.
            keyterms: Names and terms to spell right, as for the streaming STT.
            model: The Sync API model.
            timeout: How long to wait for the Sync transcript once the turn ends, before
                keeping the streaming one.
            preroll: Seconds of audio from before the turn started to include, since the
                start of speech is reported a little after the caller starts talking.
        """
        super().__init__()
        self._wanted = wanted
        self._context = context
        self._config = {"model": model, "prompt": prompt, "keyterms_prompt": keyterms}
        self._timeout = timeout
        self._preroll_seconds = preroll
        self._transcriber = aai.AsyncSyncTranscriber(api_key=os.environ["ASSEMBLYAI_API_KEY"])
        self._preroll: deque[InputAudioRawFrame] = deque()
        self._session: aai.AsyncLiveSession | None = None
        self._opened_at = 0.0

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if direction == FrameDirection.DOWNSTREAM:
            if isinstance(frame, InputAudioRawFrame):
                await self._take_audio(frame)
            elif isinstance(frame, ProposedUserStartedSpeakingFrame):
                if self._session is None and self._wanted():
                    self._open()
            elif isinstance(frame, TranscriptionFrame) and self._session is not None:
                await self._replace_transcript(frame)
        await self.push_frame(frame, direction)

    async def cleanup(self) -> None:
        await super().cleanup()
        await self._discard()
        await self._transcriber.aclose()

    async def _take_audio(self, frame: InputAudioRawFrame) -> None:
        if self._session is not None:
            self._session.write(frame.audio)
            if time.monotonic() - self._opened_at > MAX_TURN_SECONDS:
                await self._discard()
        else:
            self._preroll.append(frame)
            while sum(_seconds(f) for f in self._preroll) > self._preroll_seconds:
                self._preroll.popleft()

    def _open(self) -> None:
        if not self._preroll:
            return
        first = self._preroll[0]
        config = aai.SyncTranscriptionConfig(
            **self._config,
            sample_rate=first.sample_rate,
            channels=first.num_channels,
            conversation_context=self._context() or None,
        )
        self._session = self._transcriber.open_live(config)
        self._opened_at = time.monotonic()
        for frame in self._preroll:
            self._session.write(frame.audio)
        self._preroll.clear()

    async def _replace_transcript(self, frame: TranscriptionFrame) -> None:
        session, self._session = self._session, None
        assert session is not None
        started = time.monotonic()
        try:
            result = await asyncio.wait_for(session.result(), self._timeout)
        except Exception as e:
            logger.warning(f"second pass failed, keeping the streaming transcript: {e!r}")
            await session.abort()
            return
        text = (result.text or "").strip()
        if not text:
            return
        elapsed = (time.monotonic() - started) * 1000
        logger.info(f"second pass in {elapsed:.0f} ms: {frame.text!r} -> {text!r}")
        frame.text = text

    async def _discard(self) -> None:
        session, self._session = self._session, None
        if session is not None:
            await session.abort()


def _seconds(frame: InputAudioRawFrame) -> float:
    return len(frame.audio) / (2 * frame.num_channels * frame.sample_rate)
```

Add `"sync_second_pass"` to `known-first-party` under `[tool.ruff.lint.isort]` in `pyproject.toml`. The `Dockerfile` copies all of `src/`, so it's included in the image.

### 3. Share the STT's prompt and key terms

In `src/bot.py`, move the `prompt` and `keyterms_prompt` passed to `AssemblyAISTTService.Settings(...)` into constants near the top, after `GREETING`, so the second pass uses the same ones:

```python
# What calls are about, and the names they mention, for speech-to-text
STT_PROMPT = (
    "Phone call to a primary care and cardiology clinic. A patient gives their name, date "
    "of birth, phone number, insurance details, medications with doses and allergies, and "
    "books an appointment."
)
STT_KEYTERMS = [CLINIC_NAME, RECEPTIONIST_NAME, *(p.name for p in PROVIDERS)]
```

and in `run_bot`: `prompt=STT_PROMPT, keyterms_prompt=STT_KEYTERMS`.

### 4. Remember what the agent last said

Add a field to `CallState`:

```python
    # What the agent said last, so the second pass knows what the caller is answering
    last_reply: str = ""
```

### 5. Put it in the pipeline

In `run_bot`, add `from sync_second_pass import SyncSecondPass` to the imports at the top of the file, create the call's state before the pipeline, and the second pass after the STT:

```python
    state = CallState()
    second_pass = SyncSecondPass(
        wanted=lambda: ASKS_FOR_DETAILS.search(state.last_reply) is not None,
        context=lambda: [state.last_reply],
        prompt=STT_PROMPT,
        keyterms=STT_KEYTERMS,
    )
```

After `LLMContextAggregatorPair(...)`, keep `last_reply` up to date:

```python
    @assistant_aggregator.event_handler("on_assistant_turn_stopped")
    async def remember_last_reply(aggregator, message):
        if message.content:
            state.last_reply = message.content
```

Then put it between the STT and the user aggregator, and pass the same state to the worker:

```python
    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            second_pass,
            user_aggregator,
            ...  # unchanged
        ]
    )
    worker = PipelineWorker(
        ...,
        app_resources=state,
    )
```

`context` passes the agent's question to the Sync API as `conversation_context`, so it knows the caller is answering "What's your member ID?".

## Check it

1. `uv run ruff check` and `uv run pytest` pass. The text-only tests don't use the pipeline, so they're unaffected.
2. Run `uv run src/bot.py`, talk to it at http://localhost:7860/client as a new patient, and read out your phone number and member ID. The log shows a line per second pass, with the streaming and Sync transcripts:
   ```
   second pass in 133 ms: "Sure, it's W873-451-26." -> "Sure, it's W87345126."
   ```
   and Keegan reads back the Sync version.
3. Other turns, such as "I'd like a follow-up", log nothing and are as fast as before.

## Tuning

- **Which turns.** `wanted` decides at the start of each turn. Widen `ASKS_FOR_DETAILS` for more kinds of question, or return `True` to re-transcribe every turn, which costs more and adds the Sync wait to every reply.
- **`timeout`** (2 s): if the Sync API hasn't answered by then, the streaming transcript is kept and a warning is logged. The agent never waits longer than this.
- **Data residency.** The SDK uses `https://sync.assemblyai.com`. To keep audio in the EU, `import assemblyai as aai` and set `aai.settings.sync_base_url = "https://sync.eu.assemblyai.com"` before the pipeline starts.
- **Only the final transcript changes.** Interim transcripts still come from streaming.
