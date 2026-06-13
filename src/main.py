"""Orchestrator: Config laden → alle aktiven Provider abfragen → Events mergen
→ eine calendar.ics schreiben.

Fällt ein Provider aus, wird sein Last-Good-Cache genutzt, damit der Kalender
(bzw. eine Sportart) nie leer deployt wird.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from .cache import Cache, SequenceState
from .config import AppConfig
from .icswriter import build_calendar
from .providers.base import make_session
from .providers.bundesliga import BundesligaProvider
from .providers.formula1 import Formula1Provider
from .providers.motogp import MotoGPProvider
from .providers.worldcup import WorldCupProvider

PROVIDERS = {
    "bundesliga": BundesligaProvider,
    "formula1": Formula1Provider,
    "motogp": MotoGPProvider,
    "worldcup": WorldCupProvider,
}

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger("ical")


def run(config_path: str | Path = "config.yaml") -> Path:
    cfg = AppConfig.load(config_path)
    cache = Cache(cfg.cache_dir)
    session = make_session()

    all_events = []
    for name, cls in PROVIDERS.items():
        if not cfg.is_enabled(name):
            log.info("Provider '%s' deaktiviert – übersprungen.", name)
            continue
        provider = cls(cfg.source(name), session, cache)
        try:
            events = provider.fetch()
            cache.save_events(name, events)
            log.info("Provider '%s': %d Termine.", name, len(events))
        except Exception as e:  # noqa: BLE001
            cached = cache.load_events(name)
            if cached is not None:
                log.warning(
                    "Provider '%s' fehlgeschlagen (%s) – nutze Last-Good-Cache (%d Termine).",
                    name, e, len(cached),
                )
                events = cached
            else:
                log.error(
                    "Provider '%s' fehlgeschlagen (%s) und kein Cache – überspringe.",
                    name, e,
                )
                events = []
        all_events.extend(events)

    # nach UID deduplizieren (letzter gewinnt)
    by_uid = {ev.uid: ev for ev in all_events}
    events = list(by_uid.values())

    seq = SequenceState(cfg.cache_dir)
    ics = build_calendar(events, cfg.calendar_name, seq, cfg.timezone)
    seq.save()

    out = Path(cfg.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(ics)
    log.info("Geschrieben: %s (%d Termine).", out, len(events))
    return out


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "config.yaml")
