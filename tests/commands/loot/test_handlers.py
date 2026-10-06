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
        cog,
        _interaction(user_id=user_id),
        title="Gold grab",
        commodity="Gold",
        scu=scu,
        participants=participants,
        holder_id=None,
    )
    return (await store.guild_records(cog.bot.state, 1))[-1]


def test_parse_raid_id():
    assert handlers.parse_raid_id("12") == 12
    assert handlers.parse_raid_id("#12") == 12
    assert handlers.parse_raid_id("Gold grab") is None
    assert handlers.parse_raid_id("\u00b2") is None
    assert handlers.parse_raid_id("#\u0663") == 3


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
    await handlers.handle_new(cog, _interaction(), title="x", commodity="Gold", scu=5, participants=None, holder_id=77)
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
async def test_two_holders_logging_gold_on_one_beacon_get_their_own_lines(cog):
    await beacon_store.save_beacon(cog.bot.state, 99, _beacon())
    await handlers.handle_log(cog, _interaction(user_id=8), commodity="Gold", scu=50, holder_id=8, raid=None)
    await handlers.handle_log(cog, _interaction(user_id=9), commodity="Gold", scu=30, holder_id=9, raid=None)
    await handlers.handle_log(cog, _interaction(user_id=8), commodity="gold", scu=5, holder_id=8, raid=None)
    record = (await store.guild_records(cog.bot.state, 1))[0]
    assert [(line["commodity"], line["scu"], line["holder_id"]) for line in record["cargo"]] == [
        ("Gold", 55, 8),
        ("Gold", 30, 9),
    ]


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
    ledger.record_sale(settled, ledger.find_line(settled, "Gold"), scu=96, total=30, now=1.0)
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


@pytest.mark.asyncio
async def test_new_raid_is_saved_and_carded_under_its_lock(cog, monkeypatch):
    held = []

    async def refresh(cog_, guild, record):
        held.append(handlers._record_lock(1, record["id"]).locked())
        return None

    monkeypatch.setattr(handlers.card, "refresh_card", refresh)
    await _new_raid(cog)
    assert held == [True]


@pytest.mark.asyncio
async def test_new_beacon_raid_is_saved_and_carded_under_its_lock(cog, monkeypatch):
    held = []

    async def refresh(cog_, guild, record):
        held.append(handlers._record_lock(1, record["id"]).locked())
        return None

    monkeypatch.setattr(handlers.card, "refresh_card", refresh)
    await beacon_store.save_beacon(cog.bot.state, 99, _beacon())
    await handlers.handle_log(cog, _interaction(user_id=8), commodity="Gold", scu=5, holder_id=8, raid=None)
    assert held == [True]


@pytest.mark.asyncio
async def test_concurrent_new_raids_get_distinct_ids(cog):
    await asyncio.gather(
        handlers.handle_new(
            cog, _interaction(user_id=1), title="a", commodity="Gold", scu=1, participants=None, holder_id=None
        ),
        handlers.handle_new(
            cog, _interaction(user_id=2), title="b", commodity="Gold", scu=1, participants=None, holder_id=None
        ),
    )
    records = await store.guild_records(cog.bot.state, 1)
    assert sorted(r["id"] for r in records) == [1, 2]


@pytest.mark.asyncio
async def test_first_save_of_new_raids_happens_under_the_record_lock(cog, monkeypatch):
    held = []
    real_save = store.save_record

    async def save(state, record):
        held.append(handlers._record_lock(1, record["id"]).locked())
        await real_save(state, record)

    monkeypatch.setattr(handlers.store, "save_record", save)
    await _new_raid(cog)
    await beacon_store.save_beacon(cog.bot.state, 99, _beacon())
    await handlers.handle_log(cog, _interaction(user_id=8), commodity="Gold", scu=5, holder_id=8, raid=None)
    assert held == [True, True]


