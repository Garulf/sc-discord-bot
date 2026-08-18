import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from src.commands.beacons import lifecycle
from src.commands.beacons.rules import STATUS_ACTIVE, STATUS_OPEN

THREAD_CONFIG = {"channel_id": 10, "mode": "thread", "panel_message_id": 11, "tag_ids": {}, "roles": {"medic": 5}}
FORUM_CONFIG = {
    "channel_id": 10,
    "mode": "forum",
    "panel_message_id": 11,
    "tag_ids": {"medic": 200, "open": 201, "closed": 202},
    "roles": {},
}


def _interaction(guild_id=1, user_id=42, channel_id=99, admin=False):
    interaction = MagicMock()
    interaction.guild.id = guild_id
    interaction.guild_id = guild_id
    interaction.user.id = user_id
    interaction.user.display_name = "Garulf"
    interaction.user.guild_permissions.administrator = admin
    interaction.user.roles = []
    interaction.channel.id = channel_id
    interaction.channel.send = AsyncMock()
    interaction.channel.edit = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.message.edit = AsyncMock()
    interaction.channel.guild = interaction.guild
    return interaction


@pytest.fixture
def make_cog(monkeypatch):
    def _make(config=None, beacon=None, open_beacon=None):
        cog = MagicMock()
        cog.bot.state = MagicMock()
        monkeypatch.setattr(lifecycle.store, "get_config", AsyncMock(return_value=config))
        monkeypatch.setattr(lifecycle.store, "set_config", AsyncMock())
        monkeypatch.setattr(lifecycle.store, "get_beacon", AsyncMock(return_value=beacon))
        monkeypatch.setattr(lifecycle.store, "get_open_beacon", AsyncMock(return_value=open_beacon))
        monkeypatch.setattr(lifecycle.store, "save_beacon", AsyncMock())
        monkeypatch.setattr(lifecycle.store, "set_open_beacon", AsyncMock())
        monkeypatch.setattr(lifecycle.store, "clear_open_beacon", AsyncMock())
        monkeypatch.setattr(lifecycle.store, "set_last_open", AsyncMock())
        monkeypatch.setattr(lifecycle.store, "add_rep", AsyncMock())
        return cog

    return _make


@pytest.mark.asyncio
async def test_open_rejects_malformed_location(make_cog):
    cog = make_cog(config=THREAD_CONFIG)
    interaction = _interaction()
    await lifecycle.open_beacon(cog, interaction, "medic", {"location": "a:b:c:d"})
    interaction.followup.send.assert_awaited_once()
    assert "system:planet:location" in interaction.followup.send.await_args.args[0]
    lifecycle.store.save_beacon.assert_not_awaited()


@pytest.mark.asyncio
async def test_open_rejects_duplicate(make_cog):
    cog = make_cog(config=THREAD_CONFIG, open_beacon=555)
    interaction = _interaction()
    await lifecycle.open_beacon(cog, interaction, "medic", {"location": "Stanton"})
    msg = interaction.followup.send.await_args.args[0]
    assert "555" in msg
    lifecycle.store.save_beacon.assert_not_awaited()


@pytest.mark.asyncio
async def test_open_requires_setup(make_cog):
    cog = make_cog(config=None)
    interaction = _interaction()
    await lifecycle.open_beacon(cog, interaction, "medic", {"location": "Stanton"})
    assert "setup" in interaction.followup.send.await_args.args[0]


@pytest.mark.asyncio
async def test_open_creates_thread_and_saves_state(make_cog):
    cog = make_cog(config=THREAD_CONFIG)
    interaction = _interaction()
    thread = MagicMock()
    thread.id = 777
    thread.send = AsyncMock()
    thread.add_user = AsyncMock()
    channel = MagicMock()
    channel.create_thread = AsyncMock(return_value=thread)
    interaction.guild.get_channel = MagicMock(return_value=channel)
    await lifecycle.open_beacon(cog, interaction, "medic", {"location": "Stanton:Hurston:Lorville"})
    channel.create_thread.assert_awaited_once()
    assert channel.create_thread.await_args.kwargs["type"] == discord.ChannelType.public_thread
    sent = thread.send.await_args
    assert "<@&5>" in sent.kwargs.get("content", "")
    lifecycle.store.save_beacon.assert_awaited_once()
    lifecycle.store.set_open_beacon.assert_awaited_once()
    thread.add_user.assert_awaited_once_with(interaction.user)


