"""MotoGP-Provider auf Basis der offiziellen (undokumentierten) Pulselive-API.

Der Zeitplan kommt aus dem Broadcast-Feed ``/events?seasonYear=YYYY``. Achtung:
dieser mischt alle Klassen (MotoGP/Moto2/Moto3/MotoE) – wir filtern strikt auf
``category.acronym == 'MGP'`` und nur echte GP-Events (``kind == 'GP'``).

Ergebnisse hängen an einem ZWEITEN UUID-Namespace (Results-API). Sie werden
best-effort über die Kette seasons→events→categories→sessions→classification
aufgelöst, gecacht und bei jedem Fehler still übersprungen (der Zeitplan bleibt).

Rennen & Sprints bekommen die KOMPLETTE Klassifizierung (Platz, Fahrer, Zeit/
Abstand, Punkte). Die aktuelle WM-Wertung (Fahrer-Standings) wird zusätzlich an
das zuletzt gefahrene Rennen gehängt – die Standings-API liefert nur den
aktuellen Stand, nicht den historischen pro Rennen.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from dateutil import parser as dtparser

from ..formatting import format_podium, format_session_summary, format_standings_table
from ..config import resolve_calendar_season
from ..models import Event
from .base import Provider

API = "https://api.motogp.pulselive.com/motogp/v1"
MGP = "MGP"  # category acronym der MotoGP-Klasse

# config-key -> Menge der Broadcast-shortnames
SESSION_SHORTNAMES = {
    "race": {"RAC"},
    "sprint": {"SPR"},
    "qualifying": {"Q1", "Q2"},
    "practice": {"FP", "FP1", "FP2", "PR", "WUP"},
}

LABELS = {
    "RAC": "Rennen",
    "SPR": "Sprint",
    "Q1": "Qualifying 1",
    "Q2": "Qualifying 2",
    "WUP": "Warm Up",
    "FP1": "1. Freies Training",
    "FP2": "2. Freies Training",
    "FP": "Freies Training",
    "PR": "Practice",
}

# Sessions, die eine VOLLE Klassifizierung (statt nur Top-3) bekommen.
FULL_RESULT_SHORTNAMES = {"RAC", "SPR"}

# Mindest-/Default-Dauer in Minuten (die API liefert date_end teils == date_start)
DEFAULT_DURATION = {
    "RAC": 60, "SPR": 45, "Q1": 20, "Q2": 20,
    "WUP": 20, "FP1": 45, "FP2": 45, "FP": 45, "PR": 60,
}

# Broadcast-shortname -> (Results-Session-Typ, Nummer)
RESULT_SESSION = {
    "RAC": ("RAC", None),
    "SPR": ("SPR", None),
    "Q1": ("Q", 1),
    "Q2": ("Q", 2),
    "WUP": ("WUP", None),
    "FP1": ("FP", 1),
    "FP2": ("FP", 2),
    "PR": ("PR", None),
}

log = logging.getLogger("ical.motogp")


# --------------------------------------------------------------------------- #
# Formatierung (rein, testbar)
# --------------------------------------------------------------------------- #
def format_classification(rows: list[dict]) -> str:
    """Komplette Klassifizierung: 'Pos. Fahrer (Hersteller) — Zeit/+Abstand — Pkt'."""
    lines = []
    for r in rows:
        pos = r.get("position")
        rider = (r.get("rider") or {}).get("full_name") or "?"
        con = (r.get("constructor") or {}).get("name") or ""
        suffix = f" ({con})" if con else ""
        pts = r.get("points")

        if pos is None:  # nicht gewertet (DNF/DNS/DSQ)
            laps = r.get("total_laps")
            if laps:
                unit = "Runde" if str(laps) == "1" else "Runden"
                detail = f"DNF, {laps} {unit}"
            else:
                detail = "DNF"
            lines.append(f"– {rider}{suffix} — {detail}")
            continue

        gap = r.get("gap") or {}
        if pos == 1:
            timing = r.get("time") or ""
        else:
            lap = str(gap.get("lap") or "0")
            if lap not in ("0", "", "None"):
                timing = f"+{lap} Runde" + ("n" if lap != "1" else "")
            else:
                g = gap.get("first")
                timing = f"+{g}" if g else ""
        pts_str = f" — {pts} Pkt" if pts is not None else ""
        timing_str = f" — {timing}" if timing else ""
        lines.append(f"{pos}. {rider}{suffix}{timing_str}{pts_str}")
    return "\n".join(lines)


def format_standings(rows: list[dict]) -> str:
    """WM-Wertung aus MotoGP-Standings-Rows."""
    entries = [
        (int(r["position"]), (r.get("rider") or {}).get("full_name") or "?",
         int(r.get("points") or 0))
        for r in rows
        if r.get("position") is not None
    ]
    return format_standings_table(entries)


class MotoGPProvider(Provider):
    name = "motogp"
    emoji = "🏍️"
    categories = ["Motorsport", "MotoGP"]

    def fetch(self) -> list[Event]:
        season = resolve_calendar_season(self.options.get("season"))
        wanted = self.options.get("sessions") or ["race", "sprint", "qualifying"]
        wanted_sn = set()
        for k in wanted:
            wanted_sn |= SESSION_SHORTNAMES.get(k, set())

        data = self.get_json(f"{API}/events?seasonYear={season}")
        events_data = data if isinstance(data, list) else data.get("events", [])
        now = datetime.now(timezone.utc)
        resolver = _ResultsResolver(self, season) if self.cache is not None else None

        out: list[Event] = []
        latest_race = None  # (start, Event) – das zuletzt gefahrene Rennen
        for ev in events_data:
            if (ev.get("kind") or "").upper() != "GP":
                continue
            gp_name = self._event_name(ev)
            circuit = (ev.get("circuit") or {}).get("name")

            for b in ev.get("broadcasts") or []:
                if (b.get("type") or "").upper() != "SESSION":
                    continue
                if ((b.get("category") or {}).get("acronym") or "").upper() != MGP:
                    continue
                sn = (b.get("shortname") or "").upper()
                if sn not in wanted_sn:
                    continue
                ds = b.get("date_start")
                if not ds:
                    continue
                start = dtparser.isoparse(ds)
                de = b.get("date_end")
                end = dtparser.isoparse(de) if de else None
                if end is None or end <= start:
                    end = start + timedelta(minutes=DEFAULT_DURATION.get(sn, 60))

                description = None
                if resolver is not None and end < now and b.get("has_results"):
                    description = resolver.result_text(
                        ev, sn, full=sn in FULL_RESULT_SHORTNAMES
                    )

                event_obj = Event(
                    uid=f"motogp-{b['id']}@ical",
                    start=start,
                    end=end,
                    summary=format_session_summary(self.emoji, gp_name, LABELS.get(sn, sn)),
                    location=circuit,
                    description=description,
                    categories=list(self.categories),
                )
                out.append(event_obj)

                if sn == "RAC" and end < now and (latest_race is None or start > latest_race[0]):
                    latest_race = (start, event_obj)

        # Aktuelle WM-Wertung an das zuletzt gefahrene Rennen hängen.
        if resolver is not None and latest_race is not None:
            standings = resolver.standings_text()
            if standings:
                ev = latest_race[1]
                ev.description = (
                    f"{ev.description}\n\n{standings}" if ev.description else standings
                )

        if resolver is not None:
            resolver.flush()
        return out

    @staticmethod
    def _event_name(ev: dict) -> str:
        base = (
            ev.get("additional_name") or ev.get("shortname") or ev.get("name") or "MotoGP"
        ).strip()
        if base.isupper():
            # Title-Case, aber kurze Akronyme (USA, UAE) groß lassen.
            base = " ".join(
                w if (w.isupper() and len(w) <= 3) else w.title() for w in base.split()
            )
        return f"{base} GP"


class _ResultsResolver:
    """Löst Ergebnisse über die Results-API auf. Alles fail-safe & gecacht.

    Volle Klassifizierungen sind unveränderlich und werden persistent gecacht.
    Die WM-Wertung ist ein bewegliches Ziel (aktueller Stand) und wird pro Lauf
    einmal frisch geholt (memoisiert, nicht persistent).
    """

    def __init__(self, provider: Provider, season: int):
        self.p = provider
        self.season = season
        self.text_cache = provider.cache.load_json("motogp_results_v2")
        self.dirty = False
        self._season_uuid = None
        self._events = None  # Results-Events (lazy)
        self._cat_uuid = None  # MotoGP-Kategorie (saisonstabil)
        self._sessions_by_event: dict[str, list] = {}
        self._standings = None  # memoisierter Text pro Lauf

    # ---- öffentliche API ---------------------------------------------------
    def result_text(self, broadcast_event: dict, shortname: str, full: bool = False):
        key = f"{broadcast_event.get('id')}-{shortname}"
        if key in self.text_cache:
            return self.text_cache[key] or None

        re = self._match_event(broadcast_event)
        if not re:
            return None
        target = self._find_session(self._sessions(re["id"]), shortname)
        if not target:
            return None
        try:
            cls = self.p.get_json(
                f"{API}/results/session/{target['id']}/classification?test=false"
            )
            rows = cls.get("classification") or []
            if not rows:
                return None
            if full:
                text = "🏁 Ergebnis:\n" + format_classification(rows)
            else:
                entries = [
                    (r.get("position"), (r.get("rider") or {}).get("full_name") or "?",
                     (r.get("constructor") or {}).get("name"))
                    for r in rows[:3]
                ]
                if entries[0][0] is None:
                    return None
                text = "🏁 " + format_podium(entries)
        except Exception as e:  # noqa: BLE001
            log.warning("MotoGP-Klassifikation fehlgeschlagen: %s", e)
            return None
        self.text_cache[key] = text
        self.dirty = True
        return text

    def standings_text(self):
        if self._standings is not None:
            return self._standings
        self._load_events()
        cat = self._category_uuid()
        if not self._season_uuid or not cat:
            self._standings = ""
            return ""
        try:
            data = self.p.get_json(
                f"{API}/results/standings?seasonUuid={self._season_uuid}&categoryUuid={cat}"
            )
            self._standings = format_standings(data.get("classification") or [])
        except Exception as e:  # noqa: BLE001
            log.warning("MotoGP-WM-Wertung fehlgeschlagen: %s", e)
            self._standings = ""
        return self._standings

    # ---- interne Helfer ----------------------------------------------------
    def _load_events(self):
        if self._events is not None:
            return
        try:
            seasons = self.p.get_json(f"{API}/results/seasons")
            self._season_uuid = next(
                (s["id"] for s in seasons if s.get("year") == self.season), None
            )
            self._events = (
                self.p.get_json(
                    f"{API}/results/events?seasonUuid={self._season_uuid}&isFinished=true"
                )
                if self._season_uuid
                else []
            )
        except Exception as e:  # noqa: BLE001
            log.warning("MotoGP-Results-Events fehlgeschlagen: %s", e)
            self._events = []

    def _category_uuid(self):
        """MotoGP-Kategorie-UUID (saisonstabil) von einem echten GP-Event holen."""
        if self._cat_uuid:
            return self._cat_uuid
        self._load_events()
        for re in self._events:
            if "test" in (re.get("name") or "").lower():
                continue
            try:
                cats = self.p.get_json(f"{API}/results/categories?eventUuid={re['id']}")
            except Exception:  # noqa: BLE001
                continue
            cat = next((c for c in cats if "motogp" in (c.get("name") or "").lower()), None)
            if cat:
                self._cat_uuid = cat["id"]
                return self._cat_uuid
        return None

    def _match_event(self, broadcast_event: dict):
        self._load_events()
        bstart = broadcast_event.get("date_start")
        try:
            bday = dtparser.isoparse(bstart).date() if bstart else None
        except Exception:
            bday = None
        if bday:
            for re in self._events:
                d0 = self._date(re.get("date_start"))
                d1 = self._date(re.get("date_end")) or d0
                if d0 and d1 and d0 <= bday <= d1:
                    return re
        bc = ((broadcast_event.get("circuit") or {}).get("name") or "").lower()
        if bc:
            for re in self._events:
                if ((re.get("circuit") or {}).get("name") or "").lower() == bc:
                    return re
        return None

    def _sessions(self, event_uuid: str):
        if event_uuid in self._sessions_by_event:
            return self._sessions_by_event[event_uuid]
        sessions = []
        try:
            cats = self.p.get_json(f"{API}/results/categories?eventUuid={event_uuid}")
            cat = next((c for c in cats if "motogp" in (c.get("name") or "").lower()), None)
            if cat:
                self._cat_uuid = self._cat_uuid or cat["id"]
                sessions = self.p.get_json(
                    f"{API}/results/sessions?eventUuid={event_uuid}&categoryUuid={cat['id']}"
                )
        except Exception as e:  # noqa: BLE001
            log.warning("MotoGP-Sessions fehlgeschlagen: %s", e)
        self._sessions_by_event[event_uuid] = sessions
        return sessions

    @staticmethod
    def _find_session(sessions: list, shortname: str):
        want = RESULT_SESSION.get(shortname.upper())
        if not want:
            return None
        wtype, wnum = want
        for s in sessions:
            if (s.get("type") or "").upper() == wtype and (
                wnum is None or s.get("number") == wnum
            ):
                return s
        return None

    @staticmethod
    def _date(value):
        try:
            return dtparser.isoparse(value).date() if value else None
        except Exception:
            return None

    def flush(self):
        if self.dirty:
            self.p.cache.save_json("motogp_results_v2", self.text_cache)
