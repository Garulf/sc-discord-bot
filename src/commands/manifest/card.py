"""Manifest card rendering, list and owed summaries, and the private thread.

Each manifest has one private thread in the manifest channel holding its card.
The card is rebuilt from the record on every change and edited in place, or
re-posted when the old message is gone.
"""

from __future__ import annotations

import logging
from typing import Any

import discord

from src.commands.beacons import store as beacon_store
from src.commands.formatting import format_number

from . import ledger, store
from .ledger import MemberShare, Record

logger = logging.getLogger(__name__)

MAX_SALES_SHOWN = 8
_FIELD_LIMIT = 1024
_EMBED_LIMIT = 6000
_MESSAGE_LIMIT = 2000
_THREAD_NAME_LIMIT = 100
_ARCHIVE_AFTER_MINUTES = 10080
_STATUS_COLORS = {
    ledger.STATUS_OPEN: discord.Color.gold(),
    ledger.STATUS_PARTIAL: discord.Color.orange(),
    ledger.STATUS_SOLD: discord.Color.green(),
}
_REQUIRED_PERMISSIONS = {
    "create_private_threads": "Create Private Threads",
    "send_messages_in_threads": "Send Messages in Threads",
    "manage_threads": "Manage Threads",
}
MENTION_USERS_ONLY = discord.AllowedMentions(users=True, roles=False, everyone=False)


def _clip(text: str, limit: int = _FIELD_LIMIT) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _status_label(record: Record) -> str:
    return ledger.status(record).capitalize()


def _cargo_line(record: Record, line: Record) -> str:
    sold = ledger.sold_scu(record, line["commodity"])
    unsold = line["scu"] - sold
    parts = [f"**{line['commodity']}**: {sold}/{line['scu']} SCU sold"]
    if sold:
        received = sum(sale["total"] for sale in record["sales"] if sale["commodity"] == line["commodity"])
        parts.append(f"{received:,} aUEC received")
    if unsold:
        price = line["est_price"]
        if price:
            parts.append(f"est. {format_number(price)}/SCU · {round(unsold * price):,} aUEC unsold")
        else:
            parts.append("no estimate")
    return " · ".join(parts)


def _costs_text(record: Record) -> str:
    if not record["costs"]:
        return "No costs"
    lines = [f"{cost['label']}: {cost['amount']:,}" for cost in record["costs"]]
    lines.append(f"Total {ledger.total_costs(record):,} · {ledger.recovered_costs(record):,} recovered")
    return "\n".join(lines)


def _totals_text(record: Record) -> str:
    return (
        f"Value {ledger.value(record):,} · Costs {ledger.total_costs(record):,} · Profit {ledger.profit(record):,} aUEC"
    )


def _share_line(share: MemberShare) -> str:
    who = f"<@{share.user_id}> ×{share.weight}" if share.weight is not None else f"<@{share.user_id}> left"
    parts = [who]
    if share.projected != share.earned:
        parts.append(f"{share.projected:,} est.")
    parts.append(f"{share.earned:,} earned")
    if share.disputed:
        parts.append(f"⚠️ {share.owed:,} disputed")
    elif share.owed:
        parts.append(f"⏳ {share.owed:,} owed")
    return " · ".join(parts)


def _payout_line(payout: Record) -> str:
    if ledger.is_paid(payout):
        icon = "✅"
    elif payout["disputed_at"] is not None:
        icon = "⚠️"
    else:
        icon = "⏳"
    return f"{icon} <@{payout['user_id']}> {payout['amount']:,}"


def _sale_field(sale: Record) -> dict[str, Any]:
    name = f"Sale {sale['id']}: {sale['scu']} SCU {sale['commodity']} for {sale['total']:,} aUEC"
    header = f"Sold by <@{sale['seller_id']}> <t:{int(sale['sold_at'])}:R>"
    if sale["cost_recovered"]:
        header += f" · {sale['cost_recovered']:,} to costs"
    lines = [header] + [_payout_line(payout) for payout in sale["payouts"] if payout["amount"] > 0]
    return {"name": name[:256], "value": _clip("\n".join(lines)), "inline": False}


def _note_hidden_sales(embed: discord.Embed, hidden: int) -> None:
    if hidden:
        embed.set_footer(text=f"{hidden} older sales not shown. /manifest owed has the full picture.")


def _drop_oldest_sales_to_fit(embed: discord.Embed, first_sale_field: int, hidden: int) -> None:
    _note_hidden_sales(embed, hidden)
    while len(embed) > _EMBED_LIMIT and len(embed.fields) > first_sale_field + 1:
        embed.remove_field(first_sale_field)
        hidden += 1
        _note_hidden_sales(embed, hidden)