@pytest.mark.asyncio
async def test_open_defers_dropped_role_config_write_until_after_creation(make_cog):
    cog = make_cog(config=THREAD_CONFIG)
    interaction = _interaction()
    thread = MagicMock()
    thread.id = 778
    thread.send = AsyncMock()
    thread.add_user = AsyncMock()
    channel = MagicMock()
    channel.create_thread = AsyncMock(return_value=thread)
    interaction.guild.get_channel = MagicMock(return_value=channel)
    interaction.guild.get_role = MagicMock(return_value=None)
    await lifecycle.open_beacon(cog, interaction, "medic", {"location": "Stanton"})
    lifecycle.store.set_config.assert_awaited_once()
    lifecycle.store.save_beacon.assert_awaited_once()
    thread.send.assert_any_await(
        "The responder role mapped to Medical no longer exists and was unmapped. "
        "An admin can re-map it with `/beacon role`."
    )


@pytest.mark.asyncio
async def test_open_writes_no_state_on_http_exception(make_cog):
    import discord as discord_module

    cog = make_cog(config=THREAD_CONFIG)
    interaction = _interaction()
    channel = MagicMock()
    channel.create_thread = AsyncMock(side_effect=discord_module.HTTPException(MagicMock(status=500), "boom"))
    interaction.guild.get_channel = MagicMock(return_value=channel)
    interaction.guild.get_role = MagicMock(return_value=None)
    await lifecycle.open_beacon(cog, interaction, "medic", {"location": "Stanton"})
    lifecycle.store.set_config.assert_not_awaited()
    lifecycle.store.save_beacon.assert_not_awaited()
    lifecycle.store.set_open_beacon.assert_not_awaited()


@pytest.mark.asyncio
async def test_open_sets_activity_and_records_last_open(make_cog):
    cog = make_cog(config=THREAD_CONFIG)
    interaction = _interaction()
    thread = MagicMock()
    thread.id = 779
    thread.send = AsyncMock()
    thread.add_user = AsyncMock()
    channel = MagicMock()
    channel.create_thread = AsyncMock(return_value=thread)
    interaction.guild.get_channel = MagicMock(return_value=channel)
    await lifecycle.open_beacon(cog, interaction, "medic", {"location": "Stanton"})
    saved = lifecycle.store.save_beacon.await_args.args[2]
    assert saved["last_activity_at"] == saved["opened_at"]
    lifecycle.store.set_last_open.assert_awaited_once_with(
        cog.bot.state, interaction.guild.id, interaction.user.id, "medic", {"location": "Stanton"}
    )


@pytest.mark.asyncio
async def test_open_refreshes_board(make_cog, monkeypatch):
    cog = make_cog(config=THREAD_CONFIG)
    interaction = _interaction()
    thread = MagicMock()
    thread.id = 780
    thread.send = AsyncMock()
    thread.add_user = AsyncMock()
    channel = MagicMock()
    channel.create_thread = AsyncMock(return_value=thread)
    interaction.guild.get_channel = MagicMock(return_value=channel)
    refresh = AsyncMock()
    monkeypatch.setattr(lifecycle.board, "refresh_board", refresh)
    await lifecycle.open_beacon(cog, interaction, "medic", {"location": "Stanton"})
    refresh.assert_awaited_once_with(cog, interaction.guild)


def _open_beacon_record(**overrides):
    beacon = {
        "guild_id": 1,
        "category": "medic",
        "requester_id": 1,
        "members": [],
        "status": STATUS_OPEN,
        "opened_at": 100.0,
        "closed_at": None,
        "closed_by_id": None,
        "fields": {"location": "Stanton"},
        "last_activity_at": 100.0,
        "first_joined_at": None,
        "warned_at": None,
        "escalated_at": None,
        "voice_channel_id": None,
        "commended": False,
        "nudged": [],
    }
    beacon.update(overrides)
    return beacon


