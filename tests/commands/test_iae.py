from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from src.commands.iae import CLOSES_AT, EVENT_URL, OPENS_AT, IaeCog, Phase, build_embed, phase_at

BEFORE = OPENS_AT - timedelta(minutes=20)
DURING = OPENS_AT + timedelta(days=3)
AFTER = CLOSES_AT + timedelta(hours=1)

OPENS_TS = int(OPENS_AT.timestamp())
CLOSES_TS = int(CLOSES_AT.timestamp())


def test_phase_is_upcoming_until_the_doors_open():
    assert phase_at(BEFORE) is Phase.UPCOMING
    assert phase_at(OPENS_AT - timedelta(seconds=1)) is Phase.UPCOMING


def test_phase_is_open_from_opening_until_closing():
    assert phase_at(OPENS_AT) is Phase.OPEN
    assert phase_at(CLOSES_AT - timedelta(seconds=1)) is Phase.OPEN


def test_phase_is_ended_from_closing_onwards():
    assert phase_at(CLOSES_AT) is Phase.ENDED
    assert phase_at(AFTER) is Phase.ENDED


def test_upcoming_embed_counts_down_to_the_opening():
    embed = build_embed(BEFORE)
    assert embed.title == "Countdown to IAE 2956"
    assert embed.url == EVENT_URL
    assert embed.description == f"Doors open <t:{OPENS_TS}:R>"


def test_open_embed_counts_down_to_the_closing():
    embed = build_embed(DURING)
    assert embed.title == "IAE 2956 is open"
    assert embed.description == f"Doors close <t:{CLOSES_TS}:R>"


def test_ended_embed_says_when_the_show_closed():
    embed = build_embed(AFTER)
    assert embed.title == "IAE 2956 has ended"
    assert embed.description == f"Doors closed <t:{CLOSES_TS}:R>"


@pytest.mark.parametrize("now", [BEFORE, DURING, AFTER])
def test_every_embed_lists_both_dates_in_the_viewers_time_zone(now):
    fields = {field.name: field.value for field in build_embed(now).fields}
    assert fields == {"Opens": f"<t:{OPENS_TS}:F>", "Closes": f"<t:{CLOSES_TS}:F>"}


def _cog(widgets: list[dict] | None = None) -> tuple[IaeCog, MagicMock]:
    bot = MagicMock()
    bot.state.get = AsyncMock(return_value=None)
    bot.state.set = AsyncMock()
    message = MagicMock()
    message.edit = AsyncMock()
    message.delete = AsyncMock()
    bot.get_partial_messageable.return_value.get_partial_message.return_value = message
    cog = IaeCog(bot)
    cog.widgets = widgets if widgets is not None else []
    return cog, message


def _widget(phase: Phase = Phase.UPCOMING, channel_id: int = 10, message_id: int = 20) -> dict:
    return {"channel_id": channel_id, "message_id": message_id, "phase": phase.value}


def _http_error(cls: type[discord.HTTPException], status: int) -> discord.HTTPException:
    return cls(MagicMock(status=status, reason="x"), "x")


async def test_refresh_leaves_a_widget_alone_while_its_phase_is_current():
    cog, message = _cog([_widget(Phase.UPCOMING)])
    await cog.refresh_widgets(BEFORE)
    message.edit.assert_not_awaited()
    cog.bot.state.set.assert_not_awaited()


async def test_refresh_edits_a_widget_when_the_doors_open():
    cog, message = _cog([_widget(Phase.UPCOMING)])
    await cog.refresh_widgets(DURING)
    cog.bot.get_partial_messageable.assert_called_once_with(10)
    cog.bot.get_partial_messageable.return_value.get_partial_message.assert_called_once_with(20)
    assert message.edit.await_args.kwargs["embed"].title == "IAE 2956 is open"
    assert cog.widgets == [_widget(Phase.OPEN)]
    cog.bot.state.set.assert_awaited_once_with("iae", {"widgets": [_widget(Phase.OPEN)]})


async def test_refresh_forgets_a_widget_once_it_shows_the_ended_state():
    cog, message = _cog([_widget(Phase.OPEN)])
    await cog.refresh_widgets(AFTER)
    assert message.edit.await_args.kwargs["embed"].title == "IAE 2956 has ended"
    assert cog.widgets == []
    cog.bot.state.set.assert_awaited_once_with("iae", {"widgets": []})


@pytest.mark.parametrize(("error", "status"), [(discord.NotFound, 404), (discord.Forbidden, 403)])
async def test_refresh_forgets_a_widget_it_can_no_longer_reach(error, status):
    cog, message = _cog([_widget(Phase.UPCOMING)])
    message.edit.side_effect = _http_error(error, status)
    await cog.refresh_widgets(DURING)
    assert cog.widgets == []
    cog.bot.state.set.assert_awaited_once()


async def test_refresh_retries_a_widget_after_a_transient_discord_error():
    cog, message = _cog([_widget(Phase.UPCOMING)])
    message.edit.side_effect = _http_error(discord.HTTPException, 500)
    await cog.refresh_widgets(DURING)
    assert cog.widgets == [_widget(Phase.UPCOMING)]
    cog.bot.state.set.assert_not_awaited()


def _interaction(channel_id: int = 10, message_id: int = 99) -> MagicMock:
    interaction = MagicMock()
    interaction.channel_id = channel_id
    interaction.response.send_message = AsyncMock()
    interaction.original_response = AsyncMock(return_value=MagicMock(id=message_id))
    return interaction


async def test_post_sends_the_widget_publicly_and_tracks_it():
    cog, _ = _cog()
    interaction = _interaction()
    await cog.post_widget(interaction, BEFORE)
    sent = interaction.response.send_message.await_args.kwargs
    assert sent["embed"].title == "Countdown to IAE 2956"
    assert "ephemeral" not in sent
    assert cog.widgets == [_widget(Phase.UPCOMING, message_id=99)]
    cog.bot.state.set.assert_awaited_once_with("iae", {"widgets": cog.widgets})


async def test_post_replaces_the_previous_widget_in_the_same_channel():
    cog, old_message = _cog([_widget(Phase.UPCOMING, message_id=20), _widget(Phase.UPCOMING, channel_id=11)])
    await cog.post_widget(_interaction(message_id=99), BEFORE)
    cog.bot.get_partial_messageable.return_value.get_partial_message.assert_called_once_with(20)
    old_message.delete.assert_awaited_once()
    assert cog.widgets == [_widget(Phase.UPCOMING, channel_id=11), _widget(Phase.UPCOMING, message_id=99)]


async def test_post_survives_a_previous_widget_that_is_already_gone():
    cog, old_message = _cog([_widget(Phase.UPCOMING, message_id=20)])
    old_message.delete.side_effect = _http_error(discord.NotFound, 404)
    await cog.post_widget(_interaction(message_id=99), BEFORE)
    assert cog.widgets == [_widget(Phase.UPCOMING, message_id=99)]


async def test_post_after_the_show_is_not_tracked():
    cog, _ = _cog()
    interaction = _interaction()
    await cog.post_widget(interaction, AFTER)
    assert interaction.response.send_message.await_args.kwargs["embed"].title == "IAE 2956 has ended"
    assert cog.widgets == []
    cog.bot.state.set.assert_not_awaited()


async def test_cog_load_restores_tracked_widgets():
    cog, _ = _cog()
    cog.bot.state.get = AsyncMock(return_value={"widgets": [_widget(Phase.OPEN)]})
    cog.refresh_loop = MagicMock()
    await cog.cog_load()
    assert cog.widgets == [_widget(Phase.OPEN)]
    cog.refresh_loop.start.assert_called_once()
