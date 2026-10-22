# AGENTS.md

A Pipecat (Python) voice agent where every model is from AssemblyAI: Universal-3.6 Pro streaming speech-to-text, an LLM on AssemblyAI's LLM Gateway, and AssemblyAI streaming text-to-speech. The agent is Keegan (`RECEPTIONIST_NAME`), a receptionist for a made-up clinic who takes patient intake and books appointments. See @README.md for setup, and `src/README.md` for the reasoning behind each setting.

## Layout

- `src/bot.py`: the instructions, greeting, tool functions and their `TOOLS` schemas, and `run_bot`, which builds the pipeline. `bot()` is the entry point for Pipecat's runner and Pipecat Cloud.
- `src/assemblyai_tts.py`: `AssemblyAITTSService`, AssemblyAI streaming TTS as a Pipecat `WebsocketTTSService`. Pipecat doesn't ship one yet.
- `src/clinic.py`: the in-memory clinic the tools run against. It stands in for a practice management or EHR system; keep it free of Pipecat imports.
- `tests/test_clinic.py`: offline unit tests of the clinic.
- `tests/test_bot.py`: text-only tests of the receptionist through the LLM Gateway, using the same instructions, schemas and tool functions as `src/bot.py`. Full calls are played against a simulated caller and checked against the clinic's records; single replies are judged by an LLM.
- `tests/test_tts.py`: live tests of `AssemblyAITTSService`.
- `skills/`: step-by-step instructions for common changes, one `SKILL.md` per folder. `.claude/skills` links to it, so Claude Code loads them automatically.
- Each folder has a `README.md` for people. Keep them in step with the code.

## Skills

Before making one of these changes, read the skill's `SKILL.md` and follow it:

- `skills/change-the-voice`: a different TTS voice, accent or language, or a cloned voice
- `skills/wait-longer-for-numbers`: callers cut off while reading out numbers or IDs (turn detection)
- `skills/sync-second-pass`: more accurate numbers and IDs, re-transcribed with the Sync API from the pipeline's audio
- `skills/switch-llm`: another LLM Gateway model
- `skills/make-it-yours`: a different agent or use case, or real systems behind the tools

## Tooling

- Install with `uv sync`.
- Format and lint with `uv run ruff format` and `uv run ruff check`.
- Test with `uv run pytest`. The live tests need `ASSEMBLYAI_API_KEY` in `.env.local` and are skipped without it.
- Try changes with `uv run src/bot.py` and http://localhost:7860/client. It needs only the AssemblyAI key.

## Making changes

- When you change the instructions, a tool, or the model, run the bot tests, and run them more than once: LLM behavior varies between runs. For a new behavior, add a test first, then change the agent until it passes. Prefer checking the clinic's records over judging wording.
- Tools are plain functions over `CallState` with no Pipecat code, listed in `CLINIC_TOOLS`. Their schemas are written out in `TOOLS`, because Pipecat's direct functions drop `Literal` choices; keep the two in step. Use `"enum"` for fixed choices. Raise `ToolError` with a message that tells the model how to recover.
- Per-call state lives in `CallState`, carried by the worker as `app_resources`. Keep identifiers such as the current patient there, rather than having the LLM pass them between tools.
- Everything the agent writes is spoken. Tool outputs and instructions should produce short, plain sentences, with no markdown or lists.
- Don't log patient details. The agent logs patient IDs only.
- After changing `src/assemblyai_tts.py`, run `uv run pytest tests/test_tts.py`.

## AssemblyAI specifics

- The LLM Gateway is OpenAI-compatible: `OpenAILLMService(base_url="https://llm-gateway.assemblyai.com/v1", api_key=ASSEMBLYAI_API_KEY, settings=OpenAILLMService.Settings(model=...))`. Model IDs have no provider prefix (`gemma-4-31b`, `claude-haiku-4-5-20251001`); `GET /v1/models` lists them. The EU Gateway (`llm-gateway.eu.assemblyai.com`) serves a subset, and not `gemma-4-31b`; its own `GET /v1/models` lists them.
- Turn detection is Universal-3.6 Pro's own (`vad_force_turn_endpoint=False`): the STT tells the user aggregator when turns start and end. Tune turn-taking with the STT's `mode`, `min_turn_silence` and `max_turn_silence`. In Pipecat 1.13, changing those through `STTUpdateSettingsFrame` reconnects the STT; the wait-longer-for-numbers skill shows how to change `max_turn_silence` live instead.
- Silero's `confidence` matches the STT's `vad_threshold` (`0.2`, the Universal-3.6 Pro default). Change them together.
- Medical Mode (`domain="medical-v1"`) supports English, Spanish, German and French, and is billed as an add-on.
- AssemblyAI TTS `language` takes a name (`spanish`) on the API; `AssemblyAITTSService` also accepts codes and Pipecat `Language`s. Library voices other than the eleven featured `aai-*` voices, and cloned voices, speak only their own language.
- AssemblyAI docs: https://www.assemblyai.com/docs (an index for agents: https://www.assemblyai.com/docs/llms.txt). Universal-3.6 Pro with Pipecat: https://www.assemblyai.com/docs/voice-agents/pipecat-universal-3-5-pro

## Pipecat documentation

Check the current Pipecat docs rather than relying on memory: https://docs.pipecat.ai, with an index for agents at https://docs.pipecat.ai/llms.txt. Pipecat's own examples are in https://github.com/pipecat-ai/pipecat/tree/main/examples.
