---
name: change-the-voice
description: Change the agent's AssemblyAI text-to-speech voice, accent or language, or use a cloned voice. Use when the user wants a different voice (male, female, British, warmer, slower...), wants to hear voices, wants the agent to speak Spanish, German, French, Italian or Portuguese, wants their own cloned voice, or wants TTS kept in the EU.
---

# Change the voice

The agent speaks with AssemblyAI streaming TTS through `AssemblyAITTSService` (`src/assemblyai_tts.py`), set up in `src/bot.py`:

```python
TTS_VOICE = "987db62e-a2c2-569a-9c4d-82460cdea1bd"  # Keegan
RECEPTIONIST_NAME = "Keegan"
...
tts = AssemblyAITTSService(api_key=api_key, voice=TTS_VOICE)
```

`RECEPTIONIST_NAME` is used in the greeting, the instructions and the STT's key terms, so when the voice changes, change the name to match unless the user wants to keep it.

## 1. Find a voice

The library has 4,000+ voices. Each has an `id` (a UUID that never changes), a `name`, a `language`, a `description` and `tags` such as `gender:female`, `accent:british`, `age:young`, `warm`, `deep`, `soft-spoken`. List them with the API key from `.env.local`:

```console
set -a; . ./.env.local; set +a
curl -s "https://tts.us.assemblyai.com/v1/voices?scope=public&language=english&limit=100" \
  -H "Authorization: $ASSEMBLYAI_API_KEY" \
  | jq -r '.voices[] | select(.tags | index("accent:british") and index("gender:female")) | "\(.id)  \(.name)  \(.description)"'
```

`language` is one of `english`, `spanish`, `german`, `french`, `italian`, `portuguese`. Results come 100 at a time; when `has_more` is true, pass `&cursor=<next_cursor>` for the next page. Offer the user two or three voices that fit what they asked for, with their descriptions.

Eleven featured voices speak all six languages. Every other library voice, and every cloned voice, speaks only the language it was recorded in.

| Voice | `voice` value |
|---|---|
| Alba | `aai-alba` |
| Anna | `aai-anna` |
| Charles | `aai-charles` |
| Eve | `aai-eve` |
| George | `aai-george` |
| Jane | `aai-jane` |
| Jean | `aai-jean` |
| Mary | `aai-mary` |
| Michael | `aai-michael` |
| Paul | `aai-paul` |
| Vera | `aai-vera` |

## 2. Let the user hear it

One request turns a sentence into a WAV file. Use the agent's own greeting so the user hears what callers will:

```console
curl -sS --fail-with-body https://tts.us.assemblyai.com/v1/speech \
  -H "Authorization: $ASSEMBLYAI_API_KEY" -H "Content-Type: application/json" \
  -d '{"text": "Thanks for calling Riverside Family Medicine, this is Yasmin.", "voice_id": "ddbf46ac-77a9-5784-bec3-6685db0f0b10", "container": "wav"}' \
  -o voice.wav && afplay voice.wav
```

`afplay` is macOS. On Linux use `aplay voice.wav`; otherwise tell the user where the file is. For a language other than English with a featured voice, add `"language": "spanish"` (the full name, not a code).

## 3. Set it

In `src/bot.py`, set `TTS_VOICE` to the voice's `id` and `RECEPTIONIST_NAME` to its name. Prefer the `id` over a slug: slugs can change, ids don't. Then run `uv run src/bot.py`, open http://localhost:7860/client and let the user hear the greeting.

## A cloned voice

Voices are cloned in the [AssemblyAI dashboard](https://www.assemblyai.com/dashboard), not through this repo. Once the user has one, set `TTS_VOICE` to the id the dashboard shows. A cloned voice:

- speaks only the language of its recording, so don't pass `language` to the TTS (any other language closes the session with error `3006`);
- exists only in the region it was created in, so a voice cloned in the EU needs the EU host (below).

See [Voice cloning](https://www.assemblyai.com/docs/tts/cloned-voices).

## Another language

To have the agent speak Spanish (or German, French, Italian, Portuguese), change four things together:

1. **The voice.** A featured voice with `language`, or a library voice recorded in that language:
   ```python
   tts = AssemblyAITTSService(api_key=api_key, voice="aai-jane", language="es")  # or "spanish"
   ```
2. **The speech-to-text.** Steer Universal-3.6 Pro toward the language, and rewrite `prompt` in it:
   ```python
   from pipecat.transcriptions.language import Language

   AssemblyAISTTService.Settings(..., language_codes=[Language.ES])  # or [Language.EN, Language.ES]
   ```
   Medical Mode (`domain="medical-v1"`) supports English, Spanish, German and French only; remove it for Italian or Portuguese.
3. **The words.** Translate `GREETING`, and add to `INSTRUCTIONS` that the agent speaks only that language. `Slot.describe()` in `src/clinic.py` writes dates in English; translate its day and month names too.
4. **The tests.** Run `uv run pytest`; the simulated callers speak English, so add one in `tests/test_bot.py` that speaks the new language.

## Keep TTS in the EU

```python
from assemblyai_tts import EU_BASE_URL

tts = AssemblyAITTSService(api_key=api_key, voice=TTS_VOICE, base_url=EU_BASE_URL)
```

Look voices up on the same host (`https://tts.eu.assemblyai.com/v1/voices`). The README's "Keep data in the EU" section covers the STT and LLM too.

## If it fails

The TTS checks the voice when it connects. An unknown id fails with `3012 voice_not_found`; a voice that doesn't speak the requested language fails with `3006`, and the message lists the voices that do. Both show in the bot's log as an error frame.
