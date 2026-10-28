"""AssemblyAI Streaming TTS for Pipecat, see https://www.assemblyai.com/docs/tts/message-frames.

One WebSocket session stays open for the whole call. Each sentence Pipecat hands over is sent as
a `Generate` followed by a `Flush`, and the server answers each flush, in order, with `Audio`
frames, a `FlushDone` and a `WordBoundaries` frame of word timings. The word timings become
Pipecat's spoken-text frames, so when the caller interrupts, the bot's reply in the LLM context
keeps only the words the caller heard. An interruption sends `Cancel`, which stops synthesis
without reopening the session.
"""

from __future__ import annotations

import base64
import json
import os
import textwrap
from collections import deque
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from loguru import logger
from pipecat.frames.frames import (
    ErrorFrame,
    Frame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
)
from pipecat.processors.frame_processor import FrameProcessorSetup
from pipecat.services.settings import TTSSettings
from pipecat.services.tts_service import WebsocketTTSService
from pipecat.transcriptions.language import Language, resolve_language
from pipecat.utils.tracing.service_decorators import traced_tts
from websockets.protocol import State

US_BASE_URL = "wss://tts.us.assemblyai.com"
EU_BASE_URL = "wss://tts.eu.assemblyai.com"
DEFAULT_MODEL = "assemblyai-tts-1"
DEFAULT_VOICE = "37e65973-9d96-5aab-adcd-01bf56ab5af9"  # Kyla
SUPPORTED_SAMPLE_RATES = (8000, 16000, 22050, 24000, 44100, 48000)

# The most text one Generate frame may carry
MAX_GENERATE_CHARS = 2000

# The API takes a language's English name rather than a code
LANGUAGE_NAMES = {
    Language.EN: "english",
    Language.ES: "spanish",
    Language.FR: "french",
    Language.DE: "german",
    Language.IT: "italian",
    Language.PT: "portuguese",
}


@dataclass
class _Request:
    """One Generate + Flush: a sentence of a reply."""

    context_id: str
    # Where this sentence's audio starts within its reply, in seconds, once audio arrives
    offset: float | None = None


