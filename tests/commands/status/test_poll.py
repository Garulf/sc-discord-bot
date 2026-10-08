"""Unit tests for src.commands.status.shared.poll and its helpers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.status.shared import SEEN_KEY, SUBSCRIPTIONS_KEY, SYSTEMS_KEY, poll
from src.rsi_status import StatusEntry, StatusOverview, StatusSystem


def _cog():
    bot = MagicMock()
    cog = MagicMock()
    cog.bot = bot
    return cog


@pytest.mark.asyncio
async def test_poll_survives_state_write_failure(monkeypatch):
    """A storage error while persisting poll results must not kill the poller.

    Regression test: on 2026-09-02 the host disk filled up, `state.set` raised
    sqlite3.OperationalError from inside `_poll_systems`, and because that call
    wasn't covered by the function's try/except, the exception escaped `poll()`
    and killed the `poll_status` task loop for good (discord.ext.tasks does not
    auto-retry non-OSError exceptions). Nobody got another status update until
    the bot was manually restarted.
    """
    cog = _cog()

    async def fake_state_get(key, default=None):
        if key == SUBSCRIPTIONS_KEY:
            return [123]
        if key == SEEN_KEY:
            return {"guid-1": "old-date"}
        if key == SYSTEMS_KEY:
            return {"Platform": "operational"}
        return default

    cog.bot.state.get = AsyncMock(side_effect=fake_state_get)
    cog.bot.state.set = AsyncMock(side_effect=OSError("database or disk is full"))
    cog.bot.get_channel = MagicMock(return_value=None)

    entries = [StatusEntry(guid="guid-1", title="Incident", link=None, published="new-date", summary=None)]
    overview = StatusOverview(
        summary_status="major", systems=[StatusSystem(name="Platform", status="major", unresolved=[])]
    )

    monkeypatch.setattr("src.commands.status.shared.fetch_status_entries", AsyncMock(return_value=entries))
    monkeypatch.setattr("src.commands.status.shared.fetch_status_overview", AsyncMock(return_value=overview))

    await poll(cog)  # must not raise
