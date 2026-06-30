"""Tiny event bus + structured logging used to decouple the bot from the GUI.

The bot publishes events (status changes, log lines, detections); the GUI (or a
CLI) subscribes. Keeping this minimal avoids a hard dependency on any UI
framework in the core logic.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

logger = logging.getLogger("metin2fishbot")


@dataclass
class Event:
    """A single bus event."""

    type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)


Subscriber = Callable[[Event], None]


class EventBus:
    """Thread-safe minimal pub/sub. Subscribers receive every event."""

    def __init__(self) -> None:
        self._subscribers: List[Subscriber] = []
        self._lock = threading.Lock()

    def subscribe(self, fn: Subscriber) -> Subscriber:
        with self._lock:
            self._subscribers.append(fn)
        return fn

    def unsubscribe(self, fn: Subscriber) -> None:
        with self._lock:
            if fn in self._subscribers:
                self._subscribers.remove(fn)

    def publish(self, type: str, **payload: Any) -> None:
        event = Event(type=type, payload=payload)
        with self._lock:
            subscribers = list(self._subscribers)
        for fn in subscribers:
            try:
                fn(event)
            except Exception:  # a bad subscriber must not kill the bot
                logger.exception("event subscriber raised for %s", type)

    # Convenience: publish a log line and also send it to the stdlib logger.
    def log(self, message: str, level: str = "info") -> None:
        getattr(logger, level, logger.info)(message)
        self.publish("log", message=message, level=level)


def configure_logging(debug: bool = False) -> None:
    """Configure root logging once for CLI / standalone use."""
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
