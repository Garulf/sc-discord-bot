from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from src.commands.loot import card, ledger


def _record(participants=(1, 2)):
    record = ledger.new_record(
        loot_id=12,
        guild_id=7,
        title="Ruin gold grab",
        created_by=1,
        participants=list(participants),
        organizer_ids=[1],
        now=0.0,
    )
    ledger.add_cargo(record, "Gold", 96, holder_id=1)
    return record


def _field(embed, prefix):
    return next(f for f in embed.fields if f.name.startswith(prefix))


def test_card_shows_crew_cargo_and_estimate():
    embed = card.build_card_embed(_record(), {"Gold": 1000.0})
    assert embed.title == "#12 Ruin gold grab"
    assert embed.color == discord.Color.gold()
    assert "<@1>, <@2>" in _field(embed, "Crew (2)").value
    cargo = _field(embed, "Cargo").value
    assert "96/96 SCU left" in cargo
    assert "held by <@1>" in cargo
    assert "est. 96,000 aUEC" in cargo


def test_card_shows_sale_payout_states_and_beacon_link():
    record = _record(participants=(1, 2, 3))
    record["beacon_thread_id"] = 555
    ledger.record_sale(record, commodity="Gold", scu=96, total=300, now=50.0)
    ledger.mark_paid(record, member_id=2, seller_id=1, now=51.0)
    ledger.dispute(record, user_id=2, now=52.0)
    embed = card.build_card_embed(record, {})
    assert "<#555>" in embed.description
    assert embed.color == discord.Color.orange()
    sale = _field(embed, "Sale 1").value
    assert "✅ <@1> 100" in sale
    assert "⚠️ <@2> 100" in sale
    assert "⏳ <@3> 100" in sale


def test_settled_card_is_green():
    record = _record()
    ledger.record_sale(record, commodity="Gold", scu=96, total=200, now=1.0)
    ledger.mark_paid(record, member_id=None, seller_id=None, now=2.0)
    embed = card.build_card_embed(record, {})
    assert embed.color == discord.Color.green()
    assert embed.description.startswith("Settled")


def test_card_caps_sales_shown():
    record = _record()
    for _ in range(card.MAX_SALES_SHOWN + 2):
        ledger.record_sale(record, commodity="Gold", scu=1, total=10, now=1.0)
    embed = card.build_card_embed(record, {})
    assert sum(f.name.startswith("Sale") for f in embed.fields) == card.MAX_SALES_SHOWN
    assert "2 older" in embed.footer.text


def test_card_drops_oldest_sales_to_stay_under_embed_limit():
    record = _record(participants=range(10**17, 10**17 + 40))
    for _ in range(card.MAX_SALES_SHOWN):
        ledger.record_sale(record, commodity="Gold", scu=1, total=4000, now=1.0)
    embed = card.build_card_embed(record, {})
    assert len(embed) <= 6000
    sale_names = [f.name for f in embed.fields if f.name.startswith("Sale")]
    assert sale_names[-1].startswith(f"Sale {card.MAX_SALES_SHOWN}:")
    assert len(sale_names) < card.MAX_SALES_SHOWN
    hidden = card.MAX_SALES_SHOWN - len(sale_names)
    assert f"{hidden} older" in embed.footer.text


def test_owed_summary_sections():
    record = _record(participants=(1, 2))
    ledger.record_sale(record, commodity="Gold", scu=40, total=200, now=1.0)
    text_for_2 = card.build_owed_summary([record], 2)
    assert "Owed to you" in text_for_2
    assert "100 aUEC from <@1>" in text_for_2
    text_for_1 = card.build_owed_summary([record], 1)
    assert "You owe" in text_for_1
    assert "100 aUEC to <@2>" in text_for_1
    assert "56 SCU Gold" in text_for_1
    assert "all square" in card.build_owed_summary([record], 99)


def test_raid_list_hides_settled():
    open_raid = _record()
    settled = _record()
    settled["id"] = 13
    ledger.record_sale(settled, commodity="Gold", scu=96, total=10, now=1.0)
    ledger.mark_paid(settled, member_id=None, seller_id=None, now=2.0)
    text = card.build_raid_list([open_raid, settled], {12: {"Gold": 10.0}})
    assert "#12" in text
    assert "#13" not in text
    assert "est. 960 aUEC" in text
    assert card.build_raid_list([settled], {}) == "No unsettled raids."


@pytest.mark.asyncio
async def test_estimate_prices_requires_exact_commodity_match():
    bot = MagicMock()
    commodity = MagicMock()
    commodity.name = "Gold Ore"
    commodity.id = 3
    bot.commodities_api.find = AsyncMock(return_value=commodity)
    assert await card.estimate_prices(bot, _record()) == {"Gold": None}


