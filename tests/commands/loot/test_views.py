from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.loot import views


def test_card_view_is_persistent_with_join_and_leave():
    view = views.LootCardView(MagicMock())
    assert view.timeout is None
    assert {item.custom_id for item in view.children} == {"loot:join", "loot:leave"}


def test_log_view_is_persistent():
    view = views.LogLootView(MagicMock())
    assert view.timeout is None
    assert [item.custom_id for item in view.children] == ["loot:log"]
    assert view.children[0].label == "Log loot"


@pytest.mark.asyncio
async def test_join_button_delegates(monkeypatch):
    join = AsyncMock()
    monkeypatch.setattr(views.handlers, "handle_card_join", join)
    cog = MagicMock()
    interaction = MagicMock()
    view = views.LootCardView(cog)
    await next(b for b in view.children if b.custom_id == "loot:join").callback(interaction)
    join.assert_awaited_once_with(cog, interaction)


@pytest.mark.asyncio
async def test_log_button_opens_modal():
    interaction = MagicMock()
    interaction.response.send_modal = AsyncMock()
    view = views.LogLootView(MagicMock())
    await view.children[0].callback(interaction)
    assert isinstance(interaction.response.send_modal.await_args.args[0], views.LogLootModal)


@pytest.mark.asyncio
async def test_modal_rejects_non_numeric_scu(monkeypatch):
    log = AsyncMock()
    monkeypatch.setattr(views.handlers, "handle_log", log)
    modal = views.LogLootModal(MagicMock())
    modal.commodity._value = "Gold"
    modal.scu._value = "lots"
    interaction = MagicMock()
    interaction.response.send_message = AsyncMock()
    await modal.on_submit(interaction)
    log.assert_not_awaited()
    assert "whole number" in interaction.response.send_message.await_args.args[0]


@pytest.mark.asyncio
async def test_modal_logs_for_submitter(monkeypatch):
    log = AsyncMock()
    monkeypatch.setattr(views.handlers, "handle_log", log)
    cog = MagicMock()
    modal = views.LogLootModal(cog)
    modal.commodity._value = "Gold"
    modal.scu._value = " 96 "
    interaction = MagicMock()
    interaction.user.id = 8
    await modal.on_submit(interaction)
    log.assert_awaited_once_with(cog, interaction, commodity="Gold", scu=96, holder_id=8, raid=None)
