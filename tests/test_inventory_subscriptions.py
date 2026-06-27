import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_get_guild_subs_returns_default_when_missing():
    cog = MagicMock()
    cog.bot.state.get = AsyncMock(return_value=None)
    from src.commands.inventory.subscriptions import get_guild_subs
    result = await get_guild_subs(cog, 123)
    assert result == {"subscriptions": [], "notifications": []}


@pytest.mark.asyncio
async def test_get_guild_subs_returns_stored_value():
    cog = MagicMock()
    stored = {"subscriptions": [{"channel_id": 1, "message_id": 2}], "notifications": []}
    cog.bot.state.get = AsyncMock(return_value=stored)
    from src.commands.inventory.subscriptions import get_guild_subs
    result = await get_guild_subs(cog, 456)
    assert result["subscriptions"] == [{"channel_id": 1, "message_id": 2}]