@pytest.mark.asyncio
async def test_estimate_prices_survives_uex_errors():
    bot = MagicMock()
    bot.commodities_api.find = AsyncMock(side_effect=RuntimeError("down"))
    assert await card.estimate_prices(bot, _record()) == {"Gold": None}


@pytest.mark.asyncio
async def test_estimate_prices_uses_best_sell():
    bot = MagicMock()
    commodity = MagicMock()
    commodity.name = "Gold"
    commodity.id = 3
    bot.commodities_api.find = AsyncMock(return_value=commodity)
    bot.commodity_prices_api.best_sell = AsyncMock(return_value=MagicMock(price_sell=5000.0))
    assert await card.estimate_prices(bot, _record()) == {"Gold": 5000.0}


def _cog(channel):
    cog = MagicMock()
    cog.bot.state = MagicMock()
    cog.bot.commodities_api.find = AsyncMock(return_value=None)
    guild = MagicMock()
    guild.id = 7
    guild.get_channel = MagicMock(return_value=channel)
    return cog, guild


@pytest.mark.asyncio
async def test_loot_channel_falls_back_to_thread_mode_beacon_channel(monkeypatch):
    monkeypatch.setattr(card.store, "get_config", AsyncMock(return_value=None))
    monkeypatch.setattr(card.beacon_store, "get_config", AsyncMock(return_value={"mode": "thread", "channel_id": 10}))
    channel = MagicMock()
    cog, guild = _cog(channel)
    assert await card.loot_channel(cog.bot, guild) is channel
    guild.get_channel.assert_called_once_with(10)


@pytest.mark.asyncio
async def test_loot_channel_ignores_forum_beacon_channel(monkeypatch):
    monkeypatch.setattr(card.store, "get_config", AsyncMock(return_value=None))
    monkeypatch.setattr(card.beacon_store, "get_config", AsyncMock(return_value={"mode": "forum", "channel_id": 10}))
    cog, guild = _cog(MagicMock())
    assert await card.loot_channel(cog.bot, guild) is None


@pytest.mark.asyncio
async def test_refresh_card_posts_and_saves_reference(monkeypatch):
    monkeypatch.setattr(card.store, "get_config", AsyncMock(return_value={"channel_id": 20}))
    save = AsyncMock()
    monkeypatch.setattr(card.store, "save_record", save)
    channel = MagicMock()
    channel.id = 20
    posted = MagicMock()
    posted.id = 900
    channel.send = AsyncMock(return_value=posted)
    cog, guild = _cog(channel)
    record = _record()
    assert await card.refresh_card(cog, guild, record) is posted
    assert record["card"] == {"channel_id": 20, "message_id": 900}
    save.assert_awaited_once()


@pytest.mark.asyncio
async def test_refresh_card_reposts_when_old_message_is_gone(monkeypatch):
    monkeypatch.setattr(card.store, "get_config", AsyncMock(return_value={"channel_id": 20}))
    monkeypatch.setattr(card.store, "save_record", AsyncMock())
    channel = MagicMock()
    channel.id = 20
    partial = MagicMock()
    partial.edit = AsyncMock(side_effect=discord.NotFound(MagicMock(status=404), "gone"))
    channel.get_partial_message = MagicMock(return_value=partial)
    reposted = MagicMock()
    reposted.id = 901
    channel.send = AsyncMock(return_value=reposted)
    cog, guild = _cog(channel)
    record = _record()
    record["card"] = {"channel_id": 20, "message_id": 800}
    await card.refresh_card(cog, guild, record)
    channel.send.assert_awaited_once()
    assert record["card"]["message_id"] == 901


@pytest.mark.asyncio
async def test_refresh_card_edits_in_place(monkeypatch):
    monkeypatch.setattr(card.store, "get_config", AsyncMock(return_value={"channel_id": 20}))
    channel = MagicMock()
    channel.id = 20
    partial = MagicMock()
    partial.edit = AsyncMock(return_value=MagicMock())
    channel.get_partial_message = MagicMock(return_value=partial)
    channel.send = AsyncMock()
    cog, guild = _cog(channel)
    record = _record()
    record["card"] = {"channel_id": 20, "message_id": 800}
    await card.refresh_card(cog, guild, record)
    partial.edit.assert_awaited_once()
    assert partial.edit.await_args.kwargs["view"] is cog.card_view
    channel.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_card_without_channel_is_a_no_op(monkeypatch):
    monkeypatch.setattr(card.store, "get_config", AsyncMock(return_value=None))
    monkeypatch.setattr(card.beacon_store, "get_config", AsyncMock(return_value=None))
    cog, guild = _cog(None)
    assert await card.refresh_card(cog, guild, _record()) is None


def test_card_url():
    record = _record()
    assert card.card_url(record) is None
    record["card"] = {"channel_id": 20, "message_id": 900}
    assert card.card_url(record) == "https://discord.com/channels/7/20/900"
