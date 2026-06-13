"""WM-Provider auf Basis von football-data.org (Token via FOOTBALL_DATA_TOKEN).

Liefert alle Spiele des Wettbewerbs (default 'WC'). Vor dem Spiel die Teams,
nach Abpfiff der Score. Teamnamen sind englisch (so wie von der API geliefert).
"""
from __future__ import annotations

import os
from datetime import timedelta

from dateutil import parser as dtparser

from ..formatting import format_match_summary
from ..models import Event
from .base import Provider

API = "https://api.football-data.org/v4"
MATCH_DURATION = timedelta(hours=2)

STAGE_LABELS = {
    "GROUP_STAGE": "Gruppenphase",
    "LAST_16": "Achtelfinale",
    "ROUND_OF_16": "Achtelfinale",
    "LAST_32": "Sechzehntelfinale",
    "ROUND_OF_32": "Sechzehntelfinale",
    "QUARTER_FINALS": "Viertelfinale",
    "SEMI_FINALS": "Halbfinale",
    "THIRD_PLACE": "Spiel um Platz 3",
    "FINAL": "Finale",
    "PLAYOFFS": "Playoffs",
    "PRELIMINARY_ROUND": "Vorrunde",
}


class WorldCupProvider(Provider):
    name = "worldcup"
    emoji = "🏟️"
    categories = ["Fußball", "WM"]

    def fetch(self) -> list[Event]:
        token = os.getenv("FOOTBALL_DATA_TOKEN")
        if not token:
            raise RuntimeError(
                "FOOTBALL_DATA_TOKEN nicht gesetzt – WM-Provider übersprungen."
            )
        comp = self.options.get("competition", "WC")
        data = self.get_json(
            f"{API}/competitions/{comp}/matches",
            headers={"X-Auth-Token": token},
        )

        events: list[Event] = []
        for m in data.get("matches", []):
            utc = m.get("utcDate")
            if not utc:
                continue
            start = dtparser.isoparse(utc)
            end = start + MATCH_DURATION

            home = (m.get("homeTeam") or {}).get("name") or "TBD"
            away = (m.get("awayTeam") or {}).get("name") or "TBD"

            ft = (m.get("score") or {}).get("fullTime") or {}
            sh, sa = ft.get("home"), ft.get("away")
            finished = m.get("status") == "FINISHED" and sh is not None and sa is not None
            summary = format_match_summary(self.emoji, home, away, finished, sh, sa)

            stage = STAGE_LABELS.get(
                m.get("stage"), (m.get("stage") or "").replace("_", " ").title()
            )
            grp = m.get("group")
            label = " – ".join(
                p for p in [stage, grp.replace("_", " ").title() if grp else None] if p
            )
            desc = []
            if label:
                desc.append(label)
            if finished:
                desc.append(f"Endergebnis: {sh} : {sa}")

            events.append(
                Event(
                    uid=f"wc-{m['id']}@ical",
                    start=start,
                    end=end,
                    summary=summary,
                    location=None,
                    description="\n".join(desc) or None,
                    categories=list(self.categories),
                )
            )
        return events
