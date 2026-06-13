"""Normalisiertes internes Termin-Modell.

Jeder Provider liefert eine Liste von ``Event``-Objekten; der ICS-Writer
serialisiert sie. Zeiten sind immer tz-aware in UTC.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Event:
    uid: str                          # stabil & deterministisch, z.B. "bl1-77256@ical"
    start: datetime                   # tz-aware UTC
    end: datetime                     # tz-aware UTC
    summary: str                      # fertig formatiert inkl. Emoji + ggf. Ergebnis
    location: str | None = None
    description: str | None = None
    categories: list[str] = field(default_factory=list)

    def content_hash(self) -> str:
        """Hash über die sichtbaren Felder – steuert SEQUENCE/LAST-MODIFIED."""
        payload = "|".join(
            [
                self.summary,
                self.description or "",
                self.location or "",
                self.start.astimezone(timezone.utc).isoformat(),
                self.end.astimezone(timezone.utc).isoformat(),
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        return {
            "uid": self.uid,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "summary": self.summary,
            "location": self.location,
            "description": self.description,
            "categories": list(self.categories),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Event":
        return cls(
            uid=d["uid"],
            start=datetime.fromisoformat(d["start"]),
            end=datetime.fromisoformat(d["end"]),
            summary=d["summary"],
            location=d.get("location"),
            description=d.get("description"),
            categories=list(d.get("categories", [])),
        )
