"""WM-Provider auf Basis von OpenLigaDB (kein API-Key).

Liefert alle Spiele des WM-Turniers (default leagueShortcut 'wm26'). Deutsche
Teamnamen; nach Abpfiff Spieltag/Runde, Endergebnis und Torschützen in der
Beschreibung. (Karten sind in OpenLigaDB nicht enthalten.)
"""
from __future__ import annotations

from ..models import Event
from .base import Provider
from .football import API, build_football_event


class WorldCupProvider(Provider):
    name = "worldcup"
    emoji = "🏟️"
    categories = ["Fußball", "WM"]

    def fetch(self) -> list[Event]:
        league = self.options.get("league", "wm26")
        season = self.options.get("season", 2026)
        matches = self.get_json(f"{API}/getmatchdata/{league}/{season}")

        events: list[Event] = []
        for m in matches:
            ev = build_football_event(m, self.emoji, self.categories, "wm", use_short_names=False)
            if ev:
                events.append(ev)
        return events
