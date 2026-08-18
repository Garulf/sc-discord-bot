from unittest.mock import AsyncMock, MagicMock

import discord
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
    assert channel.create_thread.await_args.kwargs["type"] == discord.ChannelType.public_thread
    sent = thread.send.await_args
    assert "<@&5>" in sent.kwargs.get("content", "")
    lifecycle.store.save_ticket.assert_awaited_once()
    lifecycle.store.set_open_ticket.assert_awaited_once()
    thread.add_user.assert_awaited_once_with(interaction.user)


@pytest.mark.asyncio
async def test_open_defers_dropped_role_config_write_until_after_creation(make_cog):
    cog = make_cog(config=THREAD_CONFIG)
    interaction = _interaction()
    thread = MagicMock()
    thread.id = 778
    thread.send = AsyncMock()
    thread.add_user = AsyncMock()
    channel = MagicMock()
    channel.create_thread = AsyncMock(return_value=thread)
    interaction.guild.get_channel = MagicMock(return_value=channel)
    interaction.guild.get_role = MagicMock(return_value=None)
    await lifecycle.open_ticket(cog, interaction, "medic", {"location": "Stanton"})
    lifecycle.store.set_config.assert_awaited_once()
    lifecycle.store.save_ticket.assert_awaited_once()
    thread.send.assert_any_await(
        "The responder role mapped to Medic no longer exists and was unmapped. "
        "An admin can re-map it with `/ticket role`."
    )


@pytest.mark.asyncio
async def test_open_writes_no_state_on_http_exception(make_cog):
    import discord as discord_module

    cog = make_cog(config=THREAD_CONFIG)
    interaction = _interaction()
    channel = MagicMock()
    channel.create_thread = AsyncMock(side_effect=discord_module.HTTPException(MagicMock(status=500), "boom"))
    interaction.guild.get_channel = MagicMock(return_value=channel)
    interaction.guild.get_role = MagicMock(return_value=None)
    await lifecycle.open_ticket(cog, interaction, "medic", {"location": "Stanton"})
    lifecycle.store.set_config.assert_not_awaited()
    lifecycle.store.save_ticket.assert_not_awaited()
    lifecycle.store.set_open_ticket.assert_not_awaited()


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
    interaction.channel.send.assert_awaited_once()
    assert str(interaction.user.mention) in interaction.channel.send.await_args.args[0]


@pytest.mark.asyncio
async def test_untracked_ticket_button_replies_ephemerally(make_cog, monkeypatch):
    cog = make_cog(ticket=None)
    interaction = _interaction()
    fake_view = discord.ui.View()
    fake_view.add_item(discord.ui.Button(label="Claim"))
    monkeypatch.setattr(discord.ui.View, "from_message", lambda message, **kwargs: fake_view)
    await lifecycle.handle_claim(cog, interaction)
    assert "no longer tracked" in interaction.response.send_message.await_args.args[0]
    assert fake_view.children[0].disabled is True
    interaction.message.edit.assert_awaited_once_with(view=fake_view)
    assert interaction.message.edit.await_args.kwargs["view"] is not cog.ticket_view