@pytest.mark.asyncio
async def test_join_adds_member_and_thread_membership(make_cog):
    cog = make_cog(beacon=_open_beacon_record())
    interaction = _interaction(user_id=2)
    interaction.channel.add_user = AsyncMock()
    await lifecycle.handle_join(cog, interaction)
    saved = lifecycle.store.save_beacon.await_args.args[2]
    assert saved["status"] == STATUS_ACTIVE
    assert saved["members"] == [2]
    interaction.channel.add_user.assert_awaited_once_with(interaction.user)
    interaction.message.edit.assert_awaited_once()
    interaction.channel.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_second_responder_can_join(make_cog):
    cog = make_cog(beacon=_open_beacon_record(status=STATUS_ACTIVE, members=[2]))
    interaction = _interaction(user_id=3)
    interaction.channel.add_user = AsyncMock()
    await lifecycle.handle_join(cog, interaction)
    saved = lifecycle.store.save_beacon.await_args.args[2]
    assert saved["members"] == [2, 3]
    assert saved["status"] == STATUS_ACTIVE


@pytest.mark.asyncio
async def test_join_again_leaves_and_reopens_when_last_member(make_cog):
    cog = make_cog(beacon=_open_beacon_record(status=STATUS_ACTIVE, members=[2]))
    interaction = _interaction(user_id=2)
    interaction.channel.remove_user = AsyncMock()
    await lifecycle.handle_join(cog, interaction)
    saved = lifecycle.store.save_beacon.await_args.args[2]
    assert saved["members"] == []
    assert saved["status"] == STATUS_OPEN
    interaction.channel.remove_user.assert_awaited_once_with(interaction.user)


@pytest.mark.asyncio
async def test_requester_cannot_join_own_beacon(make_cog):
    cog = make_cog(beacon=_open_beacon_record())
    interaction = _interaction(user_id=1)
    await lifecycle.handle_join(cog, interaction)
    lifecycle.store.save_beacon.assert_not_awaited()
    assert interaction.followup.send.await_args.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_join_records_first_join_and_activity(make_cog):
    cog = make_cog(beacon=_open_beacon_record())
    interaction = _interaction(user_id=2)
    interaction.channel.add_user = AsyncMock()
    await lifecycle.handle_join(cog, interaction)
    saved = lifecycle.store.save_beacon.await_args.args[2]
    assert saved["first_joined_at"] is not None
    assert saved["last_activity_at"] >= saved["first_joined_at"] - 1


@pytest.mark.asyncio
async def test_join_announces_party_full(make_cog):
    record = _open_beacon_record(category="squad", members=[2], status="active")
    record["fields"] = {"location": "Stanton", "size": "2"}
    cog = make_cog(beacon=record)
    interaction = _interaction(user_id=3)
    interaction.channel.add_user = AsyncMock()
    await lifecycle.handle_join(cog, interaction)
    sends = [c.args[0] for c in interaction.channel.send.await_args_list]
    assert any("full" in s.lower() for s in sends)


@pytest.mark.asyncio
async def test_join_creates_voice_channel_when_enabled(make_cog):
    config = dict(THREAD_CONFIG, settings={"voice": True})
    cog = make_cog(config=config, beacon=_open_beacon_record())
    interaction = _interaction(user_id=2)
    interaction.channel.add_user = AsyncMock()
    interaction.channel.name = "[Medical] Garulf"
    voice = MagicMock()
    voice.id = 555
    voice.mention = "<#555>"
    interaction.guild.create_voice_channel = AsyncMock(return_value=voice)
    beacon_channel = MagicMock()
    interaction.guild.get_channel = MagicMock(return_value=beacon_channel)
    await lifecycle.handle_join(cog, interaction)
    interaction.guild.create_voice_channel.assert_awaited_once()
    saved = lifecycle.store.save_beacon.await_args.args[2]
    assert saved["voice_channel_id"] == 555


@pytest.mark.asyncio
async def test_leave_updates_activity(make_cog):
    cog = make_cog(beacon=_open_beacon_record(status=STATUS_ACTIVE, members=[2], last_activity_at=1.0))
    interaction = _interaction(user_id=2)
    interaction.channel.remove_user = AsyncMock()
    await lifecycle.handle_join(cog, interaction)
    saved = lifecycle.store.save_beacon.await_args.args[2]
    assert saved["last_activity_at"] > 1.0


