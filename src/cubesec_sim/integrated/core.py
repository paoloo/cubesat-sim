"""Deterministic simulation infrastructure and scenario contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Protocol
import time


class Clock(Protocol):
    def now(self) -> datetime: ...
    def sleep(self, seconds: float) -> None: ...


class VirtualClock:
    def __init__(self, start: datetime | None = None):
        self._time = (start or datetime(2026, 8, 26, tzinfo=timezone.utc)).astimezone(timezone.utc)

    def now(self) -> datetime:
        return self._time

    def sleep(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("seconds must be non-negative")
        self._time += timedelta(seconds=seconds)


class WallClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def sleep(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("seconds must be non-negative")
        time.sleep(seconds)


@dataclass(frozen=True)
class Event:
    sequence: int
    time: str
    topic: str
    source: str
    data: dict[str, Any]


class EventBus:
    def __init__(self, clock: Clock):
        self.clock = clock
        self.events: list[Event] = []
        self._subscribers: list[tuple[str, Callable[[Event], None]]] = []

    def publish(self, topic: str, source: str, **data: Any) -> Event:
        event = Event(len(self.events), self.clock.now().isoformat(), topic, source, data)
        self.events.append(event)
        for prefix, callback in tuple(self._subscribers):
            if topic.startswith(prefix):
                callback(event)
        return event

    def subscribe(self, topic_prefix: str, callback: Callable[[Event], None]) -> None:
        self._subscribers.append((topic_prefix, callback))

    def records(self) -> list[dict[str, Any]]:
        return [asdict(event) for event in self.events]


@dataclass
class ScenarioResult:
    scenario_id: str
    passed: bool
    checks: dict[str, bool]
    metrics: dict[str, Any]
    evidence: dict[str, Any]
    error: str | None = None


@dataclass
class Context:
    run_id: str
    seed: int
    clock: Clock
    bus: EventBus
    spacecraft: Any

