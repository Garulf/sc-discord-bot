from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.beacons.views import BeaconView, CommendView


def test_beacon_view_has_claim_and_close_buttons():
    view = BeaconView(MagicMock())
    assert view.timeout is None
    assert {item.custom_id for item in view.children} == {"beacons:claim", "beacons:close"}


def test_legacy_view_reuses_ticket_custom_ids():
    view = BeaconView(MagicMock(), legacy=True)
    assert {item.custom_id for item in view.children} == {"tickets:claim", "tickets:close"}


@pytest.mark.asyncio
async def test_beacon_buttons_delegate_to_lifecycle(monkeypatch):
    from src.commands.beacons import views as views_module

    claim = AsyncMock()
    close = AsyncMock()
    monkeypatch.setattr(views_module.lifecycle, "handle_join", claim)
    monkeypatch.setattr(views_module.lifecycle, "handle_close", close)
    cog = MagicMock()
    view = BeaconView(cog)
    interaction = MagicMock()
    await next(b for b in view.children if b.custom_id == "beacons:claim").callback(interaction)
    claim.assert_awaited_once_with(cog, interaction)
    await next(b for b in view.children if b.custom_id == "beacons:close").callback(interaction)
    close.assert_awaited_once_with(cog, interaction)


def test_join_button_label():
    view = BeaconView(MagicMock())
    button = next(b for b in view.children if b.custom_id == "beacons:claim")
    assert button.label == "Join"


def test_commend_view_has_single_commend_button():
    view = CommendView(MagicMock())
    assert view.timeout is None
    assert {item.custom_id for item in view.children} == {"beacons:commend"}
    button = view.children[0]
    assert button.label == "Commend responders"
    from discord import ButtonStyle

    assert button.style == ButtonStyle.success


@pytest.mark.asyncio
async def test_commend_button_delegates_to_lifecycle(monkeypatch):
    from src.commands.beacons import views as views_module

    commend = AsyncMock()
    monkeypatch.setattr(views_module.lifecycle, "handle_commend", commend)
    cog = MagicMock()
    view = CommendView(cog)
    interaction = MagicMock()
    await view.children[0].callback(interaction)
    commend.assert_awaited_once_with(cog, interaction)
