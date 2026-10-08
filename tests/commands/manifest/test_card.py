from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from src.commands.manifest import card, ledger, store


def _record(manifest_id=12, crew=(2, 3), carrier=1, created_by=1, cargo=None, costs=None):
    return ledger.new_manifest(
        manifest_id=manifest_id,
        guild_id=7,
        created_by=created_by,
        carrier_id=carrier,
        crew_ids=crew,
        cargo=cargo or [{"commodity": "Gold", "scu": 96, "est_price": 6500.0}],
        costs=costs or [],
        now=0.0,
    )


def _field(embed, prefix):
    return next(f for f in embed.fields if f.name.startswith(prefix))


def test_open_card_basics():
    embed = card.build_card_embed(_record())
    assert embed.title == "Manifest #12"
    assert embed.color == discord.Color.gold()
    assert embed.description == "Open · carrier <@1>"
    assert _field(embed, "Cargo").value == "**Gold**: 0/96 SCU sold · est. 6,500/SCU · 624,000 aUEC unsold"
    assert _field(embed, "Costs").value == "No costs"
    assert _field(embed, "Totals").value == "Value 624,000 · Costs 0 · Profit 624,000 aUEC"


def test_card_without_estimate():
    embed = card.build_card_embed(_record(cargo=[{"commodity": "Tin", "scu": 5, "est_price": None}]))
    assert _field(embed, "Cargo").value == "**Tin**: 0/5 SCU sold · no estimate"


def test_partial_card_with_costs_beacon_and_outstanding():
    record = _record(costs=[{"label": "Fuel", "amount": 20_000}])
    record["beacon_thread_id"] = 555
    ledger.record_sale(record, "Gold", scu=40, total=260_000, now=10.0)
    embed = card.build_card_embed(record)
    assert embed.color == discord.Color.orange()
    assert embed.description == "Partial · carrier <@1> · from beacon <#555> · 2 payouts outstanding"
    assert _field(embed, "Cargo").value == (
        "**Gold**: 40/96 SCU sold · 260,000 aUEC received · est. 6,500/SCU · 364,000 aUEC unsold"
    )
    assert _field(embed, "Costs").value == "Fuel: 20,000\nTotal 20,000 · 20,000 recovered"
    sale = _field(embed, "Sale 1")
    assert sale.name == "Sale 1: 40 SCU Gold for 260,000 aUEC"
    assert "Sold by <@1> <t:10:R> · 20,000 to costs" in sale.value
    assert "⏳ <@2> 80,000" in sale.value
    assert "✅ <@1> 80,000" in sale.value


def test_crew_and_shares_field():
    record = _record(crew=(2, 3))
    ledger.set_weight(record, 2, 2)
    ledger.record_sale(record, "Gold", scu=96, total=400_000, now=1.0)
    ledger.mark_paid(record, member_id=3, seller_id=1, now=2.0)
    ledger.dispute(record, user_id=3, now=3.0)
    embed = card.build_card_embed(record)
    assert embed.color == discord.Color.green()
    shares = _field(embed, "Crew & shares (3)").value.splitlines()
    assert shares == [
        "<@1> ×1 · 100,000 earned",
        "<@2> ×2 · 200,000 earned · ⏳ 200,000 owed",
        "<@3> ×1 · 100,000 earned · ⚠️ 100,000 disputed",
    ]


def test_crew_shares_show_estimate_and_former_crew():
    record = _record(crew=(2, 3))
    ledger.record_sale(record, "Gold", scu=6, total=3000, now=1.0)
    ledger.set_crew(record, [2])
    lines = _field(embed := card.build_card_embed(record), "Crew & shares").value.splitlines()
    assert lines[1] == f"<@2> ×1 · {1000 + 585_000 // 2:,} est. · 1,000 earned · ⏳ 1,000 owed"
    assert lines[2] == "<@3> left · 1,000 earned · ⏳ 1,000 owed"
    assert embed is not None


def test_long_history_drops_oldest_sales():
    record = _record(crew=range(2, 26), cargo=[{"commodity": "Gold", "scu": 1000, "est_price": None}])
    for _ in range(20):
        ledger.record_sale(record, "Gold", scu=1, total=1_000_000, now=1.0)
    embed = card.build_card_embed(record)
    assert len(embed) <= 6000
    assert "older sales not shown" in embed.footer.text
    assert all(len(field.value) <= 1024 for field in embed.fields)


def test_thread_name_truncates():
    names = [{"commodity": f"Commodity number {i}", "scu": 1, "est_price": None} for i in range(10)]
    name = card.thread_name(_record(cargo=names))
    assert name.startswith("Manifest #12: Commodity number 0, ")
    assert len(name) <= 100


