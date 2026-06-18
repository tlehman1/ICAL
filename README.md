# ⚽🏎️🏍️🏟️ ICAL – Ein Sport-Kalender, alle Abos

Führt mehrere Sport-Kalender zu **einem einzigen Abo** zusammen. Eine
[`config.yaml`](config.yaml) legt fest, welche Teams/Serien rein sollen; ein
Python-Skript holt Termine **und Ergebnisse** aus kostenlosen Sport-APIs und
erzeugt eine `calendar.ics`. GitHub Actions baut sie regelmäßig neu und
veröffentlicht sie über GitHub Pages.

- **Vor** dem Spiel zeigt der Titel die Teams (`⚽ Leverkusen - Bayern`),
  **nach** Abpfiff das Ergebnis (`⚽ Leverkusen 2:1 Bayern`).
- Bei Motorsport ein Termin pro Session (Rennen / Qualifying / Sprint).
  **Rennen und Sprints (F1 & MotoGP)** bekommen die komplette Klassifizierung
  in die Beschreibung – jede Platzierung mit Zeit/Abstand, Punkten und
  DNF-Gründen. Dazu die **Fahrer-WM-Wertung**: bei F1 an *jedes* Rennen (Stand
  nach der jeweiligen Runde, da Jolpica historische Standings liefert), bei
  MotoGP ans *zuletzt gefahrene* Rennen (die MotoGP-API liefert nur den
  aktuellen Stand). Auch das **Qualifying** zeigt die volle Aufstellung mit
  Zeiten/Abständen. MotoGP nennt die **Teamnamen** (z. B. „Ducati Lenovo Team").

## Aktuelle Quellen

| Sportart | Emoji | Quelle | API-Key? |
|---|---|---|---|
| Bundesliga (gewählte Teams) | ⚽ | [OpenLigaDB](https://www.openligadb.de) | nein |
| Formel 1 (Rennen/Quali/Sprint) | 🏎️ | [Jolpica-F1](https://github.com/jolpica/jolpica-f1) | nein |
| MotoGP (Rennen/Quali/Sprint) | 🏍️ | MotoGP Pulselive (inoffiziell) | nein |
| WM 2026 (alle Spiele) | 🏟️ | [football-data.org](https://www.football-data.org) | **ja** (kostenlos) |

## Einrichtung (einmalig)

1. **football-data.org-Token** holen (für die WM): kostenlos registrieren auf
   <https://www.football-data.org/client/register>, Token kopieren.
2. Token als **GitHub-Secret** hinterlegen: Repo → *Settings* →
   *Secrets and variables* → *Actions* → *New repository secret*,
   Name **`FOOTBALL_DATA_TOKEN`**.
3. **GitHub Pages** aktivieren: Repo → *Settings* → *Pages* →
   *Source* = **GitHub Actions**.
4. **Workflow starten**: Tab *Actions* → „Build & Deploy Kalender" →
   *Run workflow*. Danach läuft er automatisch (täglich + alle 30 min).

## Abonnieren

Nach dem ersten erfolgreichen Lauf liegt der Kalender unter:

```
https://tlehman1.github.io/ICAL/calendar.ics
```

Im Kalender-Client „Abo per URL hinzufügen" und diese URL nutzen – als
`webcal://` für viele Apps:

```
webcal://tlehman1.github.io/ICAL/calendar.ics
```

## Konfiguration anpassen

Alles steht in [`config.yaml`](config.yaml). Beispiele:

```yaml
sources:
  bundesliga:
    teams:
      - "Bayer 04 Leverkusen"   # Name reicht – wird auf die teamId gemappt
      - "Borussia Dortmund"     # einfach weitere Teams ergänzen
  formula1:
    sessions: [race, qualifying, sprint, sprint_qualifying]  # ggf. fp1/fp2/fp3
```

- `season: auto` ermittelt die laufende Saison automatisch (Bundesliga: ab Juli
  die neue Saison; F1/MotoGP/WM: das laufende Kalenderjahr).
- Eine Sportart abschalten: `enabled: false`.

## Lokal ausführen / entwickeln

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
$env:FOOTBALL_DATA_TOKEN = "<dein-token>"   # optional, nur für die WM
.\.venv\Scripts\python -m src.main config.yaml
.\.venv\Scripts\python -m pytest             # Tests
```

Das Ergebnis liegt unter `public/calendar.ics`.

## Wie es funktioniert

- `src/providers/*` – pro Sportart ein Provider, der die API in ein gemeinsames
  `Event`-Modell normalisiert.
- `src/icswriter.py` – baut die `.ics` mit **stabilen UIDs**, sodass ein erneuter
  Lauf bestehende Termine *aktualisiert* statt zu duplizieren. `SEQUENCE`/
  `LAST-MODIFIED` werden nur erhöht, wenn sich der Inhalt ändert (z. B. wenn ein
  Ergebnis hinzukommt) – so refreshen Kalender-Apps den Termin in-place.
- `src/cache.py` – **Last-Good-Cache**: Fällt eine API mal aus, werden die
  zuletzt erfolgreich geholten Termine wiederverwendet, damit der Kalender nie
  leer deployt wird.

## Hinweise & Grenzen

- **MotoGP** nutzt die inoffizielle Pulselive-API (treibt motogp.com an). Sie ist
  kostenlos und vollständig, aber undokumentiert – Ergebnisse werden best-effort
  aufgelöst; bei Problemen bleibt zumindest der Zeitplan erhalten.
- **WM-Teamnamen** sind englisch (so liefert football-data.org sie). Eine
  Deutsch-Mapping-Tabelle ließe sich später ergänzen.
- Falls die `WC`-Competition auf dem free tier mal nicht verfügbar ist, ist
  [OpenLigaDB](https://api.openligadb.de) (keyless, deutsche Namen) die naheliegende
  Alternativquelle.
- GitHub-Cron läuft in UTC und kann sich verzögern; scheduled Workflows werden
  bei langer Repo-Inaktivität automatisch pausiert.

## Lizenz / Daten

Alle Termine stammen aus öffentlichen Quellen der oben genannten Anbieter.
