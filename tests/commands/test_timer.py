"""Tests for the /timer command cog."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.commands.timer import TimerCog


def _make_cog() -> TimerCog:
    bot = MagicMock()
    bot.get_user.return_value = None
    bot.fetch_user = AsyncMock()
    return TimerCog(bot)


def _make_interaction(user_id: int = 42) -> MagicMock:
    interaction = MagicMock()
    interaction.user.id = user_id
    interaction.response.send_message = AsyncMock()
    return interaction


class TestCancelExisting:
    def test_returns_false_when_no_task(self):
        cog = _make_cog()
        assert cog._cancel_existing(1, "keycard") is False

    def test_returns_true_and_cancels_running_task(self):
        cog = _make_cog()
        task = MagicMock(spec=asyncio.Task)
        task.done.return_value = False
        cog._tasks[(1, "keycard")] = task
        assert cog._cancel_existing(1, "keycard") is True
        task.cancel.assert_called_once()

    def test_removes_task_from_dict(self):
        cog = _make_cog()
        task = MagicMock(spec=asyncio.Task)
        task.done.return_value = False
        cog._tasks[(1, "keycard")] = task
        cog._cancel_existing(1, "keycard")
        assert (1, "keycard") not in cog._tasks

    def test_returns_false_for_already_done_task(self):
        cog = _make_cog()
        task = MagicMock(spec=asyncio.Task)
        task.done.return_value = True
        cog._tasks[(1, "keycard")] = task
        assert cog._cancel_existing(1, "keycard") is False


def _fake_create_task(coro):
    """Replaces asyncio.create_task in tests: closes the coroutine immediately."""
    coro.close()
    return MagicMock(spec=asyncio.Task)


class TestStart:
    async def test_creates_task_in_dict(self):
        cog = _make_cog()
        interaction = _make_interaction(user_id=7)
        with patch("asyncio.create_task", side_effect=_fake_create_task) as mock_create:
            await cog._start(interaction, "keycard")
        mock_create.assert_called_once()
        assert (7, "keycard") in cog._tasks

    async def test_sends_ephemeral_response(self):
        cog = _make_cog()
        interaction = _make_interaction()
        with patch("asyncio.create_task", side_effect=_fake_create_task):
            await cog._start(interaction, "vault")
        interaction.response.send_message.assert_awaited_once()
        _, kwargs = interaction.response.send_message.call_args
        assert kwargs.get("ephemeral") is True

    async def test_message_contains_timer_label(self):
        cog = _make_cog()
        interaction = _make_interaction()
        with patch("asyncio.create_task", side_effect=_fake_create_task):
            await cog._start(interaction, "keycard")
        msg = interaction.response.send_message.call_args[0][0]
        assert "Key Card" in msg
        assert "30" in msg

    async def test_restart_prefixes_message(self):
        cog = _make_cog()
        interaction = _make_interaction(user_id=5)
        task = MagicMock(spec=asyncio.Task)
        task.done.return_value = False
        cog._tasks[(5, "vault")] = task
        with patch("asyncio.create_task", side_effect=_fake_create_task):
            await cog._start(interaction, "vault")
        msg = interaction.response.send_message.call_args[0][0]
        assert "Restarted" in msg

    async def test_fresh_start_has_no_restart_prefix(self):
        cog = _make_cog()
        interaction = _make_interaction()
        with patch("asyncio.create_task", side_effect=_fake_create_task):
            await cog._start(interaction, "keycard")
        msg = interaction.response.send_message.call_args[0][0]
        assert "Restarted" not in msg


async def _cancel(cog: TimerCog, interaction, kind: str) -> None:
    await cog.cancel.callback(cog, interaction, kind)


class TestCancel:
    async def test_cancel_active_timer_confirms(self):
        cog = _make_cog()
        interaction = _make_interaction(user_id=3)
        task = MagicMock(spec=asyncio.Task)
        task.done.return_value = False
        cog._tasks[(3, "keycard")] = task
        await _cancel(cog, interaction, "keycard")
        msg = interaction.response.send_message.call_args[0][0]
        assert "Cancelled" in msg
        assert "Key Card" in msg

    async def test_cancel_missing_timer_says_not_found(self):
        cog = _make_cog()
        interaction = _make_interaction()
        await _cancel(cog, interaction, "vault")
        msg = interaction.response.send_message.call_args[0][0]
        assert "No active" in msg

    async def test_cancel_response_is_ephemeral(self):
        cog = _make_cog()
        interaction = _make_interaction(user_id=9)
        task = MagicMock(spec=asyncio.Task)
        task.done.return_value = False
        cog._tasks[(9, "vault")] = task
        await _cancel(cog, interaction, "vault")
        _, kwargs = interaction.response.send_message.call_args
        assert kwargs.get("ephemeral") is True


class TestNotify:
    async def test_dms_user_on_fire(self):
        cog = _make_cog()
        user = MagicMock()
        user.send = AsyncMock()
        cog.bot.fetch_user = AsyncMock(return_value=user)
        await cog._notify(99, "Key Card")
        user.send.assert_awaited_once()
        assert "Key Card" in user.send.call_args[0][0]

    async def test_forbidden_error_is_swallowed(self):
        cog = _make_cog()
        user = MagicMock()
        user.send = AsyncMock(side_effect=Exception("Forbidden"))
        cog.bot.fetch_user = AsyncMock(return_value=user)
        await cog._notify(99, "Key Card")  # must not raise

    async def test_uses_cached_user_when_available(self):
        cog = _make_cog()
        user = MagicMock()
        user.send = AsyncMock()
        cog.bot.get_user.return_value = user
        await cog._notify(99, "Key Card")
        cog.bot.fetch_user.assert_not_awaited()