def test_build_list_filters_and_totals():
    mine = _record(manifest_id=1, crew=(2,), costs=[{"label": "Fuel", "amount": 24_000}])
    mine["thread_id"] = 900
    settled = _record(manifest_id=2, crew=(2,), cargo=[{"commodity": "Tin", "scu": 1, "est_price": None}])
    ledger.record_sale(settled, "Tin", scu=1, total=1000, now=1.0)
    ledger.mark_paid(settled, member_id=None, seller_id=None, now=2.0)
    hidden = _record(manifest_id=3, crew=(5,), created_by=5, carrier=5)
    text = card.build_list([mine, settled, hidden], user_id=2, is_admin=False)
    lines = text.splitlines()
    assert lines[0] == "Open cargo value 624,000 · Overall profit 601,000 aUEC"
    assert lines[1] == "**#1** Open · carrier <@1> · Gold · profit 600,000 · <#900>"
    assert lines[-1] == "1 settled not shown"
    assert "#3" not in text
    assert "#3" in card.build_list([mine, settled, hidden], user_id=2, is_admin=True)


def test_build_list_shows_owed():
    record = _record(manifest_id=1, crew=(2,))
    ledger.record_sale(record, "Gold", scu=96, total=1000, now=1.0)
    assert "**#1** Sold · carrier <@1> · Gold · profit 1,000 · 500 aUEC owed" in card.build_list(
        [record], user_id=1, is_admin=False
    )


def test_build_list_empty():
    assert "/manifest new" in card.build_list([], user_id=1, is_admin=False)


def test_build_owed_sections():
    record = _record(crew=(2,))
    ledger.record_sale(record, "Gold", scu=10, total=1000, now=1.0)
    carrier = card.build_owed([record], 1)
    assert "**You owe**\nManifest #12: 500 aUEC to <@2> (sale 1)" in carrier
    assert "**You're carrying**\nManifest #12: 86 SCU Gold" in carrier
    assert "**Owed to you**\nManifest #12: 500 aUEC from <@1> (sale 1)" in card.build_owed([record], 2)
    assert "all square" in card.build_owed([record], 9)


def test_missing_permissions():
    channel = MagicMock()
    channel.permissions_for.return_value = discord.Permissions(create_private_threads=True)
    assert card.missing_permissions(channel, MagicMock()) == ["Send Messages in Threads", "Manage Threads"]


@pytest.fixture
async def state(tmp_path):
    from src.storage import Database, StateStore

    db = Database(str(tmp_path / "card.db"))
    await db.connect()
    yield StateStore(db)
    await db.close()


def _cog(state):
    cog = MagicMock()
    cog.bot.state = state
    return cog


def _guild(channel=None, thread=None):
    guild = MagicMock()
    guild.id = 7
    guild.get_channel.return_value = channel
    guild.get_thread.return_value = thread
    guild.fetch_channel = AsyncMock(side_effect=discord.NotFound(MagicMock(status=404), "gone"))
    return guild


async def test_open_thread_creates_private_thread_and_posts_card(state):
    await store.set_config(state, 7, {"channel_id": 40})
    thread = MagicMock()
    thread.id = 900
    thread.add_user = AsyncMock()
    thread.send = AsyncMock(return_value=MagicMock(id=901))
    channel = MagicMock()
    channel.create_thread = AsyncMock(return_value=thread)
    cog = _cog(state)
    record = _record(crew=(2,))
    await store.save_record(state, record)
    assert await card.open_thread(cog, _guild(channel=channel), record) is thread
    kwargs = channel.create_thread.await_args.kwargs
    assert kwargs["type"] == discord.ChannelType.private_thread
    assert kwargs["invitable"] is False
    assert kwargs["name"] == "Manifest #12: Gold"
    assert [call.args[0].id for call in thread.add_user.await_args_list] == [1, 2]
    assert thread.send.await_args.kwargs["view"] is cog.card_view
    saved = await store.get_record(state, 7, 12)
    assert (saved["thread_id"], saved["card_message_id"]) == (900, 901)
    assert await store.get_by_thread(state, 900) == 12


async def test_open_thread_without_channel_returns_none(state):
    assert await card.open_thread(_cog(state), _guild(), _record()) is None


async def test_refresh_card_unarchives_and_reposts_when_message_gone(state):
    record = _record()
    record["thread_id"] = 900
    record["card_message_id"] = 901
    thread = MagicMock()
    thread.archived = True
    thread.edit = AsyncMock()
    partial = MagicMock()
    partial.edit = AsyncMock(side_effect=discord.NotFound(MagicMock(status=404), "gone"))
    thread.get_partial_message.return_value = partial
    thread.send = AsyncMock(return_value=MagicMock(id=950))
    await card.refresh_card(_cog(state), _guild(thread=thread), record)
    thread.edit.assert_awaited_once_with(archived=False)
    assert record["card_message_id"] == 950
    assert (await store.get_record(state, 7, 12))["card_message_id"] == 950


async def test_refresh_card_without_thread_is_noop(state):
    assert await card.refresh_card(_cog(state), _guild(), _record()) is None
