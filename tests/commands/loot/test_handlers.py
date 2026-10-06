import asyncio
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from src.commands.beacons import store as beacon_store
from src.commands.loot import handlers, ledger, store
from src.storage import Database, StateStore


@pytest.fixture
async def state(tmp_path):
    db = Database(str(tmp_path / "loot.db"))
    await db.connect()
    yield StateStore(db)
    await db.close()


@pytest.fixture
def cog(state, monkeypatch):
    cog = MagicMock()
    cog.bot.state = state
    monkeypatch.setattr(handlers.card, "refresh_card", AsyncMock(return_value=None))
    monkeypatch.setattr(handlers.card, "announce", AsyncMock())
    return cog


def _interaction(user_id=42, admin=False, channel_id=99, guild_id=1):
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
    interaction.followup.send = AsyncMock()
    interaction.message.id = 555
    return interaction


def _reply(interaction):
    return interaction.followup.send.await_args.args[0]


def _beacon(requester=7, members=(8, 9), category="piracy"):
    return {
        "guild_id": 1,
        "category": category,
        "requester_id": requester,
        "members": list(members),
        "status": "closed",
        "opened_at": 0.0,
        "closed_at": 1.0,
        "closed_by_id": requester,
        "fields": {"location": "Pyro:Ruin Station", "target": "Caterpillar"},
    }


async def _new_raid(cog, user_id=42, participants="<@43> <@44>", scu=96):
    await handlers.handle_new(
        cog, _interaction(user_id=user_id), title="Gold grab", commodity="Gold", scu=scu,
        participants=participants, holder_id=None,
    )
    return (await store.guild_records(cog.bot.state, 1))[-1]


def test_parse_raid_id():
    assert handlers.parse_raid_id("12") == 12
    assert handlers.parse_raid_id("#12") == 12
    assert handlers.parse_raid_id("Gold grab") is None


@pytest.mark.asyncio
async def test_new_creates_raid_with_creator_and_mentions(cog):
    record = await _new_raid(cog)
    assert record["id"] == 1
    assert record["participants"] == [42, 43, 44]
    assert record["organizer_ids"] == [42]
    assert record["cargo"][0] == {"commodity": "Gold", "scu": 96, "sold_scu": 0, "holder_id": 42}
    handlers.card.refresh_card.assert_awaited()


@pytest.mark.asyncio
async def test_new_reply_mentions_missing_loot_channel(cog):
    interaction = _interaction()
    await handlers.handle_new(
        cog, interaction, title="Gold grab", commodity="Gold", scu=5, participants=None, holder_id=None
    )
    assert "#1" in _reply(interaction)
    assert "/loot config channel" in _reply(interaction)


@pytest.mark.asyncio
async def test_new_rejects_participants_without_mentions(cog):
    interaction = _interaction()
    await handlers.handle_new(
        cog, interaction, title="Gold grab", commodity="Gold", scu=5, participants="bob alice", holder_id=None
    )
    assert "@mention" in _reply(interaction)
    assert await store.guild_records(cog.bot.state, 1) == []


@pytest.mark.asyncio
async def test_new_with_bad_scu_allocates_no_id(cog):
    interaction = _interaction()
    await handlers.handle_new(cog, interaction, title="x", commodity="Gold", scu=0, participants=None, holder_id=None)
    assert "SCU" in _reply(interaction)
    assert await store.allocate_id(cog.bot.state, 1) == 1


@pytest.mark.asyncio
async def test_new_with_explicit_holder(cog):
    await handlers.handle_new(
        cog, _interaction(), title="x", commodity="Gold", scu=5, participants=None, holder_id=77
    )
    record = (await store.guild_records(cog.bot.state, 1))[0]
    assert record["cargo"][0]["holder_id"] == 77


@pytest.mark.asyncio
async def test_log_in_beacon_thread_snapshots_roster(cog):
    await beacon_store.save_beacon(cog.bot.state, 99, _beacon())
    interaction = _interaction(user_id=8)
    await handlers.handle_log(cog, interaction, commodity="Gold", scu=96, holder_id=8, raid=None)
    record = (await store.guild_records(cog.bot.state, 1))[0]
    assert record["beacon_thread_id"] == 99
    assert record["category"] == "piracy"
    assert record["title"] == "Piracy Caterpillar @ Ruin Station"
    assert record["participants"] == [7, 8, 9]
    assert record["organizer_ids"] == [8, 7]
    assert await store.get_by_beacon(cog.bot.state, 99) == record["id"]


