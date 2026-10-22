# skills

Skills are instructions for coding agents: each folder holds a `SKILL.md` that teaches an agent such as Claude Code, Cursor or Codex how to make one change to this voice agent, step by step, with code that's been tested against the AssemblyAI API.

| Skill | Use it to |
|---|---|
| [change-the-voice](change-the-voice/SKILL.md) | Pick a voice from the library of 4,000+, hear it, clone your own, or speak another language |
| [wait-longer-for-numbers](wait-longer-for-numbers/SKILL.md) | Stop callers being cut off while they read out phone numbers and IDs |
| [sync-second-pass](sync-second-pass/SKILL.md) | Re-transcribe answers with numbers and IDs with the Sync API, uploaded live from the pipeline's audio |
| [switch-llm](switch-llm/SKILL.md) | Move to any of the LLM Gateway's 50 tool-calling models |
| [make-it-yours](make-it-yours/SKILL.md) | Turn the receptionist into your own agent, or connect it to your real systems |

## Using them

**Claude Code** finds them automatically: [`.claude/skills`](../.claude/skills) links to this folder. Open the repo in Claude Code and ask in your own words, such as "make Keegan British" or "callers keep getting cut off reading their member ID", and the matching skill loads. You can also name one: `/change-the-voice`.

**Other coding agents** read [`AGENTS.md`](../AGENTS.md), which lists these skills. Or point your agent at one directly: "follow skills/sync-second-pass/SKILL.md".

You can also follow a skill yourself. They're written to be read.

## Writing your own

A skill is a folder with a `SKILL.md`: a short front matter, with a `name` and a `description` that says when to use it, then the steps.

```markdown
---
name: add-call-transfer
description: Let the agent transfer the caller to a person. Use when the user wants a human handoff, warm transfer or escalation.
---

# Add call transfer

...
```

Keep them specific to this repo: name the files, constants and functions to change, show the code, and say how to check it worked.
