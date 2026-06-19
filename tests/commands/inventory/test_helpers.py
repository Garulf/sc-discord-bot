"""Unit tests for src.commands.inventory.shared — pure inventory helpers."""

from src.commands.inventory.shared import (
    ITEMS,
    complete_sets,
    embed_color,
    format_field,
    format_mine,
    guild_key,
)

_ALL_ONE = {item: 1 for item in ITEMS}
_ALL_TWO = {item: 2 for item in ITEMS}
_EMPTY: dict[str, int] = {}


class TestGuildKey:
    def test_includes_guild_id(self):
        assert "12345" in guild_key(12345)

    def test_different_guilds_produce_different_keys(self):
        assert guild_key(1) != guild_key(2)

    def test_format_is_prefixed(self):
        assert guild_key(99).startswith("inventory:")


class TestCompleteSets:
    def test_empty_inventory_is_zero(self):
        assert complete_sets(_EMPTY) == 0

    def test_one_of_each_item_is_one_set(self):
        assert complete_sets(_ALL_ONE) == 1

    def test_two_of_each_is_two_sets(self):
        assert complete_sets(_ALL_TWO) == 2

    def test_bottlenecked_by_lowest_count(self):
        inventory = {**_ALL_TWO, ITEMS[0]: 1}
        assert complete_sets(inventory) == 1

    def test_missing_one_item_means_zero_sets(self):
        partial = {item: 1 for item in ITEMS[1:]}
        assert complete_sets(partial) == 0


class TestEmbedColor:
    def test_empty_inventory_is_gray(self):
        assert embed_color(_EMPTY) == 0x99AAB5

    def test_partial_inventory_is_blurple(self):
        assert embed_color({ITEMS[0]: 1}) == 0x5865F2

    def test_complete_set_is_green(self):
        assert embed_color(_ALL_ONE) == 0x57F287

    def test_multiple_complete_sets_is_green(self):
        assert embed_color(_ALL_TWO) == 0x57F287


class TestFormatField:
    def test_owned_item_shows_checkmark(self):
        assert "✅" in format_field({ITEMS[0]: 1})

    def test_missing_item_shows_cross(self):
        assert "❌" in format_field(_EMPTY)

    def test_multiple_quantity_shows_count(self):
        result = format_field({ITEMS[0]: 3})
        assert "×3" in result

    def test_quantity_of_one_has_no_count_suffix(self):
        result = format_field({ITEMS[0]: 1})
        assert "×1" not in result

    def test_complete_sets_shown_as_trophy(self):
        result = format_field(_ALL_TWO)
        assert "🏆" in result
        assert "2 sets" in result

    def test_one_set_is_singular(self):
        result = format_field(_ALL_ONE)
        assert "1 set" in result
        assert "1 sets" not in result

    def test_no_complete_set_message_when_empty(self):
        assert "no complete set" in format_field(_EMPTY)

    def test_all_items_represented(self):
        result = format_field(_EMPTY)
        assert result.count("\n") == len(ITEMS)  # one line per item + footer


class TestFormatMine:
    def test_owned_item_is_bold(self):
        result = format_mine({ITEMS[0]: 1})
        assert f"**{ITEMS[0]}**" in result

    def test_missing_item_is_strikethrough(self):
        result = format_mine(_EMPTY)
        assert f"~~{ITEMS[0]}~~" in result

    def test_multiple_quantity_shows_count(self):
        result = format_mine({ITEMS[0]: 2})
        assert "×2" in result

    def test_single_quantity_has_no_count_suffix(self):
        result = format_mine({ITEMS[0]: 1})
        assert "×1" not in result

    def test_all_items_appear_in_output(self):
        result = format_mine(_EMPTY)
        for item in ITEMS:
            assert item in result
