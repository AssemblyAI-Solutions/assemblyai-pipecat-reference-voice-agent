---
name: medical-mode
description: Turn on AssemblyAI Medical Mode for medical vocabulary (medications, doses, conditions, procedures) in Universal-3.6 Pro transcription. Use when the agent handles healthcare conversations, such as a clinic, pharmacy, telehealth, patient intake, insurance or care line, or when drug names and medical terms are transcribed wrong. Also covers handling health data (HIPAA, BAA).
---

# Medical Mode

Medical Mode improves transcription of medication names, doses, conditions and procedures. Turn it on in `src/bot.py`:

```python
AssemblyAISTTService.Settings(
    ...,
    domain="medical-v1",
)
```

- It's a paid add-on, billed on top of streaming transcription.
- It supports English, Spanish, German and French. For other languages, leave it off.
- Nothing else in the pipeline changes.

## Ask

- Will users talk about medications, doses, symptoms or procedures?
- Which language?
- Will the agent handle protected health information? Then the user needs a Business Associate Agreement with AssemblyAI (below).

## With it

- Describe the calls in `prompt` and add the practice's names (doctors, clinic, local pharmacies) to `keyterms_prompt`: see the [keyterms-and-prompt skill](../keyterms-and-prompt/SKILL.md).
- Have the agent read doses and names back for the user to confirm; put that in `INSTRUCTIONS`.
- Patients pause mid-sentence while describing symptoms or reading a label; consider a longer `max_turn_silence`: see the [turn-detection skill](../turn-detection/SKILL.md).
- Don't log transcripts or tool arguments that contain patient details. Log IDs only.

## Health data

AssemblyAI offers a Business Associate Agreement (BAA) for protected health information. Paid accounts can sign the standard BAA from the Data Controls page in the AssemblyAI dashboard. Medical Mode doesn't change how data is handled or retained. A BAA also matters for the LLM provider and wherever transcripts are stored; flag that to the user rather than assuming.

## Check it

Run `uv run src/bot.py`, talk to it at http://localhost:7860/client, and read out a few medications with doses ("lisinopril ten milligrams once a day", "metformin five hundred milligrams twice daily"). Compare the transcripts with Medical Mode off and on.
