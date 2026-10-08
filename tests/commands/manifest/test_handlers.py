from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from src.commands.beacons import store as beacon_store
from src.commands.manifest import handlers, ledger, store
from src.commands.manifest.handlers import Draft
from src.storage import Database, StateStore


@pytest.fixture
async def state(tmp_path):
    db = Database(str(tmp_path / "manifest.db"))
    await db.connect()
    yield StateStore(db)
    await db.close()


@pytest.fixture
def thread():
    thread = MagicMock()
    thread.id = 900
    thread.mention = "<#900>"
    return thread


@pytest.fixture
def cog(state, monkeypatch, thread):
    cog = MagicMock()
    cog.bot.state = state

    async def open_thread(_cog, _guild, record):
        record["thread_id"] = thread.id
        await store.save_record(state, record)
        await store.set_by_thread(state, thread.id, record["id"])
        return thread

    monkeypatch.setattr(handlers.card, "open_thread", AsyncMock(side_effect=open_thread))
    monkeypatch.setattr(handlers.card, "refresh_card", AsyncMock(return_value=None))
    monkeypatch.setattr(handlers.card, "announce", AsyncMock())
    monkeypatch.setattr(handlers.card, "add_members", AsyncMock())
    monkeypatch.setattr(handlers.card, "close_thread", AsyncMock())
    monkeypatch.setattr(handlers.pricing, "resolve_cargo", AsyncMock(side_effect=lambda _bot, cargo: cargo))
    return cog


def _interaction(user_id=1, admin=False, channel_id=900, guild_id=7):
    interaction = MagicMock()
    interaction.guild.id = guild_id
    interaction.guild_id = guild_id
    interaction.user = MagicMock(spec=discord.Member)
    interaction.user.id = user_id
    interaction.user.guild_permissions.administrator = admin
    interaction.user.roles = []
    interaction.channel.id = channel_id
    interaction.channel.send = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    return interaction


def _reply(interaction):
    return interaction.followup.send.await_args.args[0]


def _draft(crew=(2, 3), carrier=None, cargo="Gold 100 1000", costs="", beacon=None):
    return Draft(crew_ids=list(crew), carrier_id=carrier, cargo_text=cargo, costs_text=costs, beacon_thread_id=beacon)


async def _create(cog, user_id=1, **kwargs):
    await handlers.handle_create(cog, _interaction(user_id=user_id), _draft(**kwargs))
    return (await store.guild_records(cog.bot.state, 7))[-1]


async def _get(cog, manifest_id=1):
    return await store.get_record(cog.bot.state, 7, manifest_id)


async def test_create_saves_manifest_and_opens_thread(cog):
    interaction = _interaction(user_id=1)
    await handlers.handle_create(cog, interaction, _draft(costs="Fuel 500"))
    record = await _get(cog)
    assert record["carrier_id"] == 1
    assert ledger.crew_ids(record) == [1, 2, 3]
    assert record["cargo"] == [{"commodity": "Gold", "scu": 100, "est_price": 1000.0}]
    assert record["costs"] == [{"label": "Fuel", "amount": 500}]
    assert record["thread_id"] == 900
    assert _reply(interaction) == "Created manifest #1: <#900>"


async def test_create_uses_chosen_carrier(cog):
    record = await _create(cog, user_id=1, carrier=5)
    assert record["carrier_id"] == 5
    assert ledger.crew_ids(record) == [1, 5, 2, 3]


async def test_create_with_bad_text_offers_retry(cog):
    interaction = _interaction()
    await handlers.handle_create(cog, interaction, _draft(cargo="Gold"))
    assert "Line 1" in _reply(interaction)
    assert interaction.followup.send.await_args.kwargs["view"] is not None
    assert await store.guild_records(cog.bot.state, 7) == []


async def test_create_without_channel_still_saves(cog):
    handlers.card.open_thread.side_effect = None
    handlers.card.open_thread.return_value = None
    interaction = _interaction()
    await handlers.handle_create(cog, interaction, _draft())
    assert (await _get(cog)) is not None
    assert "/manifest config channel" in _reply(interaction)


async def test_create_from_beacon_links_and_blocks_second(cog):
    interaction = _interaction(channel_id=50)
    await handlers.handle_create(cog, interaction, _draft(beacon=50))
    assert await store.get_by_beacon(cog.bot.state, 50) == 1
    assert (await _get(cog))["beacon_thread_id"] == 50
    interaction.channel.send.assert_awaited_once()
    assert "manifest #1" in interaction.channel.send.await_args.args[0]
    again = _interaction(channel_id=50)
    await handlers.handle_create(cog, again, _draft(beacon=50))
    assert "already has manifest #1" in _reply(again)
    assert len(await store.guild_records(cog.bot.state, 7)) == 1


