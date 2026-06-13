"""Bundesliga-Provider auf Basis von OpenLigaDB (kein API-Key).

Holt die komplette Saison einer Liga und filtert auf die in der Config
angegebenen Teams (Name -> teamId-Resolver). Vor dem Spiel zeigt der Titel
die Teams, nach Abpfiff den Score.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from dateutil import parser as dtparser

from ..config import resolve_football_season
from ..formatting import format_match_summary
from ..models import Event
from .base import Provider

API = "https://api.openligadb.de"
MATCH_DURATION = timedelta(hours=2)

log = logging.getLogger("ical.bundesliga")


def final_result(match: dict):
    """Endergebnis (resultTypeID == 2 / 'Endergebnis') als (home, away) oder None."""
    for r in match.get("matchResults") or []:
        if r.get("resultTypeID") == 2 or r.get("resultName") == "Endergebnis":
            ph, pa = r.get("pointsTeam1"), r.get("pointsTeam2")
            if ph is not None and pa is not None:
                return ph, pa
    return None


class BundesligaProvider(Provider):
    name = "bundesliga"
    emoji = "⚽"
    categories = ["Fußball", "Bundesliga"]

    def fetch(self) -> list[Event]:
        season = resolve_football_season(self.options.get("season"))
        league = self.options.get("league", "bl1")
        wanted = [n.lower() for n in (self.options.get("teams") or [])]

        team_ids = self._resolve_team_ids(league, season, wanted)
        matches = self.get_json(f"{API}/getmatchdata/{league}/{season}")

        events: list[Event] = []
        for m in matches:
            t1 = m.get("team1") or {}
            t2 = m.get("team2") or {}
            if not self._is_wanted(t1, t2, team_ids, wanted):
                continue

            utc = m.get("matchDateTimeUTC")
            if not utc:
                continue
            start = dtparser.isoparse(utc)
            end = start + MATCH_DURATION

            home = t1.get("shortName") or t1.get("teamName") or "?"
            away = t2.get("shortName") or t2.get("teamName") or "?"

            result = final_result(m) if m.get("matchIsFinished") else None
            finished = result is not None
            sh, sa = result if result else (None, None)
            summary = format_match_summary(self.emoji, home, away, finished, sh, sa)

            desc = []
            matchday = (m.get("group") or {}).get("groupName")
            if matchday:
                desc.append(matchday)
            if finished:
                desc.append(f"Endergebnis: {sh} : {sa}")

            loc = m.get("location") or {}
            location = None
            if loc.get("locationStadium"):
                location = loc["locationStadium"]
                if loc.get("locationCity"):
                    location += f", {loc['locationCity']}"

            events.append(
                Event(
                    uid=f"bl-{m['matchID']}@ical",
                    start=start,
                    end=end,
                    summary=summary,
                    location=location,
                    description="\n".join(desc) or None,
                    categories=list(self.categories),
                )
            )
        return events

    def _resolve_team_ids(self, league: str, season: int, wanted: list[str]) -> set:
        if not wanted:
            return set()
        ids = set()
        try:
            teams = self.get_json(f"{API}/getavailableteams/{league}/{season}")
        except Exception as e:  # noqa: BLE001
            log.warning("Team-Resolver fehlgeschlagen (%s) – fallback auf Namens-Match.", e)
            return ids
        for t in teams:
            hay = f"{t.get('teamName', '')} {t.get('shortName', '')}".lower()
            if any(n in hay for n in wanted):
                ids.add(t.get("teamId"))
        log.info("Bundesliga-Teams aufgelöst: %s -> ids %s", wanted, sorted(ids))
        return ids

    @staticmethod
    def _is_wanted(t1: dict, t2: dict, team_ids: set, wanted: list[str]) -> bool:
        if not wanted:
            return True  # kein Filter -> ganze Liga
        if t1.get("teamId") in team_ids or t2.get("teamId") in team_ids:
            return True
        hay = (
            f"{t1.get('teamName', '')} {t1.get('shortName', '')} "
            f"{t2.get('teamName', '')} {t2.get('shortName', '')}"
        ).lower()
        return any(n in hay for n in wanted)
