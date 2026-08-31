"""Unit tests for src.commands.hangar.clear — /hangar clear handler."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.hangar import HangarCog
from src.commands.hangar.clear import handle
from src.exec_hangars.schedule import HangarSchedule

_NOW = datetime(2025, 3, 15, 12, 0, 0, tzinfo=UTC)
_GUILD_ID = 42


def _cog() -> HangarCog:
    cog = HangarCog.__new__(HangarCog)
    cog.bot = MagicMock()
    cog.bot.state.set = AsyncMock()
    cog.global_schedule = HangarSchedule.from_charging(observed_at=_NOW)
    cog.global_set_at = _NOW
    cog.guild_schedules = {_GUILD_ID: HangarSchedule.from_active(observed_at=_NOW)}
    cog.guild_set_at = {_GUILD_ID: _NOW}
    cog.subscriptions = []
    cog.warnings = {}
    return cog


def _interaction(guild_id: int = _GUILD_ID) -> MagicMock:
    interaction = MagicMock()
    interaction.guild_id = guild_id
    interaction.response.send_message = AsyncMock()
    return interaction


async def test_clear_removes_guild_override_and_saves():
    cog = _cog()
    interaction = _interaction()

    await handle(cog, interaction)

    assert _GUILD_ID not in cog.guild_schedules
    assert _GUILD_ID not in cog.guild_set_at
    cog.bot.state.set.assert_awaited_once()
    interaction.response.send_message.assert_awaited_once()
    kwargs = interaction.response.send_message.await_args.kwargs
    assert kwargs["ephemeral"] is True
    assert kwargs["embed"] is not None


async def test_clear_without_override_says_already_global():
    cog = _cog()
    cog.guild_schedules = {}
    cog.guild_set_at = {}
    interaction = _interaction()

    await handle(cog, interaction)

    cog.bot.state.set.assert_not_awaited()
    msg = interaction.response.send_message.await_args.args[0]
    assert "global" in msg.lower()


async def test_clear_works_when_global_schedule_unset():
    cog = _cog()
    cog.global_schedule = None
    cog.global_set_at = None
    interaction = _interaction()

    await handle(cog, interaction)

    assert _GUILD_ID not in cog.guild_schedules
    kwargs = interaction.response.send_message.await_args.kwargs
    assert kwargs.get("embed") is None


async def test_clear_resets_guild_notify_state():
    cog = _cog()
    cog.global_schedule = None
    cog.global_set_at = None
    cog.subscriptions = [
        {"guild_id": _GUILD_ID, "channel_id": 1, "message_id": 2, "notify_state": "open", "notify_message_id": None},
        {"guild_id": 999, "channel_id": 3, "message_id": 4, "notify_state": "open", "notify_message_id": None},
    ]
    cog.bot.get_channel = MagicMock(return_value=None)
    interaction = _interaction()

    await handle(cog, interaction)

    assert cog.subscriptions[0]["notify_state"] is None
    assert cog.subscriptions[1]["notify_state"] == "open"


@pytest.mark.parametrize("registered", ["clear"])
def test_clear_command_registered(registered):
    names = [cmd.name for cmd in HangarCog.hangar.commands]
    assert registered in names