async def _sold_raid(cog, total=300):
    await _new_raid(cog, user_id=42, participants="<@43> <@44>")
    await handlers.handle_sell(cog, _interaction(user_id=42), raid="1", commodity="Gold", scu=40, total=total)
    return await store.get_record(cog.bot.state, 1, 1)


@pytest.mark.asyncio
async def test_sell_splits_and_announces(cog):
    record = await _sold_raid(cog, total=301)
    sale = record["sales"][0]
    assert sale["share"] == 100
    assert sale["seller_id"] == 42
    text = handlers.card.announce.await_args.args[2]
    assert "<@42> sold 40 SCU Gold for 301 aUEC, 100 each" in text
    assert "<@43>" in text and "<@44>" in text


@pytest.mark.asyncio
async def test_only_holder_or_admin_can_sell(cog):
    await _new_raid(cog)
    interaction = _interaction(user_id=43)
    await handlers.handle_sell(cog, interaction, raid="1", commodity="Gold", scu=10, total=100)
    assert "holder" in _reply(interaction)
    assert (await store.get_record(cog.bot.state, 1, 1))["sales"] == []


@pytest.mark.asyncio
async def test_admin_sale_is_paid_by_the_holder(cog):
    await _new_raid(cog)
    await handlers.handle_sell(cog, _interaction(user_id=500, admin=True), raid="1", commodity="Gold", scu=10, total=90)
    sale = (await store.get_record(cog.bot.state, 1, 1))["sales"][0]
    assert sale["seller_id"] == 42


async def _split_gold_raid(cog):
    await _new_raid(cog, scu=50)
    await handlers.handle_log(cog, _interaction(channel_id=12345), commodity="Gold", scu=30, holder_id=43, raid="1")
    return await store.get_record(cog.bot.state, 1, 1)


@pytest.mark.asyncio
async def test_second_holder_sells_their_own_gold(cog):
    await _split_gold_raid(cog)
    await handlers.handle_sell(cog, _interaction(user_id=43), raid="1", commodity="Gold", scu=10, total=300)
    record = await store.get_record(cog.bot.state, 1, 1)
    assert record["sales"][0]["seller_id"] == 43
    assert [line["sold_scu"] for line in record["cargo"]] == [0, 10]


@pytest.mark.asyncio
async def test_admin_sale_with_split_gold_names_the_holders(cog):
    await _split_gold_raid(cog)
    interaction = _interaction(user_id=500, admin=True)
    await handlers.handle_sell(cog, interaction, raid="1", commodity="Gold", scu=10, total=300)
    assert _reply(interaction) == "Raid #1 has Gold held by <@42> and <@43>. Ask the holder to run this."
    assert (await store.get_record(cog.bot.state, 1, 1))["sales"] == []


@pytest.mark.asyncio
async def test_non_holder_with_split_gold_is_told_to_ask_a_holder(cog):
    await _split_gold_raid(cog)
    interaction = _interaction(user_id=44)
    await handlers.handle_sell(cog, interaction, raid="1", commodity="Gold", scu=10, total=300)
    assert "Ask the holder" in _reply(interaction)


@pytest.mark.asyncio
async def test_undo_restores_the_right_line_when_gold_is_split(cog):
    await _split_gold_raid(cog)
    await handlers.handle_sell(cog, _interaction(user_id=42), raid="1", commodity="Gold", scu=10, total=300)
    await handlers.handle_sell(cog, _interaction(user_id=43), raid="1", commodity="Gold", scu=20, total=300)
    await handlers.handle_undo(cog, _interaction(user_id=43), raid="1")
    record = await store.get_record(cog.bot.state, 1, 1)
    assert [line["sold_scu"] for line in record["cargo"]] == [10, 0]


@pytest.mark.asyncio
async def test_holder_handover_merges_with_the_new_holders_line(cog):
    await _split_gold_raid(cog)
    await handlers.handle_holder(cog, _interaction(user_id=42), raid="1", commodity="Gold", member_id=43)
    record = await store.get_record(cog.bot.state, 1, 1)
    assert [(line["scu"], line["holder_id"]) for line in record["cargo"]] == [(80, 43)]


