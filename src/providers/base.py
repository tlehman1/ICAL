"""Gemeinsame Provider-Basis: HTTP-Session mit Retries + Provider-Interface."""
from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter

try:  # urllib3 v2 / v1 Pfad
    from urllib3.util.retry import Retry
except Exception:  # pragma: no cover
    from requests.packages.urllib3.util.retry import Retry  # type: ignore

from ..models import Event

USER_AGENT = "ICAL-merged-sports-calendar/1.0 (+https://github.com/tlehman1/ICAL)"


def make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    return s


class Provider:
    """Basisklasse. Unterklassen setzen ``name``/``emoji``/``categories`` und
    implementieren ``fetch() -> list[Event]``. Fehler dürfen geworfen werden –
    der Orchestrator fängt sie ab und nutzt den Last-Good-Cache."""

    name: str = "base"
    emoji: str = ""
    categories: list[str] = []

    def __init__(self, options: dict, session: requests.Session, cache=None):
        self.options = options or {}
        self.session = session
        self.cache = cache

    def fetch(self) -> list[Event]:  # pragma: no cover - abstrakt
        raise NotImplementedError

    def get_json(self, url: str, headers: dict | None = None, timeout: int = 25):
        r = self.session.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.json()
