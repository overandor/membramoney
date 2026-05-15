from __future__ import annotations
from collections import defaultdict
from typing import Any, Callable

class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Callable[[Any], None]]] = defaultdict(list)

    def subscribe(self, topic: str, handler: Callable[[Any], None]) -> None:
        self._subs[topic].append(handler)

    def publish(self, topic: str, payload: Any) -> None:
        for handler in self._subs.get(topic, []):
            handler(payload)
