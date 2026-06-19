"""Gemeinsame Bausteine für OpenLigaDB-Fußball (Bundesliga & WM).

OpenLigaDB liefert pro Spiel Anstoß, Teams, Endergebnis und die Torliste
(``goals``) mit Schütze, Minute, Elfmeter/Eigentor-Flags. **Karten (gelb/rot)
sind in OpenLigaDB NICHT enthalten** und können daher nicht angezeigt werden.
"""
from __future__ import annotations

from datetime import timedelta

from dateutil import parser as dtparser

from ..formatting import format_match_summary
from ..models import Event

API = "https://api.openligadb.de"
MATCH_DURATION = timedelta(hours=2)


def final_result(match: dict):
    """Endergebnis (resultTypeID == 2 / 'Endergebnis') als (home, away) oder None."""
    for r in match.get("matchResults") or []:
        if r.get("resultTypeID") == 2 or r.get("resultName") == "Endergebnis":
            ph, pa = r.get("pointsTeam1"), r.get("pointsTeam2")
            if ph is not None and pa is not None:
                return ph, pa
    return None


def format_goals(goals: list[dict]) -> str:
    """Torliste -> 'Tore:\\n1:0 Schütze (9.)\\n2:0 Schütze (67., Elfmeter)' oder ''."""
    lines = []
    for g in goals or []:
        s1, s2 = g.get("scoreTeam1"), g.get("scoreTeam2")
        stand = f"{s1}:{s2}" if s1 is not None and s2 is not None else ""
        name = (g.get("goalGetterName") or "").strip()

        inner = []
        if g.get("matchMinute"):
            inner.append(f"{g['matchMinute']}.")
        if g.get("isPenalty"):
            inner.append("Elfmeter")
        if g.get("isOwnGoal"):
            inner.append("Eigentor")
        suffix = f" ({', '.join(inner)})" if inner else ""

        head = f"{stand} {name}".strip() if name else stand
        line = f"{head}{suffix}".strip()
        if line:
            lines.append(line)
    return "Tore:\n" + "\n".join(lines) if lines else ""


def build_football_event(
    match: dict,
    emoji: str,
    categories: list[str],
    uid_prefix: str,
    use_short_names: bool = True,
) -> Event | None:
    """Baut ein VEVENT aus einem OpenLigaDB-Match.

    Titel vor Abpfiff: 'emoji Heim - Gast'; danach mit Score. Nach Abpfiff
    werden Spieltag/Gruppe, Endergebnis und die Torliste in die Beschreibung
    geschrieben.
    """
    utc = match.get("matchDateTimeUTC")
    if not utc:
        return None
    start = dtparser.isoparse(utc)
    end = start + MATCH_DURATION

    t1 = match.get("team1") or {}
    t2 = match.get("team2") or {}
    if use_short_names:
        home = t1.get("shortName") or t1.get("teamName") or "?"
        away = t2.get("shortName") or t2.get("teamName") or "?"
    else:
        home = t1.get("teamName") or t1.get("shortName") or "?"
        away = t2.get("teamName") or t2.get("shortName") or "?"

    result = final_result(match) if match.get("matchIsFinished") else None
    finished = result is not None
    sh, sa = result if result else (None, None)
    summary = format_match_summary(emoji, home, away, finished, sh, sa)

    head = []
    matchday = (match.get("group") or {}).get("groupName")
    if matchday:
        head.append(matchday)
    if finished:
        head.append(f"Endergebnis: {sh} : {sa}")
    description = "\n".join(head)
    if finished:
        goals = format_goals(match.get("goals"))
        if goals:
            description = f"{description}\n\n{goals}" if description else goals

    loc = match.get("location") or {}
    location = None
    if loc.get("locationStadium"):
        location = loc["locationStadium"]
        if loc.get("locationCity"):
            location += f", {loc['locationCity']}"

    return Event(
        uid=f"{uid_prefix}-{match['matchID']}@ical",
        start=start,
        end=end,
        summary=summary,
        location=location,
        description=description or None,
        categories=list(categories),
    )
