# AGENTS.md

A Pipecat (Python) voice agent starter where every model is AssemblyAI's: streaming text-to-speech, Universal-3.6 Pro streaming speech-to-text, and an LLM on the LLM Gateway, on one API key. The agent is a general assistant that tells the time; it's a template to build the user's own agent from. See @README.md for setup.

## Building an agent from this starter

Every model setting is a building block with a skill in `skills/` that says when to use it and how. Before changing settings, find out what the agent is for by asking the user the questions below. Ask the few that matter, in plain language, a couple at a time; skip any the user has already answered, and use sensible defaults for the rest. Then read the skills the answers point to, and apply them.

| Ask | The answer decides | Skill |
|---|---|---|
| What is the agent for? What should it do or look up, and in which systems? | `INSTRUCTIONS`, `GREETING`, tools | `add-a-tool` |
| What should it sound like: gender, age, accent, energy? A brand voice to clone? | `TTS_VOICE`, `ASSISTANT_NAME` | `tts-voice` |
| Which languages will users speak, and which should it reply in? | `language_codes`, TTS `language`, the voice | `languages` |
| Where will users be, and on what device? (quiet room, car, street, call center, kiosk; phone, headset, laptop, speakerphone) | `voice_focus`, `VAD_THRESHOLD`, Silero settings | `voice-focus`, `interruptions-and-vad` |
| What will users say: short answers, or long explanations, numbers, emails and addresses? Do they pause to think? | `STT_MODE`, `min_turn_silence`, `max_turn_silence` | `turn-detection` |
| Which matters more: replying fast, or never cutting the user off? | `STT_MODE`, `LLM_MODEL` | `turn-detection`, `llm-model` |
| What names, products or jargon will come up? | `keyterms_prompt`, `prompt` | `keyterms-and-prompt` |
| Is it about health: medications, symptoms, patients? | `domain="medical-v1"` | `medical-mode` |
| How complex are the conversations, and how many tools? Any cost limit? | `LLM_MODEL` | `llm-model` |
| Must data stay in the EU? | Regional hosts for all three services | `data-residency` |

### Starting points

| Agent | Settings to start from |
|---|---|
| Phone support or booking line | `voice_focus="near-field"`; `STT_MODE="balanced"`; key terms for the business's names; a fast LLM |
| Agent that collects IDs, emails or addresses | `STT_MODE="balanced"` with a longer `max_turn_silence` (2000–3000) while waiting for them; read them back in `INSTRUCTIONS` |
| Kiosk, drive-thru, in-car or smart speaker | `voice_focus="far-field"`; `VAD_THRESHOLD` 0.3; Silero `start_secs` 0.4 |
| Quick-fire assistant (quizzes, menus, short commands) | `STT_MODE="min_latency"`; the fastest LLM |
| Healthcare intake | `domain="medical-v1"`; key terms for staff and the practice; `STT_MODE="balanced"` or `"max_accuracy"`; a BAA |
| Language tutor or bilingual line | `language_codes` for the languages; a featured voice; a reply-language rule in `INSTRUCTIONS` |

Change one block at a time, run the tests, and have the user try it with `uv run src/bot.py`.

## Layout

- `src/bot.py`: the whole agent. Model settings at the top, each naming its skill; the instructions, greeting, tool functions and their `TOOLS` schemas; `run_bot`, which builds the pipeline. The STT settings list the optional building blocks, commented out. `bot()` is the entry point for Pipecat's runner and Pipecat Cloud.
- `src/assemblyai_tts.py`: `AssemblyAITTSService`, AssemblyAI streaming TTS as a Pipecat `WebsocketTTSService`. Pipecat doesn't ship one yet.
- `tests/test_bot.py`: text-only tests through the LLM Gateway, using the same instructions, schemas and tool functions as `src/bot.py`; tool calls checked, wording judged by an LLM.
- `tests/test_tts.py`: live tests of `AssemblyAITTSService`.
- `skills/`: one `SKILL.md` per building block. `.claude/skills` links to it, so Claude Code loads them automatically; other agents should read the relevant `SKILL.md` before changing a setting.
- Each folder has a `README.md` for people. Keep them in step with the code.

## Tooling

- Install with `uv sync`. Format and lint with `uv run ruff format` and `uv run ruff check`.
- Test with `uv run pytest`. The live tests need `ASSEMBLYAI_API_KEY` in `.env.local` and are skipped without it.
- Try changes with `uv run src/bot.py` and http://localhost:7860/client. It needs only the AssemblyAI key.

## Making changes

- When you change the instructions, a tool, or the model, run the tests more than once: LLM behavior varies between runs. For a new behavior, add a test first.
- Tools are plain functions with no Pipecat code, listed in `TOOL_FUNCTIONS`, with schemas in `TOOLS`. Keep the two in step. Use `"enum"` for fixed choices. Raise `ToolError` with a message that tells the model how to recover.
- Everything the agent writes is spoken. Tool outputs and instructions should produce short, plain sentences, with no markdown or lists.
- Don't log personal details. Log IDs only.
- After changing `src/assemblyai_tts.py`, run `uv run pytest tests/test_tts.py`.

## AssemblyAI specifics

- The LLM Gateway is OpenAI-compatible: `OpenAILLMService(base_url="https://llm-gateway.assemblyai.com/v1", api_key=ASSEMBLYAI_API_KEY, settings=OpenAILLMService.Settings(model=...))`. Model IDs have no provider prefix (`gemma-4-31b`). The EU Gateway serves a subset, and not `gemma-4-31b`.
- Turn detection is Universal-3.6 Pro's own (`vad_force_turn_endpoint=False`): the STT tells the user aggregator when turns start and end. Tune it with `mode`, `min_turn_silence` and `max_turn_silence`.
- The STT's `vad_threshold` and Silero's `confidence` are both `VAD_THRESHOLD`. Keep them equal.
- In Pipecat 1.13, an `STTUpdateSettingsFrame` applies `language_codes` and `agent_context` live and reconnects the STT for every other setting. The `update_live` subclass in the turn-detection skill changes `min_turn_silence`, `max_turn_silence`, `keyterms_prompt` and `prompt` without reconnecting.
- TTS `language` takes a name (`spanish`) on the API; `AssemblyAITTSService` also accepts codes and `Language`s. Only the eleven featured `aai-*` voices speak all six TTS languages.
- AssemblyAI docs: https://www.assemblyai.com/docs, with an index for agents at https://www.assemblyai.com/docs/llms.txt. Universal-3.6 Pro with Pipecat: https://www.assemblyai.com/docs/voice-agents/pipecat-universal-3-5-pro

## Pipecat documentation

Check the current Pipecat docs rather than relying on memory: https://docs.pipecat.ai, with an index for agents at https://docs.pipecat.ai/llms.txt. Pipecat's examples are in https://github.com/pipecat-ai/pipecat/tree/main/examples.
