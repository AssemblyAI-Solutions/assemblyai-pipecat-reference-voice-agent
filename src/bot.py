"""A medical receptionist voice agent that runs every model on AssemblyAI, with one API key.

Keegan, the receptionist, answers the phone for a (made-up) clinic: takes a new patient's
intake details or looks up a returning patient, finds an open slot and books the appointment.

- Speech-to-text: Universal-3.6 Pro streaming with Medical Mode, which also decides when the
  caller's turn ends
- LLM: LLM Gateway, an OpenAI-compatible API for models from Google, OpenAI, Anthropic and more
- Text-to-speech: AssemblyAI Streaming TTS, with word-level timings (src/assemblyai_tts.py)

    uv run src/bot.py               # talk to the agent in your browser at http://localhost:7860
    uv run src/bot.py -t daily      # or in a Daily room
    uv run src/bot.py -t twilio -x <your-ngrok-host>   # or on a phone number
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, get_args

from dotenv import load_dotenv
from loguru import logger
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import EndWorkerFrame, FunctionCallResultProperties, TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.assemblyai.stt import AssemblyAISTTService
from pipecat.services.llm_service import FunctionCallParams
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.daily.transport import DailyParams
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams
from pipecat.workers.runner import WorkerRunner

from assemblyai_tts import AssemblyAITTSService
from clinic import (
    CLINIC_NAME,
    PROVIDERS,
    Clinic,
    Patient,
    SlotUnavailableError,
    TimeOfDay,
    VisitType,
)

load_dotenv(Path(__file__).parents[1] / ".env.local")

# Any model from https://llm-gateway.assemblyai.com/v1/models
LLM_MODEL = "gemma-4-31b"
LLM_GATEWAY_URL = "https://llm-gateway.assemblyai.com/v1"

# A voice id from https://www.assemblyai.com/docs/tts/voices, or one of your cloned voices
TTS_VOICE = "987db62e-a2c2-569a-9c4d-82460cdea1bd"  # Keegan

# The receptionist is named after the voice; if you change one, change the other
RECEPTIONIST_NAME = "Keegan"

# Silero (used for barge-in) should agree with AssemblyAI's own VAD on what counts as speech,
# so both use the STT's default threshold on Universal-3.6 Pro.
VAD_THRESHOLD = 0.2

GREETING = (
    f"Thanks for calling {CLINIC_NAME}, this is {RECEPTIONIST_NAME}. "
    "Are you a new patient, or have you been seen here before?"
)

INSTRUCTIONS = """\
You are {name}, the receptionist for {clinic}, a primary care and cardiology clinic. You're on a \
phone call, and everything you write is spoken aloud by a text-to-speech voice. Today is \
{today}.

How to talk:
- Keep each reply to one or two short sentences, and ask one question at a time.
- Don't use lists, markdown, emojis or abbreviations that sound odd aloud.
- Write dates and times normally, like "Tuesday, October 27 at 9:30 AM".
- When you read back a phone number, member ID or confirmation number, separate every \
character with a space and group them with commas, like "5 1 2, 5 5 5, 0 1 3 4".

Safety comes first. If the caller describes possible emergency symptoms, such as chest pain \
or pressure, trouble breathing, signs of a stroke, severe bleeding or thoughts of harming \
themselves, tell them to hang up and call 911 right away, and don't book anything. Never give \
medical advice, such as about symptoms, diagnoses or medications; offer an appointment instead.

Returning patients: ask for their first and last name and date of birth, then call \
find_patient.

New patients: collect these one at a time, briefly confirming each:
1. First and last name. Ask them to spell the last name.
2. Date of birth.
3. Best callback phone number. Read it back.
4. Insurance carrier and member ID. Read the member ID back.
5. Current medications, with doses.
6. Medication allergies.
Then call register_patient with everything, exactly as the caller confirmed it.

Booking: ask what the visit is for. Primary care visits are with {primary_care}, and new \
patients start with a new patient visit. Heart concerns are a cardiology consultation with \
{cardiology}. Call check_availability, offer the caller at most two of the times it returns, \
and when they choose one, call book_appointment. Then tell them the date, time and \
confirmation number, and ask if there's anything else.

