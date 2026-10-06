"""Loot card rendering and posting.

Each raid has one public card in the loot channel. It is rebuilt from the
record on every change and edited in place, or re-posted when the old message
is gone.
"""

from __future__ import annotations

import logging
from typing import Any

import discord

from src.commands.beacons import store as beacon_store
from src.commands.formatting import format_number

from . import ledger, store
from .ledger import Record

logger = logging.getLogger(__name__)

MAX_SALES_SHOWN = 8
_FIELD_LIMIT = 1024
_EMBED_LIMIT = 6000
_MESSAGE_LIMIT = 2000
_STATUS_COLORS = {
    ledger.STATUS_HOLDING: discord.Color.gold(),
    ledger.STATUS_PAYING: discord.Color.orange(),
    ledger.STATUS_SETTLED: discord.Color.green(),
}
_MENTIONS_USERS_ONLY = discord.AllowedMentions(users=True, roles=False, everyone=False)


def _clip(text: str, limit: int = _FIELD_LIMIT) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _estimate_text(price: float | None, scu: int) -> str:
    if not price or not scu:
        return ""
    return f" · est. {format_number(price * scu)} aUEC"


def _cargo_line(line: Record, price: float | None) -> str:
    left = ledger.unsold_scu(line)
    return (
        f"**{line['commodity']}**: {left}/{line['scu']} SCU left · held by <@{line['holder_id']}>"
        f"{_estimate_text(price, left)}"
    )


def _payout_line(payout: Record) -> str:
    if ledger.is_paid(payout):
        icon = "✅"
    elif payout["disputed_at"] is not None:
        icon = "⚠️"
    else:
        icon = "⏳"
    return f"{icon} <@{payout['user_id']}> {payout['amount']:,}"


def build_card_embed(record: Record, estimates: dict[str, float | None]) -> discord.Embed:
    state = ledger.status(record)
    description = state.capitalize()
    if record["beacon_thread_id"] is not None:
        description += f" · beacon <#{record['beacon_thread_id']}>"
    embed = discord.Embed(
        title=f"#{record['id']} {record['title']}"[:256], description=description, color=_STATUS_COLORS[state]
    )
    crew = ", ".join(f"<@{user_id}>" for user_id in record["participants"]) or "Nobody yet"
    embed.add_field(name=f"Crew ({len(record['participants'])})", value=_clip(crew), inline=False)
    cargo = "\n".join(_cargo_line(line, estimates.get(line["commodity"])) for line in record["cargo"])
    embed.add_field(name="Cargo", value=_clip(cargo or "No cargo logged"), inline=False)
    first_sale_field = len(embed.fields)
    shown = record["sales"][-MAX_SALES_SHOWN:]
    for sale in shown:
        embed.add_field(**_sale_field(sale))
    _drop_oldest_sales_to_fit(embed, first_sale_field, hidden=len(record["sales"]) - len(shown))
    return embed


def _sale_field(sale: Record) -> dict[str, Any]:
    name = f"Sale {sale['id']}: {sale['scu']} SCU {sale['commodity']} for {sale['total']:,} aUEC"
    lines = [f"Sold by <@{sale['seller_id']}> <t:{int(sale['sold_at'])}:R>"]
    lines += [_payout_line(payout) for payout in sale["payouts"]]
    return {"name": name[:256], "value": _clip("\n".join(lines)), "inline": False}


def _note_hidden_sales(embed: discord.Embed, hidden: int) -> None:
    if hidden:
        embed.set_footer(text=f"{hidden} older sales not shown. /loot owed has the full picture.")


def _drop_oldest_sales_to_fit(embed: discord.Embed, first_sale_field: int, hidden: int) -> None:
    _note_hidden_sales(embed, hidden)
    while len(embed) > _EMBED_LIMIT and len(embed.fields) > first_sale_field + 1:
        embed.remove_field(first_sale_field)
        hidden += 1
        _note_hidden_sales(embed, hidden)


def _raid_label(record: Record) -> str:
    return f"#{record['id']} {record['title']}"


