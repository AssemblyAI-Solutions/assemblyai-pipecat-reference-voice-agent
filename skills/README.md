# skills

Building blocks for coding agents. Each folder holds a `SKILL.md` that tells an agent such as Claude Code, Cursor or Codex when a setting matters, what to ask you about it, and how to change it in `src/bot.py`. [`AGENTS.md`](../AGENTS.md) ties them together: the questions to ask, and which skill each answer points to.

| Skill | Setting |
|---|---|
| [tts-voice](tts-voice/SKILL.md) | The voice: library, previews, cloning |
| [languages](languages/SKILL.md) | What languages the agent hears and speaks |
| [turn-detection](turn-detection/SKILL.md) | How quickly a user's turn ends |
| [interruptions-and-vad](interruptions-and-vad/SKILL.md) | What counts as speech, and barge-in |
| [voice-focus](voice-focus/SKILL.md) | Noise suppression for noisy places |
| [keyterms-and-prompt](keyterms-and-prompt/SKILL.md) | Names and jargon to spell right |
| [medical-mode](medical-mode/SKILL.md) | Medical vocabulary |
| [llm-model](llm-model/SKILL.md) | The LLM, from 50 on the Gateway |
| [data-residency](data-residency/SKILL.md) | Keeping data in the EU |
| [add-a-tool](add-a-tool/SKILL.md) | New abilities for the agent |

Claude Code loads them automatically through [`.claude/skills`](../.claude/skills). Other coding agents find them through `AGENTS.md`.
