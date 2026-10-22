# AssemblyAI voice agent starter for Pipecat

A voice agent template for [Pipecat](https://github.com/pipecat-ai/pipecat) where the voice, the ears and the brain are all AssemblyAI, on one API key. Talk to it in five minutes, then shape it into your own agent with a coding agent.

| | AssemblyAI model | |
|---|---|---|
| **Voice** | [Streaming text-to-speech](https://www.assemblyai.com/docs/tts/getting-started/quickstart) | 4,000+ voices in six languages, or your own cloned voice. Word timings mean an interrupted reply is remembered only up to the words the user heard. |
| **Ears** | [Universal-3.6 Pro](https://www.assemblyai.com/docs/voice-agents/pipecat-universal-3-5-pro) | Streaming speech-to-text that also decides when the user has finished talking, and holds the turn open while they read out a number or an email. |
| **Brain** | [LLM Gateway](https://www.assemblyai.com/docs/llm-gateway/quickstart) | 50 models from Google, OpenAI, Anthropic and others, with tool calling, behind one OpenAI-compatible API. |

The AssemblyAI TTS service for Pipecat is [`src/assemblyai_tts.py`](src/assemblyai_tts.py), one file you can copy into any Pipecat bot.

Using LiveKit? See [assemblyai-livekit-reference-voice-agent](https://github.com/AssemblyAI-Solutions/assemblyai-livekit-reference-voice-agent).

## Get started

### 1. Install

You need [uv](https://docs.astral.sh/uv/getting-started/installation/) and an [AssemblyAI API key](https://www.assemblyai.com/dashboard/api-keys).

```console
git clone https://github.com/dan-ince-aai/assemblyai-pipecat-reference-voice-agent.git
cd assemblyai-pipecat-reference-voice-agent
uv sync
cp .env.example .env.local
```

Put your API key in `.env.local`.

### 2. Talk to it

```console
uv run src/bot.py
```

Open http://localhost:7860/client, allow the microphone and press Connect. Wear headphones so the agent doesn't hear itself. Ask what time it is in Tokyo, interrupt it mid-sentence, then say goodbye.

### 3. Hear other voices

```console
export ASSEMBLYAI_API_KEY=<your key>
curl -sS https://tts.us.assemblyai.com/v1/speech \
  -H "Authorization: $ASSEMBLYAI_API_KEY" -H "Content-Type: application/json" \
  -d '{"text": "Hi, I am Jane. How can I help?", "voice_id": "aai-jane", "container": "wav"}' \
  -o voice.wav && afplay voice.wav
```

Browse the library by language with `curl -s "https://tts.us.assemblyai.com/v1/voices?scope=public&language=spanish" -H "Authorization: $ASSEMBLYAI_API_KEY"`, then set `TTS_VOICE` in [`src/bot.py`](src/bot.py) to a voice's `id`.

### 4. Call it from a phone, or a Daily room

- **Daily:** add `DAILY_API_KEY` to `.env.local` and run `uv run src/bot.py -t daily`.
- **Phone:** point a Twilio number's [Media Streams](https://docs.pipecat.ai/pipecat/telephony/twilio-websockets) at the bot and run `uv run src/bot.py -t twilio -x <your public host>`.

## Build your agent

Open the repo in Claude Code, Cursor or Codex and describe the agent you want. [`AGENTS.md`](AGENTS.md) tells the coding agent what to ask you (who the agent is for, where its users are, what they'll say) and which building blocks to apply. Each building block is a skill in [`skills/`](skills/):

| Building block | Default | Skill |
|---|---|---|
| Voice | Keegan | [tts-voice](skills/tts-voice/SKILL.md) |
| Turn detection | `balanced` | [turn-detection](skills/turn-detection/SKILL.md) |
| Speech threshold and interruptions | `0.2` | [interruptions-and-vad](skills/interruptions-and-vad/SKILL.md) |
| Noise suppression | Off | [voice-focus](skills/voice-focus/SKILL.md) |
| Key terms and context | The agent's name | [keyterms-and-prompt](skills/keyterms-and-prompt/SKILL.md) |
| Languages | Any, replies in English | [languages](skills/languages/SKILL.md) |
| Medical vocabulary | Off | [medical-mode](skills/medical-mode/SKILL.md) |
| LLM | `gemma-4-31b` | [llm-model](skills/llm-model/SKILL.md) |
| Data residency | US | [data-residency](skills/data-residency/SKILL.md) |
| Tools | `get_current_time` | [add-a-tool](skills/add-a-tool/SKILL.md) |

## How it works

```
transport ──▶ Universal-3.6 Pro ──▶ LLM Gateway ──▶ AssemblyAI TTS ──▶ transport
              speech-to-text,        reply and        word-timed
              end of turn            tool calls       speech
```

The whole agent is [`src/bot.py`](src/bot.py). [`src/README.md`](src/README.md) explains each default.

## Test

```console
uv run pytest
```

See [`tests/README.md`](tests/README.md).

## Deploy

To [Pipecat Cloud](https://pipecat.daily.co):

```console
uv tool install "pipecat-ai[cli]" --with pipecatcloud
pipecat cloud auth login
pipecat cloud secrets set assistant-secrets --file .env.local
pipecat cloud deploy
```

`pipecat cloud deploy` builds the [`Dockerfile`](Dockerfile) in the cloud with the settings in [`pcc-deploy.toml`](pcc-deploy.toml). See [Pipecat Cloud](https://docs.pipecat.ai/pipecat-cloud/fundamentals/deploy).

## License

[MIT](LICENSE)
