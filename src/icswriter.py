"""Serialisiert eine Liste von Event-Objekten zu einer RFC-5545 .ics-Datei."""
from __future__ import annotations

from datetime import datetime, timezone

from icalendar import Calendar
from icalendar import Event as IcsEvent

from .cache import SequenceState
from .models import Event

PRODID = "-//tlehman1//ICAL merged sports calendar//DE"


def build_calendar(
    events: list[Event],
    calendar_name: str,
    sequence_state: SequenceState,
    display_timezone: str = "Europe/Berlin",
    now: datetime | None = None,
) -> bytes:
    now = now or datetime.now(timezone.utc)

    cal = Calendar()
    cal.add("prodid", PRODID)
    cal.add("version", "2.0")
    cal.add("method", "PUBLISH")
    cal.add("calscale", "GREGORIAN")
    cal.add("x-wr-calname", calendar_name)
    cal.add("x-wr-timezone", display_timezone)

    for ev in sorted(events, key=lambda e: (e.start, e.uid)):
        ie = IcsEvent()
        ie.add("uid", ev.uid)
        ie.add("dtstamp", now)
        ie.add("dtstart", ev.start.astimezone(timezone.utc))
        ie.add("dtend", ev.end.astimezone(timezone.utc))
        ie.add("summary", ev.summary)
        if ev.location:
            ie.add("location", ev.location)
        if ev.description:
            ie.add("description", ev.description)
        if ev.categories:
            ie.add("categories", ev.categories)
        seq, last_mod = sequence_state.resolve(ev)
        ie.add("sequence", seq)
        ie.add("last-modified", last_mod.astimezone(timezone.utc))
        cal.add_component(ie)

    return cal.to_ical()
