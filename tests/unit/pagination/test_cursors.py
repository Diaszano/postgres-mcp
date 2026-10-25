import importlib
import importlib.util
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from dataclasses import replace
from hashlib import sha256
from threading import Barrier

import pytest

from postgres_mcp.pagination.eligibility import PageableQuery
from postgres_mcp.security.errors import PublicToolError


@pytest.fixture
def cursors():
    assert importlib.util.find_spec("postgres_mcp.pagination.cursors") is not None, "The cursor store contract is not implemented"
    return importlib.import_module("postgres_mcp.pagination.cursors")


@pytest.fixture
def clock():
    now = [1000.0]
    return now, lambda: now[0]


@pytest.fixture
def state(cursors):
    return cursors.CursorState(
        query=PageableQuery("SELECT id FROM private_items ORDER BY id", "id"),
        database="private_database",
        mode="offset",
        max_rows=250,
        timeout_seconds=10,
        page_size=100,
        principal="alice",
    )


def test_token_is_opaque_and_random(monkeypatch):
    assert importlib.util.find_spec("postgres_mcp.pagination.cursors") is not None, "The cursor store contract is not implemented"
    cursors = importlib.import_module("postgres_mcp.pagination.cursors")
    state = cursors.CursorState(
        query=PageableQuery("SELECT id FROM private_items ORDER BY id", "id"),
        database="private_database",
        mode="offset",
        max_rows=250,
        timeout_seconds=10,
        page_size=100,
        principal="alice",
    )
    store = cursors.InMemoryCursorStore()
    token = store.issue(state)
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", token)
    assert len({token, *(store.issue(state) for _ in range(10))}) == 11
    assert state.query.sql not in token
    assert state.database not in token
    assert "postgresql://user:password@host/db" not in token
    assert sha256(token.encode()).hexdigest() in store._entries
    assert token not in repr(store._entries)
    assert all(re.fullmatch(r"[0-9a-f]{64}", key) for key in store._entries)

    sizes = []
    real_token_urlsafe = cursors.secrets.token_urlsafe

    def token_urlsafe(size):
        sizes.append(size)
        return real_token_urlsafe(size)

    monkeypatch.setattr(cursors.secrets, "token_urlsafe", token_urlsafe)
    store.issue(state)
    assert sizes == [32]
    with pytest.raises(FrozenInstanceError):
        state.offset = 1


def test_expiry_eviction_and_capacity(cursors, state, clock):
    now, monotonic = clock
    store = cursors.InMemoryCursorStore(clock=monotonic)
    token = store.issue(state)
    now[0] += 299.999
    reservation = store.reserve(token, "alice")
    store.release_on_error(reservation)
    now[0] = 1300.0
    with pytest.raises(PublicToolError) as expired:
        store.reserve(token, "alice")
    assert expired.value.code == "CURSOR_EXPIRED"
    assert token not in str(expired.value)

    tokens = [store.issue(state) for _ in range(101)]
    assert len(store._entries) == 100
    with pytest.raises(PublicToolError) as evicted:
        store.reserve(tokens[0], "alice")
    assert evicted.value.code == "CURSOR_INVALID"
    assert store.reserve(tokens[-1], "alice").state == state
    with pytest.raises(PublicToolError) as unknown:
        store.reserve("not-a-cursor", "alice")
    assert unknown.value.code == "CURSOR_INVALID"


def test_one_time_concurrent_use(cursors, state):
    store = cursors.InMemoryCursorStore()
    token = store.issue(state)
    barrier = Barrier(2)

    def consume():
        barrier.wait(timeout=5)
        try:
            return store.reserve(token, "alice")
        except PublicToolError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as consumers:
        outcomes = list(consumers.map(lambda _: consume(), range(2)))
    reservations = [result for result in outcomes if isinstance(result, cursors.CursorReservation)]
    assert len(reservations) == 1
    assert [result for result in outcomes if isinstance(result, str)] == ["CURSOR_BUSY"]
    next_state = replace(state, offset=100, total_returned_rows=100)
    successor = store.commit(reservations[0], next_state)
    assert successor != token
    assert store.reserve(successor, "alice").state == next_state
    with pytest.raises(PublicToolError) as replay:
        store.reserve(token, "alice")
    assert replay.value.code == "CURSOR_INVALID"
    with pytest.raises(PublicToolError) as double_commit:
        store.commit(reservations[0], next_state)
    assert double_commit.value.code == "CURSOR_INVALID"