@pytest.mark.asyncio
async def test_member_can_close(make_cog):
    cog = make_cog(config=THREAD_CONFIG, beacon=_open_beacon_record(status=STATUS_ACTIVE, members=[2]))
    interaction = _interaction(user_id=2)
    await lifecycle.handle_close(cog, interaction)
    saved = lifecycle.store.save_beacon.await_args.args[2]
    assert saved["status"] == "closed"
    assert saved["closed_by_id"] == 2


@pytest.mark.asyncio
async def test_close_archives_and_clears_index(make_cog):
    cog = make_cog(config=THREAD_CONFIG, beacon=_open_beacon_record())
    interaction = _interaction(user_id=1)
    await lifecycle.handle_close(cog, interaction)
    saved = lifecycle.store.save_beacon.await_args.args[2]
    assert saved["status"] == "closed"
    assert saved["closed_by_id"] == 1
    lifecycle.store.clear_open_beacon.assert_awaited_once()
    interaction.channel.edit.assert_awaited_once()
    interaction.channel.send.assert_awaited_once()
    assert "<@1>" in interaction.channel.send.await_args.args[0]


@pytest.mark.asyncio
async def test_close_posts_commend_prompt_and_deletes_voice(make_cog):
    record = _open_beacon_record(status="active", members=[2])
    record["voice_channel_id"] = 555
    cog = make_cog(config=THREAD_CONFIG, beacon=record)
    interaction = _interaction(user_id=1)
    voice = MagicMock()
    voice.delete = AsyncMock()
    interaction.guild.get_channel = MagicMock(return_value=voice)
    await lifecycle.handle_close(cog, interaction)
    sends = " ".join(c.args[0] for c in interaction.channel.send.await_args_list if c.args)
    kw_views = [c.kwargs.get("view") for c in interaction.channel.send.await_args_list]
    assert any(v is not None for v in kw_views)
    voice.delete.assert_awaited_once()
    assert "closed" in sends.lower()


@pytest.mark.asyncio
async def test_close_by_none_announces_automatic_closure(make_cog):
    record = _open_beacon_record(status=STATUS_ACTIVE, members=[])
    cog = make_cog(config=THREAD_CONFIG, beacon=record)
    channel = MagicMock()
    channel.id = 99
    channel.send = AsyncMock()
    channel.edit = AsyncMock()
    await lifecycle.close_beacon(cog, channel, record, None)
    sent = channel.send.await_args_list[0].args[0]
    assert "automatically closed" in sent.lower()


@pytest.mark.asyncio
async def test_close_edits_message_and_disables_buttons_before_archiving(make_cog, monkeypatch):
    cog = make_cog(config=THREAD_CONFIG, beacon=_open_beacon_record(status=STATUS_ACTIVE, members=[2]))
    interaction = _interaction(user_id=1)
    calls = []

    async def record_message_edit(**kwargs):
        calls.append("message_edit")

    async def record_channel_edit(**kwargs):
        calls.append("channel_edit")

    interaction.message.edit = AsyncMock(side_effect=record_message_edit)
    interaction.channel.edit = AsyncMock(side_effect=record_channel_edit)
    fake_view = discord.ui.View()
    fake_view.add_item(discord.ui.Button(label="Join"))
    monkeypatch.setattr(discord.ui.View, "from_message", lambda message, **kwargs: fake_view)
    await lifecycle.handle_close(cog, interaction)
    assert calls
    assert calls.index("message_edit") < calls.index("channel_edit")
    assert interaction.message.edit.await_count == 2


@pytest.mark.asyncio
async def test_close_survives_failed_announcement_and_still_archives(make_cog):
    cog = make_cog(config=THREAD_CONFIG, beacon=_open_beacon_record(status=STATUS_ACTIVE, members=[2]))
    interaction = _interaction(user_id=1)
    interaction.channel.send = AsyncMock(side_effect=discord.HTTPException(MagicMock(status=500), "boom"))
    await lifecycle.handle_close(cog, interaction)
    interaction.channel.edit.assert_awaited_once()
    lifecycle.store.clear_open_beacon.assert_awaited_once()
    interaction.followup.send.assert_awaited_with("Beacon closed.", ephemeral=True)


