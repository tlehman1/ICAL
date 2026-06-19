"""Bundesliga-Provider auf Basis von OpenLigaDB (kein API-Key).

Holt die komplette Saison einer Liga und filtert auf die in der Config
angegebenen Teams (Name -> teamId-Resolver). Vor dem Spiel zeigt der Titel die
Teams, nach Abpfiff den Score; die Beschreibung führt Spieltag, Endergebnis und
Torschützen.
"""
from __future__ import annotations

import logging

from ..config import resolve_football_season
from ..models import Event
from .base import Provider
from .football import API, build_football_event, final_result  # noqa: F401 (final_result re-export)

log = logging.getLogger("ical.bundesliga")


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
            if not self._is_wanted(m.get("team1") or {}, m.get("team2") or {}, team_ids, wanted):
                continue
            ev = build_football_event(m, self.emoji, self.categories, "bl", use_short_names=True)
            if ev:
                events.append(ev)
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
