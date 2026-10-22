---
name: data-residency
description: Keep audio, text and LLM requests in the EU (or pin them to the US) by pointing AssemblyAI's speech-to-text, text-to-speech and LLM Gateway at regional hosts. Use when the user mentions GDPR, data residency, the EU or Europe, where data is processed, or customers who require it.
---

# Data residency

Each AssemblyAI service has its own regional host. To keep everything in the EU, change all three in `src/bot.py`:

```python
from assemblyai_tts import EU_BASE_URL

LLM_GATEWAY_URL = "https://llm-gateway.eu.assemblyai.com/v1"
...
stt = AssemblyAISTTService(..., api_endpoint_base_url="wss://streaming.eu.assemblyai.com/v3/ws")
...
tts = AssemblyAITTSService(api_key=api_key, voice=TTS_VOICE, base_url=EU_BASE_URL)
```

## The LLM

The EU Gateway serves a subset of models, and not the default `gemma-4-31b`. Set `LLM_MODEL` to one it serves, such as `gemini-3.5-flash-lite` or `claude-haiku-4-5-20251001`. List them:

```console
curl -s https://llm-gateway.eu.assemblyai.com/v1/models -H "Authorization: $ASSEMBLYAI_API_KEY" \
  | jq -r '.data[] | select((.supported_parameters // []) | index("tools")) | .id'
```

See the [llm-model skill](../llm-model/SKILL.md) for choosing between them.

## The voice

Library voices work in both regions. A cloned voice exists only in the region where it was created, so a voice cloned in the US can't be used on the EU host; clone it again in the EU.

## Elsewhere

- Pipecat Cloud and Daily: choose a region to match. See [Pipecat Cloud regions](https://docs.pipecat.ai/pipecat-cloud/guides/regions).
- Anything else the agent calls (its tools' APIs, logs, storage) needs the same check.

## Check it

`uv run pytest` (the tests use `LLM_GATEWAY_URL`, and the TTS tests the US host), then `uv run src/bot.py`: the agent should greet, hear and reply as before.
