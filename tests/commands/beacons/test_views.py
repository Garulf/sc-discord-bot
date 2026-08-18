from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.beacons.categories import CATEGORIES
from src.commands.beacons.views import BeaconView, PanelView


def test_panel_view_has_one_persistent_button_per_category():
    view = PanelView(MagicMock())
    assert view.timeout is None
    custom_ids = {item.custom_id for item in view.children}
    assert custom_ids == {f"beacons:panel:{key}" for key in CATEGORIES}


def test_beacon_view_has_claim_and_close_buttons():
    view = BeaconView(MagicMock())
    assert view.timeout is None
    assert {item.custom_id for item in view.children} == {"beacons:claim", "beacons:close"}


@pytest.mark.asyncio
async def test_panel_button_replies_with_command_mention():
    cog = MagicMock()
    cog.command_mention = MagicMock(return_value="/beacon medic")
    view = PanelView(cog)
    button = next(b for b in view.children if b.custom_id == "beacons:panel:medic")
    interaction = MagicMock()
    interaction.response.send_message = AsyncMock()
    await button.callback(interaction)
    msg = interaction.response.send_message.await_args.args[0]
    assert "/beacon medic" in msg
    assert interaction.response.send_message.await_args.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_beacon_buttons_delegate_to_lifecycle(monkeypatch):
    from src.commands.beacons import views as views_module

    claim = AsyncMock()
    close = AsyncMock()
    monkeypatch.setattr(views_module.lifecycle, "handle_claim", claim)
    monkeypatch.setattr(views_module.lifecycle, "handle_close", close)
    cog = MagicMock()
    view = BeaconView(cog)
    interaction = MagicMock()
    await next(b for b in view.children if b.custom_id == "beacons:claim").callback(interaction)
    claim.assert_awaited_once_with(cog, interaction)
    await next(b for b in view.children if b.custom_id == "beacons:close").callback(interaction)
    close.assert_awaited_once_with(cog, interaction)


def test_legacy_views_reuse_ticket_custom_ids():
    panel = PanelView(MagicMock(), legacy=True)
    assert {item.custom_id for item in panel.children} == {f"tickets:panel:{key}" for key in CATEGORIES}
    beacon = BeaconView(MagicMock(), legacy=True)
    assert {item.custom_id for item in beacon.children} == {"tickets:claim", "tickets:close"}
