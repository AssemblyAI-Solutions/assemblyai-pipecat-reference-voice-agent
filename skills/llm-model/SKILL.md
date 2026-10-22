---
name: llm-model
description: Choose the voice agent's LLM from the models on AssemblyAI's LLM Gateway (Claude, Gemini, GPT, Gemma, Qwen, Nemotron and more), or switch to another, and check it still works. Use when setting up a new agent, when the user wants a different, faster, cheaper or smarter LLM, asks which models are available, asks about latency or time to first token, or needs an LLM served in the EU.
---

# LLM model

The agent reaches every LLM through AssemblyAI's [LLM Gateway](https://www.assemblyai.com/docs/llm-gateway/quickstart), an OpenAI-compatible API, with the same AssemblyAI key. Switching is one line in `src/bot.py`:

```python
LLM_MODEL = "gemma-4-31b"
```

Model ids have no provider prefix: `claude-haiku-4-5-20251001`, not `anthropic/claude-haiku-4-5-20251001`.

## Choosing

A voice agent can't start speaking until the LLM sends its first token, so speed matters more than in a chat app. The agent also needs a model that can call tools reliably while following a long set of instructions.

- **Fast and cheap, for most agents:** `gemma-4-31b` (the default), `gemini-3.5-flash-lite`, `gemini-2.5-flash-lite`, `gpt-6-luna`, `claude-haiku-4-5-20251001`, `gpt-4.1`. These start answering in well under a second.
- **Smarter, for complicated calls:** `claude-sonnet-4-6`, `claude-haiku-5-5`, `gemini-3.8-flash`, `gpt-6-sol`. Expect about a second before the first word.
- **Avoid for live calls:** models that reason at length before answering, such as `gemini-2.5-pro`, `gpt-5` or `kimi-k3`, which can take several seconds to start.

The Gateway publishes its own latency measurements for each model in the `performance` field of `GET /v1/models` (`ttft` is time to first token), which is where these groupings come from.

## Ask

- What matters most: replying fast, low cost, or handling complicated requests and many tools well?
- Must data stay in the EU? Then pick from the models marked EU, and see the [data-residency skill](../data-residency/SKILL.md).

Suggest one or two models.

## Every model that works for a voice agent

These support tool calling and streaming. "EU" marks models also served by the EU Gateway.

| Maker | Models |
|---|---|
| Anthropic | `claude-haiku-4-5-20251001` (EU), `claude-haiku-5-5` (EU), `claude-sonnet-4-5-20250929` (EU), `claude-sonnet-4-6` (EU), `claude-sonnet-5`, `claude-sonnet-5-5`, `claude-opus-4-5-20251101`, `claude-opus-4-6`, `claude-opus-4-7`, `claude-opus-4-8`, `claude-opus-5`, `claude-opus-5-5` (EU) |
| Google | `gemma-4-31b`, `gemini-2.5-flash-lite` (EU), `gemini-2.5-flash` (EU), `gemini-2.5-pro` (EU), `gemini-3.1-flash-lite` (EU), `gemini-3.5-flash-lite` (EU), `gemini-3.5-flash` (EU), `gemini-3.6-flash` (EU), `gemini-3.7-flash` (EU), `gemini-3.8-flash` (EU), `gemini-4-argon` (EU) |
| OpenAI | `gpt-4.1`, `gpt-5`, `gpt-5-mini`, `gpt-5-nano`, `gpt-5.1`, `gpt-5.2`, `gpt-5.5`, `gpt-5.6-luna` (EU), `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-6-luna`, `gpt-6-sol` (EU), `gpt-6-astra` |
| Nvidia | `nemotron-3-nano-30b-a3b` (EU), `nemotron-3-super-120b-a12b` (EU), `nemotron-nano-9b-v2` (EU), `nemotron-lightning-3p5-30b-a3b` |
| Qwen | `qwen3-32B` (EU), `qwen3-next-80b-a3b` (EU) |
| DeepSeek | `deepseek-v4.1-flash`, `deepseek-v4.1-flash-1017` |
| Z.ai | `glm-5.3`, `glm-5.3-flash` |
| xAI | `grok-4.7` |
| Moonshot AI | `kimi-k3` |
| MiniMax | `minimax-m3` |
| Meta | `muse-spark-open` |

The list changes as models are added. To get the current one, with pricing and context lengths:

```console
set -a; . ./.env.local; set +a
curl -s https://llm-gateway.assemblyai.com/v1/models -H "Authorization: $ASSEMBLYAI_API_KEY" \
  | jq -r '.data[] | select((.supported_parameters // []) | index("tools") and index("stream")) | .id'
```

Use `https://llm-gateway.eu.assemblyai.com/v1/models` for the EU list. See the [model catalog](https://www.assemblyai.com/products/llm-gateway/models) for prices.

## Steps

1. Set `LLM_MODEL` in `src/bot.py` to the model's id.
2. For the EU, also set `LLM_GATEWAY_URL = "https://llm-gateway.eu.assemblyai.com/v1"` and choose an EU model.
3. Run the tests twice, since an LLM doesn't answer the same way every time:
   ```console
   uv run pytest tests/test_bot.py
   uv run pytest tests/test_bot.py
   ```
4. Talk to it with `uv run src/bot.py` at http://localhost:7860/client to feel the latency.

## If the tests fail

- **The model answers instead of calling a tool, or makes things up:** make the relevant instruction in `INSTRUCTIONS` more explicit, or choose a stronger model.
- **Replies are long or use lists:** some models need the "How to talk" rules repeated; add "Never use lists or markdown." to the end of `INSTRUCTIONS`.
- **`404` or "model not found":** check the id against the list from `/v1/models`, without a provider prefix, and that the model is served by the Gateway you're using (US or EU).

The tests' judge uses `JUDGE_MODEL` in `tests/test_bot.py` (`claude-sonnet-4-6`); leave it as it is when you switch the agent's model, so the bar stays the same.
