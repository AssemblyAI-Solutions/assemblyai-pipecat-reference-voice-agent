# tests

```console
uv run pytest
```

| File | What it checks |
|---|---|
| [`test_bot.py`](test_bot.py) | The assistant, as text through the LLM Gateway: it uses `get_current_time` for the right place, doesn't make up a time for somewhere without a time zone, keeps replies short and speakable, and hangs up after goodbye |
| [`test_tts.py`](test_tts.py) | `AssemblyAITTSService` against the live API: a reply with word timings, and an interruption |

`test_bot.py` runs the same instructions, tool schemas and tool functions as `src/bot.py`, without audio or a Pipecat pipeline. Tool calls are checked exactly; wording is judged by another LLM. Both files need `ASSEMBLYAI_API_KEY` in `.env.local` and are skipped without it.

Run them whenever you change the instructions, a tool or the model, and more than once, since an LLM doesn't answer the same way every time. Run `test_tts.py` after any change to `src/assemblyai_tts.py`. For each new tool or behavior, add a test like these; the [add-a-tool skill](../skills/add-a-tool/SKILL.md) has an example.
