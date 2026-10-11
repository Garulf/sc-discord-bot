import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.site_sync import SiteSyncCog, SiteSyncConfig, member_payload, setup

GUILD_ID = 100


class FakeRole:
    def __init__(self, role_id: int) -> None:
        self.id = role_id

    def is_default(self) -> bool:
        return self.id == GUILD_ID

    def __eq__(self, other) -> bool:
        return isinstance(other, FakeRole) and other.id == self.id


class FakeGuild:
    def __init__(self, members, member_count=None, chunked=True) -> None:
        self.id = GUILD_ID
        self.members = members
        self.member_count = len(members) if member_count is None else member_count
        self.chunked = chunked
        self.chunk = AsyncMock()

    def get_member(self, member_id):
        return next((m for m in self.members if m.id == member_id), None)


HASH = "a" * 32


class FakeAsset:
    def __init__(self, key: str) -> None:
        self.key = key

    def __eq__(self, other) -> bool:
        return isinstance(other, FakeAsset) and other.key == self.key


def _member(member_id, *role_ids, name="Ghost", avatar=None, bot=False, guild_id=GUILD_ID):
    roles = [FakeRole(GUILD_ID), *(FakeRole(r) for r in role_ids)]
    return SimpleNamespace(
        id=member_id,
        roles=roles,
        display_name=name,
        avatar=FakeAsset(avatar) if avatar else None,
        bot=bot,
        guild=SimpleNamespace(id=guild_id),
    )


def _user(user_id, name="Ghost", avatar=None):
    return SimpleNamespace(id=user_id, display_name=name, avatar=FakeAsset(avatar) if avatar else None)


def _cog(guild=None):
    bot = MagicMock()
    bot.get_guild = MagicMock(return_value=guild)
    client = MagicMock()
    client.update_member = AsyncMock(return_value=1)
    client.remove_member = AsyncMock(return_value=1)
    client.sync_roster = AsyncMock(return_value=0)
    return SiteSyncCog(bot, client, GUILD_ID), client


def test_member_payload_sends_string_ids_without_everyone_role():
    payload = member_payload(_member(42, 7, 8, name="Nick", avatar=HASH))

    assert payload == {"id": "42", "roles": ["7", "8"], "name": "Nick", "avatar": HASH}


def test_member_payload_sends_null_avatar_when_member_has_none():
    assert member_payload(_member(42))["avatar"] is None


async def test_resync_sends_every_guild_member():
    guild = FakeGuild([_member(1, 7, name="A"), _member(2, name="B")])
    cog, client = _cog(guild)

    await cog.resync()

    client.sync_roster.assert_awaited_once_with(
        [
            {"id": "1", "roles": ["7"], "name": "A", "avatar": None},
            {"id": "2", "roles": [], "name": "B", "avatar": None},
        ]
    )


async def test_resync_leaves_out_bot_accounts():
    guild = FakeGuild([_member(1, 7), _member(2, 7, bot=True)])
    cog, client = _cog(guild)

    await cog.resync()

    assert [m["id"] for m in client.sync_roster.await_args.args[0]] == ["1"]


async def test_resync_loads_members_when_guild_is_not_chunked():
    guild = FakeGuild([_member(1)], chunked=False)
    cog, client = _cog(guild)

    await cog.resync()

    guild.chunk.assert_awaited_once()
    client.sync_roster.assert_awaited_once()


async def test_resync_skips_incomplete_member_list(caplog):
    guild = FakeGuild([_member(i) for i in range(5)], member_count=10)
    cog, client = _cog(guild)

    with caplog.at_level(logging.WARNING):
        await cog.resync()

    client.sync_roster.assert_not_awaited()
    assert "5 of 10" in caplog.text


async def test_resync_skips_when_bot_is_not_in_guild():
    cog, client = _cog(guild=None)

    await cog.resync()

    client.sync_roster.assert_not_awaited()


async def test_resync_logs_site_errors_instead_of_raising(caplog):
    cog, client = _cog(FakeGuild([_member(1)]))
    client.sync_roster.side_effect = RuntimeError("site down")

    with caplog.at_level(logging.ERROR):
        await cog.resync()

    assert "site down" in caplog.text


async def test_role_change_pushes_member():
    cog, client = _cog()
    after = _member(1, 7, name="A")

    await cog.on_member_update(_member(1, name="A"), after)

    client.update_member.assert_awaited_once_with({"id": "1", "roles": ["7"], "name": "A", "avatar": None})