@pytest.mark.asyncio
async def test_second_log_on_same_beacon_adds_cargo(cog):
    await beacon_store.save_beacon(cog.bot.state, 99, _beacon())
    await handlers.handle_log(cog, _interaction(user_id=8), commodity="Gold", scu=50, holder_id=8, raid=None)
    await handlers.handle_log(cog, _interaction(user_id=9), commodity="Silver", scu=10, holder_id=9, raid=None)
    records = await store.guild_records(cog.bot.state, 1)
    assert len(records) == 1
    assert [line["commodity"] for line in records[0]["cargo"]] == ["Gold", "Silver"]


@pytest.mark.asyncio
async def test_concurrent_logs_on_same_beacon_make_one_raid(cog):
    await beacon_store.save_beacon(cog.bot.state, 99, _beacon())
    await asyncio.gather(
        handlers.handle_log(cog, _interaction(user_id=8), commodity="Gold", scu=50, holder_id=8, raid=None),
        handlers.handle_log(cog, _interaction(user_id=9), commodity="Silver", scu=10, holder_id=9, raid=None),
    )
    records = await store.guild_records(cog.bot.state, 1)
    assert len(records) == 1
    assert {line["commodity"] for line in records[0]["cargo"]} == {"Gold", "Silver"}


@pytest.mark.asyncio
async def test_log_survives_locked_thread(cog, monkeypatch):
    await beacon_store.save_beacon(cog.bot.state, 99, _beacon())
    posted = MagicMock()
    posted.jump_url = "https://discord.com/channels/1/2/3"
    monkeypatch.setattr(handlers.card, "refresh_card", AsyncMock(return_value=posted))
    interaction = _interaction(user_id=8)
    interaction.channel.send = AsyncMock(side_effect=discord.Forbidden(MagicMock(status=403), "locked"))
    await handlers.handle_log(cog, interaction, commodity="Gold", scu=5, holder_id=8, raid=None)
    assert "#1" in _reply(interaction)
    assert len(await store.guild_records(cog.bot.state, 1)) == 1


@pytest.mark.asyncio
async def test_log_outside_beacon_without_raid_explains_options(cog):
    interaction = _interaction(channel_id=12345)
    await handlers.handle_log(cog, interaction, commodity="Gold", scu=5, holder_id=42, raid=None)
    assert "/loot new" in _reply(interaction)


@pytest.mark.asyncio
async def test_log_with_raid_adds_to_existing(cog):
    await _new_raid(cog)
    interaction = _interaction(channel_id=12345)
    await handlers.handle_log(cog, interaction, commodity="Silver", scu=3, holder_id=42, raid="1")
    record = await store.get_record(cog.bot.state, 1, 1)
    assert ledger.find_line(record, "Silver")["scu"] == 3


@pytest.mark.asyncio
async def test_unknown_raid_is_reported(cog):
    interaction = _interaction()
    await handlers.handle_log(cog, interaction, commodity="Gold", scu=3, holder_id=42, raid="404")
    assert "#404 not found" in _reply(interaction)


@pytest.mark.asyncio
async def test_config_channel(cog):
    interaction = _interaction()
    channel = MagicMock()
    channel.id = 321
    channel.mention = "<#321>"
    await handlers.handle_config_channel(cog, interaction, channel)
    assert await store.get_config(cog.bot.state, 1) == {"channel_id": 321}
    assert "<#321>" in interaction.response.send_message.await_args.args[0]


@pytest.mark.asyncio
async def test_raid_autocomplete_lists_open_raids_first(cog):
    await _new_raid(cog)
    settled = await _new_raid(cog)
    ledger.record_sale(settled, commodity="Gold", scu=96, total=30, now=1.0)
    ledger.mark_paid(settled, member_id=None, seller_id=None, now=2.0)
    await store.save_record(cog.bot.state, settled)
    choices = await handlers.raid_autocomplete(cog, _interaction(), "")
    assert [c.value for c in choices] == ["1", "2"]
    assert choices[0].name == "#1 Gold grab"
    assert await handlers.raid_autocomplete(cog, _interaction(), "nothing") == []


@pytest.mark.asyncio
async def test_cargo_autocomplete_reads_selected_raid(cog):
    await _new_raid(cog)
    interaction = _interaction()
    interaction.namespace.raid = "1"
    choices = await handlers.cargo_autocomplete(cog, interaction, "go")
    assert [c.value for c in choices] == ["Gold"]
    interaction.namespace.raid = None
    assert await handlers.cargo_autocomplete(cog, interaction, "") == []