def test_auth_and_stdio_binding(cursors, state, monkeypatch):
    store = cursors.InMemoryCursorStore()
    token = store.issue(state)
    with pytest.raises(PublicToolError) as wrong_principal:
        store.reserve(token, "bob")
    assert wrong_principal.value.code == "CURSOR_INVALID"
    reservation = store.reserve(token, "alice")
    assert reservation.state == state
    with pytest.raises(PublicToolError) as changed_principal:
        store.commit(reservation, replace(state, principal="bob"))
    assert changed_principal.value.code == "CURSOR_INVALID"
    assert store.commit(reservation, None) is None

    stdio_state = replace(state, principal=None)
    stdio_token = store.issue(stdio_state)
    other_session = cursors.InMemoryCursorStore()
    with pytest.raises(PublicToolError) as wrong_session:
        other_session.reserve(stdio_token, None)
    assert wrong_session.value.code == "CURSOR_INVALID"
    with pytest.raises(PublicToolError):
        store.reserve(stdio_token, "alice")
    real_pid = cursors.os.getpid()
    monkeypatch.setattr(cursors.os, "getpid", lambda: real_pid + 1)
    with pytest.raises(PublicToolError) as wrong_process:
        store.reserve(stdio_token, None)
    assert wrong_process.value.code == "CURSOR_INVALID"
    monkeypatch.setattr(cursors.os, "getpid", lambda: real_pid)
    assert store.reserve(stdio_token, None).state == stdio_state


def test_release_preserves_expiry_and_rejects_stale_reservations(cursors, state, clock):
    now, monotonic = clock
    store = cursors.InMemoryCursorStore(clock=monotonic)
    token = store.issue(state)
    reservation = store.reserve(token, "alice")
    store.release_on_error(reservation)
    retry = store.reserve(token, "alice")
    store.release_on_error(reservation)
    with pytest.raises(PublicToolError) as stale:
        store.commit(reservation, state)
    assert stale.value.code == "CURSOR_INVALID"
    with pytest.raises(PublicToolError) as busy:
        store.reserve(token, "alice")
    assert busy.value.code == "CURSOR_BUSY"
    now[0] += 300
    store.release_on_error(retry)
    with pytest.raises(PublicToolError) as expired:
        store.reserve(token, "alice")
    assert expired.value.code == "CURSOR_EXPIRED"


def test_completion_invalidation_and_reservation_identity(cursors, state):
    store = cursors.InMemoryCursorStore()
    token = store.issue(state)
    reservation = store.reserve(token, "alice")
    forged = replace(reservation)
    with pytest.raises(PublicToolError) as invalid:
        store.commit(forged, None)
    assert invalid.value.code == "CURSOR_INVALID"
    assert store.commit(reservation, None) is None
    with pytest.raises(PublicToolError):
        store.reserve(token, "alice")
    another_token = store.issue(state)
    another_reservation = store.reserve(another_token, "alice")
    store.invalidate_all()
    with pytest.raises(PublicToolError):
        store.reserve(another_token, "alice")
    with pytest.raises(PublicToolError):
        store.commit(another_reservation, state)
    assert store._entries == {}


def test_expired_reservation_cannot_issue_successor(cursors, state, clock):
    now, monotonic = clock
    store = cursors.InMemoryCursorStore(clock=monotonic)
    token = store.issue(state)
    reservation = store.reserve(token, "alice")
    now[0] += 300
    with pytest.raises(PublicToolError) as expired:
        store.commit(reservation, replace(state, offset=100))
    assert expired.value.code == "CURSOR_EXPIRED"
    assert store._entries == {}


def test_token_collision_does_not_overwrite_cursor(cursors, state, monkeypatch):
    store = cursors.InMemoryCursorStore()
    first = store.issue(state)
    second = store.issue(state)
    candidates = iter([first, second, "A" * 43])
    monkeypatch.setattr(cursors.secrets, "token_urlsafe", lambda _: next(candidates))
    assert store.issue(replace(state, offset=100)) == "A" * 43
    assert store.reserve(first, "alice").state == state
    assert store.reserve(second, "alice").state == state
