# ⚽🏎️🏍️🏟️ ICAL – Ein Sport-Kalender, alle Abos

Führt mehrere Sport-Kalender zu **einem einzigen Abo** zusammen. Eine
[`config.yaml`](config.yaml) legt fest, welche Teams/Serien rein sollen; ein
Python-Skript holt Termine **und Ergebnisse** aus kostenlosen Sport-APIs und
erzeugt eine `calendar.ics`. GitHub Actions baut sie regelmäßig neu und
veröffentlicht sie über GitHub Pages.

- **Vor** dem Spiel zeigt der Titel die Teams (`⚽ Leverkusen - Bayern`),
  **nach** Abpfiff das Ergebnis (`⚽ Leverkusen 2:1 Bayern`). Bei Fußball
  (Bundesliga & WM) stehen dann auch die **Torschützen mit Minute** in der
  Beschreibung. (Karten liefert OpenLigaDB nicht.) Bei der **WM** steht zudem
  die **Länderflagge** vor jedem Team (`🇩🇪 Deutschland - 🇨🇼 Curaçao`).
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
| WM 2026 (alle Spiele) | 🏟️ | [OpenLigaDB](https://www.openligadb.de) (`wm26`) | nein |

**Alle Quellen sind kostenlos und ohne API-Key** – es ist keinerlei
Registrierung nötig.

## Einrichtung (einmalig)

1. **GitHub Pages** aktivieren: Repo → *Settings* → *Pages* →
   *Source* = **GitHub Actions**.
2. **Workflow starten**: Tab *Actions* → „Build & Deploy Kalender" →
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

- **Fußball-Details:** OpenLigaDB liefert Torschützen + Minute (inkl. Elfmeter/
  Eigentor), aber **keine Karten** – gelbe/rote Karten lassen sich daher nicht
  anzeigen. Die WM nutzt den community-gepflegten Shortcut `wm26`; die K.-o.-Spiele
  erscheinen, sobald sie dort eingetragen sind.
- **MotoGP** nutzt die inoffizielle Pulselive-API (treibt motogp.com an). Sie ist
  kostenlos und vollständig, aber undokumentiert – Ergebnisse werden best-effort
  aufgelöst; bei Problemen bleibt zumindest der Zeitplan erhalten.
- GitHub-Cron läuft in UTC und kann sich verzögern; scheduled Workflows werden
  bei langer Repo-Inaktivität automatisch pausiert.

## Lizenz / Daten

Alle Termine stammen aus öffentlichen Quellen der oben genannten Anbieter.