class AssemblyAITTSService(WebsocketTTSService):
    """Speaks text with AssemblyAI Streaming TTS, with word timings and interruptions."""

    Settings = TTSSettings

    def __init__(
        self,
        *,
        api_key: str | None = None,
        voice: str = DEFAULT_VOICE,
        language: Language | str | None = None,
        model: str = DEFAULT_MODEL,
        sample_rate: int | None = None,
        base_url: str = US_BASE_URL,
        **kwargs: Any,
    ) -> None:
        """Create an AssemblyAI TTS service.

        Args:
            api_key: AssemblyAI API key. Defaults to the ASSEMBLYAI_API_KEY environment variable.
            voice: A voice id from https://www.assemblyai.com/docs/tts/voices, or one of your
                cloned voices. Defaults to Kyla.
            language: The language to speak: English, Spanish, French, German, Italian or
                Portuguese, as a Language, a code such as "es" or "es-MX", or a name such as
                "spanish". Defaults to the voice's own language.
            model: The TTS model. Defaults to "assemblyai-tts-1".
            sample_rate: Output sample rate in Hz, one of 8000, 16000, 22050, 24000, 44100 or
                48000. Defaults to the pipeline's output rate.
            base_url: The Streaming TTS host. Use EU_BASE_URL to keep text and audio in the EU;
                cloned voices are only available in the region where they were created.
            **kwargs: Passed on to Pipecat's WebsocketTTSService.
        """
        super().__init__(
            sample_rate=sample_rate,
            # Spoken text comes from the word timings, not from the LLM's text
            push_text_frames=False,
            # Hold the next reply until this one's audio is all out
            pause_frame_processing=True,
            settings=self.Settings(
                model=model,
                voice=voice,
                language=self.language_to_service_language(language) if language else None,
            ),
            **kwargs,
        )
        self._api_key = api_key or os.environ.get("ASSEMBLYAI_API_KEY")
        if not self._api_key:
            raise ValueError("Set ASSEMBLYAI_API_KEY, or pass api_key")
        self._base_url = base_url.rstrip("/")
        self._receive_task = None
        self._reset_requests()

    def can_generate_metrics(self) -> bool:
        return True

    def language_to_service_language(self, language: Language | str) -> str | None:
        try:
            return resolve_language(Language(language), LANGUAGE_NAMES)
        except ValueError:
            return str(language).lower()  # already a name, such as "spanish"

    async def _update_settings(self, delta: TTSSettings) -> dict[str, Any]:
        # The voice, model and language are fixed per session, so a change opens a new one
        changed = await super()._update_settings(delta)
        if changed and self._websocket:
            await self._disconnect()
            await self._connect()
        return changed

    @traced_tts
    async def run_tts(self, text: str, context_id: str) -> AsyncGenerator[Frame | None, None]:
        if not self._websocket or self._websocket.state is not State.OPEN:
            await self._connect()
        if not self.audio_context_available(context_id):
            await self.create_audio_context(context_id)
            await self.start_ttfb_metrics()
            self._context_bytes[context_id] = 0
            yield TTSStartedFrame(context_id=context_id)
        try:
            for chunk in textwrap.wrap(text, MAX_GENERATE_CHARS, break_on_hyphens=False):
                await self._websocket.send(json.dumps({"type": "Generate", "text": chunk}))
                await self._websocket.send(json.dumps({"type": "Flush"}))
                self._waiting.append(_Request(context_id))
            await self.start_tts_usage_metrics(text)
        except Exception as e:
            yield ErrorFrame(error=f"AssemblyAI TTS: {e}")
            yield TTSStoppedFrame(context_id=context_id)
        # The audio arrives on the receive task
        yield None

    async def flush_audio(self, context_id: str | None = None) -> None:
        # Pipecat calls this once a reply's text has all been sent. The reply ends when the
        # server has answered every one of its flushes.
        if context_id:
            self._closing.add(context_id)
            await self._maybe_finish(context_id)

    async def on_audio_context_interrupted(self, context_id: str) -> None:
        # Cancel stops everything the session is still synthesizing, so skip it if a reply that
        # can't be interrupted still has audio coming. The interrupted reply's frames are then
        # dropped as they arrive.
        outstanding = self._outstanding()
        mine = any(r.context_id == context_id for r in outstanding)
        others = any(r.context_id != context_id for r in outstanding)
        if mine and not others and self._websocket and self._websocket.state is State.OPEN:
            await self._websocket.send(json.dumps({"type": "Cancel"}))
            # Until Cancelled arrives, every frame belongs to the cancelled requests
            self._cancels_pending += 1
            self._waiting.clear()
            self._started.clear()
        self._closing.discard(context_id)
        self._context_bytes.pop(context_id, None)
        await self.stop_all_metrics()
        await super().on_audio_context_interrupted(context_id)

    async def setup(self, setup: FrameProcessorSetup) -> None:
        await super().setup(setup)
        if self.sample_rate not in SUPPORTED_SAMPLE_RATES:
            raise ValueError(f"sample_rate must be one of {SUPPORTED_SAMPLE_RATES}")
        await self._connect()

    async def _connect(self) -> None:
        await super()._connect()
        await self._connect_websocket()
        if self._websocket and not self._receive_task:
            self._receive_task = self.create_task(self._receive_task_handler(self._report_error))

    async def _disconnect(self) -> None:
        await super()._disconnect()
        if self._receive_task:
            await self.cancel_task(self._receive_task)
            self._receive_task = None
        await self._disconnect_websocket()

    async def _connect_websocket(self) -> None:
        if self._websocket and self._websocket.state is State.OPEN:
            return
        params = {
            "model_id": self._settings.model,
            "voice_id": self._settings.voice,
            "sample_rate": self.sample_rate,
            "encoding": "pcm_s16le",
            "word_boundaries": "true",
        }
        if self._settings.language:
            params["language"] = self._settings.language
        try:
            self._websocket = await self._websocket_connect(
                f"{self._base_url}/v1/ws?{urlencode(params)}",
                # The raw key: "Bearer <key>" is rejected
                additional_headers={"Authorization": self._api_key},
            )
            self._reset_requests()
            await self._call_event_handler("on_connected")
        except Exception as e:
            self._websocket = None
            await self.push_error(error_msg=f"AssemblyAI TTS: couldn't connect: {e}", exception=e)
            await self._call_event_handler("on_connection_error", f"{e}")

    async def _disconnect_websocket(self) -> None:
        try:
            await self.stop_all_metrics()
            if self._websocket and self._websocket.state is State.OPEN:
                await self._websocket.send(json.dumps({"type": "Terminate"}))
                await self._websocket.close()
        except Exception as e:
            logger.debug(f"{self}: error closing the session: {e}")
        finally:
            self._websocket = None
            await self._call_event_handler("on_disconnected")

    async def _receive_messages(self) -> None:
        async for message in self._websocket:
            frame = json.loads(message)
            kind = frame.get("type")
            if kind == "Error":
                await self._on_error(frame)
            elif kind == "Cancelled":
                self._cancels_pending = max(0, self._cancels_pending - 1)
            elif kind in ("Audio", "FlushDone", "WordBoundaries") and not self._cancels_pending:
                await self._on_request_frame(kind, frame)

    async def _on_request_frame(self, kind: str, frame: dict[str, Any]) -> None:
        flush_id = frame["flush_id"]
        request = self._started.get(flush_id)
        if request is None:
            if kind == "WordBoundaries" or not self._waiting:
                return
            # Flushes are answered in order, so the first frame with a new flush_id belongs to
            # the oldest request still waiting. Its id is read, not counted: a Cancel uses one.
            request = self._started[flush_id] = self._waiting.popleft()
        context_id = request.context_id

        if kind == "Audio":
            audio = base64.b64decode(frame["audio"])
            sent = self._context_bytes.get(context_id, 0)
            if request.offset is None:
                await self.stop_ttfb_metrics()
                request.offset = sent / (self.sample_rate * 2)
            self._context_bytes[context_id] = sent + len(audio)
            await self.append_to_audio_context(
                context_id,
                TTSAudioRawFrame(audio, self.sample_rate, 1, context_id=context_id),
            )
        elif kind == "FlushDone" and not frame.get("audio_duration_ms"):
            # No audio, such as for a sentence of only punctuation, means no word timings
            await self._finish_request(flush_id)
        elif kind == "WordBoundaries":
            # Times are in ms on the session's audio timeline, where this request starts at
            # audio_start_ms. Pipecat wants seconds from the start of the reply.
            base = (request.offset or 0) - frame.get("audio_start_ms", 0) / 1000
            words = [(w["word"], base + w["start"] / 1000) for w in frame.get("words", [])]
            if words:
                await self.add_word_timestamps(words, context_id=context_id)
            await self._finish_request(flush_id)

    async def _finish_request(self, flush_id: int) -> None:
        request = self._started.pop(flush_id)
        await self._maybe_finish(request.context_id)

    async def _maybe_finish(self, context_id: str) -> None:
        """End a reply once all its text is sent and the server has answered all of it."""
        outstanding = self._outstanding()
        if context_id not in self._closing or any(r.context_id == context_id for r in outstanding):
            return
        self._closing.discard(context_id)
        self._context_bytes.pop(context_id, None)
        if self.audio_context_available(context_id):
            await self.append_to_audio_context(context_id, TTSStoppedFrame(context_id=context_id))
            await self.remove_audio_context(context_id)

    async def _on_error(self, frame: dict[str, Any]) -> None:
        message = frame.get("error") or frame.get("message") or "unknown error"
        await self.push_error(
            error_msg=f"AssemblyAI TTS error {frame.get('error_code')}: {message}"
        )
        # The session closes after an error, so end the replies it was speaking
        contexts = {r.context_id for r in self._outstanding()}
        self._reset_requests()
        for context_id in contexts:
            self._closing.add(context_id)
            await self._maybe_finish(context_id)

    def _outstanding(self) -> list[_Request]:
        return [*self._waiting, *self._started.values()]

    def _reset_requests(self) -> None:
        # Requests sent but not yet answered, oldest first
        self._waiting: deque[_Request] = deque()
        # Requests being answered, by flush_id
        self._started: dict[int, _Request] = {}
        # Bytes of audio received so far for each reply
        self._context_bytes: dict[str, int] = {}
        # Replies whose text has all been sent
        self._closing: set[str] = set()
        self._cancels_pending = 0
