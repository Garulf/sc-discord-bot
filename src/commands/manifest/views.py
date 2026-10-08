"""Manifest UI: the create/edit modal, persistent card and beacon buttons, and
the short-lived pickers and confirmations they open."""

from __future__ import annotations

import discord

from src.commands.beacons.lifecycle import is_beacon_admin

from . import handlers, ledger, parsing
from .handlers import Draft
from .ledger import Record

_PANEL_TIMEOUT = 600
_TEXT_LIMIT = 2000
_TITLE_LIMIT = 45


def _users(ids: list[int]) -> list[discord.Object]:
    return [discord.Object(id=user_id) for user_id in ids][: ledger.MAX_CREW]


def _humans(users) -> list[int]:
    return [user.id for user in users if not getattr(user, "bot", False)]


def _parse_amount(raw: str) -> int | None:
    digits = raw.strip().replace(",", "")
    return int(digits) if digits.isdecimal() else None


class ManifestModal(discord.ui.Modal):
    def __init__(self, cog, draft: Draft, *, editing: int | None = None) -> None:
        title = f"Edit manifest #{editing}" if editing is not None else "New manifest"
        super().__init__(title=title[:_TITLE_LIMIT])
        self._cog = cog
        self._draft = draft
        self._editing = editing
        self.crew = self.carrier = None
        if editing is None:
            self.crew = discord.ui.UserSelect(
                min_values=0,
                max_values=ledger.MAX_CREW,
                required=False,
                default_values=_users(draft.crew_ids),
            )
            self.add_item(
                discord.ui.Label(
                    text="Crew", description="Who shares the profit. You're always in.", component=self.crew
                )
            )
            self.carrier = discord.ui.UserSelect(
                min_values=0,
                max_values=1,
                required=False,
                default_values=_users([draft.carrier_id] if draft.carrier_id else []),
            )
            self.add_item(
                discord.ui.Label(
                    text="Carrier", description="Holds and sells the cargo. Defaults to you.", component=self.carrier
                )
            )
        self.cargo = discord.ui.TextInput(
            style=discord.TextStyle.paragraph,
            placeholder="Gold 96\nQuantanium 12 88000",
            default=draft.cargo_text or None,
            max_length=_TEXT_LIMIT,
        )
        self.add_item(
            discord.ui.Label(
                text="Cargo",
                description="One per line: commodity, SCU, optional est. price per SCU",
                component=self.cargo,
            )
        )
        self.costs = discord.ui.TextInput(
            style=discord.TextStyle.paragraph,
            placeholder="Fuel 20000\nCargo purchase 150000",
            default=draft.costs_text or None,
            required=False,
            max_length=_TEXT_LIMIT,
        )
        self.add_item(
            discord.ui.Label(
                text="Costs", description="Optional. One per line: what for, and aUEC", component=self.costs
            )
        )

    def submitted_draft(self) -> Draft:
        crew_ids = _humans(self.crew.values) if self.crew is not None else []
        carriers = _humans(self.carrier.values) if self.carrier is not None else []
        return Draft(
            crew_ids=crew_ids,
            carrier_id=carriers[0] if carriers else self._draft.carrier_id,
            cargo_text=self.cargo.value,
            costs_text=self.costs.value,
            beacon_thread_id=self._draft.beacon_thread_id,
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        draft = self.submitted_draft()
        if self._editing is not None:
            await handlers.handle_edit(self._cog, interaction, self._editing, draft.cargo_text, draft.costs_text)
        else:
            await handlers.handle_create(self._cog, interaction, draft)


class RetryView(discord.ui.View):
    def __init__(self, cog, draft: Draft, *, editing: int | None = None) -> None:
        super().__init__(timeout=_PANEL_TIMEOUT)
        self._cog = cog
        self._draft = draft
        self._editing = editing

    @discord.ui.button(label="Try again", style=discord.ButtonStyle.primary)
    async def retry(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.send_modal(ManifestModal(self._cog, self._draft, editing=self._editing))


class SellModal(discord.ui.Modal):
    def __init__(self, cog, manifest_id: int, commodity: str, unsold: int) -> None:
        super().__init__(title=f"Sell {commodity}"[:_TITLE_LIMIT])
        self._cog = cog
        self._manifest_id = manifest_id
        self._commodity = commodity
        self.scu = discord.ui.TextInput(label="SCU sold", default=str(unsold), max_length=9)
        self.total = discord.ui.TextInput(label="aUEC received", placeholder="260000", max_length=17)
        self.add_item(self.scu)
        self.add_item(self.total)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        scu = _parse_amount(self.scu.value)
        total = _parse_amount(self.total.value)
        if scu is None or total is None:
            await interaction.response.send_message("SCU and aUEC must be whole numbers.", ephemeral=True)
            return
        await handlers.handle_sell(self._cog, interaction, self._manifest_id, self._commodity, scu=scu, total=total)


class SellPickView(discord.ui.View):
    def __init__(self, cog, manifest_id: int, unsold: list[tuple[str, int]]) -> None:
        super().__init__(timeout=_PANEL_TIMEOUT)
        self._cog = cog
        self._manifest_id = manifest_id
        self._unsold = dict(unsold)
        self.pick = discord.ui.Select(
            placeholder="Commodity sold",
            options=[
                discord.SelectOption(label=f"{name} ({left} SCU left)"[:100], value=name[:100])
                for name, left in unsold[:25]
            ],
        )
        self.pick.callback = self._picked
        self.add_item(self.pick)

    async def _picked(self, interaction: discord.Interaction) -> None:
        commodity = self.pick.values[0]
        await interaction.response.send_modal(
            SellModal(self._cog, self._manifest_id, commodity, self._unsold.get(commodity, 0))
        )


def _member_label(guild: discord.Guild | None, user_id: int) -> str:
    member = guild.get_member(user_id) if guild is not None else None
    return member.display_name if member is not None else str(user_id)


class CrewPanel(discord.ui.View):
    def __init__(self, cog, record: Record, guild: discord.Guild | None) -> None:
        super().__init__(timeout=_PANEL_TIMEOUT)
        self._cog = cog
        self._manifest_id = record["id"]
        self._member_id: int | None = None
        self.crew = discord.ui.UserSelect(
            placeholder="Crew",
            min_values=0,
            max_values=ledger.MAX_CREW,
            default_values=_users(ledger.crew_ids(record)),
            row=0,
        )
        self.crew.callback = self._crew_changed
        self.carrier = discord.ui.UserSelect(
            placeholder="Carrier", default_values=_users([record["carrier_id"]]), row=1
        )
        self.carrier.callback = self._carrier_changed
        self.member = discord.ui.Select(
            placeholder="Member to weight",
            options=[
                discord.SelectOption(
                    label=f"{_member_label(guild, m['user_id'])} (×{m['weight']})"[:100], value=str(m["user_id"])
                )
                for m in record["crew"]
            ],
            row=2,
        )
        self.member.callback = self._member_picked
        self.weight = discord.ui.Select(
            placeholder="Weight",
            options=[discord.SelectOption(label=f"×{w}", value=str(w)) for w in range(1, ledger.MAX_WEIGHT + 1)],
            row=3,
        )
        self.weight.callback = self._weight_picked
        for item in (self.crew, self.carrier, self.member, self.weight):
            self.add_item(item)

    async def _crew_changed(self, interaction: discord.Interaction) -> None:
        await handlers.handle_set_crew(self._cog, interaction, self._manifest_id, _humans(self.crew.values))

    async def _carrier_changed(self, interaction: discord.Interaction) -> None:
        carriers = _humans(self.carrier.values)
        if not carriers:
            await interaction.response.send_message("Pick a person, not a bot.", ephemeral=True)
            return
        await handlers.handle_set_carrier(self._cog, interaction, self._manifest_id, carriers[0])

    async def _member_picked(self, interaction: discord.Interaction) -> None:
        self._member_id = int(self.member.values[0])
        await interaction.response.defer()

    async def _weight_picked(self, interaction: discord.Interaction) -> None:
        if self._member_id is None:
            await interaction.response.send_message("Pick a member first.", ephemeral=True)
            return
        await handlers.handle_set_weight(
            self._cog, interaction, self._manifest_id, self._member_id, int(self.weight.values[0])
        )


class MarkPaidView(discord.ui.View):
    def __init__(self, cog, manifest_id: int, members: list[tuple[int, str]]) -> None:
        super().__init__(timeout=_PANEL_TIMEOUT)
        self._cog = cog
        self._manifest_id = manifest_id
        options = [discord.SelectOption(label="Everyone", value="all")]
        options += [discord.SelectOption(label=label[:100], value=str(user_id)) for user_id, label in members[:24]]
        self.pick = discord.ui.Select(placeholder="Who did you pay?", options=options)
        self.pick.callback = self._picked
        self.add_item(self.pick)

    async def _picked(self, interaction: discord.Interaction) -> None:
        value = self.pick.values[0]
        member_id = None if value == "all" else int(value)
        await handlers.handle_mark_paid(self._cog, interaction, self._manifest_id, member_id)


class ConfirmUndoView(discord.ui.View):
    def __init__(self, cog, manifest_id: int, sale_id: int) -> None:
        super().__init__(timeout=60)
        self._cog = cog
        self._manifest_id = manifest_id
        self._sale_id = sale_id

    @discord.ui.button(label="Undo sale", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await handlers.handle_undo(self._cog, interaction, self._manifest_id, self._sale_id)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Kept the sale.", view=None)


class ConfirmDeleteView(discord.ui.View):
    def __init__(self, cog, guild_id: int, manifest_id: int) -> None:
        super().__init__(timeout=60)
        self._cog = cog
        self._guild_id = guild_id
        self._manifest_id = manifest_id

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await handlers.confirm_delete(self._cog, interaction, self._guild_id, self._manifest_id)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Kept the manifest.", view=None)


async def _refuse(interaction: discord.Interaction, message: str) -> None:
    await interaction.response.send_message(message, ephemeral=True)


async def open_sell(cog, interaction: discord.Interaction) -> None:
    record = await handlers.manifest_for_thread(cog, interaction)
    if record is None:
        return
    if not ledger.can_sell(record, interaction.user.id, is_beacon_admin(interaction)):
        await _refuse(interaction, f"Only the carrier <@{record['carrier_id']}> or an officer can sell this cargo.")
        return
    unsold = [
        (line["commodity"], ledger.unsold_scu(record, line))
        for line in record["cargo"]
        if ledger.unsold_scu(record, line) > 0
    ]
    if not unsold:
        await _refuse(interaction, "Everything on this manifest is sold.")
        return
    await interaction.response.send_message(
        "What did you sell?", view=SellPickView(cog, record["id"], unsold), ephemeral=True
    )


async def open_edit(cog, interaction: discord.Interaction) -> None:
    record = await handlers.manifest_for_thread(cog, interaction)
    if record is None:
        return
    if not ledger.can_edit(record, interaction.user.id, is_beacon_admin(interaction)):
        await _refuse(interaction, handlers.EDIT_REFUSAL)
        return
    draft = Draft(
        crew_ids=[],
        carrier_id=None,
        cargo_text=parsing.format_cargo(record["cargo"]),
        costs_text=parsing.format_costs(record["costs"]),
    )
    await interaction.response.send_modal(ManifestModal(cog, draft, editing=record["id"]))


async def open_crew(cog, interaction: discord.Interaction) -> None:
    record = await handlers.manifest_for_thread(cog, interaction)
    if record is None:
        return
    if not ledger.can_edit(record, interaction.user.id, is_beacon_admin(interaction)):
        await _refuse(interaction, handlers.EDIT_REFUSAL)
        return
    await interaction.response.send_message(
        "Change the crew, the carrier, or someone's weight. Changes save as you pick; weights apply to future sales.",
        view=CrewPanel(cog, record, interaction.guild),
        ephemeral=True,
    )


def _owed_members(record: Record, user_id: int, is_admin: bool) -> list[int]:
    if is_admin:
        return list(dict.fromkeys(payout["user_id"] for _, payout in ledger.unpaid(record)))
    return ledger.owes(record, user_id)


async def open_mark_paid(cog, interaction: discord.Interaction) -> None:
    record = await handlers.manifest_for_thread(cog, interaction)
    if record is None:
        return
    is_admin = is_beacon_admin(interaction)
    members = _owed_members(record, interaction.user.id, is_admin)
    if not members:
        sold_any = any(sale["seller_id"] == interaction.user.id for sale in record["sales"])
        await _refuse(
            interaction,
            "Nobody is waiting on a payout from you here." if sold_any or is_admin else handlers.PAID_REFUSAL,
        )
        return
    labels = [(user_id, _member_label(interaction.guild, user_id)) for user_id in members]
    await interaction.response.send_message(
        "Who did you pay?", view=MarkPaidView(cog, record["id"], labels), ephemeral=True
    )


async def open_dispute(cog, interaction: discord.Interaction) -> None:
    record = await handlers.manifest_for_thread(cog, interaction)
    if record is not None:
        await handlers.handle_dispute(cog, interaction, record["id"])


async def open_undo(cog, interaction: discord.Interaction) -> None:
    record = await handlers.manifest_for_thread(cog, interaction)
    if record is None:
        return
    if not record["sales"]:
        await _refuse(interaction, "There are no sales to undo.")
        return
    sale = record["sales"][-1]
    await interaction.response.send_message(
        f"Undo sale {sale['id']} ({sale['scu']} SCU {sale['commodity']} for {sale['total']:,} aUEC)?",
        view=ConfirmUndoView(cog, record["id"], sale["id"]),
        ephemeral=True,
    )


class _CardButton(discord.ui.Button):
    def __init__(self, cog, *, label: str, key: str, style: discord.ButtonStyle, row: int, opener) -> None:
        super().__init__(label=label, style=style, custom_id=f"manifest:{key}", row=row)
        self._cog = cog
        self._opener = opener

    async def callback(self, interaction: discord.Interaction) -> None:
        await self._opener(self._cog, interaction)


class ManifestCardView(discord.ui.View):
    def __init__(self, cog) -> None:
        super().__init__(timeout=None)
        buttons = [
            ("Sell", "sell", discord.ButtonStyle.success, 0, open_sell),
            ("Edit cargo & costs", "edit", discord.ButtonStyle.secondary, 0, open_edit),
            ("Crew & weights", "crew", discord.ButtonStyle.secondary, 0, open_crew),
            ("Mark paid", "paid", discord.ButtonStyle.primary, 1, open_mark_paid),
            ("Not received", "dispute", discord.ButtonStyle.secondary, 1, open_dispute),
            ("Undo last sale", "undo", discord.ButtonStyle.danger, 1, open_undo),
        ]
        for label, key, style, row, opener in buttons:
            self.add_item(_CardButton(cog, label=label, key=key, style=style, row=row, opener=opener))


class _CreateFromBeaconButton(discord.ui.Button):
    def __init__(self, cog) -> None:
        super().__init__(label="Create manifest", style=discord.ButtonStyle.success, custom_id="loot:log")
        self._cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await handlers.handle_beacon_button(self._cog, interaction)


class CreateFromBeaconView(discord.ui.View):
    def __init__(self, cog) -> None:
        super().__init__(timeout=None)
        self.add_item(_CreateFromBeaconButton(cog))
