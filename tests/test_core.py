"""Tests für die kernlogischen Module: formatting, models, icswriter."""
from datetime import datetime, timedelta, timezone

from icalendar import Calendar

from src.cache import SequenceState
from src.formatting import format_match_summary, format_podium, format_session_summary
from src.icswriter import build_calendar
from src.models import Event


def test_match_summary_before_and_after():
    assert format_match_summary("⚽", "Leverkusen", "Bayern", False) == "⚽ Leverkusen - Bayern"
    assert format_match_summary("⚽", "Leverkusen", "Bayern", True, 2, 1) == "⚽ Leverkusen 2:1 Bayern"
    # finished aber ohne Score -> wie "vorher"
    assert format_match_summary("⚽", "A", "B", True, None, None) == "⚽ A - B"


def test_session_summary_and_podium():
    assert format_session_summary("🏎️", "Spanish GP", "Qualifying") == "🏎️ Spanish GP - Qualifying"
    assert format_podium([("1", "Verstappen", "Red Bull"), ("2", "Norris", None)]) == (
        "P1 Verstappen (Red Bull), P2 Norris"
    )


def _event(uid="e1", summary="A - B"):
    start = datetime(2026, 6, 13, 18, 0, tzinfo=timezone.utc)
    return Event(uid=uid, start=start, end=start + timedelta(hours=2), summary=summary,
                 categories=["Test"])


def test_content_hash_changes_with_summary():
    a = _event(summary="A - B")
    b = _event(summary="A 1:0 B")
    assert a.content_hash() != b.content_hash()


def test_event_roundtrip():
    ev = _event()
    assert Event.from_dict(ev.to_dict()).content_hash() == ev.content_hash()


def test_icswriter_emits_parsable_calendar(tmp_path):
    seq = SequenceState(tmp_path)
    ics = build_calendar([_event(summary="⚽ A 2:1 B")], "Mein Kalender", seq)
    cal = Calendar.from_ical(ics)
    vevents = [c for c in cal.walk("VEVENT")]
    assert len(vevents) == 1
    ev = vevents[0]
    assert str(ev["summary"]) == "⚽ A 2:1 B"
    assert str(ev["uid"]) == "e1"
    assert int(ev["sequence"]) == 0
    # DTSTART als UTC
    assert ev["dtstart"].to_ical().decode().endswith("Z")


def test_sequence_bumps_only_on_change(tmp_path):
    now1 = datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc)
    now2 = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)

    # 1. Lauf: neues Event -> SEQUENCE 0
    seq = SequenceState(tmp_path, now=now1)
    build_calendar([_event(summary="⚽ A - B")], "K", seq)
    seq.save()

    # 2. Lauf, gleicher Inhalt -> SEQUENCE bleibt 0
    seq = SequenceState(tmp_path, now=now2)
    build_calendar([_event(summary="⚽ A - B")], "K", seq)
    s, _ = seq.resolve(_event(summary="⚽ A - B"))
    assert s == 0

    # 3. Lauf, geänderter Inhalt -> SEQUENCE 1
    seq = SequenceState(tmp_path, now=now2)
    build_calendar([_event(summary="⚽ A 1:0 B")], "K", seq)
    s, _ = seq.resolve(_event(summary="⚽ A 1:0 B"))
    assert s == 1
