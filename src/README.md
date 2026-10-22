# src

| File | What's in it |
|---|---|
| [`bot.py`](bot.py) | The whole agent: the settings, each naming its skill; the instructions, greeting and tools; `run_bot`, which builds the pipeline |
| [`assemblyai_tts.py`](assemblyai_tts.py) | `AssemblyAITTSService`: AssemblyAI streaming TTS as a Pipecat service, with word timings and interruptions. Copy it into any Pipecat bot |

Run it from the repo root with `uv run src/bot.py`. Here's why each default is what it is.

## Text-to-speech

- **One session per call.** `AssemblyAITTSService` keeps one WebSocket to AssemblyAI open for the call, and sends each sentence from the LLM as soon as it's ready.
- **The greeting doesn't wait for the LLM.** When the user connects, a `TTSSpeakFrame` sends a fixed greeting straight to the TTS.
- **Interruptions are remembered word by word.** The service passes AssemblyAI's word timings on as the bot's spoken text. When the user cuts in, it cancels the reply, and the reply saved in the LLM context ends at the last word the user heard.

## Speech-to-text

- **Universal-3.6 Pro decides when the user is done** (`vad_force_turn_endpoint=False`), from the words as well as the silence, and tells the user aggregator when turns start and end. `mode="balanced"` ends a turn after at most 1.28 seconds of silence.
- **The STT knows what the agent just asked.** Pipecat passes each reply to Universal-3.6 Pro as context, so after "What's your email?" it expects an email. That needs no code.
- **One speech threshold.** `VAD_THRESHOLD` (0.2, Universal-3.6 Pro's default) is used by both the STT and Silero, which catches interruptions, so the two agree on what counts as speech.
- **The agent's name is a key term**, so it's spelled right when users say it.

## The LLM and tools

- **The LLM Gateway is used through the OpenAI service:** `OpenAILLMService` with the Gateway's URL and your AssemblyAI key.
- **Tools are plain functions** with their schemas in `TOOLS`, written out so fixed choices keep their `enum`. `get_current_time` is the example; a `ToolError` tells the LLM how to recover.
- **The agent can hang up.** `end_call` pushes an `EndWorkerFrame` behind the goodbye, so the call ends once it's been spoken.