@pytest.mark.asyncio
async def test_close_refreshes_board(make_cog, monkeypatch):
    cog = make_cog(config=THREAD_CONFIG, beacon=_open_beacon_record())
    refresh = AsyncMock()
    monkeypatch.setattr(lifecycle.board, "refresh_board", refresh)
    interaction = _interaction(user_id=1)
    await lifecycle.handle_close(cog, interaction)
    refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_commend_adds_rep_once(make_cog, monkeypatch):
    record = _open_beacon_record(status="closed", members=[2, 3])
    cog = make_cog(beacon=record)
    add_rep = AsyncMock()
    monkeypatch.setattr(lifecycle.store, "add_rep", add_rep)
    interaction = _interaction(user_id=1)
    await lifecycle.handle_commend(cog, interaction)
    assert add_rep.await_count == 2
    saved = lifecycle.store.save_beacon.await_args.args[2]
    assert saved["commended"] is True

    cog = make_cog(beacon=dict(record, commended=True))
    add_rep.reset_mock()
    interaction = _interaction(user_id=1)
    await lifecycle.handle_commend(cog, interaction)
    add_rep.assert_not_awaited()


@pytest.mark.asyncio
async def test_commend_survives_failed_announcement(make_cog):
    record = _open_beacon_record(status="closed", members=[2])
    cog = make_cog(beacon=record)
    interaction = _interaction(user_id=1)
    interaction.channel.send = AsyncMock(side_effect=discord.HTTPException(MagicMock(status=500), "boom"))
    await lifecycle.handle_commend(cog, interaction)
    saved = lifecycle.store.save_beacon.await_args.args[2]
    assert saved["commended"] is True
    interaction.followup.send.assert_awaited_with("Commended the responders.", ephemeral=True)


@pytest.mark.asyncio
async def test_commend_requires_requester_or_admin(make_cog):
    record = _open_beacon_record(status="closed", members=[2])
    cog = make_cog(beacon=record)
    interaction = _interaction(user_id=99)
    await lifecycle.handle_commend(cog, interaction)
    lifecycle.store.add_rep.assert_not_awaited()
    lifecycle.store.save_beacon.assert_not_awaited()


@pytest.mark.asyncio
async def test_commend_refuses_when_no_members(make_cog):
    record = _open_beacon_record(status="closed", members=[])
    cog = make_cog(beacon=record)
    interaction = _interaction(user_id=1)
    await lifecycle.handle_commend(cog, interaction)
    lifecycle.store.add_rep.assert_not_awaited()


@pytest.mark.asyncio
async def test_untracked_beacon_button_replies_ephemerally(make_cog, monkeypatch):
    cog = make_cog(beacon=None)
    interaction = _interaction()
    fake_view = discord.ui.View()
    fake_view.add_item(discord.ui.Button(label="Join"))
    monkeypatch.setattr(discord.ui.View, "from_message", lambda message, **kwargs: fake_view)
    await lifecycle.handle_join(cog, interaction)
    assert "no longer tracked" in interaction.followup.send.await_args.args[0]
    assert fake_view.children[0].disabled is True
    interaction.message.edit.assert_awaited_once_with(view=fake_view)
    assert interaction.message.edit.await_args.kwargs["view"] is not cog.beacon_view


@pytest.mark.asyncio
async def test_open_forum_mode_applies_tags_and_saves_thread(make_cog):
    cog = make_cog(config=FORUM_CONFIG)
    interaction = _interaction()
    thread = MagicMock()
    thread.id = 900
    thread.send = AsyncMock()
    thread.add_user = AsyncMock()
    created = MagicMock()
    created.thread = thread
    channel = MagicMock(spec=discord.ForumChannel)
    channel.create_thread = AsyncMock(return_value=created)
    medic_tag = MagicMock()
    open_tag = MagicMock()
    tags_by_id = {200: medic_tag, 201: open_tag}
    channel.get_tag = MagicMock(side_effect=lambda tag_id: tags_by_id.get(tag_id))
    interaction.guild.get_channel = MagicMock(return_value=channel)
    await lifecycle.open_beacon(cog, interaction, "medic", {"location": "Stanton"})
    channel.create_thread.assert_awaited_once()
    applied_tags = channel.create_thread.await_args.kwargs["applied_tags"]
    assert medic_tag in applied_tags
    assert open_tag in applied_tags
    lifecycle.store.save_beacon.assert_awaited_once()
    assert lifecycle.store.save_beacon.await_args.args[1] == 900


