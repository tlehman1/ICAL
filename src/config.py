"""Laden & Validieren von config.yaml + Saison-Helfer."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml


@dataclass
class AppConfig:
    calendar_name: str
    timezone: str
    output: str
    cache_dir: str
    sources: dict
    raw: dict

    @classmethod
    def load(cls, path: str | Path) -> "AppConfig":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        sources = data.get("sources", {}) or {}
        return cls(
            calendar_name=data.get("calendar_name", "Sport-Kalender"),
            timezone=data.get("timezone", "Europe/Berlin"),
            output=data.get("output", "public/calendar.ics"),
            cache_dir=data.get("cache_dir", "data/cache"),
            sources=sources,
            raw=data,
        )

    def source(self, name: str) -> dict:
        return self.sources.get(name, {}) or {}

    def is_enabled(self, name: str) -> bool:
        return bool(self.source(name).get("enabled", False))


def resolve_football_season(value, now: datetime | None = None) -> int:
    """Bundesliga-Saison = Startjahr. 'auto' -> ab Juli das laufende Jahr, sonst Vorjahr."""
    if value not in (None, "auto"):
        return int(value)
    now = now or datetime.now(timezone.utc)
    return now.year if now.month >= 7 else now.year - 1


def resolve_calendar_season(value, now: datetime | None = None) -> int:
    """Kalenderjahr-Saison (F1/MotoGP/WM). 'auto' -> laufendes Jahr."""
    if value not in (None, "auto"):
        return int(value)
    now = now or datetime.now(timezone.utc)
    return now.year
