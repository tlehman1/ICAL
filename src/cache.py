"""Persistenz für Resilienz (Last-Good) und SEQUENCE/LAST-MODIFIED-Status.

Alles liegt unter ``cache_dir`` (default ``data/cache``). In GitHub Actions wird
dieses Verzeichnis via ``actions/cache`` über Läufe hinweg erhalten, damit ein
einzelner API-Ausfall den Kalender (oder eine Sportart) nicht leert und SEQUENCE
korrekt mitzählt.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .models import Event


class Cache:
    def __init__(self, cache_dir: str | Path):
        self.dir = Path(cache_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    # ---- Last-Good Events pro Provider -------------------------------------
    def save_events(self, provider: str, events: list[Event]) -> None:
        path = self.dir / f"provider_{provider}.json"
        payload = [e.to_dict() for e in events]
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def load_events(self, provider: str) -> list[Event] | None:
        path = self.dir / f"provider_{provider}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return [Event.from_dict(d) for d in data]
        except Exception:
            return None

    # ---- generischer JSON-Blob (z.B. Ergebnis-Caches) ----------------------
    def load_json(self, name: str) -> dict:
        path = self.dir / f"{name}.json"
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save_json(self, name: str, data: dict) -> None:
        path = self.dir / f"{name}.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class SequenceState:
    """Hält pro UID {hash, sequence, last_modified}. Bumpt SEQUENCE &
    LAST-MODIFIED nur, wenn sich der sichtbare Inhalt ändert."""

    def __init__(self, cache_dir: str | Path, now: datetime | None = None):
        self.path = Path(cache_dir) / "sequence_state.json"
        self._now = now or datetime.now(timezone.utc)
        self._state: dict = {}
        if self.path.exists():
            try:
                self._state = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self._state = {}

    def resolve(self, event: Event) -> tuple[int, datetime]:
        h = event.content_hash()
        prev = self._state.get(event.uid)
        if prev is None:
            seq, last_mod = 0, self._now
        elif prev.get("hash") != h:
            seq, last_mod = int(prev.get("sequence", 0)) + 1, self._now
        else:
            seq = int(prev.get("sequence", 0))
            last_mod = datetime.fromisoformat(prev["last_modified"])
        self._state[event.uid] = {
            "hash": h,
            "sequence": seq,
            "last_modified": last_mod.isoformat(),
        }
        return seq, last_mod

    def save(self) -> None:
        self.path.write_text(
            json.dumps(self._state, ensure_ascii=False), encoding="utf-8"
        )
