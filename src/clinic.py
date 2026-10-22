"""A made-up clinic for the receptionist to work with: its doctors, open slots and patients.

Everything lives in memory and starts over with each call. To connect a real practice
management or EHR system, reimplement `Clinic`'s methods against its API; the agent only
calls `find_patient`, `register_patient`, `upcoming_appointments`, `open_slots` and `book`.
"""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Literal

CLINIC_NAME = "Riverside Family Medicine"

VisitType = Literal["new patient visit", "follow-up", "cardiology consultation"]
TimeOfDay = Literal["morning", "afternoon"]

# How many days ahead the schedule is open for booking
BOOKING_WINDOW_DAYS = 14


@dataclass(frozen=True)
class Provider:
    name: str
    visit_types: tuple[VisitType, ...]
    weekdays: tuple[int, ...]  # Monday is 0
    start_times: tuple[time, ...]


def _every_half_hour(start: time, end: time) -> tuple[time, ...]:
    day = date.min
    t, stop = datetime.combine(day, start), datetime.combine(day, end)
    times = []
    while t < stop:
        times.append(t.time())
        t += timedelta(minutes=30)
    return tuple(times)


PROVIDERS = (
    Provider(
        name="Dr. Nakamura",
        visit_types=("new patient visit", "follow-up"),
        weekdays=(0, 1, 2, 3, 4),
        start_times=_every_half_hour(time(9), time(12))
        + _every_half_hour(time(13, 30), time(16, 30)),
    ),
    Provider(
        name="Dr. Okafor",
        visit_types=("cardiology consultation",),
        weekdays=(1, 3),
        start_times=_every_half_hour(time(13), time(17)),
    ),
)


@dataclass
class Patient:
    id: str
    first_name: str
    last_name: str
    date_of_birth: date
    phone_number: str
    insurance_carrier: str
    insurance_member_id: str
    medications: list[str] = field(default_factory=list)
    allergies: list[str] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


@dataclass(frozen=True)
class Slot:
    id: str
    provider: Provider
    start: datetime

    def describe(self) -> str:
        """Say when the slot is, e.g. "Tuesday, October 27 at 9:30 AM with Dr. Nakamura"."""
        hour = self.start.hour % 12 or 12
        meridiem = "AM" if self.start.hour < 12 else "PM"
        return (
            f"{self.start:%A, %B} {self.start.day} at {hour}:{self.start:%M} {meridiem} "
            f"with {self.provider.name}"
        )


@dataclass(frozen=True)
class Appointment:
    confirmation_number: str
    patient: Patient
    slot: Slot
    visit_type: VisitType
    reason: str


class SlotUnavailableError(LookupError):
    pass


class Clinic:
    def __init__(self, today: date | None = None, *, seed: int | None = None) -> None:
        self.today = today or date.today()
        # The same day always gets the same schedule, unless a seed says otherwise
        self._rng = random.Random(self.today.toordinal() if seed is None else seed)
        self._patient_ids = (f"P{n}" for n in itertools.count(1001))
        self._patients: list[Patient] = []
        self._appointments: list[Appointment] = []
        self._slots = self._open_schedule()

        # A returning patient to try: "Maria Garcia, born March 14, 1985"
        self.register_patient(
            first_name="Maria",
            last_name="Garcia",
            date_of_birth=date(1985, 3, 14),
            phone_number="5125550134",
            insurance_carrier="Blue Cross Blue Shield",
            insurance_member_id="BCX449201",
            medications=["lisinopril 10 mg once a day"],
            allergies=["penicillin"],
        )

    def find_patient(self, first_name: str, last_name: str, date_of_birth: date) -> Patient | None:
        for patient in self._patients:
            if (
                patient.first_name.casefold() == first_name.strip().casefold()
                and patient.last_name.casefold() == last_name.strip().casefold()
                and patient.date_of_birth == date_of_birth
            ):
                return patient
        return None

    def register_patient(
        self,
        *,
        first_name: str,
        last_name: str,
        date_of_birth: date,
        phone_number: str,
        insurance_carrier: str,
        insurance_member_id: str,
        medications: list[str],
        allergies: list[str],
    ) -> Patient:
        patient = Patient(
            id=next(self._patient_ids),
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            date_of_birth=date_of_birth,
            phone_number="".join(c for c in phone_number if c.isdigit()),
            insurance_carrier=insurance_carrier.strip(),
            insurance_member_id=insurance_member_id.replace(" ", "").upper(),
            medications=medications,
            allergies=allergies,
        )
        self._patients.append(patient)
        return patient

    def upcoming_appointments(self, patient: Patient) -> list[Appointment]:
        return [a for a in self._appointments if a.patient is patient]

    def open_slots(
        self,
        visit_type: VisitType,
        *,
        earliest_date: date | None = None,
        time_of_day: TimeOfDay | None = None,
        limit: int = 3,
    ) -> list[Slot]:
        """The first open slots for a visit type, soonest first."""
        matches = []
        for slot in self._slots.values():
            if visit_type not in slot.provider.visit_types:
                continue
            if earliest_date and slot.start.date() < earliest_date:
                continue
            if time_of_day and (slot.start.hour < 12) != (time_of_day == "morning"):
                continue
            matches.append(slot)
        return matches[:limit]

    def book(
        self, patient: Patient, slot_id: str, visit_type: VisitType, reason: str
    ) -> Appointment:
        slot = self._slots.get(slot_id)
        if slot is None:
            raise SlotUnavailableError(slot_id)
        if visit_type not in slot.provider.visit_types:
            raise SlotUnavailableError(
                f"{slot_id} is with {slot.provider.name}, not for a {visit_type}"
            )
        del self._slots[slot_id]
        appointment = Appointment(
            confirmation_number=str(self._rng.randint(10000, 99999)),
            patient=patient,
            slot=slot,
            visit_type=visit_type,
            reason=reason,
        )
        self._appointments.append(appointment)
        return appointment

    def _open_schedule(self) -> dict[str, Slot]:
        """Every bookable slot in the window, soonest first, with about half already taken."""
        slot_ids = (f"S{n}" for n in itertools.count(1))
        slots = {}
        for offset in range(1, BOOKING_WINDOW_DAYS + 1):
            day = self.today + timedelta(days=offset)
            for start_time in sorted({t for p in PROVIDERS for t in p.start_times}):
                for provider in PROVIDERS:
                    if (
                        day.weekday() not in provider.weekdays
                        or start_time not in provider.start_times
                    ):
                        continue
                    if self._rng.random() < 0.5:
                        continue  # already booked by someone else
                    slot = Slot(next(slot_ids), provider, datetime.combine(day, start_time))
                    slots[slot.id] = slot
        return slots