Only use what the tools tell you; never make up patients, times or confirmation numbers. When \
the caller has nothing else, say a short goodbye and call end_call."""


def instructions(today: date | None = None) -> str:
    today = today or date.today()
    return INSTRUCTIONS.format(
        name=RECEPTIONIST_NAME,
        clinic=CLINIC_NAME,
        today=f"{today:%A, %B} {today.day}, {today.year}",
        primary_care=_providers_for("follow-up"),
        cardiology=_providers_for("cardiology consultation"),
    )


@dataclass
class CallState:
    clinic: Clinic = field(default_factory=Clinic)
    # The patient this call is about, once they've been found or registered
    patient: Patient | None = None


class ToolError(Exception):
    """A tool failed in a way the LLM can recover from; the message tells it how."""


# The tools. Each takes the call's state and the LLM's arguments, and returns what to tell the
# LLM. They don't depend on Pipecat, so tests can call them directly.


def find_patient(state: CallState, first_name: str, last_name: str, date_of_birth: str) -> str:
    patient = state.clinic.find_patient(first_name, last_name, _parse_date(date_of_birth))
    if patient is None:
        raise ToolError(
            "No patient has that name and date of birth. Check the spelling and the date "
            "with the caller, or offer to register them as a new patient."
        )
    state.patient = patient

    appointments = state.clinic.upcoming_appointments(patient)
    if not appointments:
        return f"Found {patient.full_name}. They have no upcoming appointments."
    booked = "; ".join(f"a {a.visit_type} on {a.slot.describe()}" for a in appointments)
    return f"Found {patient.full_name}. Their upcoming appointments: {booked}."


def register_patient(
    state: CallState,
    first_name: str,
    last_name: str,
    date_of_birth: str,
    phone_number: str,
    insurance_carrier: str,
    insurance_member_id: str,
    medications: list[str],
    allergies: list[str],
) -> str:
    patient = state.clinic.register_patient(
        first_name=first_name,
        last_name=last_name,
        date_of_birth=_parse_date(date_of_birth),
        phone_number=phone_number,
        insurance_carrier=insurance_carrier,
        insurance_member_id=insurance_member_id,
        medications=medications,
        allergies=allergies,
    )
    state.patient = patient
    logger.info(f"registered patient {patient.id}")
    return f"Registered {patient.full_name} as a new patient."


def check_availability(
    state: CallState,
    visit_type: VisitType,
    earliest_date: str | None = None,
    time_of_day: TimeOfDay | None = None,
) -> str:
    slots = state.clinic.open_slots(
        visit_type,
        earliest_date=_parse_date(earliest_date) if earliest_date else None,
        time_of_day=time_of_day,
    )
    if not slots:
        return "No openings match. Ask the caller about other days or times."
    return "Open times, by slot ID: " + "; ".join(f"{s.id}: {s.describe()}" for s in slots)


def book_appointment(state: CallState, slot_id: str, visit_type: VisitType, reason: str) -> str:
    patient = state.patient
    if patient is None:
        raise ToolError("Find or register the patient before booking.")
    try:
        appointment = state.clinic.book(patient, slot_id, visit_type, reason)
    except SlotUnavailableError:
        raise ToolError(
            "That slot isn't available. Call check_availability for current times."
        ) from None
    logger.info(f"booked {appointment.slot.id} for patient {patient.id}")
    return (
        f"Booked a {visit_type} on {appointment.slot.describe()}. "
        f"Confirmation number {appointment.confirmation_number}."
    )


CLINIC_TOOLS = {
    f.__name__: f for f in (find_patient, register_patient, check_availability, book_appointment)
}


def call_tool(state: CallState, name: str, arguments: dict[str, Any]) -> str:
    """Run one of the clinic tools, turning a ToolError into a message for the LLM."""
    try:
        return CLINIC_TOOLS[name](state, **arguments)
    except ToolError as e:
        return f"Error: {e}"


async def _run_clinic_tool(params: FunctionCallParams) -> None:
    state: CallState = params.app_resources
    await params.result_callback(call_tool(state, params.function_name, dict(params.arguments)))


async def _end_call(params: FunctionCallParams) -> None:
    # The goodbye is already queued ahead of this, so the call ends once it's been spoken
    await params.result_callback(None, properties=FunctionCallResultProperties(run_llm=False))
    await params.llm.push_frame(EndWorkerFrame(reason="the receptionist ended the call"))


def _function(name: str, description: str, required: list[str], **properties: Any):
    return FunctionSchema(name, description, properties, required, handler=_run_clinic_tool)


_DATE = {"type": "string", "description": "As YYYY-MM-DD"}
_VISIT_TYPE = {"type": "string", "enum": list(get_args(VisitType)), "description": "The visit"}

# What the LLM sees of the tools. Keep the descriptions accurate: they're the tools' docs.
TOOLS = ToolsSchema(
    standard_tools=[
        _function(
            "find_patient",
            "Look up a returning patient's record.",
            ["first_name", "last_name", "date_of_birth"],
            first_name={"type": "string", "description": "The patient's first name"},
            last_name={"type": "string", "description": "The last name, as they spelled it"},
            date_of_birth=_DATE,
        ),
        _function(
            "register_patient",
            "Register a new patient with the intake details they've confirmed.",
            [
                "first_name",
                "last_name",
                "date_of_birth",
                "phone_number",
                "insurance_carrier",
                "insurance_member_id",
                "medications",
                "allergies",
            ],
            first_name={"type": "string", "description": "The patient's first name"},
            last_name={"type": "string", "description": "The last name, as they spelled it"},
            date_of_birth=_DATE,
            phone_number={"type": "string", "description": "The best callback number, digits"},
            insurance_carrier={"type": "string", "description": "Their insurance company"},
            insurance_member_id={"type": "string", "description": "Their insurance member ID"},
            medications={
                "type": "array",
                "items": {"type": "string"},
                "description": "Each current medication with its dose, or empty if none",
            },
            allergies={
                "type": "array",
                "items": {"type": "string"},
                "description": "Each medication allergy, or empty if none",
            },
        ),
        _function(
            "check_availability",
            "Find the soonest open appointment times for a visit.",
            ["visit_type"],
            visit_type=_VISIT_TYPE,
            earliest_date={
                "type": "string",
                "description": "The first day the caller could come in, as YYYY-MM-DD; "
                "for a specific day, that day",
            },
            time_of_day={
                "type": "string",
                "enum": list(get_args(TimeOfDay)),
                "description": "Whether the caller prefers mornings or afternoons, if they said",
            },
        ),
        _function(
            "book_appointment",
            "Book the patient into an open slot from check_availability.",
            ["slot_id", "visit_type", "reason"],
            slot_id={"type": "string", "description": 'The slot\'s ID, such as "S12"'},
            visit_type=_VISIT_TYPE,
            reason={"type": "string", "description": "Why the patient is coming in"},
        ),
        FunctionSchema(
            "end_call",
            "Hang up, after you've said goodbye.",
            properties={},
            required=[],
            handler=_end_call,
        ),
    ]
)


def _providers_for(visit_type: VisitType) -> str:
    return " and ".join(p.name for p in PROVIDERS if visit_type in p.visit_types)


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ToolError(f"{value!r} isn't a date; use YYYY-MM-DD.") from None


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments) -> None:
    api_key = os.getenv("ASSEMBLYAI_API_KEY")
    if not api_key:
        raise ValueError("Set ASSEMBLYAI_API_KEY in .env.local or the environment")

    stt = AssemblyAISTTService(
        api_key=api_key,
        # Universal-3.6 Pro decides when the caller has finished speaking
        vad_force_turn_endpoint=False,
        settings=AssemblyAISTTService.Settings(
            model="universal-3-6-pro",
            # Medical Mode (a paid add-on) for drug names, conditions and dosages
            domain="medical-v1",
            # What the calls are about, and the names they'll mention
            prompt=(
                "Phone call to a primary care and cardiology clinic. A patient gives their "
                "name, date of birth, phone number, insurance details, medications with doses "
                "and allergies, and books an appointment."
            ),
            keyterms_prompt=[CLINIC_NAME, RECEPTIONIST_NAME, *(p.name for p in PROVIDERS)],
            # "balanced" waits up to 1.28 s of silence before ending a turn, so a caller can
            # pause while reading out a phone number or member ID; "min_latency" waits 0.64 s.
            mode="balanced",
            vad_threshold=VAD_THRESHOLD,
        ),
    )
    llm = OpenAILLMService(
        api_key=api_key,
        base_url=LLM_GATEWAY_URL,
        settings=OpenAILLMService.Settings(model=LLM_MODEL, system_instruction=instructions()),
    )
    tts = AssemblyAITTSService(api_key=api_key, voice=TTS_VOICE)

    context = LLMContext(tools=TOOLS)
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(params=VADParams(confidence=VAD_THRESHOLD))
        ),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )
    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
        # The tools find this call's clinic and patient in params.app_resources
        app_resources=CallState(),
    )
    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)
    await runner.add_workers(worker)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        # A fixed greeting is spoken right away, without waiting on the LLM
        await worker.queue_frames([TTSSpeakFrame(GREETING)])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        await runner.cancel()

    await runner.run()


async def bot(runner_args: RunnerArguments) -> None:
    """The entry point for Pipecat's runner and Pipecat Cloud."""
    transport = await create_transport(
        runner_args,
        {
            "daily": lambda: DailyParams(audio_in_enabled=True, audio_out_enabled=True),
            "twilio": lambda: FastAPIWebsocketParams(audio_in_enabled=True, audio_out_enabled=True),
            "webrtc": lambda: TransportParams(audio_in_enabled=True, audio_out_enabled=True),
        },
    )
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
