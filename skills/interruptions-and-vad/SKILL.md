---
name: interruptions-and-vad
description: Tune what counts as speech (the VAD threshold, shared by Universal-3.6 Pro and Silero) and how the agent handles being interrupted (barge-in). Use when setting up an agent for a noisy or quiet environment, when background noise, TV, other people or echo make the agent stop talking or hear things, when quiet speakers aren't heard, when interruptions feel slow or too eager, or when some messages must not be interrupted.
---

# Interruptions and VAD

Two things decide when the user is speaking: Universal-3.6 Pro's own voice activity detection (`vad_threshold`) and Silero's in the user aggregator (`confidence`), which makes interruptions fast. They should agree, so both come from one setting in `src/bot.py`:

```python
VAD_THRESHOLD = 0.2  # used for Settings(vad_threshold=...) and VADParams(confidence=...)
```

`0.2` is Universal-3.6 Pro's default in every mode. Always change the two together: if they differ, one hears speech the other doesn't, and interruptions lag.

## Ask

- Where will users be? A quiet room, a car, the street, a busy office or call center, a shop floor, a kiosk?
- On what device: phone handset, headset, laptop or speakerphone?
- Can the agent hear itself (speakerphone, laptop speakers without echo cancellation)?

## Choose

| Situation | What to do |
|---|---|
| Quiet room, headset or phone | Keep `0.2`. |
| Background noise or chatter makes the agent stop mid-reply, or hear words nobody said | Turn on the [voice-focus skill](../voice-focus/SKILL.md) first. If it still happens, raise `VAD_THRESHOLD` to `0.3`, then `0.4`. |
| Quiet or distant speakers aren't heard | Lower `VAD_THRESHOLD` to `0.15`. |
| Coughs or short noises cut the agent off | Raise Silero's `start_secs` (below). |
| Interruptions feel slow | Lower `interruption_delay` (below). |

Higher thresholds miss soft speech; lower ones react to noise. Move in steps of about 0.1 and test with real audio from the target environment.

## Other settings

- **Silero, in `VADParams(...)`:** `start_secs` (default `0.2`) is how long speech must last before it counts; raise it to `0.4` in noisy places. `min_volume` (default `0.6`) ignores quiet audio; raise it if distant voices trigger interruptions.
- **`interruption_delay`** in `AssemblyAISTTService.Settings(...)` sets how soon the first partial transcript arrives (0 to 1000 ms; the server adds 256 ms). `"balanced"` uses 500. Lower it (`0`) for faster barge-in; raise it for more confident first partials in noise.
- **`should_interrupt=False`** on `AssemblyAISTTService(...)` makes the agent impossible to interrupt.
- **Messages that must be heard in full,** such as a disclosure: give the user aggregator a mute strategy, in `LLMUserAggregatorParams(user_mute_strategies=[...])`, from `pipecat.turns.user_mute`. `FirstSpeechUserMuteStrategy()` protects the greeting; `FunctionCallUserMuteStrategy()` protects tool calls; `AlwaysUserMuteStrategy()` turns interruptions off.

## Check it

Run `uv run src/bot.py` and talk at http://localhost:7860/client with the noise the agent will face (play a recording of it if needed). Talk over the agent, cough, and stay silent while the noise plays. The agent should stop for real interruptions only.
