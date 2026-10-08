from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord

from src.commands.manifest import ledger, views
from src.commands.manifest.handlers import Draft


def _record(crew=(2,), carrier=1, sales=0):
    record = ledger.new_manifest(
        manifest_id=3,
        guild_id=7,
        created_by=1,
        carrier_id=carrier,
        crew_ids=crew,
        cargo=[{"commodity": "Gold", "scu": 10, "est_price": None}, {"commodity": "Tin", "scu": 2, "est_price": None}],
        costs=[{"label": "Fuel", "amount": 5}],
        now=0.0,
    )
    for _ in range(sales):
        ledger.record_sale(record, "Tin", scu=1, total=100, now=1.0)
    return record


def _interaction(user_id=1, admin=False):
    interaction = MagicMock()
    interaction.user = MagicMock(spec=discord.Member)
    interaction.user.id = user_id
    interaction.user.guild_permissions.administrator = admin
    interaction.user.roles = []
    interaction.guild.get_member.return_value = None
    interaction.response.send_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    return interaction


def _labels(modal):
    return [item.text for item in modal.children]


def test_create_modal_has_people_and_text_fields():
    modal = views.ManifestModal(MagicMock(), Draft(crew_ids=[2, 3], carrier_id=1, cargo_text="", costs_text=""))
    assert modal.title == "New manifest"
    assert _labels(modal) == ["Crew", "Carrier", "Cargo", "Costs"]
    assert [value.id for value in modal.crew.default_values] == [2, 3]
    assert [value.id for value in modal.carrier.default_values] == [1]


def test_edit_modal_only_has_text_fields_prefilled():
    draft = Draft(crew_ids=[], carrier_id=None, cargo_text="Gold 5", costs_text="Fuel 1")
    modal = views.ManifestModal(MagicMock(), draft, editing=4)
    assert modal.title == "Edit manifest #4"
    assert _labels(modal) == ["Cargo", "Costs"]
    assert modal.cargo.default == "Gold 5"
    assert modal.costs.default == "Fuel 1"


def test_submitted_draft_skips_bots_and_keeps_beacon():
    draft = Draft(crew_ids=[], carrier_id=1, cargo_text="", costs_text="", beacon_thread_id=50)
    modal = views.ManifestModal(MagicMock(), draft)
    human, bot = SimpleNamespace(id=2, bot=False), SimpleNamespace(id=99, bot=True)
    modal.crew._values = [human, bot]
    modal.carrier._values = [bot]
    modal.cargo._value = "Gold 1"
    modal.costs._value = ""
    submitted = modal.submitted_draft()
    assert submitted.crew_ids == [2]
    assert submitted.carrier_id == 1
    assert submitted.beacon_thread_id == 50
    assert submitted.cargo_text == "Gold 1"


async def test_create_modal_submit_calls_handler(monkeypatch):
    create = AsyncMock()
    monkeypatch.setattr(views.handlers, "handle_create", create)
    modal = views.ManifestModal(MagicMock(), Draft(crew_ids=[], carrier_id=1, cargo_text="Gold 1", costs_text=""))
    await modal.on_submit(MagicMock())
    assert create.await_args.args[2].cargo_text == "Gold 1"


async def test_edit_modal_submit_calls_handler(monkeypatch):
    edit = AsyncMock()
    monkeypatch.setattr(views.handlers, "handle_edit", edit)
    modal = views.ManifestModal(
        MagicMock(), Draft(crew_ids=[], carrier_id=None, cargo_text="Gold 2", costs_text=""), editing=4
    )
    await modal.on_submit(MagicMock())
    assert edit.await_args.args[2:] == (4, "Gold 2", "")


def test_card_view_buttons():
    view = views.ManifestCardView(MagicMock())
    assert view.timeout is None
    assert [(item.custom_id, item.row) for item in view.children] == [
        ("manifest:sell", 0),
        ("manifest:edit", 0),
        ("manifest:crew", 0),
        ("manifest:paid", 1),
        ("manifest:dispute", 1),
        ("manifest:undo", 1),
    ]


def test_beacon_view_keeps_old_custom_id():
    view = views.CreateFromBeaconView(MagicMock())
    assert view.timeout is None
    assert [(item.custom_id, item.label) for item in view.children] == [("loot:log", "Create manifest")]


async def test_beacon_button_delegates(monkeypatch):
    handler = AsyncMock()
    monkeypatch.setattr(views.handlers, "handle_beacon_button", handler)
    cog, interaction = MagicMock(), MagicMock()
    await views.CreateFromBeaconView(cog).children[0].callback(interaction)
    handler.assert_awaited_once_with(cog, interaction)


