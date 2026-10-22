# tests

```console
uv run pytest
```

| File | What it checks | Needs |
|---|---|---|
| [`test_clinic.py`](test_clinic.py) | The made-up clinic: finding and registering patients, open times, booking | Nothing |
| [`test_bot.py`](test_bot.py) | The receptionist, as text through the LLM Gateway | `ASSEMBLYAI_API_KEY` in `.env.local` |
| [`test_tts.py`](test_tts.py) | `AssemblyAITTSService` against the live API: a reply with word timings, and an interruption | `ASSEMBLYAI_API_KEY` in `.env.local` |

The receptionist tests use the same instructions, tool schemas and tool functions as `src/bot.py`, without audio or a Pipecat pipeline. Two of them play out a whole call against a simulated caller, another LLM given a persona, then check what ended up in the clinic's records:

- **A new patient**, whose intake details must be saved exactly as given, and an afternoon new patient visit booked.
- **Maria Garcia, a returning patient**, who must get a morning follow-up with Dr. Nakamura.

The rest check single replies, judged by an LLM: the agent doesn't invent a patient it can't find, sends an emergency to 911, and gives no medical advice.

## When to run them

Run them whenever you change the instructions, a tool or the model, and run them more than once, because an LLM doesn't answer the same way every time. Run `test_tts.py` after any change to `src/assemblyai_tts.py`. Without a key, the live tests are skipped.

## Adding a test

For a new behavior, write the test first, then change the agent until it passes. Check the clinic's records where you can, rather than the agent's wording. The two simulated calls in `test_bot.py` show the pattern: a persona, a call played until something is booked, then assertions on the appointment.