@pytest.mark.asyncio
async def test_concurrent_joins_keep_both_members(monkeypatch):
    beacon_state = {99: _open_beacon_record(requester_id=1)}

    async def fake_get_beacon(state, channel_id):
        await asyncio.sleep(0)
        return dict(beacon_state[channel_id])

    async def fake_save_beacon(state, channel_id, beacon):
        await asyncio.sleep(0)
        beacon_state[channel_id] = beacon

    monkeypatch.setattr(lifecycle.store, "get_beacon", fake_get_beacon)
    monkeypatch.setattr(lifecycle.store, "save_beacon", fake_save_beacon)
    monkeypatch.setattr(lifecycle.store, "get_config", AsyncMock(return_value=None))

    cog = MagicMock()
    cog.bot.state = MagicMock()
    interaction_a = _interaction(user_id=2, channel_id=99)
    interaction_a.channel.add_user = AsyncMock()
    interaction_b = _interaction(user_id=3, channel_id=99)
    interaction_b.channel.add_user = AsyncMock()

    await asyncio.gather(
        lifecycle.handle_join(cog, interaction_a),
        lifecycle.handle_join(cog, interaction_b),
    )

    joined = beacon_state[99]
    assert joined["status"] == STATUS_ACTIVE
    assert sorted(joined["members"]) == [2, 3]


@pytest.mark.asyncio
async def test_open_rejects_malformed_destination(make_cog):
    cog = make_cog(config=THREAD_CONFIG)
    interaction = _interaction()
    await lifecycle.open_beacon(cog, interaction, "escort", {"location": "Stanton", "destination": "a:b:c:d"})
    msg = interaction.followup.send.await_args.args[0]
    assert "system:planet:location" in msg
    lifecycle.store.save_beacon.assert_not_awaited()


def _thread_message(author_id=5, channel_id=99, bot=False, admin=False):
    message = MagicMock()
    message.guild = MagicMock()
    message.author.id = author_id
    message.author.bot = bot
    message.author.guild_permissions.administrator = admin
    message.author.roles = []
    message.author.mention = f"<@{author_id}>"
    message.channel = MagicMock(spec=discord.Thread)
    message.channel.id = channel_id
    message.channel.send = AsyncMock()
    return message


@pytest.mark.asyncio
async def test_outsider_message_gets_a_join_nudge_once(make_cog):
    cog = make_cog(beacon=_open_beacon_record(status=STATUS_ACTIVE, members=[2]))
    message = _thread_message(author_id=5)
    await lifecycle.handle_thread_message(cog, message)
    message.channel.send.assert_awaited_once()
    assert "<@5>" in message.channel.send.await_args.args[0]
    saved = lifecycle.store.save_beacon.await_args.args[2]
    assert saved["nudged"] == [5]
    lifecycle.store.save_beacon.assert_awaited_once()


@pytest.mark.asyncio
async def test_thread_message_activity_and_nudge_write_once(make_cog):
    cog = make_cog(beacon=_open_beacon_record(status=STATUS_ACTIVE, members=[2], last_activity_at=1.0))
    message = _thread_message(author_id=5)
    await lifecycle.handle_thread_message(cog, message)
    lifecycle.store.save_beacon.assert_awaited_once()
    saved = lifecycle.store.save_beacon.await_args.args[2]
    assert saved["nudged"] == [5]
    assert saved["last_activity_at"] > 1.0


