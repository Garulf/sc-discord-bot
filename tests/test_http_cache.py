"""Unit tests for the shared in-memory HTTP cache."""

from src.http_cache import TTLCache, cache_key


class TestTTLCacheGetSet:
    async def test_set_then_get_returns_value(self):
        cache = TTLCache(ttl=100)
        await cache.set("k", "v")
        assert await cache.get("k") == "v"

    async def test_missing_key_returns_none(self):
        assert await TTLCache().get("absent") is None

    async def test_expired_entry_returns_none(self):
        cache = TTLCache()
        await cache.set("k", "v", ttl=-1)  # already expired
        assert await cache.get("k") is None

    async def test_per_call_ttl_overrides_default(self):
        cache = TTLCache(ttl=0)
        await cache.set("k", "v", ttl=100)
        assert await cache.get("k") == "v"


class TestTTLCacheLocks:
    def test_same_key_returns_same_lock(self):
        cache = TTLCache()
        assert cache.lock("k") is cache.lock("k")

    def test_different_keys_return_different_locks(self):
        cache = TTLCache()
        assert cache.lock("a") is not cache.lock("b")


class TestTTLCacheClear:
    async def test_clear_drops_all_entries(self):
        cache = TTLCache(ttl=100)
        await cache.set("a", 1)
        await cache.set("b", 2)
        await cache.clear()
        assert await cache.get("a") is None
        assert await cache.get("b") is None


class TestCacheKey:
    def test_no_params_is_just_the_path(self):
        assert cache_key("things", None) == "things"
        assert cache_key("things", {}) == "things"

    def test_params_are_appended_sorted(self):
        assert cache_key("things", {"b": 2, "a": 1}) == "things?a=1&b=2"

    def test_key_is_independent_of_insertion_order(self):
        assert cache_key("p", {"x": 1, "y": 2}) == cache_key("p", {"y": 2, "x": 1})
