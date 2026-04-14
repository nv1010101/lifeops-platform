from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True, slots=True)
class CircuitDecision:
    allow_request: bool
    requires_probe: bool


class ModuleCircuitBreaker:
    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        failure_window_seconds: int = 60,
        open_duration_seconds: int = 30,
        initial_state: CircuitState = CircuitState.HALF_OPEN,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._failure_window_seconds = failure_window_seconds
        self._open_duration_seconds = open_duration_seconds
        self._state: CircuitState = initial_state
        self._failures: deque[datetime] = deque()
        self._open_until: datetime | None = None
        self._probe_in_flight = False
        self._lock = asyncio.Lock()

    async def before_request(self) -> CircuitDecision:
        async with self._lock:
            now = datetime.now(UTC)
            self._prune_failures(now)

            if self._state is CircuitState.OPEN:
                if self._open_until is None or now < self._open_until:
                    return CircuitDecision(allow_request=False, requires_probe=False)
                self._state = CircuitState.HALF_OPEN
                self._open_until = None

            if self._state is CircuitState.HALF_OPEN:
                if self._probe_in_flight:
                    return CircuitDecision(allow_request=False, requires_probe=False)
                self._probe_in_flight = True
                return CircuitDecision(allow_request=True, requires_probe=True)

            return CircuitDecision(allow_request=True, requires_probe=False)

    async def on_probe_success(self) -> None:
        async with self._lock:
            self._probe_in_flight = False
            self._state = CircuitState.CLOSED
            self._failures.clear()
            self._open_until = None

    async def on_probe_failure(self) -> None:
        async with self._lock:
            self._probe_in_flight = False
            self._open_circuit(datetime.now(UTC))

    async def on_success(self) -> None:
        async with self._lock:
            if self._state is CircuitState.CLOSED:
                self._failures.clear()

    async def on_failure(self) -> None:
        async with self._lock:
            now = datetime.now(UTC)
            self._prune_failures(now)

            if self._state is CircuitState.HALF_OPEN:
                self._probe_in_flight = False
                self._open_circuit(now)
                return

            if self._state is CircuitState.CLOSED:
                self._failures.append(now)
                if len(self._failures) >= self._failure_threshold:
                    self._open_circuit(now)

    def _open_circuit(self, now: datetime) -> None:
        self._state = CircuitState.OPEN
        self._open_until = now + timedelta(seconds=self._open_duration_seconds)
        self._failures.clear()

    def _prune_failures(self, now: datetime) -> None:
        window_start = now - timedelta(seconds=self._failure_window_seconds)
        while self._failures and self._failures[0] < window_start:
            self._failures.popleft()


_circuit_registry: dict[str, ModuleCircuitBreaker] = {}
_circuit_registry_lock = asyncio.Lock()


async def get_module_circuit_breaker(module_id: str) -> ModuleCircuitBreaker:
    async with _circuit_registry_lock:
        breaker = _circuit_registry.get(module_id)
        if breaker is None:
            breaker = ModuleCircuitBreaker()
            _circuit_registry[module_id] = breaker
        return breaker
