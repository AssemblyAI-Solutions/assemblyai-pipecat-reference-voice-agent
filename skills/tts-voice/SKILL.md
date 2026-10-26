---
name: tts-voice
description: Choose the agent's AssemblyAI text-to-speech voice, find and preview voices in the 4,000+ voice library, or use a cloned voice. Use when setting up a new agent's persona, or when the user wants a different voice (male, female, young, older, British, American, warm, deep, energetic, calm...), wants to hear voices, or wants their own or their brand's voice.
---

# TTS voice

The agent speaks with AssemblyAI streaming TTS. The voice is set in `src/bot.py`, through `AssemblyAITTSService` in `src/assemblyai_tts.py`:

```python
TTS_VOICE = "49c443a4-8a1d-5f7e-b70b-98bdbd9823c3"  # Audrey
ASSISTANT_NAME = "Audrey"
...
tts = AssemblyAITTSService(api_key=api_key, voice=TTS_VOICE)
```

`ASSISTANT_NAME` is used in the greeting, the instructions and the STT's key terms. When the voice changes, change the name to the voice's name, unless the user wants the agent called something else.

## Ask

- Who's the agent for, and what should it sound like? Gender, age, accent, energy (calm, warm, upbeat, fast-paced).
- Does the user have a brand or person's voice to clone?
- What language will it speak? If not English, also use the [languages skill](../languages/SKILL.md).

## Find candidates

Every voice has an `id` (a UUID that never changes), a `name`, a `language`, a `description` and `tags`: `gender:female`/`gender:male`, `age:young`/`age:middle-aged`/`age:old`, `accent:british`/`accent:irish`/`accent:south-african`, and style tags such as `warm`, `deep`, `soft-spoken`, `energetic`, `expressive`, `fast-paced`, `breathy`, `unhurried`.

```console
set -a; . ./.env.local; set +a
curl -s "https://tts.us.assemblyai.com/v1/voices?scope=public&language=english&limit=100" \
  -H "Authorization: $ASSEMBLYAI_API_KEY" \
  | jq -r '.voices[] | select(.tags | index("accent:british") and index("gender:female")) | "\(.id)  \(.name)  \(.description)"'
```

`language` is one of `english`, `spanish`, `german`, `french`, `italian`, `portuguese`. Results come 100 at a time; while `has_more` is true, add `&cursor=<next_cursor>` for the next page. Offer the user two or three voices that fit, with their descriptions.

Eleven featured voices speak all six languages; every other library voice speaks only the language it was recorded in:

| Voice | `TTS_VOICE` |
|---|---|
| Alba, Anna, Charles, Eve, George, Jane, Jean, Mary, Michael, Paul, Vera | `aai-alba`, `aai-anna`, `aai-charles`, `aai-eve`, `aai-george`, `aai-jane`, `aai-jean`, `aai-mary`, `aai-michael`, `aai-paul`, `aai-vera` |

## Let the user hear them

One request turns a sentence into a WAV file. Use the agent's own greeting:

```console
curl -sS --fail-with-body https://tts.us.assemblyai.com/v1/speech \
  -H "Authorization: $ASSEMBLYAI_API_KEY" -H "Content-Type: application/json" \
  -d '{"text": "Hi, I'\''m Yasmin. How can I help?", "voice_id": "ddbf46ac-77a9-5784-bec3-6685db0f0b10", "container": "wav"}' \
  -o voice.wav && afplay voice.wav
```

`afplay` is macOS; on Linux use `aplay`; otherwise tell the user where the file is. For a featured voice in another language, add `"language": "spanish"` (a name, not a code).

## Set it

Set `TTS_VOICE` to the voice's `id` (prefer ids to slugs: slugs can change) and `ASSISTANT_NAME` to its name. Run `uv run src/bot.py`, open http://localhost:7860/client and let the user hear the greeting.

## A cloned voice

Voices are cloned in the [AssemblyAI dashboard](https://www.assemblyai.com/dashboard), not in code. Set `TTS_VOICE` to the id the dashboard shows. A cloned voice speaks only the language it was recorded in (don't pass another `language`), and exists only in the region it was created in (see the [data-residency skill](../data-residency/SKILL.md)). See [Voice cloning](https://www.assemblyai.com/docs/tts/cloned-voices).

## If it fails

The TTS checks the voice when it connects, and the error is in the bot's log: `3012 voice_not_found` for an unknown id, `3006` for a voice that doesn't speak the requested language (the message lists voices that do).
