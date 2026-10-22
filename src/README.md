# src

The agent, in three files short enough to read top to bottom.

| File | What's in it |
|---|---|
| [`bot.py`](bot.py) | Keegan: the instructions, the greeting, the tools and their schemas, and `run_bot`, which builds the pipeline. `bot()` is the entry point for Pipecat's runner and Pipecat Cloud |
| [`assemblyai_tts.py`](assemblyai_tts.py) | `AssemblyAITTSService`: AssemblyAI streaming TTS as a Pipecat service, with word timings and interruptions. Copy it into any Pipecat bot |
| [`clinic.py`](clinic.py) | The made-up clinic the tools work on: two doctors, two weeks of open times, and one returning patient. It has no Pipecat code in it, so you can swap it for your real systems |

Run the agent from the repo root with `uv run src/bot.py`, then open http://localhost:7860/client. Here's what each part does, and why.

## Text-to-speech

**One session per call.** `AssemblyAITTSService` opens one WebSocket to AssemblyAI when the pipeline starts and keeps it for the call. Each sentence from the LLM is sent as it's ready, so Keegan starts speaking before the LLM has finished the reply.

**The greeting doesn't wait for the LLM.** When the caller connects, `on_client_connected` queues a `TTSSpeakFrame` with a fixed greeting, which goes straight to the TTS.

**Interruptions are remembered word by word.** AssemblyAI TTS sends the time of every word it speaks, and the service passes those on as the bot's spoken text (`push_text_frames=False`). When the caller cuts in, the service sends `Cancel`, and the reply saved in the LLM context ends at the last word the caller heard, so the LLM doesn't think it said things it didn't.

**The voice is one setting.** `TTS_VOICE` is a voice id from the [voice library](https://www.assemblyai.com/docs/tts/voices) or a voice you've cloned. `RECEPTIONIST_NAME` is the name the agent introduces itself by, so change them together. To speak another language, pass it to the TTS, for example `AssemblyAITTSService(voice=..., language="es")`, and pick a voice that speaks it.

**Replies are written to be heard.** The instructions ask for one or two short sentences with no lists or markdown. Numbers to check are read one character at a time, in groups: "4 1 5, 5 5 5, 0 1 9 9".

## Speech-to-text

**Medical Mode, a description of the call, and the names it will hear.** `domain="medical-v1"` turns on [Medical Mode](https://www.assemblyai.com/docs/streaming/medical-mode) for medications, conditions and doses. It's a paid add-on; remove it to compare. `prompt` describes what a call is about, and `keyterms_prompt` lists the clinic's and doctors' names so they're spelled right.

**Universal-3.6 Pro decides when the caller is done.** `vad_force_turn_endpoint=False` uses AssemblyAI's end-of-turn detection, which reads the words as well as the silence: a caller who pauses partway through a phone number has said an unfinished number, so the turn stays open. The STT then tells Pipecat's user aggregator when turns start and end, so there's no Smart Turn model to configure. `mode="balanced"` ends a turn after at most 1.28 seconds of silence; `"min_latency"` cuts that to 0.64 seconds. To give callers longer while they read out numbers, use the [wait-longer-for-numbers skill](../skills/wait-longer-for-numbers/SKILL.md).

**The STT knows what the agent just asked.** Pipecat passes each of the agent's replies to Universal-3.6 Pro as context, so after "What's your date of birth?" it expects a date. That's on by default and needs no code.

**Silero and AssemblyAI agree on what speech is.** Silero's voice activity detection, in the user aggregator, helps decide when the caller is interrupting. Its threshold matches the STT's own (`VAD_THRESHOLD = 0.2`), so the two don't disagree about quiet speech. Change them together.

## The conversation

**The instructions are the receptionist's playbook.** `INSTRUCTIONS` covers how to talk on the phone, the safety rules (send emergencies to 911, give no medical advice), the order of the intake questions and how to book.

**Tools are plain functions with their schemas alongside.** `find_patient`, `register_patient`, `check_availability` and `book_appointment` take the call's state and the LLM's arguments and return what to tell the LLM. They don't depend on Pipecat, so the tests call them directly. `TOOLS` holds the schemas the LLM sees, written out so `visit_type` and `time_of_day` keep their fixed choices; keep the descriptions accurate.

**The patient is kept in the call's state, not passed around by the LLM.** `CallState` holds the clinic and the patient the call is about, so the LLM can't book an appointment for the wrong person. The pipeline worker carries it as `app_resources`, and tool handlers read it as `params.app_resources`.

**Errors tell the LLM how to recover.** A tool raises `ToolError` with a message such as "Check the spelling and the date with the caller, or offer to register them as a new patient", and the LLM passes that on to the caller.

**The LLM Gateway is used through the OpenAI service.** The Gateway speaks the OpenAI Chat Completions API, so the LLM is `OpenAILLMService` with the Gateway's URL and your AssemblyAI key. `LLM_MODEL` picks the model.

**The agent can hang up.** `end_call` pushes an `EndWorkerFrame` behind the goodbye, so the call ends once the goodbye has been spoken.

**Patient details stay out of the logs.** The agent logs patient IDs only.
