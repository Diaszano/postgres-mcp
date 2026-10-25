"""Opaque process-local cursors with atomic, one-time successful consumption.

Reservations exclude competing consumers. Failed pages may release and retry the
original token until its original expiry; commits invalidate it permanently.
"""

import os
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from hashlib import sha256
from threading import Lock
from typing import Literal

from ..security.errors import PublicToolError
from .eligibility import PageableQuery


@dataclass(frozen=True)
class CursorState:
    query: PageableQuery = field(repr=False)
    database: str | None = field(repr=False)
    mode: Literal["offset", "keyset"]
    max_rows: int
    timeout_seconds: float
    page_size: int
    principal: str | None = field(default=None, repr=False)
    total_returned_rows: int = 0
    offset: int = 0
    last_key: object | None = field(default=None, repr=False)


@dataclass(frozen=True)
class CursorReservation:
    state: CursorState = field(repr=False)
    token_digest: str = field(repr=False)


@dataclass(repr=False)
class _Entry:
    state: CursorState
    expires_at: float
    reservation: CursorReservation | None = None


class InMemoryCursorStore:
    """Keep at most 100 cursors for 300 seconds; each instance is a stdio session.

    Oldest issued entries, including outstanding reservations, may be evicted.
    A forked process must create its own store before issuing or consuming tokens.
    """

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._process_id = os.getpid()
        self._entries: dict[str, _Entry] = {}
        self._lock = Lock()

    def _check_process(self) -> None:
        if os.getpid() != self._process_id:
            raise PublicToolError("CURSOR_INVALID", "The query cursor is invalid.")

    def _issue(self, state: CursorState) -> str:
        now = self._clock()
        for key in [key for key, entry in self._entries.items() if entry.expires_at <= now]:
            del self._entries[key]
        while True:
            token = secrets.token_urlsafe(32)
            key = sha256(token.encode()).hexdigest()
            if key not in self._entries:
                break
        if len(self._entries) >= 100:
            del self._entries[next(iter(self._entries))]
        self._entries[key] = _Entry(state, now + 300)
        return token

    def issue(self, state: CursorState) -> str:
        with self._lock:
            self._check_process()
            return self._issue(state)

    def _entry(self, key: str) -> _Entry:
        entry = self._entries.get(key)
        if entry is None:
            raise PublicToolError("CURSOR_INVALID", "The query cursor is invalid.")
        if entry.expires_at <= self._clock():
            del self._entries[key]
            raise PublicToolError("CURSOR_EXPIRED", "The query cursor has expired.")
        return entry

    def reserve(self, token: str, principal: str | None) -> CursorReservation:
        with self._lock:
            self._check_process()
            key = sha256(token.encode()).hexdigest()
            entry = self._entry(key)
            if entry.state.principal != principal:
                raise PublicToolError("CURSOR_INVALID", "The query cursor is invalid.")
            if entry.reservation is not None:
                raise PublicToolError("CURSOR_BUSY", "The query cursor is already in use.", retryable=True)
            reservation = CursorReservation(entry.state, key)
            entry.reservation = reservation
            return reservation

    def commit(self, reservation: CursorReservation, next_state: CursorState | None) -> str | None:
        with self._lock:
            self._check_process()
            entry = self._entry(reservation.token_digest)
            if entry.reservation is not reservation or (next_state is not None and next_state.principal != entry.state.principal):
                raise PublicToolError("CURSOR_INVALID", "The query cursor is invalid.")
            del self._entries[reservation.token_digest]
            return self._issue(next_state) if next_state is not None else None

    def release_on_error(self, reservation: CursorReservation) -> None:
        with self._lock:
            self._check_process()
            entry = self._entries.get(reservation.token_digest)
            if entry is not None and entry.reservation is reservation:
                entry.reservation = None

    def invalidate_all(self) -> None:
        with self._lock:
            self._entries.clear()
