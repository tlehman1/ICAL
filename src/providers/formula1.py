"""Formel-1-Provider auf Basis der Jolpica-F1-API (Ergast-Nachfolger, kein Key).

Ein Call liefert den kompletten Saisonkalender mit allen Sessions. Pro
gewünschter Session wird ein VEVENT erzeugt; nach Abschluss werden die Top-3
(bzw. Pole) in die DESCRIPTION geschrieben. Ergebnisse werden gecacht, damit
abgeschlossene Sessions nicht bei jedem Lauf erneut abgefragt werden.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from dateutil import parser as dtparser

from ..config import resolve_calendar_season
from ..formatting import format_podium, format_session_summary
from ..models import Event
from .base import Provider

API = "https://api.jolpi.ca/ergast/f1"

# config-key -> (Jolpica-Session-Keys, deutsches Label, Dauer (min), Ergebnis-Endpoint)
# Der Sentinel "__race__" steht für das Rennen (Datum/Zeit am Race-Objekt selbst).
SESSIONS = {
    "fp1": (["FirstPractice"], "1. Freies Training", 60, None),
    "fp2": (["SecondPractice"], "2. Freies Training", 60, None),
    "fp3": (["ThirdPractice"], "3. Freies Training", 60, None),
    "sprint_qualifying": (["SprintQualifying", "SprintShootout"], "Sprint-Qualifying", 45, None),
    "sprint": (["Sprint"], "Sprint", 60, "sprint"),
    "qualifying": (["Qualifying"], "Qualifying", 60, "qualifying"),
    "race": (["__race__"], "Rennen", 120, "results"),
}

log = logging.getLogger("ical.formula1")


def _podium_from_rows(rows: list[dict]) -> list[tuple]:
    return [
        (r.get("position"), (r.get("Driver") or {}).get("familyName") or "?",
         (r.get("Constructor") or {}).get("name"))
        for r in rows[:3]
    ]


class Formula1Provider(Provider):
    name = "formula1"
    emoji = "🏎️"
    categories = ["Motorsport", "Formel 1"]

    def fetch(self) -> list[Event]:
        season = resolve_calendar_season(self.options.get("season"))
        wanted = self.options.get("sessions") or [
            "race", "qualifying", "sprint", "sprint_qualifying"
        ]
        data = self.get_json(f"{API}/{season}.json")
        races = data["MRData"]["RaceTable"]["Races"]
        now = datetime.now(timezone.utc)

        cache = self.cache.load_json("f1_results") if self.cache else {}
        dirty = False

        events: list[Event] = []
        for r in races:
            rnd = r.get("round")
            gp = r.get("raceName", "").replace("Grand Prix", "GP").strip()
            circuit = r.get("Circuit") or {}
            cl = circuit.get("Location") or {}
            location = ", ".join(
                p for p in [circuit.get("circuitName"), cl.get("locality"), cl.get("country")] if p
            ) or None

            for key in wanted:
                spec = SESSIONS.get(key)
                if not spec:
                    continue
                jolpica_keys, label, dur, res_kind = spec
                start = self._session_start(r, jolpica_keys)
                if start is None:
                    continue
                end = start + timedelta(minutes=dur)

                description = None
                if res_kind and end < now:
                    ck = f"{season}-{rnd}-{key}"
                    text = cache.get(ck)
                    if text is None:
                        text = self._fetch_result(season, rnd, res_kind)
                        if text:
                            cache[ck] = text
                            dirty = True
                    description = text or None

                events.append(
                    Event(
                        uid=f"f1-{season}-{rnd}-{key}@ical",
                        start=start,
                        end=end,
                        summary=format_session_summary(self.emoji, gp, label),
                        location=location,
                        description=description,
                        categories=list(self.categories),
                    )
                )

        if dirty and self.cache:
            self.cache.save_json("f1_results", cache)
        return events

    @staticmethod
    def _session_start(race: dict, keys: list[str]):
        for k in keys:
            if k == "__race__":
                d, t = race.get("date"), race.get("time")
            else:
                obj = race.get(k)
                if not obj:
                    continue
                d, t = obj.get("date"), obj.get("time")
            if d and t:
                return dtparser.isoparse(f"{d}T{t}")
        return None

    def _fetch_result(self, season: int, rnd: str, kind: str):
        endpoints = {
            "results": ("results.json", "Results", "🏁 "),
            "qualifying": ("qualifying.json", "QualifyingResults", "🏁 Pole: "),
            "sprint": ("sprint.json", "SprintResults", "🏁 Sprint: "),
        }
        path, field, prefix = endpoints[kind]
        try:
            data = self.get_json(f"{API}/{season}/{rnd}/{path}")
            races = data["MRData"]["RaceTable"]["Races"]
            if not races:
                return None
            rows = races[0].get(field) or []
            entries = _podium_from_rows(rows)
            if not entries or entries[0][0] is None:
                return None
            return prefix + format_podium(entries)
        except Exception as e:  # noqa: BLE001
            log.warning("F1-Ergebnis %s R%s/%s fehlgeschlagen: %s", season, rnd, kind, e)
            return None
