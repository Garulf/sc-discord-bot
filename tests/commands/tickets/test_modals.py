from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.tickets.categories import CATEGORIES
from src.commands.tickets.modals import TicketModal

_LOCATION_KEYS = {"location", "route_from", "route_to"}


def test_modal_has_one_labeled_input_per_category_field():
    for key, category in CATEGORIES.items():
        modal = TicketModal(MagicMock(), key)
        labels = [item.text for item in modal.children]
        assert labels == [spec.label for spec in category.fields]


def test_modal_inputs_mirror_field_required_flags():
    for key, category in CATEGORIES.items():
        modal = TicketModal(MagicMock(), key)
        required = [item.component.required for item in modal.children]
        assert required == [spec.required for spec in category.fields]


def test_location_inputs_show_format_placeholder():
    for key, category in CATEGORIES.items():
        modal = TicketModal(MagicMock(), key)
        for spec, item in zip(category.fields, modal.children, strict=True):
            if spec.key in _LOCATION_KEYS:
                assert "Stanton:Hurston:Lorville" in item.component.placeholder


@pytest.mark.asyncio
async def test_submit_collects_stripped_values_and_opens_ticket(monkeypatch):
    from src.commands.tickets import modals as modals_module

    opened = AsyncMock()
    monkeypatch.setattr(modals_module, "open_ticket", opened)
    cog = MagicMock()
    modal = TicketModal(cog, "medic")
    values = {"location": " Stanton:Hurston:Lorville ", "tier": "T2", "notes": "   "}
    for item in modal.children:
        item.component._value = values[modal.field_key(item.component)]
    interaction = MagicMock()
    await modal.on_submit(interaction)
    opened.assert_awaited_once_with(
        cog, interaction, "medic", {"location": "Stanton:Hurston:Lorville", "tier": "T2"}
    )
