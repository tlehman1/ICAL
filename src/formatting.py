"""Zentrale, testbare Formatierung von Titeln, Emojis und Ergebnissen."""
from __future__ import annotations


def format_match_summary(
    emoji: str,
    home: str,
    away: str,
    finished: bool,
    score_home=None,
    score_away=None,
) -> str:
    """Fußball-Titel.

    Vorher : 'emoji Home - Away'
    Nachher: 'emoji Home x:y Away'  (Fußball-Score mit ':')
    """
    prefix = f"{emoji} " if emoji else ""
    if finished and score_home is not None and score_away is not None:
        return f"{prefix}{home} {score_home}:{score_away} {away}"
    return f"{prefix}{home} - {away}"


def format_session_summary(emoji: str, event_name: str, session_label: str) -> str:
    """Motorsport-Titel: 'emoji Event - Session'."""
    prefix = f"{emoji} " if emoji else ""
    return f"{prefix}{event_name} - {session_label}"


def format_podium(entries) -> str:
    """entries: Liste von (pos, name, extra) -> 'P1 Verstappen (Red Bull), P2 ...'."""
    parts = []
    for pos, name, extra in entries:
        if extra:
            parts.append(f"P{pos} {name} ({extra})")
        else:
            parts.append(f"P{pos} {name}")
    return ", ".join(parts)