def _description(record: Record) -> str:
    parts = [_status_label(record), f"carrier <@{record['carrier_id']}>"]
    if record["beacon_thread_id"] is not None:
        parts.append(f"from beacon <#{record['beacon_thread_id']}>")
    outstanding = ledger.outstanding_payouts(record)
    if outstanding:
        parts.append(f"{outstanding} payout{'s' if outstanding != 1 else ''} outstanding")
    return " · ".join(parts)


def _chunk_lines(lines: list[str]) -> list[str]:
    chunks: list[str] = []
    for line in lines:
        line = _clip(line)
        if chunks and len(chunks[-1]) + 1 + len(line) <= _FIELD_LIMIT:
            chunks[-1] += "\n" + line
        else:
            chunks.append(line)
    return chunks


def _add_line_fields(embed: discord.Embed, name: str, lines: list[str]) -> None:
    for index, chunk in enumerate(_chunk_lines(lines)):
        embed.add_field(name=name if index == 0 else f"{name} (cont.)", value=chunk, inline=False)


def build_card_embed(record: Record) -> discord.Embed:
    embed = discord.Embed(
        title=f"Manifest #{record['id']}",
        description=_description(record),
        color=_STATUS_COLORS[ledger.status(record)],
    )
    _add_line_fields(embed, "Cargo", [_cargo_line(record, line) for line in record["cargo"]])
    embed.add_field(name="Costs", value=_clip(_costs_text(record)), inline=False)
    embed.add_field(name="Totals", value=_totals_text(record), inline=False)
    shares = [_share_line(share) for share in ledger.member_shares(record)]
    _add_line_fields(embed, f"Crew & shares ({len(record['crew'])})", shares)
    first_sale_field = len(embed.fields)
    shown = record["sales"][-MAX_SALES_SHOWN:]
    for sale in shown:
        embed.add_field(**_sale_field(sale))
    _drop_oldest_sales_to_fit(embed, first_sale_field, hidden=len(record["sales"]) - len(shown))
    return embed


def thread_name(record: Record) -> str:
    name = f"Manifest #{record['id']}: " + ", ".join(line["commodity"] for line in record["cargo"])
    return _clip(name, _THREAD_NAME_LIMIT)


def _is_settled(record: Record) -> bool:
    return ledger.status(record) == ledger.STATUS_SOLD and ledger.owed_amount(record) == 0


def _list_line(record: Record) -> str:
    parts = [
        f"**#{record['id']}** {_status_label(record)}",
        f"carrier <@{record['carrier_id']}>",
        ", ".join(line["commodity"] for line in record["cargo"]),
        f"profit {ledger.profit(record):,}",
    ]
    owed = ledger.owed_amount(record)
    if owed:
        parts.append(f"{owed:,} aUEC owed")
    if record["thread_id"] is not None:
        parts.append(f"<#{record['thread_id']}>")
    return " · ".join(parts)


def build_list(records: list[Record], user_id: int, is_admin: bool) -> str:
    visible = [record for record in records if ledger.is_visible(record, user_id, is_admin)]
    if not visible:
        return "You have no manifests yet. Start one with `/manifest new`."
    open_value = sum(
        ledger.remaining_value(record) for record in visible if ledger.status(record) != ledger.STATUS_SOLD
    )
    total_profit = sum(ledger.profit(record) for record in visible)
    lines = [f"Open cargo value {open_value:,} · Overall profit {total_profit:,} aUEC"]
    lines += [_list_line(record) for record in visible if not _is_settled(record)]
    settled = sum(1 for record in visible if _is_settled(record))
    if settled:
        lines.append(f"{settled} settled not shown")
    return _clip("\n".join(lines), _MESSAGE_LIMIT)


def build_owed(records: list[Record], user_id: int) -> str:
    sections = []
    owed_to = ledger.owed_to(records, user_id)
    if owed_to:
        lines = [
            f"Manifest #{r['id']}: {p['amount']:,} aUEC from <@{s['seller_id']}> (sale {s['id']})"
            for r, s, p in owed_to
        ]
        sections.append("**Owed to you**\n" + "\n".join(lines))
    owed_by = ledger.owed_by(records, user_id)
    if owed_by:
        lines = [
            f"Manifest #{r['id']}: {p['amount']:,} aUEC to <@{p['user_id']}> (sale {s['id']})" for r, s, p in owed_by
        ]
        sections.append("**You owe**\n" + "\n".join(lines))
    carried = ledger.carried_by(records, user_id)
    if carried:
        lines = [f"Manifest #{r['id']}: {ledger.unsold_scu(r, line)} SCU {line['commodity']}" for r, line in carried]
        sections.append("**You're carrying**\n" + "\n".join(lines))
    if not sections:
        return "You're all square: nobody owes you, you owe nobody, and you aren't carrying any cargo."
    return _clip("\n\n".join(sections), _MESSAGE_LIMIT)