async def test_card_button_delegates(monkeypatch):
    opener = AsyncMock()
    monkeypatch.setattr(views, "open_dispute", opener)
    cog, interaction = MagicMock(), MagicMock()
    button = next(b for b in views.ManifestCardView(cog).children if b.custom_id == "manifest:dispute")
    await button.callback(interaction)
    opener.assert_awaited_once_with(cog, interaction)


def _with_record(monkeypatch, record):
    monkeypatch.setattr(views.handlers, "manifest_for_thread", AsyncMock(return_value=record))


async def test_open_sell_lists_unsold(monkeypatch):
    record = _record(sales=2)
    _with_record(monkeypatch, record)
    interaction = _interaction(user_id=1)
    await views.open_sell(MagicMock(), interaction)
    view = interaction.response.send_message.await_args.kwargs["view"]
    assert [option.value for option in view.pick.options] == ["Gold"]


async def test_open_sell_refuses_crew(monkeypatch):
    _with_record(monkeypatch, _record())
    interaction = _interaction(user_id=2)
    await views.open_sell(MagicMock(), interaction)
    assert interaction.response.send_message.await_args.args[0].startswith("Only the carrier <@1>")


async def test_sell_modal_validates_numbers(monkeypatch):
    sell = AsyncMock()
    monkeypatch.setattr(views.handlers, "handle_sell", sell)
    modal = views.SellModal(MagicMock(), 3, "Gold", 10)
    assert modal.scu.default == "10"
    modal.scu._value = "4"
    modal.total._value = "1,000"
    await modal.on_submit(MagicMock())
    assert sell.await_args.kwargs == {"scu": 4, "total": 1000}
    bad = _interaction()
    modal.total._value = "lots"
    await modal.on_submit(bad)
    assert "whole numbers" in bad.response.send_message.await_args.args[0]


async def test_open_edit_prefills_from_record(monkeypatch):
    _with_record(monkeypatch, _record())
    interaction = _interaction(user_id=1)
    await views.open_edit(MagicMock(), interaction)
    modal = interaction.response.send_modal.await_args.args[0]
    assert modal.cargo.default == "Gold 10\nTin 2"
    assert modal.costs.default == "Fuel 5"


async def test_open_edit_and_crew_refuse_crew_member(monkeypatch):
    _with_record(monkeypatch, _record())
    for opener in (views.open_edit, views.open_crew):
        interaction = _interaction(user_id=2)
        await opener(MagicMock(), interaction)
        assert "Only the creator, the carrier or an officer" in interaction.response.send_message.await_args.args[0]


async def test_crew_panel_weight_flow(monkeypatch):
    record = _record()
    _with_record(monkeypatch, record)
    interaction = _interaction(user_id=1)
    await views.open_crew(MagicMock(), interaction)
    panel = interaction.response.send_message.await_args.kwargs["view"]
    assert [option.value for option in panel.member.options] == ["1", "2"]
    set_weight = AsyncMock()
    monkeypatch.setattr(views.handlers, "handle_set_weight", set_weight)
    early = _interaction()
    panel.weight._values = ["3"]
    await panel._weight_picked(early)
    assert "Pick a member first" in early.response.send_message.await_args.args[0]
    panel.member._values = ["2"]
    picked = _interaction()
    picked.response.defer = AsyncMock()
    await panel._member_picked(picked)
    await panel._weight_picked(_interaction())
    assert set_weight.await_args.args[2:] == (3, 2, 3)


async def test_open_mark_paid(monkeypatch):
    record = _record(sales=1)
    _with_record(monkeypatch, record)
    seller = _interaction(user_id=1)
    await views.open_mark_paid(MagicMock(), seller)
    view = seller.response.send_message.await_args.kwargs["view"]
    assert [option.value for option in view.pick.options] == ["all", "2"]
    crew = _interaction(user_id=2)
    await views.open_mark_paid(MagicMock(), crew)
    assert crew.response.send_message.await_args.args[0] == "Only whoever sold it or an officer can mark payouts paid."


async def test_open_undo(monkeypatch):
    _with_record(monkeypatch, _record())
    none = _interaction()
    await views.open_undo(MagicMock(), none)
    assert none.response.send_message.await_args.args[0] == "There are no sales to undo."
    _with_record(monkeypatch, _record(sales=1))
    asked = _interaction()
    await views.open_undo(MagicMock(), asked)
    assert asked.response.send_message.await_args.args[0] == "Undo sale 1 (1 SCU Tin for 100 aUEC)?"


async def test_untracked_thread_stops_openers(monkeypatch):
    _with_record(monkeypatch, None)
    for opener in (views.open_sell, views.open_edit, views.open_crew, views.open_mark_paid, views.open_undo):
        interaction = _interaction()
        await opener(MagicMock(), interaction)
        interaction.response.send_message.assert_not_awaited()