async def test_edit_replaces_cargo_and_costs(cog):
    await _create(cog)
    interaction = _interaction(user_id=1)
    await handlers.handle_edit(cog, interaction, 1, "Gold 120\nTin 4 10", "Fuel 100")
    record = await _get(cog)
    assert [line["scu"] for line in record["cargo"]] == [120, 4]
    assert record["costs"] == [{"label": "Fuel", "amount": 100}]
    handlers.card.refresh_card.assert_awaited()


async def test_edit_refuses_crew_member(cog):
    await _create(cog)
    interaction = _interaction(user_id=2)
    await handlers.handle_edit(cog, interaction, 1, "Gold 1", "")
    assert "Only the creator, the carrier or an officer" in _reply(interaction)
    assert (await _get(cog))["cargo"][0]["scu"] == 100


async def test_sell_records_sale_and_announces(cog):
    await _create(cog, costs="Fuel 300")
    interaction = _interaction(user_id=1)
    await handlers.handle_sell(cog, interaction, 1, "Gold", scu=10, total=3300)
    record = await _get(cog)
    assert record["sales"][0]["cost_recovered"] == 300
    assert _reply(interaction) == "Recorded sale 1: 3,000 aUEC split after 300 to costs."
    announcement = handlers.card.announce.await_args.args[2]
    assert announcement == (
        "<@1> sold 10 SCU Gold for 3,300 aUEC. 300 went to costs. Owed: <@2> 1,000, <@3> 1,000"
    )


async def test_sell_refuses_non_carrier(cog):
    await _create(cog)
    interaction = _interaction(user_id=2)
    await handlers.handle_sell(cog, interaction, 1, "Gold", scu=1, total=1)
    assert _reply(interaction) == "Only the carrier <@1> or an officer can sell this cargo."


async def test_sell_by_officer(cog):
    await _create(cog)
    await handlers.handle_sell(cog, _interaction(user_id=9, admin=True), 1, "Gold", scu=1, total=30)
    assert len((await _get(cog))["sales"]) == 1


async def test_change_on_missing_manifest(cog):
    interaction = _interaction()
    await handlers.handle_sell(cog, interaction, 42, "Gold", scu=1, total=1)
    assert _reply(interaction) == "Manifest #42 no longer exists."


async def test_set_crew_adds_new_members_to_thread(cog):
    await _create(cog, crew=(2,))
    await handlers.handle_set_crew(cog, _interaction(user_id=1), 1, [2, 4])
    assert ledger.crew_ids(await _get(cog)) == [1, 2, 4]
    assert handlers.card.add_members.await_args.args[2] == [4]


async def test_set_carrier_and_weight(cog):
    await _create(cog, crew=(2,))
    await handlers.handle_set_carrier(cog, _interaction(user_id=1), 1, 6)
    await handlers.handle_set_weight(cog, _interaction(user_id=6), 1, 2, 3)
    record = await _get(cog)
    assert record["carrier_id"] == 6
    assert {m["user_id"]: m["weight"] for m in record["crew"]}[2] == 3


async def test_crew_changes_need_permission(cog):
    await _create(cog, crew=(2,))
    interaction = _interaction(user_id=2)
    await handlers.handle_set_weight(cog, interaction, 1, 2, 5)
    assert "Only the creator, the carrier or an officer" in _reply(interaction)


async def test_mark_paid_by_seller_and_refusal(cog):
    await _create(cog, crew=(2, 3))
    await handlers.handle_sell(cog, _interaction(user_id=1), 1, "Gold", scu=1, total=300)
    refused = _interaction(user_id=2)
    await handlers.handle_mark_paid(cog, refused, 1, None)
    assert _reply(refused) == "Only whoever sold it or an officer can mark payouts paid."
    interaction = _interaction(user_id=1)
    await handlers.handle_mark_paid(cog, interaction, 1, 2)
    assert _reply(interaction) == "Marked 1 payout paid."
    await handlers.handle_mark_paid(cog, interaction, 1, None)
    assert ledger.owed_amount(await _get(cog)) == 0


