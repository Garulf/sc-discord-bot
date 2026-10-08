"""Interaction handlers for manifests: defer, lock, apply a ledger change, save,
refresh the card, and reply."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass

import discord
from discord import app_commands

from src.commands.autocomplete import MAX_AUTOCOMPLETE_CHOICES, MAX_CHOICE_LABEL
from src.commands.beacons import store as beacon_store
from src.commands.beacons.lifecycle import is_beacon_admin, lock_for

from . import card, ledger, parsing, pricing, store
from .ledger import ManifestError, Record

logger = logging.getLogger(__name__)

_NO_THREAD_HINT = "No manifest channel is set, so there's no thread yet. An officer can run `/manifest config channel`."
EDIT_REFUSAL = "Only the creator, the carrier or an officer can change this manifest."
PAID_REFUSAL = "Only whoever sold it or an officer can mark payouts paid."


@dataclass(frozen=True)
class Outcome:
    reply: str
    announcement: str | None = None
    new_members: tuple[int, ...] = ()


@dataclass
class Draft:
    crew_ids: list[int]
    carrier_id: int | None
    cargo_text: str
    costs_text: str
    beacon_thread_id: int | None = None


def parse_manifest_id(raw: str) -> int | None:
    digits = raw.strip().lstrip("#")
    return int(digits) if digits.isdecimal() else None


def _record_lock(guild_id: int, manifest_id: int):
    return lock_for(f"manifest:record:{guild_id}:{manifest_id}")


def _id_lock(guild_id: int):
    return lock_for(f"manifest:ids:{guild_id}")


async def _reply(interaction: discord.Interaction, message: str, **kwargs) -> None:
    await interaction.followup.send(message, ephemeral=True, **kwargs)


def _mentions(user_ids: Iterable[int]) -> str:
    return ", ".join(f"<@{user_id}>" for user_id in user_ids)


async def run_change(
    cog,
    interaction: discord.Interaction,
    manifest_id: int,
    change: Callable[[Record], Outcome],
    *,
    deferred: bool = False,
) -> None:
    if not deferred:
        await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    try:
        async with _record_lock(guild.id, manifest_id):
            record = await store.get_record(cog.bot.state, guild.id, manifest_id)
            if record is None:
                raise ManifestError(f"Manifest #{manifest_id} no longer exists.")
            outcome = change(record)
            await store.save_record(cog.bot.state, record)
            if outcome.new_members:
                await card.add_members(guild, record, list(outcome.new_members))
            await card.refresh_card(cog, guild, record)
    except ManifestError as error:
        await _reply(interaction, str(error))
        return
    if outcome.announcement:
        await card.announce(guild, record, outcome.announcement)
    await _reply(interaction, outcome.reply)


async def manifest_for_thread(cog, interaction: discord.Interaction) -> Record | None:
    manifest_id = await store.get_by_thread(cog.bot.state, interaction.channel.id)
    record = (
        await store.get_record(cog.bot.state, interaction.guild.id, manifest_id) if manifest_id is not None else None
    )
    if record is None:
        await interaction.response.send_message("This manifest is no longer tracked.", ephemeral=True)
    return record


def _require_edit(record: Record, interaction: discord.Interaction) -> None:
    if not ledger.can_edit(record, interaction.user.id, is_beacon_admin(interaction)):
        raise ManifestError(EDIT_REFUSAL)


async def _parse_draft(cog, draft: Draft) -> tuple[list[Record], list[Record]]:
    cargo = parsing.parse_cargo(draft.cargo_text)
    costs = parsing.parse_costs(draft.costs_text)
    return await pricing.resolve_cargo(cog.bot, cargo), costs


async def _offer_retry(cog, interaction: discord.Interaction, error: ManifestError, draft: Draft, editing=None):
    from .views import RetryView

    heading = "Couldn't save the manifest:" if editing else "Couldn't create the manifest:"
    await _reply(interaction, f"{heading}\n{error}", view=RetryView(cog, draft, editing=editing))


async def _publish(cog, guild: discord.Guild, record: Record):
    async with _id_lock(guild.id):
        record["id"] = await store.allocate_id(cog.bot.state, guild.id)
    async with _record_lock(guild.id, record["id"]):
        await store.save_record(cog.bot.state, record)
        if record["beacon_thread_id"] is not None:
            await store.set_by_beacon(cog.bot.state, record["beacon_thread_id"], record["id"])
        return await card.open_thread(cog, guild, record)


def _where(thread) -> str:
    return f": {thread.mention}" if thread is not None else f". {_NO_THREAD_HINT}"


async def _post_beacon_link(channel, record: Record) -> None:
    try:
        await channel.send(f"Cargo from this beacon is tracked on manifest #{record['id']}.")
    except discord.HTTPException:
        logger.info("Could not post the manifest link in beacon thread %s", getattr(channel, "id", "?"))


async def _create_locked(cog, interaction: discord.Interaction, draft: Draft, cargo, costs):
    if draft.beacon_thread_id is not None:
        existing = await store.get_by_beacon(cog.bot.state, draft.beacon_thread_id)
        if existing is not None:
            raise ManifestError(f"This beacon already has manifest #{existing}.")
    record = ledger.new_manifest(
        manifest_id=0,
        guild_id=interaction.guild.id,
        created_by=interaction.user.id,
        carrier_id=draft.carrier_id or interaction.user.id,
        crew_ids=draft.crew_ids,
        cargo=cargo,
        costs=costs,
        now=time.time(),
        beacon_thread_id=draft.beacon_thread_id,
    )
    thread = await _publish(cog, interaction.guild, record)
    return record, thread


async def handle_create(cog, interaction: discord.Interaction, draft: Draft) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        cargo, costs = await _parse_draft(cog, draft)
    except ManifestError as error:
        await _offer_retry(cog, interaction, error, draft)
        return
    try:
        if draft.beacon_thread_id is None:
            record, thread = await _create_locked(cog, interaction, draft, cargo, costs)
        else:
            async with lock_for(f"manifest:beacon:{draft.beacon_thread_id}"):
                record, thread = await _create_locked(cog, interaction, draft, cargo, costs)
    except ManifestError as error:
        await _reply(interaction, str(error))
        return
    if draft.beacon_thread_id is not None:
        await _post_beacon_link(interaction.channel, record)
    await _reply(interaction, f"Created manifest #{record['id']}{_where(thread)}")


async def handle_edit(cog, interaction: discord.Interaction, manifest_id: int, cargo_text: str, costs_text: str):
    await interaction.response.defer(ephemeral=True)
    draft = Draft(crew_ids=[], carrier_id=None, cargo_text=cargo_text, costs_text=costs_text)
    try:
        cargo, costs = await _parse_draft(cog, draft)
    except ManifestError as error:
        await _offer_retry(cog, interaction, error, draft, editing=manifest_id)
        return

    def change(record: Record) -> Outcome:
        _require_edit(record, interaction)
        ledger.replace_cargo(record, cargo)
        ledger.replace_costs(record, costs)
        return Outcome(f"Updated manifest #{record['id']}.")

    await run_change(cog, interaction, manifest_id, change, deferred=True)


def sale_announcement(record: Record, sale: Record) -> str:
    text = f"<@{sale['seller_id']}> sold {sale['scu']} SCU {sale['commodity']} for {sale['total']:,} aUEC."
    if sale["cost_recovered"]:
        text += f" {sale['cost_recovered']:,} went to costs."
    owed = [f"<@{p['user_id']}> {p['amount']:,}" for p in sale["payouts"] if not ledger.is_paid(p)]
    return f"{text} Owed: {', '.join(owed)}" if owed else text


async def handle_sell(cog, interaction: discord.Interaction, manifest_id: int, commodity: str, *, scu: int, total: int):
    is_admin = is_beacon_admin(interaction)

    def change(record: Record) -> Outcome:
        if not ledger.can_sell(record, interaction.user.id, is_admin):
            raise ManifestError(f"Only the carrier <@{record['carrier_id']}> or an officer can sell this cargo.")
        sale = ledger.record_sale(record, commodity, scu=scu, total=total, now=time.time())
        split = sale["total"] - sale["cost_recovered"]
        reply = f"Recorded sale {sale['id']}: {split:,} aUEC split"
        reply += f" after {sale['cost_recovered']:,} to costs." if sale["cost_recovered"] else "."
        return Outcome(reply, sale_announcement(record, sale))

    await run_change(cog, interaction, manifest_id, change)


async def handle_set_crew(cog, interaction: discord.Interaction, manifest_id: int, user_ids: list[int]) -> None:
    def change(record: Record) -> Outcome:
        _require_edit(record, interaction)
        before = set(ledger.crew_ids(record))
        ledger.set_crew(record, user_ids)
        added = tuple(user_id for user_id in ledger.crew_ids(record) if user_id not in before)
        return Outcome(f"Crew is now {_mentions(ledger.crew_ids(record))}.", new_members=added)

    await run_change(cog, interaction, manifest_id, change)


async def handle_set_carrier(cog, interaction: discord.Interaction, manifest_id: int, user_id: int) -> None:
    def change(record: Record) -> Outcome:
        _require_edit(record, interaction)
        was_crew = user_id in ledger.crew_ids(record)
        ledger.set_carrier(record, user_id)
        return Outcome(f"<@{user_id}> is now the carrier.", new_members=() if was_crew else (user_id,))

    await run_change(cog, interaction, manifest_id, change)


async def handle_set_weight(cog, interaction: discord.Interaction, manifest_id: int, user_id: int, weight: int):
    def change(record: Record) -> Outcome:
        _require_edit(record, interaction)
        ledger.set_weight(record, user_id, weight)
        return Outcome(f"<@{user_id}> now has weight {weight}. It applies to future sales.")

    await run_change(cog, interaction, manifest_id, change)


async def handle_mark_paid(cog, interaction: discord.Interaction, manifest_id: int, member_id: int | None) -> None:
    seller_filter = None if is_beacon_admin(interaction) else interaction.user.id

    def change(record: Record) -> Outcome:
        if seller_filter is not None and not ledger.owes(record, seller_filter):
            raise ManifestError(PAID_REFUSAL)
        count = ledger.mark_paid(record, member_id=member_id, seller_id=seller_filter, now=time.time())
        return Outcome(f"Marked {count} payout{'s' if count != 1 else ''} paid.")

    await run_change(cog, interaction, manifest_id, change)


async def handle_dispute(cog, interaction: discord.Interaction, manifest_id: int) -> None:
    def change(record: Record) -> Outcome:
        sellers = ledger.dispute(record, user_id=interaction.user.id, now=time.time())
        return Outcome(
            "Flagged your share as not received. The seller has been pinged.",
            f"<@{interaction.user.id}> says they haven't received their share from manifest #{record['id']}. "
            f"{_mentions(sellers)}, please check.",
        )

    await run_change(cog, interaction, manifest_id, change)


async def handle_undo(cog, interaction: discord.Interaction, manifest_id: int) -> None:
    is_admin = is_beacon_admin(interaction)

    def change(record: Record) -> Outcome:
        sale = ledger.undo_last_sale(record, user_id=interaction.user.id, is_admin=is_admin)
        return Outcome(
            f"Removed sale {sale['id']}. {sale['scu']} SCU {sale['commodity']} is back in the hold.",
            f"<@{interaction.user.id}> undid sale {sale['id']} ({sale['scu']} SCU {sale['commodity']}).",
        )

    await run_change(cog, interaction, manifest_id, change)


async def handle_list(cog, interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    records = await store.guild_records(cog.bot.state, interaction.guild.id)
    text = card.build_list(records, interaction.user.id, is_beacon_admin(interaction))
    await _reply(interaction, text, allowed_mentions=discord.AllowedMentions.none())


async def handle_owed(cog, interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    records = await store.guild_records(cog.bot.state, interaction.guild.id)
    await _reply(
        interaction, card.build_owed(records, interaction.user.id), allowed_mentions=discord.AllowedMentions.none()
    )


async def handle_delete(cog, interaction: discord.Interaction, manifest: str) -> None:
    from .views import ConfirmDeleteView

    await interaction.response.defer(ephemeral=True)
    manifest_id = parse_manifest_id(manifest)
    record = (
        await store.get_record(cog.bot.state, interaction.guild.id, manifest_id) if manifest_id is not None else None
    )
    if record is None:
        await _reply(interaction, f"Manifest {manifest} not found.")
        return
    if not ledger.can_delete(record):
        await _reply(
            interaction,
            f"Manifest #{record['id']} still has {ledger.owed_amount(record):,} aUEC owed. Settle it first.",
        )
        return
    await _reply(
        interaction,
        f"Delete manifest #{record['id']}? Its thread will be locked. This can't be undone.",
        view=ConfirmDeleteView(cog, interaction.guild.id, record["id"]),
    )


async def confirm_delete(cog, interaction: discord.Interaction, guild_id: int, manifest_id: int) -> None:
    await interaction.response.defer()
    async with _record_lock(guild_id, manifest_id):
        record = await store.get_record(cog.bot.state, guild_id, manifest_id)
        if record is None:
            await interaction.edit_original_response(content=f"Manifest #{manifest_id} is already gone.", view=None)
            return
        if not ledger.can_delete(record):
            await interaction.edit_original_response(
                content=f"Manifest #{manifest_id} has payouts owed again.", view=None
            )
            return
        await store.delete_record(cog.bot.state, record)
    await card.close_thread(interaction.guild, record)
    await interaction.edit_original_response(content=f"Deleted manifest #{manifest_id}.", view=None)


async def handle_config_channel(cog, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
    await store.set_config(cog.bot.state, interaction.guild.id, {"channel_id": channel.id})
    message = f"Manifest threads will be created in {channel.mention}."
    missing = card.missing_permissions(channel, interaction.guild.me)
    if missing:
        message += f" I'm missing these permissions there: {', '.join(missing)}."
    await interaction.response.send_message(message, ephemeral=True)


def _thread_link(record: Record) -> str:
    return f": <#{record['thread_id']}>" if record["thread_id"] is not None else "."


async def handle_new(cog, interaction: discord.Interaction) -> None:
    from .views import ManifestModal

    draft = Draft(crew_ids=[], carrier_id=interaction.user.id, cargo_text="", costs_text="")
    await interaction.response.send_modal(ManifestModal(cog, draft))


async def handle_beacon_button(cog, interaction: discord.Interaction) -> None:
    from .views import ManifestModal

    thread_id = interaction.channel.id
    beacon = await beacon_store.get_beacon(cog.bot.state, thread_id)
    if beacon is None or beacon["guild_id"] != interaction.guild.id:
        await interaction.response.send_message("This button only works in a beacon thread.", ephemeral=True)
        return
    existing = await store.get_by_beacon(cog.bot.state, thread_id)
    record = await store.get_record(cog.bot.state, interaction.guild.id, existing) if existing is not None else None
    if record is not None:
        await interaction.response.send_message(
            f"This beacon already has manifest #{record['id']}{_thread_link(record)}", ephemeral=True
        )
        return
    draft = Draft(
        crew_ids=[beacon["requester_id"], *beacon["members"]],
        carrier_id=interaction.user.id,
        cargo_text="",
        costs_text="",
        beacon_thread_id=thread_id,
    )
    await interaction.response.send_modal(ManifestModal(cog, draft))


async def manifest_autocomplete(cog, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    records = await store.guild_records(cog.bot.state, interaction.guild_id)
    needle = current.strip().lower()
    choices = []
    for record in reversed(records):
        commodities = ", ".join(line["commodity"] for line in record["cargo"])
        label = f"#{record['id']} {ledger.status(record).capitalize()} · {commodities}"
        if needle and needle not in label.lower():
            continue
        choices.append(app_commands.Choice(name=label[:MAX_CHOICE_LABEL], value=str(record["id"])))
        if len(choices) >= MAX_AUTOCOMPLETE_CHOICES:
            break
    return choices