def missing_permissions(channel: Any, me: Any) -> list[str]:
    permissions = channel.permissions_for(me)
    return [label for name, label in _REQUIRED_PERMISSIONS.items() if not getattr(permissions, name)]


async def manifest_channel(bot: Any, guild: discord.Guild) -> Any:
    config = await store.get_config(bot.state, guild.id)
    channel_id = (config or {}).get("channel_id")
    if channel_id is None:
        beacon_config = await beacon_store.get_config(bot.state, guild.id)
        if beacon_config and beacon_config.get("mode") == "thread":
            channel_id = beacon_config["channel_id"]
    return guild.get_channel(channel_id) if channel_id is not None else None


async def _thread(guild: discord.Guild, record: Record) -> Any:
    if record["thread_id"] is None:
        return None
    thread = guild.get_thread(record["thread_id"])
    if thread is not None:
        return thread
    try:
        return await guild.fetch_channel(record["thread_id"])
    except discord.HTTPException:
        logger.info("Thread for manifest %s is gone", record["id"])
        return None


async def _add_users(thread: Any, user_ids: list[int]) -> None:
    for user_id in user_ids:
        try:
            await thread.add_user(discord.Object(id=user_id))
        except discord.HTTPException:
            logger.info("Could not add %s to manifest thread %s", user_id, thread.id)


async def add_members(guild: discord.Guild, record: Record, user_ids: list[int]) -> None:
    thread = await _thread(guild, record)
    if thread is not None:
        await _add_users(thread, user_ids)


async def open_thread(cog: Any, guild: discord.Guild, record: Record) -> Any:
    channel = await manifest_channel(cog.bot, guild)
    if channel is None:
        return None
    try:
        thread = await channel.create_thread(
            name=thread_name(record),
            type=discord.ChannelType.private_thread,
            invitable=False,
            auto_archive_duration=_ARCHIVE_AFTER_MINUTES,
        )
    except discord.HTTPException:
        logger.warning("Could not create a thread for manifest %s", record["id"])
        return None
    record["thread_id"] = thread.id
    await store.save_record(cog.bot.state, record)
    await store.set_by_thread(cog.bot.state, thread.id, record["id"])
    await _add_users(thread, ledger.crew_ids(record))
    try:
        message = await thread.send(embed=build_card_embed(record), view=cog.card_view)
    except discord.HTTPException:
        logger.warning("Could not post the card for manifest %s", record["id"])
        return thread
    record["card_message_id"] = message.id
    await store.save_record(cog.bot.state, record)
    return thread


async def _unarchive(thread: Any) -> None:
    if not getattr(thread, "archived", False):
        return
    try:
        await thread.edit(archived=False)
    except discord.HTTPException:
        logger.info("Could not unarchive manifest thread %s", thread.id)


async def refresh_card(cog: Any, guild: discord.Guild, record: Record) -> discord.Message | None:
    thread = await _thread(guild, record)
    if thread is None:
        return None
    await _unarchive(thread)
    embed = build_card_embed(record)
    if record["card_message_id"] is not None:
        try:
            return await thread.get_partial_message(record["card_message_id"]).edit(embed=embed, view=cog.card_view)
        except discord.NotFound:
            pass
        except discord.HTTPException:
            logger.warning("Could not edit the card for manifest %s", record["id"])
            return None
    try:
        message = await thread.send(embed=embed, view=cog.card_view)
    except discord.HTTPException:
        logger.warning("Could not post the card for manifest %s", record["id"])
        return None
    record["card_message_id"] = message.id
    await store.save_record(cog.bot.state, record)
    return message


async def announce(guild: discord.Guild, record: Record, content: str) -> None:
    thread = await _thread(guild, record)
    if thread is None:
        return
    try:
        await thread.send(content, allowed_mentions=MENTION_USERS_ONLY)
    except discord.HTTPException:
        logger.warning("Could not post in the thread for manifest %s", record["id"])


async def close_thread(guild: discord.Guild, record: Record) -> None:
    thread = await _thread(guild, record)
    if thread is None:
        return
    try:
        await thread.edit(archived=True, locked=True)
    except discord.HTTPException:
        logger.info("Could not close the thread for manifest %s", record["id"])
