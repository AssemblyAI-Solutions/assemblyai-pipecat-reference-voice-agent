---
name: voice-focus
description: Turn on AssemblyAI Voice Focus, server-side noise suppression that isolates the main speaker before transcription. Use when users will be somewhere noisy (call center, street, car, café, shop, drive-thru, kiosk, conference room, speakerphone or laptop mic), when background voices, TV, music or keyboard noise get transcribed or interrupt the agent, or when the user asks about noise cancellation.
---

# Voice Focus

Voice Focus isolates the primary voice and suppresses background chatter, keyboard clicks, fan hum and room echo on AssemblyAI's side, before the audio reaches Universal-3.6 Pro. It's off by default. Turn it on in `src/bot.py`:

```python
AssemblyAISTTService.Settings(
    ...,
    voice_focus="near-field",
    # voice_focus_threshold=0.7,  # 0.0 to 1.0; higher suppresses more
)
```

## Ask

- How close is the speaker to the microphone? Phone held to the ear or a headset, or a laptop, speakerphone, kiosk or room mic?
- What's in the background? Other people talking, TV, traffic, music, machinery?

## Choose

| Setting | `voice_focus` |
|---|---|
| Phone calls, headsets, earbuds, handsets | `"near-field"` |
| Laptop mics, speakerphones, kiosks, drive-thrus, conference rooms, smart speakers | `"far-field"` |
| Quiet rooms with close mics | Leave it off |

`voice_focus_threshold` defaults to `0.7` for both. Raise it (`0.8`, `0.9`) if background voices still get transcribed; lower it (`0.5`) if quiet parts of the user's own speech go missing.

Changing either mid-call reconnects the STT.

## Don't stack noise cancellation

Don't also clean the audio before it reaches the STT, for example with an `audio_in_filter` on the transport: its artifacts usually hurt accuracy more than the noise. Use Voice Focus instead. Leave the sample rate at 16 kHz; higher rates don't help.

## With it

If noise still interrupts the agent with Voice Focus on, raise the VAD threshold: see the [interruptions-and-vad skill](../interruptions-and-vad/SKILL.md).

## Check it

Run `uv run src/bot.py`, talk to it at http://localhost:7860/client, and play the kind of background noise the agent will face (a recording of a café or street is fine) while talking. Compare the transcripts in the bot's log with Voice Focus off and on.
