# AssemblyAI voice agent starter for Pipecat

Build a voice agent on [Pipecat](https://github.com/pipecat-ai/pipecat) where the voice, the ears and the brain are all AssemblyAI, on one API key.

You start with Keegan, a receptionist who answers the phone for a made-up clinic. Keegan takes a new patient's details or looks up a returning one, finds an open time and books the appointment. Talk to Keegan in your browser in five minutes, then make the agent your own.

| | AssemblyAI model | What it does |
|---|---|---|
| **Voice** | [Streaming text-to-speech](https://www.assemblyai.com/docs/tts/getting-started/quickstart) | Speaks every reply as it's written, in any of 4,000+ voices across six languages, or a voice you clone. Word timings mean an interrupted reply is remembered only up to the words the caller heard. |
| **Ears** | [Universal-3.6 Pro streaming speech-to-text](https://www.assemblyai.com/docs/voice-agents/pipecat-universal-3-5-pro) | Transcribes the caller, with [Medical Mode](https://www.assemblyai.com/docs/streaming/medical-mode) for drug names and doses, and decides when they've finished talking. |
| **Brain** | [LLM Gateway](https://www.assemblyai.com/docs/llm-gateway/quickstart) | Runs the conversation and calls the clinic's tools, on your choice of 50 models from Google, OpenAI, Anthropic and others. |

The AssemblyAI TTS service for Pipecat is in [`src/assemblyai_tts.py`](src/assemblyai_tts.py), one file you can copy into any Pipecat bot.

Using LiveKit? The same agent is in [assemblyai-livekit-reference-voice-agent](https://github.com/AssemblyAI-Solutions/assemblyai-livekit-reference-voice-agent).

## Get started

### 1. Install

You need [uv](https://docs.astral.sh/uv/getting-started/installation/) and an [AssemblyAI API key](https://www.assemblyai.com/dashboard/api-keys).

```console
git clone https://github.com/AssemblyAI-Solutions/assemblyai-pipecat-reference-voice-agent.git
cd assemblyai-pipecat-reference-voice-agent
uv sync
cp .env.example .env.local
```

Put your API key in `.env.local`. It's the only key you need to talk to the agent.

### 2. Talk to Keegan

```console
uv run src/bot.py
```

Open http://localhost:7860/client, allow the microphone, and press Connect. Wear headphones so the agent doesn't hear itself.

Things to try:

- **Be a new patient.** Give your name, date of birth, phone number, insurance and medications, then book a visit. Keegan reads numbers back one character at a time so you can catch mistakes.
- **Be a returning patient.** Say you're Maria Garcia, born March 14, 1985, and book a follow-up with Dr. Nakamura.
- **Cut Keegan off mid-sentence.** Keegan stops, and remembers only what you heard.
- **Ask for something a receptionist shouldn't do**, such as whether to double a medication, or describe chest pain.

### 3. Change the voice

The voice is one line in [`src/bot.py`](src/bot.py):

```python
TTS_VOICE = "987db62e-a2c2-569a-9c4d-82460cdea1bd"  # Keegan
```

Hear any voice before you pick it (`afplay` is macOS; elsewhere, open `voice.wav`):

```console
export ASSEMBLYAI_API_KEY=<your key>
curl -sS https://tts.us.assemblyai.com/v1/speech \
  -H "Authorization: $ASSEMBLYAI_API_KEY" -H "Content-Type: application/json" \
  -d '{"text": "Thanks for calling Riverside Family Medicine.", "voice_id": "aai-jane", "container": "wav"}' \
  -o voice.wav && afplay voice.wav
```

Browse the library, for example its Spanish voices:

```console
curl -s "https://tts.us.assemblyai.com/v1/voices?scope=public&language=spanish&limit=20" \
  -H "Authorization: $ASSEMBLYAI_API_KEY" | jq -r '.voices[] | "\(.id)  \(.name)  \(.description)"'
```

Set `TTS_VOICE` to the voice's id, and `RECEPTIONIST_NAME` to match, since the agent introduces itself by name. To use your own voice, [clone it in the dashboard](https://www.assemblyai.com/docs/tts/cloned-voices) and use its id. The [change-the-voice skill](skills/change-the-voice/SKILL.md) covers languages, featured voices and data residency.

### 4. Call it from a phone, or deploy it

- **A Daily room:** add a `DAILY_API_KEY` to `.env.local` and run `uv run src/bot.py -t daily`.
- **A phone number:** point a Twilio number's [Media Streams](https://docs.pipecat.ai/pipecat/telephony/twilio-websockets) at the bot and run `uv run src/bot.py -t twilio -x <your public host>`, for example an ngrok host.
- **Pipecat Cloud:** see [Deploy](#deploy).

## Build it out with skills

The [`skills/`](skills/) folder holds instructions for coding agents, such as Claude Code, Cursor or Codex. Each one teaches your coding agent a change worth making, with code that's been tested against the AssemblyAI API. Open the repo in Claude Code and ask for what you want, for example "give Keegan a British voice" or "make phone numbers more accurate". The matching skill loads automatically.

| Skill | What it does |
|---|---|
| [change-the-voice](skills/change-the-voice/SKILL.md) | Pick a voice from the library, clone your own, or speak Spanish, German, French, Italian or Portuguese |
| [wait-longer-for-numbers](skills/wait-longer-for-numbers/SKILL.md) | Give callers time to read out phone numbers and IDs, so a pause doesn't end their turn |
| [sync-second-pass](skills/sync-second-pass/SKILL.md) | Re-transcribe answers with numbers and IDs with the Sync API, uploaded live as the caller speaks |
| [switch-llm](skills/switch-llm/SKILL.md) | Choose one of the LLM Gateway's 50 models for tool calling |
| [make-it-yours](skills/make-it-yours/SKILL.md) | Turn the receptionist into your own agent, or connect it to your real systems |

## How it works

```
transport.input() ─▶ Universal-3.6 Pro STT ─▶ user context ─▶ LLM Gateway ─▶ AssemblyAI TTS ─▶ transport.output()
                     Medical Mode, decides                     tools change   word-timed audio
                     when the caller is done                   the clinic's records
```

- [`src/bot.py`](src/bot.py) is the whole agent: the instructions, the greeting, four tools and the pipeline.
- [`src/assemblyai_tts.py`](src/assemblyai_tts.py) is AssemblyAI streaming TTS as a Pipecat service.
- [`src/clinic.py`](src/clinic.py) is the made-up clinic the tools work on: doctors, open times and patients.

[`src/README.md`](src/README.md) walks through every setting and why it's there.

## Models

**Voice.** Any of the 4,000+ voices in the [AssemblyAI voice library](https://www.assemblyai.com/docs/tts/voices), in English, Spanish, German, French, Italian and Portuguese, or a [voice you clone](https://www.assemblyai.com/docs/tts/cloned-voices).

**LLM.** Set `LLM_MODEL` in `src/bot.py` to any LLM Gateway model that supports tool calling. Time to the first token matters most in a voice agent, because the agent can't speak until the LLM does. These were fastest in one test, streaming a reply with a tool attached, from the US East Coast in October 2026:

| Model | Median time to first token |
|---|---|
| `gemma-4-31b` (default) | ~0.6 s |
| `gemini-3.5-flash-lite` | ~0.7 s |
| `claude-haiku-4-5-20251001` | ~0.8 s |
| `gpt-4.1` | ~0.8 s |

The [switch-llm skill](skills/switch-llm/SKILL.md) lists every suitable model. After switching, run the tests: larger models handle unusual calls better but answer more slowly.

**Speech-to-text.** Universal-3.6 Pro, with Medical Mode for English, Spanish, German and French. It recognizes many languages and switches between them on its own.

## Keep data in the EU

Point all three services at AssemblyAI's EU hosts in `src/bot.py`:

```python
AssemblyAISTTService(..., api_endpoint_base_url="wss://streaming.eu.assemblyai.com/v3/ws")
AssemblyAITTSService(..., base_url=EU_BASE_URL)  # from assemblyai_tts
LLM_GATEWAY_URL = "https://llm-gateway.eu.assemblyai.com/v1"
```

The EU Gateway doesn't serve `gemma-4-31b`, so also set `LLM_MODEL` to an EU model such as `gemini-3.5-flash-lite`. A cloned voice works only in the region where you created it.

## Test

```console
uv run pytest
```

The tests play whole calls against a simulated caller and check what ended up in the clinic's records, and check the TTS service against the live API. Run them after you change the instructions, a tool or the model. See [`tests/README.md`](tests/README.md).

## Deploy

To [Pipecat Cloud](https://pipecat.daily.co), with the Pipecat CLI:

```console
uv tool install "pipecat-ai[cli]" --with pipecatcloud
pipecat cloud auth login
pipecat cloud secrets set receptionist-secrets --file .env.local
pipecat cloud deploy
```

`pipecat cloud deploy` builds the [`Dockerfile`](Dockerfile) in the cloud and deploys it with the settings in [`pcc-deploy.toml`](pcc-deploy.toml). Commit `uv.lock`, since the image installs from it. See [Pipecat Cloud](https://docs.pipecat.ai/pipecat-cloud/fundamentals/deploy) for sessions, scaling and telephony.

## Project layout

```
src/        the agent, the AssemblyAI TTS service and the made-up clinic
tests/      simulated calls, TTS checks and unit tests
skills/     instructions for coding agents, to build the agent out
AGENTS.md   guidance for coding agents working on this repo (CLAUDE.md points to it)
```

## Resources

- [AssemblyAI text-to-speech](https://www.assemblyai.com/docs/tts/getting-started/quickstart): voices, languages and cloning
- [Universal-3.6 Pro with Pipecat](https://www.assemblyai.com/docs/voice-agents/pipecat-universal-3-5-pro): turn detection and accuracy settings
- [LLM Gateway](https://www.assemblyai.com/docs/llm-gateway/quickstart): models and tool calling
- [Sync speech-to-text](https://www.assemblyai.com/docs/sync-stt/getting-started/quickstart): a transcript in one HTTP request
- [Pipecat](https://docs.pipecat.ai): pipelines, transports and deployment

## License

[MIT](LICENSE)