@pytest.mark.asyncio
async def test_already_nudged_user_is_not_nudged_again(make_cog):
    cog = make_cog(beacon=_open_beacon_record(status=STATUS_ACTIVE, members=[2], nudged=[5]))
    message = _thread_message(author_id=5)
    await lifecycle.handle_thread_message(cog, message)
    message.channel.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_members_requester_bots_and_admins_are_not_nudged(make_cog):
    for kwargs, record in (
        (dict(author_id=2), dict(status=STATUS_ACTIVE, members=[2])),
        (dict(author_id=1), dict()),
        (dict(author_id=5, bot=True), dict()),
        (dict(author_id=5, admin=True), dict()),
    ):
        cog = make_cog(beacon=_open_beacon_record(**record))
        message = _thread_message(**kwargs)
        await lifecycle.handle_thread_message(cog, message)
        message.channel.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_untracked_or_closed_threads_are_not_nudged(make_cog):
    cog = make_cog(beacon=None)
    message = _thread_message()
    await lifecycle.handle_thread_message(cog, message)
    message.channel.send.assert_not_awaited()

    cog = make_cog(beacon=_open_beacon_record(status="closed"))
    message = _thread_message()
    await lifecycle.handle_thread_message(cog, message)
    message.channel.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_member_message_updates_activity_but_no_nudge(make_cog):
    cog = make_cog(beacon=_open_beacon_record(status=STATUS_ACTIVE, members=[2], last_activity_at=1.0))
    message = _thread_message(author_id=2)
    await lifecycle.handle_thread_message(cog, message)
    message.channel.send.assert_not_awaited()
    saved = lifecycle.store.save_beacon.await_args.args[2]
    assert saved["last_activity_at"] > 1.0


@pytest.mark.asyncio
async def test_close_command_rejects_untracked_channel(make_cog):
    cog = make_cog(config=THREAD_CONFIG, beacon=None)
    interaction = _interaction()
    await lifecycle.handle_close_command(cog, interaction)
    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    assert interaction.followup.send.await_args.args[0] == "This channel is not a tracked beacon."
    lifecycle.store.save_beacon.assert_not_awaited()


@pytest.mark.asyncio
async def test_close_command_rejects_without_permission(make_cog):
    cog = make_cog(config=THREAD_CONFIG, beacon=_open_beacon_record(status=STATUS_ACTIVE, members=[2]))
    interaction = _interaction(user_id=99)
    await lifecycle.handle_close_command(cog, interaction)
    assert "close this beacon" in interaction.followup.send.await_args.args[0]
    lifecycle.store.save_beacon.assert_not_awaited()


@pytest.mark.asyncio
async def test_close_command_closes_and_confirms(make_cog):
    cog = make_cog(config=THREAD_CONFIG, beacon=_open_beacon_record(status=STATUS_ACTIVE, members=[2]))
    interaction = _interaction(user_id=2)
    await lifecycle.handle_close_command(cog, interaction)
    saved = lifecycle.store.save_beacon.await_args.args[2]
    assert saved["status"] == "closed"
    assert saved["closed_by_id"] == 2
    interaction.followup.send.assert_awaited_with("Beacon closed.", ephemeral=True)
    interaction.message.edit.assert_not_awaited()


@pytest.mark.asyncio
async def test_again_replies_when_no_previous_beacon(monkeypatch):
    monkeypatch.setattr(lifecycle.store, "get_last_open", AsyncMock(return_value=None))
    cog = MagicMock()
    cog.bot.state = MagicMock()
    interaction = _interaction()
    await lifecycle.handle_again(cog, interaction)
    interaction.response.send_message.assert_awaited_once_with("No previous beacon to repeat.", ephemeral=True)
    interaction.response.defer.assert_not_awaited()


@pytest.mark.asyncio
async def test_again_reopens_last_beacon(monkeypatch, make_cog):
    monkeypatch.setattr(
        lifecycle.store,
        "get_last_open",
        AsyncMock(return_value={"category": "medic", "fields": {"location": "Stanton"}}),
    )
    cog = make_cog(config=THREAD_CONFIG)
    interaction = _interaction()
    thread = MagicMock()
    thread.id = 900
    thread.send = AsyncMock()
    thread.add_user = AsyncMock()
    channel = MagicMock()
    channel.create_thread = AsyncMock(return_value=thread)
    interaction.guild.get_channel = MagicMock(return_value=channel)
    await lifecycle.handle_again(cog, interaction)
    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    lifecycle.store.save_beacon.assert_awaited_once()
    saved = lifecycle.store.save_beacon.await_args.args[2]
    assert saved["category"] == "medic"
    assert saved["fields"] == {"location": "Stanton"}


@pytest.mark.asyncio
async def test_activity_update_is_throttled_within_60_seconds(make_cog):
    now = time.time()
    cog = make_cog(beacon=_open_beacon_record(status=STATUS_ACTIVE, members=[2], last_activity_at=now))
    message = _thread_message(author_id=2)
    await lifecycle.handle_thread_message(cog, message)
    lifecycle.store.save_beacon.assert_not_awaited()