async def test_dispute_pings_seller(cog):
    await _create(cog, crew=(2,))
    await handlers.handle_sell(cog, _interaction(user_id=1), 1, "Gold", scu=1, total=200)
    await handlers.handle_mark_paid(cog, _interaction(user_id=1), 1, None)
    interaction = _interaction(user_id=2)
    await handlers.handle_dispute(cog, interaction, 1)
    assert "seller has been pinged" in _reply(interaction)
    assert handlers.card.announce.await_args.args[2] == (
        "<@2> says they haven't received their share from manifest #1. <@1>, please check."
    )


async def test_undo_last_sale(cog):
    await _create(cog, crew=(2,))
    await handlers.handle_sell(cog, _interaction(user_id=1), 1, "Gold", scu=5, total=200)
    interaction = _interaction(user_id=1)
    await handlers.handle_undo(cog, interaction, 1)
    assert _reply(interaction) == "Removed sale 1. 5 SCU Gold is back in the hold."
    assert (await _get(cog))["sales"] == []


async def test_list_is_ephemeral_and_filtered(cog):
    await _create(cog, user_id=1, crew=(2,))
    outsider = _interaction(user_id=9)
    await handlers.handle_list(cog, outsider)
    assert "no manifests yet" in _reply(outsider)
    assert outsider.followup.send.await_args.kwargs["ephemeral"] is True
    crew = _interaction(user_id=2)
    await handlers.handle_list(cog, crew)
    assert "**#1**" in _reply(crew)


async def test_owed(cog):
    await _create(cog, crew=(2,))
    interaction = _interaction(user_id=1)
    await handlers.handle_owed(cog, interaction)
    assert "You're carrying" in _reply(interaction)


async def test_delete_flow(cog):
    await _create(cog, crew=(2,))
    await handlers.handle_sell(cog, _interaction(user_id=1), 1, "Gold", scu=1, total=200)
    blocked = _interaction(admin=True)
    await handlers.handle_delete(cog, blocked, "1")
    assert "still has 100 aUEC owed" in _reply(blocked)
    await handlers.handle_mark_paid(cog, _interaction(user_id=1), 1, None)
    asked = _interaction(admin=True)
    await handlers.handle_delete(cog, asked, "#1")
    assert "Delete manifest #1?" in _reply(asked)
    confirm = _interaction(admin=True)
    await handlers.confirm_delete(cog, confirm, 7, 1)
    assert await _get(cog) is None
    assert await store.get_by_thread(cog.bot.state, 900) is None
    handlers.card.close_thread.assert_awaited_once()
    assert confirm.edit_original_response.await_args.kwargs["content"] == "Deleted manifest #1."


async def test_delete_unknown(cog):
    interaction = _interaction(admin=True)
    await handlers.handle_delete(cog, interaction, "abc")
    assert _reply(interaction) == "Manifest abc not found."


async def test_manifest_for_thread(cog):
    await _create(cog)
    assert (await handlers.manifest_for_thread(cog, _interaction(channel_id=900)))["id"] == 1
    stray = _interaction(channel_id=123)
    assert await handlers.manifest_for_thread(cog, stray) is None
    assert stray.response.send_message.await_args.args[0] == "This manifest is no longer tracked."


async def test_config_channel_warns_about_missing_permissions(cog, monkeypatch):
    monkeypatch.setattr(handlers.card, "missing_permissions", MagicMock(return_value=["Manage Threads"]))
    channel = MagicMock()
    channel.id = 40
    channel.mention = "<#40>"
    interaction = _interaction(admin=True)
    await handlers.handle_config_channel(cog, interaction, channel)
    assert await store.get_config(cog.bot.state, 7) == {"channel_id": 40}
    message = interaction.response.send_message.await_args.args[0]
    assert "<#40>" in message
    assert "Manage Threads" in message


async def test_beacon_button_links_existing_manifest(cog):
    await beacon_store.save_beacon(
        cog.bot.state,
        50,
        {"guild_id": 7, "requester_id": 7, "members": [8], "category": "piracy", "status": "closed"},
    )
    await _create(cog, beacon=50)
    interaction = _interaction(channel_id=50)
    await handlers.handle_beacon_button(cog, interaction)
    assert interaction.response.send_message.await_args.args[0] == "This beacon already has manifest #1: <#900>"


async def test_beacon_button_outside_beacon(cog):
    interaction = _interaction(channel_id=77)
    await handlers.handle_beacon_button(cog, interaction)
    assert "beacon thread" in interaction.response.send_message.await_args.args[0]
