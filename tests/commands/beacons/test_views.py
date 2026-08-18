from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.beacons.views import BeaconView


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
