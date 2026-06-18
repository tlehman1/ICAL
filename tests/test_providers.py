"""Provider-Tests mit eingebetteten Fixtures (kein Netzwerk).

Wir überschreiben pro Instanz ``get_json`` mit einem Dispatcher, der je nach
URL die passende Fixture liefert.
"""
from src.cache import Cache
from src.providers.bundesliga import BundesligaProvider, final_result
from src.providers.formula1 import Formula1Provider, format_f1_classification
from src.providers.motogp import MotoGPProvider, format_classification, format_standings
from src.providers.worldcup import WorldCupProvider


def patch_json(provider, dispatch):
    provider.get_json = lambda url, **kw: dispatch(url, **kw)


# --------------------------------------------------------------------------- #
# Bundesliga
# --------------------------------------------------------------------------- #
OLDB_TEAMS = [{"teamId": 6, "teamName": "Bayer 04 Leverkusen", "shortName": "Leverkusen"}]
OLDB_MATCHES = [
    {  # gewünscht + abgeschlossen
        "matchID": 1, "matchDateTimeUTC": "2024-08-23T18:30:00Z", "matchIsFinished": True,
        "group": {"groupName": "1. Spieltag"},
        "team1": {"teamId": 87, "teamName": "Borussia Mönchengladbach", "shortName": "Gladbach"},
        "team2": {"teamId": 6, "teamName": "Bayer 04 Leverkusen", "shortName": "Leverkusen"},
        "matchResults": [
            {"resultName": "Halbzeitergebnis", "resultTypeID": 1, "pointsTeam1": 0, "pointsTeam2": 2},
            {"resultName": "Endergebnis", "resultTypeID": 2, "pointsTeam1": 2, "pointsTeam2": 3},
        ],
        "location": {"locationStadium": "Borussia Park", "locationCity": "Mönchengladbach"},
    },
    {  # nicht gewünscht (kein Leverkusen) -> herausgefiltert
        "matchID": 2, "matchDateTimeUTC": "2024-08-24T13:30:00Z", "matchIsFinished": False,
        "group": {"groupName": "1. Spieltag"},
        "team1": {"teamId": 40, "teamName": "FC Bayern", "shortName": "Bayern"},
        "team2": {"teamId": 99, "teamName": "VfB Stuttgart", "shortName": "Stuttgart"},
        "matchResults": [],
    },
]


def test_bundesliga_filters_and_formats():
    p = BundesligaProvider({"season": 2024, "teams": ["Bayer 04 Leverkusen"]}, session=None)
    patch_json(p, lambda url, **kw: OLDB_TEAMS if "getavailableteams" in url else OLDB_MATCHES)
    events = p.fetch()
    assert len(events) == 1
    ev = events[0]
    assert ev.summary == "⚽ Gladbach 2:3 Leverkusen"
    assert "1. Spieltag" in ev.description and "Endergebnis: 2 : 3" in ev.description
    assert ev.uid == "bl-1@ical"
    assert ev.location == "Borussia Park, Mönchengladbach"


def test_final_result_ignores_halftime_only():
    assert final_result({"matchResults": [{"resultName": "Halbzeitergebnis", "resultTypeID": 1,
                                            "pointsTeam1": 1, "pointsTeam2": 0}]}) is None


# --------------------------------------------------------------------------- #
# WM / World Cup
# --------------------------------------------------------------------------- #
WC = {"matches": [
    {"id": 10, "utcDate": "2026-06-11T20:00:00Z", "status": "FINISHED", "stage": "GROUP_STAGE",
     "group": "GROUP_A", "homeTeam": {"name": "Mexico"}, "awayTeam": {"name": "South Africa"},
     "score": {"fullTime": {"home": 2, "away": 0}}},
    {"id": 11, "utcDate": "2026-06-12T18:00:00Z", "status": "TIMED", "stage": "GROUP_STAGE",
     "group": "GROUP_B", "homeTeam": {"name": "Qatar"}, "awayTeam": {"name": "Switzerland"},
     "score": {"fullTime": {"home": None, "away": None}}},
]}


def test_worldcup_formats(monkeypatch):
    monkeypatch.setenv("FOOTBALL_DATA_TOKEN", "dummy")
    p = WorldCupProvider({"competition": "WC"}, session=None)
    patch_json(p, lambda url, **kw: WC)
    events = sorted(p.fetch(), key=lambda e: e.uid)
    assert events[0].summary == "🏟️ Mexico 2:0 South Africa"
    assert "Gruppenphase" in events[0].description
    assert events[1].summary == "🏟️ Qatar - Switzerland"


def test_worldcup_requires_token(monkeypatch):
    monkeypatch.delenv("FOOTBALL_DATA_TOKEN", raising=False)
    p = WorldCupProvider({}, session=None)
    try:
        p.fetch()
        assert False, "sollte ohne Token scheitern"
    except RuntimeError:
        pass