def build_owed_summary(records: list[Record], user_id: int) -> str:
    sections = []
    owed_to = ledger.owed_to(records, user_id)
    if owed_to:
        lines = [
            f"{_raid_label(r)}: {p['amount']:,} aUEC from <@{s['seller_id']}> (sale {s['id']})" for r, s, p in owed_to
        ]
        sections.append("**Owed to you**\n" + "\n".join(lines))
    owed_by = ledger.owed_by(records, user_id)
    if owed_by:
        lines = [f"{_raid_label(r)}: {p['amount']:,} aUEC to <@{p['user_id']}> (sale {s['id']})" for r, s, p in owed_by]
        sections.append("**You owe**\n" + "\n".join(lines))
    held = ledger.held_by(records, user_id)
    if held:
        lines = [f"{_raid_label(r)}: {ledger.unsold_scu(line)} SCU {line['commodity']}" for r, line in held]
        sections.append("**You're holding**\n" + "\n".join(lines))
    if not sections:
        return "You're all square: nobody owes you, you owe nobody, and you aren't holding any loot."
    return _clip("\n\n".join(sections), _MESSAGE_LIMIT)


def build_raid_list(records: list[Record], estimates_by_id: dict[int, dict[str, float | None]]) -> str:
    lines = []
    for record in records:
        state = ledger.status(record)
        if state == ledger.STATUS_SETTLED:
            continue
        prices = estimates_by_id.get(record["id"], {})
        cargo = ", ".join(
            f"{ledger.unsold_scu(line)} SCU {line['commodity']} (<@{line['holder_id']}>)"
            f"{_estimate_text(prices.get(line['commodity']), ledger.unsold_scu(line))}"
            for line in record["cargo"]
            if ledger.unsold_scu(line) > 0
        )
        owed = ledger.owed_amount(record)
        parts = [f"**{_raid_label(record)}**", state]
        if cargo:
            parts.append(cargo)
        if owed:
            parts.append(f"{owed:,} aUEC owed")
        url = card_url(record)
        if url:
            parts.append(url)
        lines.append(" · ".join(parts))
    return _clip("\n".join(lines), _MESSAGE_LIMIT) if lines else "No unsettled raids."


def card_url(record: Record) -> str | None:
    card = record["card"]
    if card is None:
        return None
    return f"https://discord.com/channels/{record['guild_id']}/{card['channel_id']}/{card['message_id']}"


async def _best_sell_price(bot: Any, name: str) -> float | None:
    try:
        commodity = await bot.commodities_api.find(name)
        if commodity is None or commodity.id is None or commodity.name.lower() != name.strip().lower():
            return None
        best = await bot.commodity_prices_api.best_sell(commodity.id)
    except Exception:  # noqa: BLE001 - estimates are decoration and must never block a loot change
        logger.warning("Could not estimate a price for %s", name)
        return None
    return best.price_sell if best is not None else None


async def estimate_prices(bot: Any, record: Record) -> dict[str, float | None]:
    return {
        line["commodity"]: await _best_sell_price(bot, line["commodity"])
        for line in record["cargo"]
        if ledger.unsold_scu(line) > 0
    }


async def loot_channel(bot: Any, guild: discord.Guild) -> discord.abc.Messageable | None:
    config = await store.get_config(bot.state, guild.id)
    channel_id = (config or {}).get("channel_id")
    if channel_id is None:
        beacon_config = await beacon_store.get_config(bot.state, guild.id)
        if beacon_config and beacon_config.get("mode") == "thread":
            channel_id = beacon_config["channel_id"]
    return guild.get_channel(channel_id) if channel_id is not None else None


async def refresh_card(cog: Any, guild: discord.Guild, record: Record) -> discord.Message | None:
    channel = await loot_channel(cog.bot, guild)
    if channel is None:
        return None
    embed = build_card_embed(record, await estimate_prices(cog.bot, record))
    existing = record["card"]
    if existing is not None and existing["channel_id"] == channel.id:
        try:
            return await channel.get_partial_message(existing["message_id"]).edit(embed=embed, view=cog.card_view)
        except discord.NotFound:
            pass
        except discord.HTTPException:
            logger.warning("Could not edit loot card for raid %s", record["id"])
            return None
    try:
        message = await channel.send(embed=embed, view=cog.card_view)
    except discord.HTTPException:
        logger.warning("Could not post loot card for raid %s", record["id"])
        return None
    record["card"] = {"channel_id": channel.id, "message_id": message.id}
    await store.save_record(cog.bot.state, record)
    return message


async def announce(cog: Any, guild: discord.Guild, content: str) -> None:
    channel = await loot_channel(cog.bot, guild)
    if channel is None:
        return
    try:
        await channel.send(content, allowed_mentions=_MENTIONS_USERS_ONLY)
    except discord.HTTPException:
        logger.warning("Could not post loot announcement in guild %s", guild.id)
