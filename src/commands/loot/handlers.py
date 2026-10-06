"""Interaction handlers for /loot: defer, lock, apply a ledger change, save,
refresh the loot card, and reply."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Literal

import discord
from discord import app_commands

from src.commands.autocomplete import MAX_AUTOCOMPLETE_CHOICES, MAX_CHOICE_LABEL, name_choices
from src.commands.beacons import store as beacon_store
from src.commands.beacons.categories import CATEGORIES
from src.commands.beacons.embeds import beacon_summary
from src.commands.beacons.lifecycle import is_beacon_admin, lock_for

from . import card, ledger, store
from .ledger import LootError, Record

logger = logging.getLogger(__name__)

_NO_CHANNEL_HINT = "No loot channel is set, so there's no card yet. An admin can run `/loot config channel`."


@dataclass(frozen=True)
class Outcome:
    reply: str
    announcement: str | None = None


def parse_raid_id(raw: str) -> int | None:
    digits = raw.strip().lstrip("#")
    return int(digits) if digits.isdecimal() else None


def _record_lock(guild_id: int, loot_id: int):
    return lock_for(f"loot:record:{guild_id}:{loot_id}")


def _id_lock(guild_id: int):
    return lock_for(f"loot:ids:{guild_id}")


async def _reply(interaction: discord.Interaction, message: str) -> None:
    await interaction.followup.send(message, ephemeral=True)


def _card_note(message: discord.Message | None) -> str:
    return f" {message.jump_url}" if message is not None else f" {_NO_CHANNEL_HINT}"


@asynccontextmanager
async def _locked_record(cog, guild_id: int, raid: str | int) -> AsyncIterator[Record]:
    loot_id = raid if isinstance(raid, int) else parse_raid_id(raid)
    if loot_id is None:
        raise LootError(f"`{raid}` isn't a raid id. Pick one from the list.")
    async with _record_lock(guild_id, loot_id):
        record = await store.get_record(cog.bot.state, guild_id, loot_id)
        if record is None:
            raise LootError(f"Raid #{loot_id} not found.")
        yield record


async def run_change(
    cog, interaction: discord.Interaction, raid: str | int, change: Callable[[Record], Outcome]
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        async with _locked_record(cog, interaction.guild.id, raid) as record:
            outcome = change(record)
            await store.save_record(cog.bot.state, record)
            await card.refresh_card(cog, interaction.guild, record)
    except LootError as error:
        await _reply(interaction, str(error))
        return
    if outcome.announcement:
        await card.announce(cog, interaction.guild, outcome.announcement)
    await _reply(interaction, outcome.reply)


def beacon_loot_title(beacon: Record) -> str:
    label = CATEGORIES[beacon["category"]].label
    summary = beacon_summary(beacon["category"], beacon["fields"])
    return f"{label} {summary}" if summary else label


async def _publish_new(cog, guild: discord.Guild, record: Record) -> discord.Message | None:
    async with _id_lock(guild.id):
        record["id"] = await store.allocate_id(cog.bot.state, guild.id)
    async with _record_lock(guild.id, record["id"]):
        await store.save_record(cog.bot.state, record)
        if record["beacon_thread_id"] is not None:
            await store.set_by_beacon(cog.bot.state, record["beacon_thread_id"], record["id"])
        return await card.refresh_card(cog, guild, record)


async def handle_new(
    cog,
    interaction: discord.Interaction,
    *,
    title: str,
    commodity: str,
    scu: int,
    participants: str | None,
    holder_id: int | None,
) -> None:
    await interaction.response.defer(ephemeral=True)
    creator = interaction.user.id
    mentioned = ledger.parse_mentions(participants)
    try:
        if participants and participants.strip() and not mentioned:
            raise LootError("Tag the crew with @mentions in `participants`, e.g. `@Alice @Bob`.")
        record = ledger.new_record(
            loot_id=0,
            guild_id=interaction.guild.id,
            title=title,
            created_by=creator,
            participants=[creator, *mentioned],
            organizer_ids=[creator],
            now=time.time(),
        )
        ledger.add_cargo(record, commodity, scu, holder_id if holder_id is not None else creator)
    except LootError as error:
        await _reply(interaction, str(error))
        return
    message = await _publish_new(cog, interaction.guild, record)
    await _reply(interaction, f"Created raid #{record['id']}.{_card_note(message)}")


async def _log_on_beacon(cog, interaction: discord.Interaction, commodity: str, scu: int, holder_id: int):
    thread_id = interaction.channel.id
    beacon = await beacon_store.get_beacon(cog.bot.state, thread_id)
    if beacon is None or beacon["guild_id"] != interaction.guild.id:
        raise LootError("Run this inside a beacon thread, pass `raid:` to add to an existing raid, or use `/loot new`.")
    async with lock_for(f"loot:beacon:{thread_id}"):
        loot_id = await store.get_by_beacon(cog.bot.state, thread_id)
        if loot_id is not None:
            async with _locked_record(cog, interaction.guild.id, loot_id) as record:
                ledger.add_cargo(record, commodity, scu, holder_id)
                await store.save_record(cog.bot.state, record)
                message = await card.refresh_card(cog, interaction.guild, record)
            return record, message, False
        record = ledger.new_record(
            loot_id=0,
            guild_id=interaction.guild.id,
            title=beacon_loot_title(beacon),
            created_by=interaction.user.id,
            participants=[beacon["requester_id"], *beacon["members"]],
            organizer_ids=[interaction.user.id, beacon["requester_id"]],
            now=time.time(),
            beacon_thread_id=thread_id,
            category=beacon["category"],
        )
        ledger.add_cargo(record, commodity, scu, holder_id)
        message = await _publish_new(cog, interaction.guild, record)
        return record, message, True


async def _post_card_link(channel, record: Record, message: discord.Message | None) -> None:
    if message is None:
        return
    try:
        await channel.send(f"Loot from this beacon is tracked as raid #{record['id']}: {message.jump_url}")
    except discord.HTTPException:
        logger.info("Could not post loot link in beacon thread %s", getattr(channel, "id", "?"))


async def handle_log(
    cog,
    interaction: discord.Interaction,
    *,
    commodity: str,
    scu: int,
    holder_id: int,
    raid: str | None,
) -> None:
    if raid is not None:

        def change(record: Record) -> Outcome:
            line = ledger.add_cargo(record, commodity, scu, holder_id)
            return Outcome(f"Added {scu} SCU {line['commodity']} to raid #{record['id']}.")

        await run_change(cog, interaction, raid, change)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        record, message, created = await _log_on_beacon(cog, interaction, commodity, scu, holder_id)
    except LootError as error:
        await _reply(interaction, str(error))
        return
    if created:
        await _post_card_link(interaction.channel, record, message)
        await _reply(interaction, f"Logged {scu} SCU {commodity.strip()} as raid #{record['id']}.{_card_note(message)}")
    else:
        await _reply(interaction, f"Added {scu} SCU {commodity.strip()} to raid #{record['id']}.")


async def handle_config_channel(cog, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
    await store.set_config(cog.bot.state, interaction.guild.id, {"channel_id": channel.id})
    await interaction.response.send_message(f"Loot cards will be posted in {channel.mention}.", ephemeral=True)


async def raid_autocomplete(cog, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    records = await store.guild_records(cog.bot.state, interaction.guild_id)
    needle = current.strip().lower()
    ordered = sorted(records, key=lambda r: (ledger.status(r) == ledger.STATUS_SETTLED, r["id"]))
    choices = []
    for record in ordered:
        label = f"#{record['id']} {record['title']}"
        if needle and needle not in label.lower():
            continue
        choices.append(app_commands.Choice(name=label[:MAX_CHOICE_LABEL], value=str(record["id"])))
        if len(choices) >= MAX_AUTOCOMPLETE_CHOICES:
            break
    return choices


async def cargo_autocomplete(cog, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    loot_id = parse_raid_id(str(getattr(interaction.namespace, "raid", None) or ""))
    if loot_id is None:
        return []
    record = await store.get_record(cog.bot.state, interaction.guild_id, loot_id)
    if record is None:
        return []
    needle = current.strip().lower()
    return name_choices(line["commodity"] for line in record["cargo"] if needle in line["commodity"].lower())


def _mentions(user_ids: list[int]) -> str:
    return " ".join(f"<@{user_id}>" for user_id in user_ids)


def _sale_announcement(record: Record, sale: Record) -> str:
    owed = [p["user_id"] for p in sale["payouts"] if not ledger.is_paid(p)]
    text = (
        f"Raid #{record['id']}: <@{sale['seller_id']}> sold {sale['scu']} SCU {sale['commodity']} "
        f"for {sale['total']:,} aUEC, {sale['share']:,} each."
    )
    return f"{text} Owed: {_mentions(owed)}" if owed else text


def _require_line_access(record: Record, commodity: str, user_id: int, is_admin: bool) -> Record:
    line = ledger.resolve_line(record, commodity, user_id)
    if not ledger.can_handle_line(line, user_id, is_admin):
        raise LootError(
            f"Only <@{line['holder_id']}> (the holder) or an admin can do that with this {line['commodity']}."
        )
    return line


async def handle_sell(
    cog, interaction: discord.Interaction, *, raid: str, commodity: str, scu: int, total: int
) -> None:
    is_admin = is_beacon_admin(interaction)

    def change(record: Record) -> Outcome:
        line = _require_line_access(record, commodity, interaction.user.id, is_admin)
        sale = ledger.record_sale(record, line, scu=scu, total=total, now=time.time())
        return Outcome(
            f"Recorded sale {sale['id']} on raid #{record['id']}: {sale['share']:,} aUEC each.",
            _sale_announcement(record, sale),
        )

    await run_change(cog, interaction, raid, change)


async def handle_paid(cog, interaction: discord.Interaction, *, raid: str, member_id: int | None) -> None:
    seller_filter = None if is_beacon_admin(interaction) else interaction.user.id

    def change(record: Record) -> Outcome:
        count = ledger.mark_paid(record, member_id=member_id, seller_id=seller_filter, now=time.time())
        noun = "payout" if count == 1 else "payouts"
        return Outcome(f"Marked {count} {noun} paid on raid #{record['id']}.")

    await run_change(cog, interaction, raid, change)


async def handle_dispute(cog, interaction: discord.Interaction, *, raid: str) -> None:
    def change(record: Record) -> Outcome:
        payers = ledger.dispute(record, user_id=interaction.user.id, now=time.time())
        return Outcome(
            "Flagged your share as not received. The payer has been pinged.",
            f"<@{interaction.user.id}> says they haven't received their share from raid #{record['id']}. "
            f"{_mentions(payers)}, please check.",
        )

    await run_change(cog, interaction, raid, change)


async def handle_undo(cog, interaction: discord.Interaction, *, raid: str) -> None:
    is_admin = is_beacon_admin(interaction)

    def change(record: Record) -> Outcome:
        sale = ledger.undo_last_sale(record, user_id=interaction.user.id, is_admin=is_admin)
        return Outcome(f"Removed sale {sale['id']}. {sale['scu']} SCU {sale['commodity']} is back in the hold.")

    await run_change(cog, interaction, raid, change)


async def handle_holder(cog, interaction: discord.Interaction, *, raid: str, commodity: str, member_id: int) -> None:
    is_admin = is_beacon_admin(interaction)

    def change(record: Record) -> Outcome:
        line = _require_line_access(record, commodity, interaction.user.id, is_admin)
        ledger.set_holder(record, line, member_id)
        return Outcome(f"<@{member_id}> now holds the {line['commodity']} from raid #{record['id']}.")

    await run_change(cog, interaction, raid, change)


async def handle_cargo_fix(cog, interaction: discord.Interaction, *, raid: str, commodity: str, scu: int) -> None:
    is_admin = is_beacon_admin(interaction)

    def change(record: Record) -> Outcome:
        line = _require_line_access(record, commodity, interaction.user.id, is_admin)
        name = line["commodity"]
        fixed = ledger.fix_cargo(record, line, scu)
        if fixed is None:
            return Outcome(f"Removed {name} from raid #{record['id']}.")
        return Outcome(f"Raid #{record['id']} now has {scu} SCU {name} in total.")

    await run_change(cog, interaction, raid, change)


async def handle_participants(
    cog, interaction: discord.Interaction, *, raid: str, action: Literal["add", "remove"], member_id: int
) -> None:
    is_admin = is_beacon_admin(interaction)

    def change(record: Record) -> Outcome:
        if not ledger.can_manage_roster(record, interaction.user.id, is_admin):
            raise LootError("Only the raid's organizers, a cargo holder, or an admin can change the crew.")
        if action == "add":
            ledger.add_participant(record, member_id)
            return Outcome(f"Added <@{member_id}> to raid #{record['id']}. They share in future sales.")
        ledger.remove_participant(record, member_id)
        return Outcome(f"Removed <@{member_id}> from raid #{record['id']}. Past sales are unchanged.")

    await run_change(cog, interaction, raid, change)


async def _record_id_for_card(cog, interaction: discord.Interaction) -> int | None:
    for record in await store.guild_records(cog.bot.state, interaction.guild.id):
        if record["card"] is not None and record["card"]["message_id"] == interaction.message.id:
            return record["id"]
    return None


async def _card_roster_change(cog, interaction: discord.Interaction, change: Callable[[Record], Outcome]) -> None:
    loot_id = await _record_id_for_card(cog, interaction)
    if loot_id is None:
        await interaction.response.send_message("This loot card is no longer tracked.", ephemeral=True)
        return
    await run_change(cog, interaction, loot_id, change)


async def handle_card_join(cog, interaction: discord.Interaction) -> None:
    def change(record: Record) -> Outcome:
        ledger.add_participant(record, interaction.user.id)
        return Outcome(f"You're on raid #{record['id']}. You'll share in future sales.")

    await _card_roster_change(cog, interaction, change)


async def handle_card_leave(cog, interaction: discord.Interaction) -> None:
    def change(record: Record) -> Outcome:
        ledger.remove_participant(record, interaction.user.id)
        return Outcome(f"You left raid #{record['id']}. Past sales are unchanged.")

    await _card_roster_change(cog, interaction, change)


async def handle_owed(cog, interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    records = await store.guild_records(cog.bot.state, interaction.guild.id)
    await _reply(interaction, card.build_owed_summary(records, interaction.user.id))


async def handle_list(cog, interaction: discord.Interaction) -> None:
    await interaction.response.defer()
    records = [
        record
        for record in await store.guild_records(cog.bot.state, interaction.guild.id)
        if ledger.status(record) != ledger.STATUS_SETTLED
    ]
    estimates = {record["id"]: await card.estimate_prices(cog.bot, record) for record in records}
    await interaction.followup.send(
        card.build_raid_list(records, estimates), allowed_mentions=discord.AllowedMentions.none()
    )


async def handle_delete(cog, interaction: discord.Interaction, *, raid: str) -> None:
    from .views import ConfirmDeleteView

    await interaction.response.defer(ephemeral=True)
    loot_id = parse_raid_id(raid)
    record = await store.get_record(cog.bot.state, interaction.guild.id, loot_id) if loot_id is not None else None
    if record is None:
        await _reply(interaction, f"Raid {raid} not found.")
        return
    if not ledger.can_delete(record):
        await _reply(
            interaction, f"Raid #{record['id']} still has {ledger.owed_amount(record):,} aUEC owed. Settle it first."
        )
        return
    await interaction.followup.send(
        f"Delete raid #{record['id']} {record['title']}? This can't be undone.",
        view=ConfirmDeleteView(cog, interaction.guild.id, record["id"]),
        ephemeral=True,
    )


async def _delete_card_message(cog, interaction: discord.Interaction, record: Record) -> None:
    if record["card"] is None:
        return
    channel = interaction.guild.get_channel(record["card"]["channel_id"])
    if channel is None:
        return
    try:
        await channel.get_partial_message(record["card"]["message_id"]).delete()
    except discord.HTTPException:
        logger.info("Loot card for raid %s was already gone", record["id"])


async def confirm_delete(cog, interaction: discord.Interaction, guild_id: int, loot_id: int) -> None:
    await interaction.response.defer()
    async with _record_lock(guild_id, loot_id):
        record = await store.get_record(cog.bot.state, guild_id, loot_id)
        if record is None:
            await interaction.edit_original_response(content=f"Raid #{loot_id} is already gone.", view=None)
            return
        if not ledger.can_delete(record):
            await interaction.edit_original_response(content=f"Raid #{loot_id} has payouts owed again.", view=None)
            return
        await store.delete_record(cog.bot.state, record)
    await _delete_card_message(cog, interaction, record)
    await interaction.edit_original_response(content=f"Deleted raid #{loot_id}.", view=None)