@pytest.mark.asyncio
async def test_cargo_fix_changes_only_the_callers_line(cog):
    await _split_gold_raid(cog)
    await handlers.handle_cargo_fix(cog, _interaction(user_id=43), raid="1", commodity="Gold", scu=25)
    record = await store.get_record(cog.bot.state, 1, 1)
    assert [(line["scu"], line["holder_id"]) for line in record["cargo"]] == [(50, 42), (25, 43)]


@pytest.mark.asyncio
async def test_oversell_is_rejected(cog):
    await _new_raid(cog, scu=10)
    interaction = _interaction()
    await handlers.handle_sell(cog, interaction, raid="1", commodity="Gold", scu=11, total=100)
    assert "Only 10 SCU" in _reply(interaction)


@pytest.mark.asyncio
async def test_paid_by_seller(cog):
    await _sold_raid(cog)
    interaction = _interaction(user_id=42)
    await handlers.handle_paid(cog, interaction, raid="1", member_id=43)
    assert "1 payout" in _reply(interaction)
    await handlers.handle_paid(cog, _interaction(user_id=42), raid="1", member_id=None)
    assert ledger.status(await store.get_record(cog.bot.state, 1, 1)) == ledger.STATUS_HOLDING


@pytest.mark.asyncio
async def test_non_seller_cannot_mark_paid(cog):
    await _sold_raid(cog)
    interaction = _interaction(user_id=43)
    await handlers.handle_paid(cog, interaction, raid="1", member_id=44)
    assert "Nothing left" in _reply(interaction)


@pytest.mark.asyncio
async def test_dispute_pings_payer(cog):
    await _sold_raid(cog)
    await handlers.handle_paid(cog, _interaction(user_id=42), raid="1", member_id=43)
    interaction = _interaction(user_id=43)
    await handlers.handle_dispute(cog, interaction, raid="1")
    text = handlers.card.announce.await_args.args[2]
    assert "<@43>" in text and "<@42>" in text


@pytest.mark.asyncio
async def test_undo_and_holder_and_fix(cog):
    await _sold_raid(cog)
    await handlers.handle_undo(cog, _interaction(user_id=42), raid="1")
    record = await store.get_record(cog.bot.state, 1, 1)
    assert record["sales"] == []
    await handlers.handle_holder(cog, _interaction(user_id=42), raid="1", commodity="Gold", member_id=43)
    await handlers.handle_cargo_fix(cog, _interaction(user_id=43), raid="1", commodity="Gold", scu=80)
    line = (await store.get_record(cog.bot.state, 1, 1))["cargo"][0]
    assert (line["holder_id"], line["scu"]) == (43, 80)


@pytest.mark.asyncio
async def test_holder_change_needs_current_holder(cog):
    await _new_raid(cog)
    interaction = _interaction(user_id=43)
    await handlers.handle_holder(cog, interaction, raid="1", commodity="Gold", member_id=43)
    assert "holder" in _reply(interaction)


@pytest.mark.asyncio
async def test_participants_add_remove_permissions(cog):
    await _new_raid(cog)
    await handlers.handle_participants(cog, _interaction(user_id=42), raid="1", action="add", member_id=50)
    await handlers.handle_participants(cog, _interaction(user_id=42), raid="1", action="remove", member_id=43)
    assert (await store.get_record(cog.bot.state, 1, 1))["participants"] == [42, 44, 50]
    outsider = _interaction(user_id=60)
    await handlers.handle_participants(cog, outsider, raid="1", action="add", member_id=60)
    assert "organizers" in _reply(outsider)


