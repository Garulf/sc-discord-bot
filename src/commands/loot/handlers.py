"""Interaction handlers for /loot: defer, lock, apply a ledger change, save,
refresh the loot card, and reply."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass

import discord
from discord import app_commands

from src.commands.autocomplete import MAX_AUTOCOMPLETE_CHOICES, MAX_CHOICE_LABEL, name_choices
from src.commands.beacons import store as beacon_store
from src.commands.beacons.categories import CATEGORIES
from src.commands.beacons.embeds import beacon_summary
from src.commands.beacons.lifecycle import lock_for

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
    return int(digits) if digits.isdigit() else None


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


async def _save_new(cog, record: Record) -> Record:
    async with _id_lock(record["guild_id"]):
        record["id"] = await store.allocate_id(cog.bot.state, record["guild_id"])
    await store.save_record(cog.bot.state, record)
    return record


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
    await _save_new(cog, record)
    async with _record_lock(record["guild_id"], record["id"]):
        message = await card.refresh_card(cog, interaction.guild, record)
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
        await _save_new(cog, record)
        await store.set_by_beacon(cog.bot.state, thread_id, record["id"])
        async with _record_lock(record["guild_id"], record["id"]):
            message = await card.refresh_card(cog, interaction.guild, record)
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
