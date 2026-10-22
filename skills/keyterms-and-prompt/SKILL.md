---
name: keyterms-and-prompt
description: Help Universal-3.6 Pro spell names, brands, products and jargon right with keyterms_prompt, and describe what conversations are about with prompt, including updating them mid-call (for example with the caller's name after a lookup). Use when setting up an agent for a specific business or domain, or when names, product names, technical terms or other words are transcribed wrong.
---

# Key terms and prompt

Universal-3.6 Pro is accurate out of the box, so start with neither and add them only for words it gets wrong, or will plainly need (the agent's own name, the company, its products). Both go in `AssemblyAISTTService.Settings(...)` in `src/bot.py`:

```python
STT_KEYTERMS = [ASSISTANT_NAME, "Northwind Bank", "FlexSaver", "Dr. Okafor"]
...
AssemblyAISTTService.Settings(
    ...,
    keyterms_prompt=STT_KEYTERMS,
    prompt="Customer support call to a bank about cards, accounts and payments.",
)
```

## Ask

- What names will come up: the company, staff, products, places, competitors?
- Is there jargon, product codes or acronyms?
- What are the conversations about, in a sentence?

## `keyterms_prompt`: words to spell right

- At most 100 terms per session, each 50 characters or less (longer ones are ignored; more than 100 is an error).
- Write each exactly as it should appear in the transcript: spelling, capitals, punctuation.
- Only uncommon words. Common words ("account", "information") don't help and can cause wrong substitutions.
- It's safe to pass terms that may not be said, so a whole product catalog is fine within the limit.

## `prompt`: what the conversation is about

One short sentence or paragraph of context, not instructions and not a list of words (that's what key terms are for). Start broad ("Customer support call about an internet outage") and add only details the app actually knows, such as the caller's name or account. Transcription behavior (punctuation, verbatim output, turn detection) is built in; the prompt can't change it.

## Mid-call

To add a name once a tool has looked up who's calling, without reconnecting the STT, use the `AssemblyAISTT` subclass from the [turn-detection skill](../turn-detection/SKILL.md) ("Only while waiting for something long"):

```python
await stt.update_live(keyterms_prompt=[*STT_KEYTERMS, "Siobhan Ní Bhriain"])
```

## Already handled

Pipecat passes each of the agent's replies to Universal-3.6 Pro as context (`agent_context`), so after "What's your email?" it expects an email. That's on by default and needs no code.

## Check it

Run `uv run src/bot.py`, talk at http://localhost:7860/client, and say the terms as a user would, in sentences. Check the transcripts in the bot's log. For a medical vocabulary, see also the [medical-mode skill](../medical-mode/SKILL.md).
