---
name: make-it-yours
description: Turn the clinic receptionist into the user's own voice agent (a different business, use case, persona or language), or connect its tools to real systems such as a practice management system, EHR, CRM, booking or order API. Use when the user wants to build their own agent from this starter, rename or repurpose it, add or change tools, or replace the made-up clinic with real data.
---

# Make it yours

The receptionist is three things you change, on a pipeline you don't need to touch:

| What | Where |
|---|---|
| What the agent knows and does: its records and actions | `src/clinic.py`, and the tool functions and `TOOLS` schemas in `src/bot.py` |
| How it talks: persona, rules, the order of questions | `INSTRUCTIONS`, `GREETING`, `RECEPTIONIST_NAME`, `TTS_VOICE` in `src/bot.py` |
| What it expects to hear | The STT's `domain`, `prompt` and `keyterms_prompt` in `run_bot` |

The rest of `run_bot` (transport → STT → LLM → TTS) stays as it is.

## First, ask

Before changing code, find out from the user, briefly:

1. What the agent is for, and who calls it.
2. What it must collect or look up, and what it must be able to do (book, cancel, check an order, transfer...).
3. Whether there's a real system behind it now (an API to call), or it should run on made-up data first.
4. Its name, and the language it speaks.

Start with made-up data unless they already have an API ready: it gets a working agent to talk to quickly, and the real system can replace it later without touching the agent.

## Connect the receptionist to a real system

If the user keeps the receptionist and wants real patients and schedules, only `src/clinic.py` changes. The agent calls five methods on `Clinic`: `find_patient`, `register_patient`, `upcoming_appointments`, `open_slots` and `book`. Reimplement those against the system's API, keeping their arguments and return types (`Patient`, `Slot`, `Appointment`).

- If the API client is async, make those methods `async`, make the four tool functions `async` and `await` them, and `await` the tool in `call_tool` and `_run_clinic_tool`.
- Read credentials from the environment, add them to `.env.example` with a comment, and to the Pipecat Cloud secret set when deploying.
- Keep `clinic.py` free of Pipecat imports, so `tests/test_clinic.py` can test it alone. Replace that test's fixtures with a sandbox account or recorded responses.
- `CLINIC_NAME` and `PROVIDERS` feed the instructions and the STT's key terms, so load them from the real system too.

## Build a different agent

Work in this order, running `uv run pytest` as you go and talking to it with `uv run src/bot.py`.

1. **The records.** Replace `src/clinic.py` with a module for the new domain, such as `src/store.py` with orders and returns, in the same shape: plain dataclasses and one class whose methods are the actions, with no Pipecat code. Rewrite `tests/test_clinic.py` for it.
2. **The tools.** Replace the four tool functions in `src/bot.py`, keep `CLINIC_TOOLS` (rename it) pointing at them, and rewrite their schemas in `TOOLS`. Follow the rules below. Keep `end_call`.
3. **The state.** `CallState` holds what the call is about once it's known, such as the customer or the order. Tools take it as their first argument, rather than the LLM passing IDs between tools.
4. **The words.** Rewrite `INSTRUCTIONS` with the same sections: who it is and that everything is spoken; how to talk; safety and limits; each task step by step, naming the tool to call; and when to end the call. Rewrite `GREETING`. Set `RECEPTIONIST_NAME` (rename it, too) and pick a voice with the [change-the-voice skill](../change-the-voice/SKILL.md).
5. **The ears.** In `run_bot`, rewrite the STT's `prompt` to describe the new calls, and put the business's names, products and jargon in `keyterms_prompt`. Remove `domain="medical-v1"` unless the calls are medical.
6. **The deployment name.** Change `agent_name` and `secret_set` in `pcc-deploy.toml`.
7. **The tests.** Rewrite the personas and checks in `tests/test_bot.py`: one simulated call per main task, asserting on the records it leaves behind, plus single-reply checks for the things it must never do. Run them at least twice.
8. **The docs.** Update `README.md`, `src/README.md` and `AGENTS.md` so they describe the new agent.

## Rules for tools

- A tool is a plain function that takes the call's state and the LLM's arguments and returns a string. It has no Pipecat code, so the tests can call it directly.
- Its schema in `TOOLS` is what the LLM sees: say what it does in one line, and describe every property. Use `"enum"` for fixed choices, as `visit_type` does, so the LLM can only pass valid ones.
- Take dates as `YYYY-MM-DD` strings and parse them in the tool, as `_parse_date` does.
- Return one or two plain spoken sentences. Everything the agent says is spoken, so no JSON, lists or markdown.
- When something goes wrong, raise `ToolError` with a message that tells the LLM how to recover with the caller: "No order has that number. Read the number back to the caller and ask them to check it."
- Log IDs only, never names, numbers or other personal details.

## Check it

- `uv run ruff format && uv run ruff check` are clean.
- `uv run pytest` passes, twice.
- A spoken call at http://localhost:7860/client goes end to end, including an interruption, a correction ("no, it's 4 1 6") and a goodbye that ends the call.
