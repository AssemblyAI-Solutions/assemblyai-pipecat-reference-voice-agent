"""Unit tests of the made-up clinic. They need no API key or network."""

from __future__ import annotations

from datetime import date

import pytest

from clinic import BOOKING_WINDOW_DAYS, Clinic, SlotUnavailableError

TODAY = date(2026, 10, 21)  # a Wednesday


@pytest.fixture
def clinic() -> Clinic:
    return Clinic(today=TODAY)


def new_patient(clinic: Clinic):
    return clinic.register_patient(
        first_name=" Jordan ",
        last_name="Lee",
        date_of_birth=date(1990, 6, 2),
        phone_number="(415) 555-0199",
        insurance_carrier="Aetna",
        insurance_member_id="w873 4512 6",
        medications=["metformin 500 mg twice a day"],
        allergies=[],
    )


def test_finds_the_returning_patient_regardless_of_case(clinic: Clinic) -> None:
    patient = clinic.find_patient("maria", "GARCIA", date(1985, 3, 14))
    assert patient is not None
    assert patient.full_name == "Maria Garcia"


def test_needs_the_right_date_of_birth(clinic: Clinic) -> None:
    assert clinic.find_patient("Maria", "Garcia", date(1985, 3, 15)) is None


def test_registers_a_patient_with_normalized_details(clinic: Clinic) -> None:
    patient = new_patient(clinic)

    assert patient.first_name == "Jordan"
    assert patient.phone_number == "4155550199"
    assert patient.insurance_member_id == "W87345126"
    assert clinic.find_patient("Jordan", "Lee", date(1990, 6, 2)) is patient


def test_schedules_are_the_same_for_the_same_day() -> None:
    first, second = Clinic(today=TODAY), Clinic(today=TODAY)
    assert first.open_slots("follow-up", limit=20) == second.open_slots("follow-up", limit=20)


def test_slots_are_soonest_first_and_within_the_booking_window(clinic: Clinic) -> None:
    slots = clinic.open_slots("follow-up", limit=1000)

    starts = [s.start for s in slots]
    assert starts == sorted(starts)
    assert all(0 < (s.start.date() - TODAY).days <= BOOKING_WINDOW_DAYS for s in slots)
    assert all(s.start.weekday() < 5 for s in slots)


def test_cardiology_is_with_dr_okafor_on_tuesday_and_thursday_afternoons(clinic: Clinic) -> None:
    slots = clinic.open_slots("cardiology consultation", limit=1000)

    assert slots
    assert {s.provider.name for s in slots} == {"Dr. Okafor"}
    assert {s.start.strftime("%A") for s in slots} <= {"Tuesday", "Thursday"}
    assert all(s.start.hour >= 12 for s in slots)


def test_filters_by_earliest_date_and_time_of_day(clinic: Clinic) -> None:
    monday = date(2026, 10, 26)
    slots = clinic.open_slots("follow-up", earliest_date=monday, time_of_day="morning", limit=10)

    assert slots
    assert all(s.start.date() >= monday and s.start.hour < 12 for s in slots)


def test_describes_a_slot_for_speaking(clinic: Clinic) -> None:
    slot = clinic.open_slots("follow-up", time_of_day="afternoon")[0]
    description = slot.describe()

    assert description.startswith(f"{slot.start:%A, %B} {slot.start.day} at ")
    assert description.endswith(" PM with Dr. Nakamura")


def test_booking_takes_the_slot(clinic: Clinic) -> None:
    patient = new_patient(clinic)
    slot = clinic.open_slots("new patient visit")[0]

    appointment = clinic.book(patient, slot.id, "new patient visit", "annual checkup")

    assert appointment.slot == slot
    assert appointment.confirmation_number.isdigit()
    assert clinic.upcoming_appointments(patient) == [appointment]
    assert slot not in clinic.open_slots("new patient visit", limit=1000)
    with pytest.raises(SlotUnavailableError):
        clinic.book(patient, slot.id, "new patient visit", "annual checkup")


def test_refuses_a_slot_with_the_wrong_doctor(clinic: Clinic) -> None:
    patient = new_patient(clinic)
    primary_care = clinic.open_slots("follow-up")[0]

    with pytest.raises(SlotUnavailableError):
        clinic.book(patient, primary_care.id, "cardiology consultation", "palpitations")