@pytest.mark.asyncio
async def test_card_join_and_leave(cog):
    record = await _new_raid(cog)
    record["card"] = {"channel_id": 20, "message_id": 555}
    await store.save_record(cog.bot.state, record)
    joiner = _interaction(user_id=70)
    await handlers.handle_card_join(cog, joiner)
    assert 70 in (await store.get_record(cog.bot.state, 1, 1))["participants"]
    leaver = _interaction(user_id=70)
    await handlers.handle_card_leave(cog, leaver)
    assert 70 not in (await store.get_record(cog.bot.state, 1, 1))["participants"]


@pytest.mark.asyncio
async def test_card_join_on_untracked_message(cog):
    interaction = _interaction()
    interaction.message.id = 999
    await handlers.handle_card_join(cog, interaction)
    assert "no longer tracked" in interaction.response.send_message.await_args.args[0]


@pytest.mark.asyncio
async def test_owed_is_ephemeral_summary(cog):
    await _sold_raid(cog)
    interaction = _interaction(user_id=43)
    await handlers.handle_owed(cog, interaction)
    assert "Owed to you" in _reply(interaction)
    assert interaction.followup.send.await_args.kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_list_shows_unsettled_with_estimates(cog, monkeypatch):
    await _new_raid(cog)
    monkeypatch.setattr(handlers.card, "estimate_prices", AsyncMock(return_value={"Gold": 10.0}))
    interaction = _interaction()
    await handlers.handle_list(cog, interaction)
    text = interaction.followup.send.await_args.args[0]
    assert "#1 Gold grab" in text
    assert "est. 960 aUEC" in text


@pytest.mark.asyncio
async def test_delete_blocked_while_owed(cog):
    await _sold_raid(cog)
    interaction = _interaction(admin=True)
    await handlers.handle_delete(cog, interaction, raid="1")
    assert "aUEC owed" in _reply(interaction)
    assert await store.get_record(cog.bot.state, 1, 1) is not None


@pytest.mark.asyncio
async def test_delete_asks_for_confirmation_then_deletes(cog):
    await _new_raid(cog)
    interaction = _interaction(admin=True)
    await handlers.handle_delete(cog, interaction, raid="1")
    assert interaction.followup.send.await_args.kwargs["view"] is not None
    confirm = _interaction(admin=True)
    confirm.edit_original_response = AsyncMock()
    await handlers.confirm_delete(cog, confirm, 1, 1)
    assert await store.get_record(cog.bot.state, 1, 1) is None
    assert "Deleted raid #1" in confirm.edit_original_response.await_args.kwargs["content"]
    assert confirm.edit_original_response.await_args.kwargs["view"] is None


@pytest.mark.asyncio
async def test_confirm_delete_defers_before_doing_any_work(cog, monkeypatch):
    await _new_raid(cog)
    confirm = _interaction(admin=True)
    confirm.edit_original_response = AsyncMock()
    order = []
    confirm.response.defer = AsyncMock(side_effect=lambda *a, **k: order.append("defer"))
    real_delete = store.delete_record

    async def delete(state, record):
        order.append("delete")
        await real_delete(state, record)

    monkeypatch.setattr(handlers.store, "delete_record", delete)
    await handlers.confirm_delete(cog, confirm, 1, 1)
    assert order == ["defer", "delete"]


@pytest.mark.asyncio
async def test_confirm_delete_reports_a_missing_raid(cog):
    confirm = _interaction(admin=True)
    confirm.edit_original_response = AsyncMock()
    await handlers.confirm_delete(cog, confirm, 1, 404)
    assert "already gone" in confirm.edit_original_response.await_args.kwargs["content"]


@pytest.mark.asyncio
async def test_confirm_delete_refuses_when_payouts_are_owed_again(cog):
    await _sold_raid(cog)
    confirm = _interaction(admin=True)
    confirm.edit_original_response = AsyncMock()
    await handlers.confirm_delete(cog, confirm, 1, 1)
    assert "owed again" in confirm.edit_original_response.await_args.kwargs["content"]
    assert await store.get_record(cog.bot.state, 1, 1) is not None
