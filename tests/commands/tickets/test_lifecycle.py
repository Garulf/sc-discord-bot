from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.tickets import lifecycle
from src.commands.tickets.rules import STATUS_CLAIMED, STATUS_OPEN

THREAD_CONFIG = {"channel_id": 10, "mode": "thread", "panel_message_id": 11, "tag_ids": {}, "roles": {"medic": 5}}


def _interaction(guild_id=1, user_id=42, channel_id=99, admin=False):
    interaction = MagicMock()
    interaction.guild.id = guild_id
    interaction.guild_id = guild_id
    interaction.user.id = user_id
    interaction.user.display_name = "Garulf"
    interaction.user.guild_permissions.administrator = admin
    interaction.user.roles = []
    interaction.channel.id = channel_id
    interaction.channel.send = AsyncMock()
    interaction.channel.edit = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.message.edit = AsyncMock()
    return interaction


@pytest.fixture
def make_cog(monkeypatch):
    def _make(config=None, ticket=None, open_ticket=None):
        cog = MagicMock()
        cog.bot.state = MagicMock()
        monkeypatch.setattr(lifecycle.store, "get_config", AsyncMock(return_value=config))
        monkeypatch.setattr(lifecycle.store, "set_config", AsyncMock())
        monkeypatch.setattr(lifecycle.store, "get_ticket", AsyncMock(return_value=ticket))
        monkeypatch.setattr(lifecycle.store, "get_open_ticket", AsyncMock(return_value=open_ticket))
        monkeypatch.setattr(lifecycle.store, "save_ticket", AsyncMock())
        monkeypatch.setattr(lifecycle.store, "set_open_ticket", AsyncMock())
        monkeypatch.setattr(lifecycle.store, "clear_open_ticket", AsyncMock())
        return cog

    return _make


@pytest.mark.asyncio
async def test_open_rejects_malformed_location(make_cog):
    cog = make_cog(config=THREAD_CONFIG)
    interaction = _interaction()
    await lifecycle.open_ticket(cog, interaction, "medic", {"location": "a:b:c:d"})
    interaction.response.send_message.assert_awaited_once()
    assert "system:planet:location" in interaction.response.send_message.await_args.args[0]
    lifecycle.store.save_ticket.assert_not_awaited()


@pytest.mark.asyncio
async def test_open_rejects_duplicate(make_cog):
    cog = make_cog(config=THREAD_CONFIG, open_ticket=555)
    interaction = _interaction()
    await lifecycle.open_ticket(cog, interaction, "medic", {"location": "Stanton"})
    msg = interaction.response.send_message.await_args.args[0]
    assert "555" in msg
    lifecycle.store.save_ticket.assert_not_awaited()


@pytest.mark.asyncio
async def test_open_requires_setup(make_cog):
    cog = make_cog(config=None)
    interaction = _interaction()
    await lifecycle.open_ticket(cog, interaction, "medic", {"location": "Stanton"})
    assert "setup" in interaction.response.send_message.await_args.args[0]


@pytest.mark.asyncio
async def test_open_creates_thread_and_saves_state(make_cog):
    cog = make_cog(config=THREAD_CONFIG)
    interaction = _interaction()
    thread = MagicMock()
    thread.id = 777
    thread.send = AsyncMock()
    thread.add_user = AsyncMock()
    channel = MagicMock()
    channel.create_thread = AsyncMock(return_value=thread)
    interaction.guild.get_channel = MagicMock(return_value=channel)
    await lifecycle.open_ticket(cog, interaction, "medic", {"location": "Stanton:Hurston:Lorville"})
    channel.create_thread.assert_awaited_once()
    sent = thread.send.await_args
    assert "<@&5>" in sent.kwargs.get("content", "")
    lifecycle.store.save_ticket.assert_awaited_once()
    lifecycle.store.set_open_ticket.assert_awaited_once()
    thread.add_user.assert_awaited_once_with(interaction.user)


def _open_ticket_record(**overrides):
    ticket = {
        "guild_id": 1,
        "category": "medic",
        "requester_id": 1,
        "claimer_id": None,
        "status": STATUS_OPEN,
        "opened_at": 100.0,
        "closed_at": None,
        "closed_by_id": None,
        "fields": {"location": "Stanton"},
    }
    ticket.update(overrides)
    return ticket


@pytest.mark.asyncio
async def test_claim_updates_ticket_and_embed(make_cog):
    cog = make_cog(ticket=_open_ticket_record())
    interaction = _interaction(user_id=2)
    await lifecycle.handle_claim(cog, interaction)
    saved = lifecycle.store.save_ticket.await_args.args[2]
    assert saved["status"] == STATUS_CLAIMED
    assert saved["claimer_id"] == 2
    interaction.message.edit.assert_awaited_once()
    interaction.channel.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_requester_cannot_claim_own_ticket(make_cog):
    cog = make_cog(ticket=_open_ticket_record())
    interaction = _interaction(user_id=1)
    await lifecycle.handle_claim(cog, interaction)
    lifecycle.store.save_ticket.assert_not_awaited()
    assert interaction.response.send_message.await_args.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_close_archives_and_clears_index(make_cog):
    cog = make_cog(config=THREAD_CONFIG, ticket=_open_ticket_record())
    interaction = _interaction(user_id=1)
    await lifecycle.handle_close(cog, interaction)
    saved = lifecycle.store.save_ticket.await_args.args[2]
    assert saved["status"] == "closed"
    assert saved["closed_by_id"] == 1
    lifecycle.store.clear_open_ticket.assert_awaited_once()
    interaction.channel.edit.assert_awaited_once()


@pytest.mark.asyncio
async def test_untracked_ticket_button_replies_ephemerally(make_cog):
    cog = make_cog(ticket=None)
    interaction = _interaction()
    await lifecycle.handle_claim(cog, interaction)
    assert "no longer tracked" in interaction.response.send_message.await_args.args[0]
