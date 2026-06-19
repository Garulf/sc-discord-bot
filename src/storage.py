"""SQLite-backed persistence for the bot: a TTL cache for API responses and a
small key/value store for bot state. Both share a single :class:`Database`
connection and survive restarts.

API responses are JSON, so cache and state values are stored as JSON text.
Cache entries expire on wall-clock time (``time.time``) so they remain valid
across process restarts.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any

import aiosqlite

DEFAULT_CACHE_TTL_SECONDS = 300

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cache (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);
"""


class Database:
    """Owns the aiosqlite connection and creates the schema on connect."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        directory = os.path.dirname(self._path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._conn = await aiosqlite.connect(self._path)
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.executescript(_SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database is not connected; call connect() first")
        return self._conn


class SqliteCache:
    """A persistent TTL cache scoped to a namespace.

    Keys are prefixed with the namespace so several clients can share one
    database without colliding (e.g. the wiki and UEX clients both caching a
    ``vehicles`` path). Per-key :class:`asyncio.Lock` coalescing is kept in
    memory so concurrent callers asking for the same key share one fetch.
    """

    def __init__(self, db: Database, *, namespace: str, ttl: float = DEFAULT_CACHE_TTL_SECONDS) -> None:
        self._db = db
        self._namespace = namespace
        self._ttl = ttl
        self._locks: dict[str, asyncio.Lock] = {}

    def _scoped(self, key: str) -> str:
        return f"{self._namespace}:{key}"

    async def get(self, key: str) -> Any | None:
        scoped = self._scoped(key)
        async with self._db.conn.execute("SELECT value, expires_at FROM cache WHERE key = ?", (scoped,)) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        value, expires_at = row
        if expires_at < time.time():
            await self._db.conn.execute("DELETE FROM cache WHERE key = ?", (scoped,))
            await self._db.conn.commit()
            return None
        return json.loads(value)

    async def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        lifetime = self._ttl if ttl is None else ttl
        await self._db.conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
            (self._scoped(key), json.dumps(value), time.time() + lifetime),
        )
        await self._db.conn.commit()

    async def clear(self) -> None:
        await self._db.conn.execute("DELETE FROM cache WHERE key LIKE ?", (f"{self._namespace}:%",))
        await self._db.conn.commit()

    def lock(self, key: str) -> asyncio.Lock:
        existing = self._locks.get(key)
        if existing is not None:
            return existing
        created = asyncio.Lock()
        self._locks[key] = created
        return created


class StateStore:
    """A small JSON key/value store for bot state that survives restarts."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def get(self, key: str, default: Any = None) -> Any:
        async with self._db.conn.execute("SELECT value FROM state WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
        return json.loads(row[0]) if row is not None else default

    async def set(self, key: str, value: Any) -> None:
        await self._db.conn.execute(
            "INSERT OR REPLACE INTO state (key, value, updated_at) VALUES (?, ?, ?)",
            (key, json.dumps(value), time.time()),
        )
        await self._db.conn.commit()

    async def delete(self, key: str) -> None:
        await self._db.conn.execute("DELETE FROM state WHERE key = ?", (key,))
        await self._db.conn.commit()
