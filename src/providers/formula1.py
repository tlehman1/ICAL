"""Formel-1-Provider auf Basis der Jolpica-F1-API (Ergast-Nachfolger, kein Key).

Ein Call liefert den kompletten Saisonkalender mit allen Sessions. Pro
gewünschter Session wird ein VEVENT erzeugt.

Nach Abschluss:
- Rennen & Sprints bekommen die KOMPLETTE Klassifizierung (Platz, Fahrer, Team,
  Zeit/Abstand, Punkte, DNF-Gründe).
- An jedes Rennen wird die Fahrer-WM-Wertung NACH DIESER RUNDE gehängt (Jolpica
  liefert Standings historisch pro Runde – jedes Rennen zeigt also die korrekte
  Tabelle zum jeweiligen Zeitpunkt).
- Qualifying bleibt kompakt (Pole/Top-3).

Ergebnisse werden gecacht, damit abgeschlossene Runden nicht bei jedem Lauf
erneut abgefragt werden.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from dateutil import parser as dtparser

from ..config import resolve_calendar_season
from ..formatting import format_podium, format_session_summary, format_standings_table
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

# Sessions mit voller Klassifizierung (statt nur Top-3).
FULL_RESULT_KINDS = {"results", "sprint"}

# Ergebnis-Endpoint -> (Pfad, JSON-Feld)
RESULT_ENDPOINT = {
    "results": ("results.json", "Results"),
    "sprint": ("sprint.json", "SprintResults"),
    "qualifying": ("qualifying.json", "QualifyingResults"),
}

# Häufige DNF-/Ausfall-Status -> deutsch (Fallback: Originaltext).
STATUS_DE = {
    "Accident": "Unfall", "Collision": "Kollision", "Collision damage": "Kollisionsschaden",
    "Engine": "Motor", "Gearbox": "Getriebe", "Transmission": "Getriebe",
    "Hydraulics": "Hydraulik", "Brakes": "Bremsen", "Suspension": "Aufhängung",
    "Electrical": "Elektrik", "Power Unit": "Antriebseinheit", "Retired": "Aufgabe",
    "Withdrew": "Zurückgezogen", "Disqualified": "Disqualifiziert", "Puncture": "Reifenschaden",
    "Overheating": "Überhitzung", "Spun off": "Abflug", "Out of fuel": "Kein Sprit",
    "Wheel": "Rad", "Tyre": "Reifen", "Fuel system": "Kraftstoffsystem", "Throttle": "Gas",
    "Clutch": "Kupplung", "Water leak": "Wasserleck", "Oil leak": "Ölleck",
    "Driveshaft": "Antriebswelle", "Vibrations": "Vibrationen", "Battery": "Batterie",
}

log = logging.getLogger("ical.formula1")


# --------------------------------------------------------------------------- #
# Formatierung (rein, testbar)
# --------------------------------------------------------------------------- #
def _timing(row: dict, winner_laps: int):
    """-> (Text, classified?). Sieger: Gesamtzeit; Verfolger: +Abstand;
    Überrundete: +N Runden; Ausfälle: deutscher Status (classified=False)."""
    status = row.get("status") or ""
    pos = str(row.get("position") or "")
    time = (row.get("Time") or {}).get("time")

    if pos == "1":
        return (time or ""), True
    if status == "Finished":
        return (time or ""), True
    if status == "Lapped" or status.startswith("+"):
        try:
            behind = winner_laps - int(row.get("laps") or winner_laps)
        except (TypeError, ValueError):
            behind = 0
        if behind > 0:
            return f"+{behind} Runde" + ("n" if behind != 1 else ""), True
        return status, True
    return STATUS_DE.get(status, status), False


def format_f1_classification(rows: list[dict]) -> str:
    """Komplette Klassifizierung: 'Pos. Fahrer (Team) — Zeit/+Abstand — Pkt'."""
    if not rows:
        return ""
    try:
        winner_laps = int(rows[0].get("laps") or 0)
    except (TypeError, ValueError):
        winner_laps = 0

    lines = []
    for r in rows:
        name = (r.get("Driver") or {}).get("familyName") or "?"
        con = (r.get("Constructor") or {}).get("name") or ""
        suffix = f" ({con})" if con else ""
        timing, classified = _timing(r, winner_laps)
        if classified:
            pts = r.get("points")
            pts_str = f" — {pts} Pkt" if pts is not None else ""
            timing_str = f" — {timing}" if timing else ""
            lines.append(f"{r.get('position')}. {name}{suffix}{timing_str}{pts_str}")
        else:
            detail = f" — {timing}" if timing else " — DNF"
            lines.append(f"– {name}{suffix}{detail}")
    return "\n".join(lines)


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

        cache = self.cache.load_json("f1_results_v2") if self.cache else {}
        self._dirty = False

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
                    description = self._classification(cache, season, rnd, key, res_kind)
                    if key == "race" and description:
                        standings = self._standings(cache, season, rnd)
                        if standings:
                            description += "\n\n" + standings

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

        if self._dirty and self.cache:
            self.cache.save_json("f1_results_v2", cache)
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

    def _classification(self, cache: dict, season: int, rnd: str, key: str, res_kind: str):
        ck = f"{season}-{rnd}-{key}"
        if ck in cache:
            return cache[ck] or None
        text = self._fetch_classification(season, rnd, res_kind)
        if text:
            cache[ck] = text
            self._dirty = True
        return text

    def _fetch_classification(self, season: int, rnd: str, res_kind: str):
        path, field = RESULT_ENDPOINT[res_kind]
        try:
            data = self.get_json(f"{API}/{season}/{rnd}/{path}")
            races = data["MRData"]["RaceTable"]["Races"]
            if not races:
                return None
            rows = races[0].get(field) or []
            if not rows:
                return None
            if res_kind == "qualifying":
                entries = [
                    (r.get("position"), (r.get("Driver") or {}).get("familyName") or "?",
                     (r.get("Constructor") or {}).get("name"))
                    for r in rows[:3]
                ]
                if entries[0][0] is None:
                    return None
                return "🏁 Pole: " + format_podium(entries)
            return "🏁 Ergebnis:\n" + format_f1_classification(rows)
        except Exception as e:  # noqa: BLE001
            log.warning("F1-Ergebnis %s R%s/%s fehlgeschlagen: %s", season, rnd, res_kind, e)
            return None

    def _standings(self, cache: dict, season: int, rnd: str):
        ck = f"{season}-{rnd}-standings"
        if ck in cache:
            return cache[ck] or None
        try:
            data = self.get_json(f"{API}/{season}/{rnd}/driverStandings.json")
            lists = data["MRData"]["StandingsTable"]["StandingsLists"]
            if not lists:
                return None
            ds = lists[0].get("DriverStandings") or []
            entries = [
                (int(d["position"]), (d.get("Driver") or {}).get("familyName") or "?",
                 int(d.get("points") or 0))
                for d in ds
            ]
            text = format_standings_table(entries)
        except Exception as e:  # noqa: BLE001
            log.warning("F1-WM-Wertung %s R%s fehlgeschlagen: %s", season, rnd, e)
            return None
        if text:
            cache[ck] = text
            self._dirty = True
        return text