# --------------------------------------------------------------------------- #
# Formel 1
# --------------------------------------------------------------------------- #
F1_SCHEDULE = {"MRData": {"RaceTable": {"Races": [{
    "season": "2024", "round": "1", "raceName": "Bahrain Grand Prix",
    "date": "2024-03-02", "time": "15:00:00Z",
    "Circuit": {"circuitName": "Bahrain International Circuit",
                "Location": {"locality": "Sakhir", "country": "Bahrain"}},
    "Qualifying": {"date": "2024-03-01", "time": "16:00:00Z"},
}]}}}
F1_RESULTS = {"MRData": {"RaceTable": {"Races": [{"Results": [
    {"position": "1", "Driver": {"familyName": "Verstappen"}, "Constructor": {"name": "Red Bull"},
     "points": "25", "status": "Finished", "Time": {"time": "1:30:00.000"}, "laps": "57"},
    {"position": "2", "Driver": {"familyName": "Norris"}, "Constructor": {"name": "McLaren"},
     "points": "18", "status": "Finished", "Time": {"time": "+5.000"}, "laps": "57"},
    {"position": "18", "Driver": {"familyName": "Zhou"}, "Constructor": {"name": "Sauber"},
     "points": "0", "status": "Lapped", "Time": {"time": "+2.0"}, "laps": "56"},
    {"position": "20", "Driver": {"familyName": "Sargeant"}, "Constructor": {"name": "Williams"},
     "points": "0", "status": "Accident", "laps": "10"},
]}]}}}
F1_QUALI = {"MRData": {"RaceTable": {"Races": [{"QualifyingResults": [
    {"position": "1", "Driver": {"familyName": "Verstappen"}, "Constructor": {"name": "Red Bull"}},
]}]}}}
F1_STANDINGS = {"MRData": {"StandingsTable": {"StandingsLists": [{"round": "1", "DriverStandings": [
    {"position": "1", "points": "25", "Driver": {"familyName": "Verstappen"}},
    {"position": "2", "points": "18", "Driver": {"familyName": "Norris"}},
]}]}}}


def test_formula1_schedule_results_and_standings(tmp_path):
    p = Formula1Provider({"season": 2024, "sessions": ["race", "qualifying"]},
                         session=None, cache=Cache(tmp_path))

    def dispatch(url, **kw):
        if url.endswith("2024.json"):
            return F1_SCHEDULE
        if "results.json" in url:
            return F1_RESULTS
        if "qualifying.json" in url:
            return F1_QUALI
        if "driverStandings.json" in url:
            return F1_STANDINGS
        raise AssertionError(url)

    patch_json(p, dispatch)
    events = {e.uid: e for e in p.fetch()}
    race = events["f1-2024-1-race@ical"]
    quali = events["f1-2024-1-qualifying@ical"]
    assert race.summary == "🏎️ Bahrain GP - Rennen"
    assert race.description.startswith("🏁 Ergebnis:")
    assert "1. Verstappen (Red Bull) — 1:30:00.000 — 25 Pkt" in race.description
    assert "2. Norris (McLaren) — +5.000 — 18 Pkt" in race.description
    # voller Renn-Standings-Block ans Rennen gehängt
    assert "🏆 WM-Wertung:" in race.description
    assert "1. Verstappen — 25 Pkt" in race.description
    assert "2. Norris — 18 Pkt (-7)" in race.description
    # Qualifying bleibt kompakt, ohne Standings
    assert quali.description.startswith("🏁 Pole:")
    assert "WM-Wertung" not in (quali.description or "")
    assert race.location == "Bahrain International Circuit, Sakhir, Bahrain"


def test_f1_classification_format():
    rows = [
        {"position": "1", "Driver": {"familyName": "Verstappen"}, "Constructor": {"name": "Red Bull"},
         "points": "25", "status": "Finished", "Time": {"time": "1:30:00.000"}, "laps": "57"},
        {"position": "2", "Driver": {"familyName": "Norris"}, "Constructor": {"name": "McLaren"},
         "points": "18", "status": "Finished", "Time": {"time": "+5.000"}, "laps": "57"},
        {"position": "17", "Driver": {"familyName": "Zhou"}, "Constructor": {"name": "Sauber"},
         "points": "0", "status": "Lapped", "laps": "56"},
        {"position": "20", "Driver": {"familyName": "Sargeant"}, "Constructor": {"name": "Williams"},
         "points": "0", "status": "Accident", "laps": "10"},
    ]
    lines = format_f1_classification(rows).splitlines()
    assert lines[0] == "1. Verstappen (Red Bull) — 1:30:00.000 — 25 Pkt"
    assert lines[1] == "2. Norris (McLaren) — +5.000 — 18 Pkt"
    assert lines[2] == "17. Zhou (Sauber) — +1 Runde — 0 Pkt"
    assert lines[3] == "– Sargeant (Williams) — Unfall"


