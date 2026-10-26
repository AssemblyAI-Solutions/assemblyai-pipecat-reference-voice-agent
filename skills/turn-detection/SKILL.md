---
name: turn-detection
description: Choose how quickly Universal-3.6 Pro decides the user has finished speaking, with the STT mode preset (min_latency, balanced, max_accuracy) and min_turn_silence / max_turn_silence. Use when setting up a new agent, when the agent feels slow to reply or replies before the user has finished, when users get cut off mid-sentence or while reading out numbers, emails or addresses, or when the user asks about latency, endpointing or turn-taking.
---

# Turn detection

Universal-3.6 Pro decides when the user's turn has ended, reading the words as well as the silence (`vad_force_turn_endpoint=False` in `src/bot.py`). After a short pause (`min_turn_silence`) it checks whether the turn reads as finished: a complete sentence ends the turn there; an unfinished one stays open. After a long pause (`max_turn_silence`) the turn ends regardless.

**Entity-aware endpointing** is built in and needs no settings: when a turn ends in something still in progress, such as digits, a spelled code, an email, an address, a date or a name, the turn is held open until `max_turn_silence`. AssemblyAI measured it cutting phone-number errors from 7.0% to 2.2%, with the median reply time unchanged.

## The preset

```python
STT_MODE = "balanced"  # src/bot.py
```

| `STT_MODE` | `min_turn_silence` | `max_turn_silence` | First partial (`interruption_delay` + 256 ms) | Use for |
|---|---|---|---|---|
| `"min_latency"` | 128 ms | 640 ms | ~256 ms | Fast back-and-forth with short answers: quick Q&A, menus, confirmations. Long pauses split turns. |
| `"balanced"` (default) | 128 ms | 1280 ms | ~756 ms | Most voice agents. |
| `"max_accuracy"` | 512 ms | 2560 ms | ~756 ms | Users who dictate (IDs, addresses, emails), think aloud, or speak slowly, where a slower reply is acceptable. |

## Ask

- What will users say: short answers, or long explanations, numbers, emails, addresses?
- Do they pause to think or look things up mid-sentence (older callers, people reading from a card)?
- Which matters more when they conflict: replying fast, or never cutting the user off?

## Fine-tuning

Set either value in `AssemblyAISTTService.Settings(...)` to override the preset's:

```python
AssemblyAISTTService.Settings(..., mode=STT_MODE, max_turn_silence=2000)
```

- **Users cut off mid-thought or while dictating:** raise `max_turn_silence` (try 2000, up to about 4000). Turns that are held open then take that long to end.
- **Turns end early on a pause after something that looks complete,** such as a spelled email ("It's John." "Smith."): raise `min_turn_silence` (try 400).
- **Replies feel slow:** lower `max_turn_silence`, or use `"min_latency"`. Expect more split turns; an LLM usually copes with a split sentence, but not with a split ID.

## Only while waiting for something long

To be patient only when the agent has asked for something like a phone number, change the values mid-call. In Pipecat 1.13, changing them through an `STTUpdateSettingsFrame` reconnects the STT, so send AssemblyAI's `UpdateConfiguration` message directly with a small subclass in `src/bot.py`:

```python
class AssemblyAISTT(AssemblyAISTTService):
    """AssemblyAI streaming STT whose settings can change mid-call without reconnecting."""

    async def update_live(self, **fields) -> None:
        for name, value in fields.items():
            setattr(self._settings, name, value)  # so a reconnect keeps them
        await self._send_update_configuration(**fields)
```

Create the STT with `AssemblyAISTT(...)` instead, with the same arguments, and switch on the agent's latest reply (after `LLMContextAggregatorPair(...)` in `run_bot`):

```python
    @assistant_aggregator.event_handler("on_assistant_turn_stopped")
    async def wait_longer_for_numbers(aggregator, message):
        asks = "?" in message.content and "number" in message.content.lower()
        await stt.update_live(max_turn_silence=3000 if asks else 1280)
```

It uses a private method of Pipecat's service, so check it still exists when you upgrade `pipecat-ai`. In testing, a phone number read with a 2.2-second pause arrived as two turns on `balanced` and as one with `max_turn_silence=3000`; the agent then replied about 3 seconds after the number ended.

## Keep as they are

`vad_force_turn_endpoint=True` (Pipecat's default) would hand turn decisions to Pipecat's own turn analyzer instead and force AssemblyAI to end turns at every short pause. Keep `False` to use Universal-3.6 Pro's turn detection.

## Check it

Run `uv run src/bot.py` and talk at http://localhost:7860/client: pause mid-sentence for a second, read out a phone number in chunks. Turns should end where the user expects.