async def test_nickname_change_pushes_member():
    cog, client = _cog()

    await cog.on_member_update(_member(1, name="Old"), _member(1, name="New"))

    client.update_member.assert_awaited_once()


async def test_avatar_change_pushes_member():
    cog, client = _cog()

    await cog.on_member_update(_member(1), _member(1, avatar=HASH))

    client.update_member.assert_awaited_once()


async def test_bot_account_change_is_ignored():
    cog, client = _cog()

    await cog.on_member_update(_member(1, bot=True), _member(1, 7, bot=True))

    client.update_member.assert_not_awaited()


async def test_unrelated_member_change_is_ignored():
    cog, client = _cog()

    await cog.on_member_update(_member(1, 7), _member(1, 7))

    client.update_member.assert_not_awaited()


async def test_member_change_in_other_guild_is_ignored():
    cog, client = _cog()

    await cog.on_member_update(_member(1, guild_id=999), _member(1, 7, guild_id=999))

    client.update_member.assert_not_awaited()


async def test_member_update_logs_site_errors_instead_of_raising(caplog):
    cog, client = _cog()
    client.update_member.side_effect = RuntimeError("site down")

    with caplog.at_level(logging.ERROR):
        await cog.on_member_update(_member(1), _member(1, 7))

    assert "site down" in caplog.text


async def test_global_name_change_pushes_guild_member():
    member = _member(1, 7, name="New")
    cog, client = _cog(FakeGuild([member]))

    await cog.on_user_update(_user(1, name="Old"), _user(1, name="New"))

    client.update_member.assert_awaited_once_with({"id": "1", "roles": ["7"], "name": "New", "avatar": None})


async def test_global_avatar_change_pushes_guild_member():
    member = _member(1, 7, avatar=HASH)
    cog, client = _cog(FakeGuild([member]))

    await cog.on_user_update(_user(1), _user(1, avatar=HASH))

    client.update_member.assert_awaited_once_with({"id": "1", "roles": ["7"], "name": "Ghost", "avatar": HASH})


async def test_unrelated_user_change_is_ignored():
    cog, client = _cog(FakeGuild([_member(1)]))

    await cog.on_user_update(_user(1, avatar=HASH), _user(1, avatar=HASH))

    client.update_member.assert_not_awaited()


async def test_user_change_outside_guild_is_ignored():
    cog, client = _cog(FakeGuild([]))

    await cog.on_user_update(_user(1, name="Old"), _user(1, name="New"))

    client.update_member.assert_not_awaited()


async def test_member_leaving_revokes_access():
    cog, client = _cog()

    await cog.on_member_remove(_member(1))

    client.remove_member.assert_awaited_once_with(1)


async def test_member_leaving_other_guild_is_ignored():
    cog, client = _cog()

    await cog.on_member_remove(_member(1, guild_id=999))

    client.remove_member.assert_not_awaited()


def test_config_requires_url_token_and_guild():
    assert SiteSyncConfig.from_env({"GOK_SITE_URL": "https://x", "GOK_SITE_TOKEN": "t"}) is None
    assert SiteSyncConfig.from_env({}) is None


def test_config_reads_env():
    env = {"GOK_SITE_URL": "https://x", "GOK_SITE_TOKEN": "t", "GOK_GUILD_ID": "100"}

    assert SiteSyncConfig.from_env(env) == SiteSyncConfig(url="https://x", token="t", guild_id=100)


async def test_setup_without_config_adds_no_cog(monkeypatch):
    for name in ("GOK_SITE_URL", "GOK_SITE_TOKEN", "GOK_GUILD_ID"):
        monkeypatch.delenv(name, raising=False)
    bot = MagicMock()
    bot.add_cog = AsyncMock()

    await setup(bot)

    bot.add_cog.assert_not_awaited()


async def test_setup_with_config_adds_cog(monkeypatch):
    monkeypatch.setenv("GOK_SITE_URL", "https://x")
    monkeypatch.setenv("GOK_SITE_TOKEN", "t")
    monkeypatch.setenv("GOK_GUILD_ID", "100")
    bot = MagicMock()
    bot.add_cog = AsyncMock()

    await setup(bot)

    bot.add_cog.assert_awaited_once()


@pytest.mark.parametrize("configured", [True, False])
def test_members_intent_follows_config(monkeypatch, configured):
    from src.bot import build_intents

    for name, value in {"GOK_SITE_URL": "https://x", "GOK_SITE_TOKEN": "t", "GOK_GUILD_ID": "100"}.items():
        if configured:
            monkeypatch.setenv(name, value)
        else:
            monkeypatch.delenv(name, raising=False)

    assert build_intents().members is configured
