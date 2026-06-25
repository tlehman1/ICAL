"""WM-Provider auf Basis von OpenLigaDB (kein API-Key).

Liefert alle Spiele des WM-Turniers (default leagueShortcut 'wm26'). Deutsche
Teamnamen mit **Länderflagge** im Titel (z.B. '🇩🇪 Deutschland - 🇨🇼 Curaçao').
Nach Abpfiff Spieltag/Runde, Endergebnis und Torschützen in der Beschreibung.
(Karten sind in OpenLigaDB nicht enthalten.)
"""
from __future__ import annotations

from ..models import Event
from .base import Provider
from .football import API, build_football_event

# OpenLigaDB-3-Buchstaben-Code -> ISO-3166-1 alpha-2 (für das Flaggen-Emoji).
# Überwiegend ISO-Alpha-3, aber einige FIFA-Codes weichen ab (GER->DE, RSA->ZA …).
CODE_TO_ISO2 = {
    "ARG": "AR", "AUS": "AU", "AUT": "AT", "BEL": "BE", "BIH": "BA", "BRA": "BR",
    "CAN": "CA", "CHE": "CH", "CIV": "CI", "COD": "CD", "COL": "CO", "CPV": "CV",
    "CUW": "CW", "CZE": "CZ", "DZA": "DZ", "ECU": "EC", "EGY": "EG", "ESP": "ES",
    "FRA": "FR", "GER": "DE", "GHA": "GH", "HRV": "HR", "HTI": "HT", "IRN": "IR",
    "IRQ": "IQ", "JOR": "JO", "JPN": "JP", "KOR": "KR", "MAR": "MA", "MEX": "MX",
    "NLD": "NL", "NOR": "NO", "NZL": "NZ", "PAN": "PA", "PAR": "PY", "PRT": "PT",
    "QAT": "QA", "RSA": "ZA", "SAU": "SA", "SEN": "SN", "SWE": "SE", "TUN": "TN",
    "TUR": "TR", "URY": "UY", "USA": "US", "UZB": "UZ",
    # gängige FIFA-Alternativcodes als Absicherung (falls OpenLigaDB sie nutzt):
    "SUI": "CH", "NED": "NL", "POR": "PT", "CRO": "HR", "DEN": "DK",
    "GRE": "GR", "URU": "UY", "SRB": "RS", "SVN": "SI",
}

# Landesteile ohne eigenen ISO-2-Code -> Flaggen-Tag-Sequenzen.
SPECIAL_FLAGS = {
    "ENG": "🏴\U000e0067\U000e0062\U000e0065\U000e006e\U000e0067\U000e007f",
    "SCT": "🏴\U000e0067\U000e0062\U000e0073\U000e0063\U000e0074\U000e007f",
    "WAL": "🏴\U000e0067\U000e0062\U000e0077\U000e006c\U000e0073\U000e007f",
}


def flag_for(code3: str) -> str:
    """3-Buchstaben-Code -> Flaggen-Emoji ('' wenn unbekannt/Platzhalter)."""
    code3 = (code3 or "").strip().upper()
    if code3 in SPECIAL_FLAGS:
        return SPECIAL_FLAGS[code3]
    iso2 = CODE_TO_ISO2.get(code3)
    if not iso2 or len(iso2) != 2:
        return ""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso2)


class WorldCupProvider(Provider):
    name = "worldcup"
    emoji = "🏟️"
    categories = ["Fußball", "WM"]

    def fetch(self) -> list[Event]:
        league = self.options.get("league", "wm26")
        season = self.options.get("season", 2026)
        matches = self.get_json(f"{API}/getmatchdata/{league}/{season}")

        def team_flag(team: dict) -> str:
            return flag_for(team.get("shortName"))

        events: list[Event] = []
        for m in matches:
            ev = build_football_event(
                m, "", self.categories, "wm",
                use_short_names=False, team_prefix=team_flag,
            )
            if ev:
                events.append(ev)
        return events
