---
name: wait-longer-for-numbers
description: Give callers more time to finish reading out phone numbers, member IDs, dates of birth and spellings, by slowing Universal-3.6 Pro's turn detection only while the agent waits for one. Use when callers get cut off mid-number, a number is split across two turns, the agent replies before the caller has finished an ID, or the user asks to slow down or tune turn detection or endpointing.
---

# Wait longer for numbers

Universal-3.6 Pro decides when the caller has finished talking (`vad_force_turn_endpoint=False` in `src/bot.py`). With `mode="balanced"` it ends a turn after at most 1.28 seconds of silence (`max_turn_silence=1280`). That's right for most answers, but people pause while they read a number off a card: "4 1 5, 5 5 5 ... 0 1 9 9". If the pause is longer than 1.28 seconds, the number arrives as two turns, and the agent answers the first half.

The fix is to wait longer only when the agent has just asked for something like that. The agent's own question says when: the moment it asks for a phone number, raise `max_turn_silence`; when it asks anything else, put it back. Every other turn keeps its speed.

Tested against the live API in a Pipecat pipeline: a phone number read with a 2.2-second pause arrived as two turns ("415-555." then "0199.") at the default, and as one ("415-555-0199.") with `max_turn_silence=3000`.

## Why a subclass

AssemblyAI applies a new `max_turn_silence` to an open stream through an `UpdateConfiguration` message. Pipecat 1.13's `AssemblyAISTTService` sends that message itself for only a few settings; changing `max_turn_silence` through an `STTUpdateSettingsFrame` reconnects the WebSocket instead, mid-call. A four-line subclass sends the update without reconnecting.

## Steps

### 1. Add the subclass and settings to `src/bot.py`

Add `import re` to the imports. Then, next to the other settings near the top:

```python
# The agent's questions whose answers callers read out slowly: numbers, IDs, dates, spellings
ASKS_FOR_DETAILS = re.compile(r"phone|number|member id|date of birth|birthday|spell", re.IGNORECASE)
# How long a pause can be before the caller's turn ends, in ms, after one of those questions
PATIENT_MAX_TURN_SILENCE = 3000
# ...and after any other question: what mode="balanced" uses
BALANCED_MAX_TURN_SILENCE = 1280
```

And before `run_bot`:

```python
class AssemblyAISTT(AssemblyAISTTService):
    """AssemblyAI streaming STT whose turn detection can be slowed down mid-call."""

    async def set_max_turn_silence(self, ms: int) -> None:
        """Change how long a pause ends the caller's turn, without reconnecting."""
        self._settings.max_turn_silence = ms  # so a reconnect keeps it
        await self._send_update_configuration(max_turn_silence=ms)
```

It uses a private method of Pipecat's service, so check it still exists when you upgrade `pipecat-ai`.

### 2. Use it in `run_bot`

Create the STT with the subclass, with the same arguments:

```python
    stt = AssemblyAISTT(
        api_key=api_key,
        ...  # unchanged
    )
```

Then, after `LLMContextAggregatorPair(...)`, switch the setting each time the agent finishes a reply:

```python
    @assistant_aggregator.event_handler("on_assistant_turn_stopped")
    async def wait_longer_for_details(aggregator, message):
        asks = "?" in message.content and ASKS_FOR_DETAILS.search(message.content) is not None
        await stt.set_max_turn_silence(
            PATIENT_MAX_TURN_SILENCE if asks else BALANCED_MAX_TURN_SILENCE
        )
```

### 3. Fit the pattern to the agent

`ASKS_FOR_DETAILS` matches the receptionist's questions about phone numbers, member IDs, dates of birth and spelling. If the agent collects other things read out slowly, such as order numbers, card numbers, postcodes or email addresses, add words from those questions. Only questions count (`"?"`), so "Your confirmation number is 4 1 2 0 7." doesn't slow the next turn.

## Check it

1. `uv run ruff check` and `uv run pytest` pass. The text-only tests don't use the STT.
2. Run `uv run src/bot.py` and talk to it at http://localhost:7860/client as a new patient. When it asks for your phone number, read it with a two-second pause in the middle: it should wait for the whole number and read it back in full.

## Tuning

- **3000 ms** suits a caller reading from a card. In testing, the agent then replied about 3 seconds after the caller finished the number, rather than about 1.3, so the agent feels slower on exactly these answers. Go lower if that's too slow, or higher (up to about 5000) for callers who look things up mid-call.
- If turns end on a pause after something that looks complete, such as "415-555.", also raise `min_turn_silence` (balanced uses 128 ms): set `self._settings.min_turn_silence` and pass `min_turn_silence=` to `_send_update_configuration` the same way, and set it back with the other value.
- For the best accuracy on the numbers themselves, add the [sync-second-pass skill](../sync-second-pass/SKILL.md) too. It needs the whole number in one turn, which this skill provides.