# --------------------------------------------------------------------------- #
# MotoGP – Klassen-/Session-Filter + Mindestdauer
# --------------------------------------------------------------------------- #
MGP_CAT = {"acronym": "MGP", "name": "MotoGP"}
MT2_CAT = {"acronym": "MT2", "name": "Moto2"}
MOTOGP_EVENTS = [
    {"kind": "TEST", "name": "BARCELONA TEST", "broadcasts": []},  # Test -> ignoriert
    {"kind": "GP", "additional_name": "USA", "circuit": {"name": "COTA"}, "broadcasts": [
        {"shortname": "RAC", "type": "SESSION", "category": MGP_CAT, "has_results": False,
         "id": "b-rac", "date_start": "2099-04-14T20:00:00+0200", "date_end": "2099-04-14T20:00:00+0200"},
        {"shortname": "Q2", "type": "SESSION", "category": MGP_CAT, "has_results": False,
         "id": "b-q2", "date_start": "2099-04-13T15:10:00+0200"},
        {"shortname": "RAC", "type": "SESSION", "category": MT2_CAT, "has_results": False,
         "id": "b-rac-mt2", "date_start": "2099-04-14T18:00:00+0200"},  # andere Klasse -> ignoriert
        {"shortname": "FP1", "type": "SESSION", "category": MGP_CAT, "has_results": False,
         "id": "b-fp1", "date_start": "2099-04-12T10:00:00+0200"},  # Practice nicht gewünscht
        {"shortname": "PRESS", "type": "MEDIA", "category": MGP_CAT, "has_results": False,
         "id": "b-press", "date_start": "2099-04-12T09:00:00+0200"},  # MEDIA -> ignoriert
    ]},
]


def test_motogp_filters_class_and_session_and_duration(tmp_path):
    p = MotoGPProvider({"season": 2099, "sessions": ["race", "qualifying"]},
                       session=None, cache=Cache(tmp_path))
    patch_json(p, lambda url, **kw: MOTOGP_EVENTS)
    events = {e.uid: e for e in p.fetch()}
    # nur MGP RAC + Q2 (kein Moto2, kein FP1, kein PRESS)
    assert set(events) == {"motogp-b-rac@ical", "motogp-b-q2@ical"}
    rac = events["motogp-b-rac@ical"]
    assert rac.summary == "🏍️ USA GP - Rennen"
    assert rac.location == "COTA"
    # Mindestdauer erzwungen (date_end == date_start -> +60min für RAC)
    assert (rac.end - rac.start).total_seconds() == 60 * 60


def test_motogp_classification_format():
    rows = [
        {"position": 1, "rider": {"full_name": "Marc Marquez"}, "constructor": {"name": "Ducati"},
         "time": "39:37.244", "gap": {"first": "0.000", "lap": "0"}, "points": 25},
        {"position": 2, "rider": {"full_name": "Alex Marquez"}, "constructor": {"name": "Ducati"},
         "time": "39:38.976", "gap": {"first": "1.732", "lap": "0"}, "points": 20},
        {"position": 16, "rider": {"full_name": "Lapped Guy"}, "constructor": {"name": "KTM"},
         "gap": {"first": "0.000", "lap": "1"}, "points": 0},
        {"position": None, "rider": {"full_name": "Joan Mir"}, "constructor": {"name": "Honda"},
         "gap": {"first": "0.000", "lap": "12"}, "points": 0, "total_laps": 14, "status": "OUTSTND"},
    ]
    lines = format_classification(rows).splitlines()
    assert lines[0] == "1. Marc Marquez (Ducati) — 39:37.244 — 25 Pkt"
    assert lines[1] == "2. Alex Marquez (Ducati) — +1.732 — 20 Pkt"
    assert lines[2] == "16. Lapped Guy (KTM) — +1 Runde — 0 Pkt"
    assert lines[3].startswith("– Joan Mir (Honda) — DNF")
    assert "14 Runden" in lines[3]


def test_motogp_standings_format():
    rows = [
        {"position": 1, "rider": {"full_name": "Marc Marquez"}, "points": 545},
        {"position": 2, "rider": {"full_name": "Alex Marquez"}, "points": 467},
    ]
    lines = format_standings(rows).splitlines()
    assert lines[0] == "🏆 WM-Wertung:"
    assert lines[1] == "1. Marc Marquez — 545 Pkt"
    assert lines[2] == "2. Alex Marquez — 467 Pkt (-78)"
    assert format_standings([]) == ""
