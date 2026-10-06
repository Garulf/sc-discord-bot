import pytest

from src.commands.loot import ledger
from src.commands.loot.ledger import LootError


def _record(participants=(1, 2, 3, 4)):
    return ledger.new_record(
        loot_id=12,
        guild_id=7,
        title="Ruin gold grab",
        created_by=1,
        participants=list(participants),
        organizer_ids=[1],
        now=100.0,
    )


def _sell(record, commodity, *, user_id=1, **kwargs):
    return ledger.record_sale(record, ledger.resolve_line(record, commodity, user_id), **kwargs)


def test_new_record_shape():
    record = _record()
    assert record["id"] == 12
    assert record["guild_id"] == 7
    assert record["title"] == "Ruin gold grab"
    assert record["participants"] == [1, 2, 3, 4]
    assert record["organizer_ids"] == [1]
    assert record["cargo"] == []
    assert record["sales"] == []
    assert record["card"] is None
    assert record["beacon_thread_id"] is None
    assert record["category"] is None


def test_new_record_dedupes_participants_keeping_order():
    record = _record(participants=(3, 1, 3, 2, 1))
    assert record["participants"] == [3, 1, 2]


def test_new_record_requires_title():
    with pytest.raises(LootError):
        ledger.new_record(
            loot_id=1, guild_id=7, title="   ", created_by=1, participants=[1], organizer_ids=[1], now=0.0
        )


def test_normalize_fills_missing_fields():
    raw = {"id": 1, "guild_id": 7, "title": "t", "created_by": 5, "created_at": 0.0, "participants": [5]}
    record = ledger.normalize_loot(raw)
    assert record["organizer_ids"] == [5]
    assert record["cargo"] == []
    assert record["sales"] == []
    assert record["card"] is None
    assert record["beacon_thread_id"] is None


def test_add_cargo_creates_line_with_holder():
    record = _record()
    line = ledger.add_cargo(record, "Gold", 96, holder_id=2)
    assert line == {"commodity": "Gold", "scu": 96, "sold_scu": 0, "holder_id": 2}
    assert record["cargo"] == [line]


def test_add_cargo_merges_same_commodity_and_holder_case_insensitively():
    record = _record()
    ledger.add_cargo(record, "Gold", 50, holder_id=2)
    line = ledger.add_cargo(record, " gold ", 10, holder_id=2)
    assert len(record["cargo"]) == 1
    assert line["scu"] == 60
    assert line["holder_id"] == 2


def test_add_cargo_gives_each_holder_their_own_line():
    record = _record()
    ledger.add_cargo(record, "Gold", 50, holder_id=2)
    second = ledger.add_cargo(record, "gold", 10, holder_id=3)
    assert [(line["commodity"], line["scu"], line["holder_id"]) for line in record["cargo"]] == [
        ("Gold", 50, 2),
        ("Gold", 10, 3),
    ]
    assert second is record["cargo"][1]


@pytest.mark.parametrize("commodity,scu", [("", 5), ("Gold", 0), ("Gold", -1)])
def test_add_cargo_rejects_bad_input(commodity, scu):
    with pytest.raises(LootError):
        ledger.add_cargo(_record(), commodity, scu, holder_id=1)


def test_resolve_line_names_missing_commodity():
    with pytest.raises(LootError, match="Quantanium"):
        ledger.resolve_line(_record(), "Quantanium", 1)


def _split_gold_record():
    record = _record()
    ledger.add_cargo(record, "Gold", 50, holder_id=1)
    ledger.add_cargo(record, "Gold", 30, holder_id=2)
    return record


def test_resolve_line_prefers_the_callers_own_line():
    record = _split_gold_record()
    assert ledger.resolve_line(record, "gold", 2) is record["cargo"][1]
    assert ledger.resolve_line(record, "gold", 1) is record["cargo"][0]


def test_resolve_line_falls_back_to_the_only_line():
    record = _record()
    ledger.add_cargo(record, "Gold", 50, holder_id=1)
    assert ledger.resolve_line(record, "Gold", 99) is record["cargo"][0]


def test_resolve_line_with_several_holders_names_them():
    with pytest.raises(LootError) as error:
        ledger.resolve_line(_split_gold_record(), "Gold", 99)
    assert str(error.value) == "Raid #12 has Gold held by <@1> and <@2>. Ask the holder to run this."


def test_resolve_line_lists_three_holders():
    record = _split_gold_record()
    ledger.add_cargo(record, "Gold", 5, holder_id=3)
    with pytest.raises(LootError, match="<@1>, <@2> and <@3>"):
        ledger.resolve_line(record, "Gold", 99)


def test_split_returns_share_and_remainder():
    assert ledger.split(1_250_003, 4) == (312_500, 3)
    assert ledger.split(100, 3) == (33, 1)


def test_record_sale_splits_equally_and_auto_pays_holder():
    record = _record()
    ledger.add_cargo(record, "Gold", 96, holder_id=2)
    sale = _sell(record, "gold", scu=40, total=1_250_003, now=200.0)
    assert sale["id"] == 1
    assert sale["commodity"] == "Gold"
    assert sale["seller_id"] == 2
    assert sale["share"] == 312_500
    amounts = {p["user_id"]: p["amount"] for p in sale["payouts"]}
    assert amounts == {1: 312_500, 2: 312_500, 3: 312_500, 4: 312_500}
    paid = {p["user_id"] for p in sale["payouts"] if ledger.is_paid(p)}
    assert paid == {2}
    assert record["cargo"][0]["sold_scu"] == 40
    assert ledger.unsold_scu(record["cargo"][0]) == 56


def test_record_sale_sells_from_the_given_line_and_pays_its_holder():
    record = _split_gold_record()
    sale = _sell(record, "Gold", user_id=2, scu=10, total=400, now=1.0)
    assert sale["seller_id"] == 2
    assert [line["sold_scu"] for line in record["cargo"]] == [0, 10]


def test_record_sale_when_holder_is_not_on_the_crew_owes_everyone():
    record = _record(participants=(1, 3))
    ledger.add_cargo(record, "Gold", 10, holder_id=9)
    sale = _sell(record, "Gold", scu=10, total=1000, now=1.0)
    assert sale["seller_id"] == 9
    assert not any(ledger.is_paid(p) for p in sale["payouts"])
    assert ledger.owed_amount(record) == 1000


def test_sale_ids_increase():
    record = _record()
    ledger.add_cargo(record, "Gold", 96, holder_id=1)
    first = _sell(record, "Gold", scu=10, total=100, now=1.0)
    second = _sell(record, "Gold", scu=10, total=100, now=2.0)
    assert (first["id"], second["id"]) == (1, 2)


@pytest.mark.parametrize(
    "scu,total,match",
    [(0, 100, "greater than 0"), (97, 100, "Only 96 SCU"), (10, 0, "aUEC")],
)
def test_record_sale_validation(scu, total, match):
    record = _record()
    ledger.add_cargo(record, "Gold", 96, holder_id=1)
    with pytest.raises(LootError, match=match):
        _sell(record, "Gold", scu=scu, total=total, now=1.0)
    assert record["sales"] == []
    assert record["cargo"][0]["sold_scu"] == 0


def test_record_sale_needs_participants():
    record = _record(participants=())
    ledger.add_cargo(record, "Gold", 10, holder_id=1)
    with pytest.raises(LootError, match="participants"):
        _sell(record, "Gold", scu=5, total=100, now=1.0)


def test_status_progression():
    record = _record(participants=(1, 2))
    assert ledger.status(record) == ledger.STATUS_HOLDING
    ledger.add_cargo(record, "Gold", 10, holder_id=1)
    assert ledger.status(record) == ledger.STATUS_HOLDING
    sale = _sell(record, "Gold", scu=10, total=100, now=1.0)
    assert ledger.status(record) == ledger.STATUS_PAYING
    for payout in sale["payouts"]:
        payout["paid_at"] = 5.0
    assert ledger.status(record) == ledger.STATUS_SETTLED


def _sold_record():
    record = _record(participants=(1, 2, 3))
    ledger.add_cargo(record, "Gold", 30, holder_id=1)
    _sell(record, "Gold", scu=30, total=300, now=10.0)
    return record


def test_parse_mentions_handles_both_forms_and_dedupes():
    assert ledger.parse_mentions("<@11> <@!22> and <@11>, bob") == [11, 22]
    assert ledger.parse_mentions("bob alice") == []
    assert ledger.parse_mentions(None) == []


def test_line_permissions():
    line = {"commodity": "Gold", "scu": 1, "sold_scu": 0, "holder_id": 5}
    assert ledger.can_handle_line(line, 5, is_admin=False)
    assert not ledger.can_handle_line(line, 6, is_admin=False)
    assert ledger.can_handle_line(line, 6, is_admin=True)


def test_roster_permissions_cover_organizers_holders_and_admins():
    record = _record()
    ledger.add_cargo(record, "Gold", 1, holder_id=9)
    assert ledger.can_manage_roster(record, 1, is_admin=False)
    assert ledger.can_manage_roster(record, 9, is_admin=False)
    assert ledger.can_manage_roster(record, 50, is_admin=True)
    assert not ledger.can_manage_roster(record, 50, is_admin=False)


def test_add_and_remove_participant():
    record = _record(participants=(1,))
    ledger.add_participant(record, 2)
    assert record["participants"] == [1, 2]
    with pytest.raises(LootError, match="already"):
        ledger.add_participant(record, 2)
    ledger.remove_participant(record, 1)
    assert record["participants"] == [2]
    with pytest.raises(LootError, match="isn't on"):
        ledger.remove_participant(record, 1)


def test_cannot_join_settled_raid():
    record = _sold_record()
    ledger.mark_paid(record, member_id=None, seller_id=None, now=11.0)
    with pytest.raises(LootError, match="settled"):
        ledger.add_participant(record, 99)


def test_roster_change_only_affects_future_sales():
    record = _record(participants=(1, 2))
    ledger.add_cargo(record, "Gold", 20, holder_id=1)
    _sell(record, "Gold", scu=10, total=100, now=1.0)
    ledger.add_participant(record, 3)
    second = _sell(record, "Gold", scu=10, total=90, now=2.0)
    assert [p["user_id"] for p in record["sales"][0]["payouts"]] == [1, 2]
    assert [p["user_id"] for p in second["payouts"]] == [1, 2, 3]


def test_set_holder():
    record = _record()
    line = ledger.add_cargo(record, "Gold", 5, holder_id=1)
    assert ledger.set_holder(record, line, 4)["holder_id"] == 4


def test_set_holder_merges_into_the_new_holders_existing_line():
    record = _split_gold_record()
    _sell(record, "Gold", user_id=1, scu=20, total=100, now=1.0)
    _sell(record, "Gold", user_id=2, scu=5, total=100, now=2.0)
    merged = ledger.set_holder(record, record["cargo"][0], 2)
    assert record["cargo"] == [merged]
    assert (merged["scu"], merged["sold_scu"], merged["holder_id"]) == (80, 25, 2)


def test_set_holder_to_the_current_holder_changes_nothing():
    record = _split_gold_record()
    line = ledger.set_holder(record, record["cargo"][0], 1)
    assert line is record["cargo"][0]
    assert len(record["cargo"]) == 2


def test_fix_cargo_rules():
    record = _record()
    ledger.add_cargo(record, "Gold", 50, holder_id=1)
    _sell(record, "Gold", scu=20, total=100, now=1.0)
    gold = ledger.find_line(record, "Gold")
    assert ledger.fix_cargo(record, gold, 30)["scu"] == 30
    with pytest.raises(LootError, match="already sold"):
        ledger.fix_cargo(record, gold, 10)
    silver = ledger.add_cargo(record, "Silver", 5, holder_id=1)
    assert ledger.fix_cargo(record, silver, 0) is None
    assert ledger.find_line(record, "Silver") is None
    with pytest.raises(LootError):
        ledger.fix_cargo(record, gold, -1)


def test_fix_cargo_only_touches_the_given_line():
    record = _split_gold_record()
    ledger.fix_cargo(record, record["cargo"][1], 0)
    assert [(line["scu"], line["holder_id"]) for line in record["cargo"]] == [(50, 1)]


def test_mark_paid_single_member_and_all():
    record = _sold_record()
    assert ledger.mark_paid(record, member_id=2, seller_id=1, now=11.0) == 1
    assert ledger.owed_amount(record) == 100
    assert ledger.mark_paid(record, member_id=None, seller_id=1, now=12.0) == 1
    assert ledger.status(record) == ledger.STATUS_SETTLED
    with pytest.raises(LootError, match="Nothing"):
        ledger.mark_paid(record, member_id=None, seller_id=1, now=13.0)


def test_mark_paid_respects_seller_filter():
    record = _sold_record()
    with pytest.raises(LootError):
        ledger.mark_paid(record, member_id=2, seller_id=3, now=11.0)
    assert ledger.mark_paid(record, member_id=2, seller_id=None, now=11.0) == 1


def test_dispute_reopens_paid_share_and_returns_payer():
    record = _sold_record()
    ledger.mark_paid(record, member_id=2, seller_id=1, now=11.0)
    assert ledger.dispute(record, user_id=2, now=12.0) == [1]
    payout = next(p for p in record["sales"][0]["payouts"] if p["user_id"] == 2)
    assert payout["paid_at"] is None
    assert payout["disputed_at"] == 12.0
    ledger.mark_paid(record, member_id=2, seller_id=1, now=13.0)
    assert payout["disputed_at"] is None


def test_dispute_with_nothing_paid_is_an_error():
    with pytest.raises(LootError, match="no payouts marked paid"):
        ledger.dispute(_sold_record(), user_id=2, now=12.0)


def test_seller_cannot_dispute_own_auto_paid_share():
    with pytest.raises(LootError):
        ledger.dispute(_sold_record(), user_id=1, now=12.0)


def test_undo_last_sale_restores_scu():
    record = _sold_record()
    sale = ledger.undo_last_sale(record, user_id=1, is_admin=False)
    assert sale["id"] == 1
    assert record["sales"] == []
    assert record["cargo"][0]["sold_scu"] == 0


def test_undo_rules():
    record = _sold_record()
    with pytest.raises(LootError, match="seller or an admin"):
        ledger.undo_last_sale(record, user_id=2, is_admin=False)
    ledger.mark_paid(record, member_id=2, seller_id=1, now=11.0)
    with pytest.raises(LootError, match="already marked paid"):
        ledger.undo_last_sale(record, user_id=1, is_admin=True)
    with pytest.raises(LootError, match="no sales"):
        ledger.undo_last_sale(_record(), user_id=1, is_admin=True)


def test_undo_restores_the_sellers_line_when_gold_is_split():
    record = _split_gold_record()
    _sell(record, "Gold", user_id=1, scu=10, total=100, now=1.0)
    _sell(record, "Gold", user_id=2, scu=20, total=100, now=2.0)
    ledger.undo_last_sale(record, user_id=2, is_admin=False)
    assert [line["sold_scu"] for line in record["cargo"]] == [10, 0]


def test_undo_follows_the_sale_when_the_holder_changed_since():
    record = _sold_record()
    ledger.set_holder(record, record["cargo"][0], 3)
    ledger.undo_last_sale(record, user_id=1, is_admin=False)
    assert record["cargo"][0]["sold_scu"] == 0
    assert record["cargo"][0]["holder_id"] == 3


def test_undo_after_handover_finds_the_only_line_with_enough_sold():
    record = _split_gold_record()
    _sell(record, "Gold", user_id=1, scu=10, total=100, now=1.0)
    record["cargo"][0]["holder_id"] = 9
    ledger.undo_last_sale(record, user_id=1, is_admin=False)
    assert [line["sold_scu"] for line in record["cargo"]] == [0, 0]


def test_undo_after_handover_and_relog_never_goes_negative():
    record = _record()
    ledger.add_cargo(record, "Gold", 50, holder_id=1)
    _sell(record, "Gold", user_id=1, scu=10, total=100, now=1.0)
    ledger.set_holder(record, record["cargo"][0], 2)
    ledger.add_cargo(record, "Gold", 5, holder_id=1)
    ledger.undo_last_sale(record, user_id=1, is_admin=False)
    lines = {line["holder_id"]: (line["scu"], line["sold_scu"]) for line in record["cargo"]}
    assert lines == {2: (50, 0), 1: (5, 0)}


def test_undo_refuses_when_the_source_line_is_ambiguous():
    record = _split_gold_record()
    _sell(record, "Gold", user_id=1, scu=10, total=100, now=1.0)
    _sell(record, "Gold", user_id=2, scu=10, total=100, now=2.0)
    record["sales"].pop(0)
    record["cargo"][0]["holder_id"] = 8
    record["cargo"][1]["holder_id"] = 9
    with pytest.raises(LootError, match="can't be undone"):
        ledger.undo_last_sale(record, user_id=2, is_admin=False)
    assert [line["sold_scu"] for line in record["cargo"]] == [10, 10]
    assert len(record["sales"]) == 1


def test_undo_blocked_while_a_payout_is_disputed():
    record = _sold_record()
    ledger.mark_paid(record, member_id=2, seller_id=1, now=11.0)
    ledger.dispute(record, user_id=2, now=12.0)
    with pytest.raises(LootError, match="disputed payout"):
        ledger.undo_last_sale(record, user_id=1, is_admin=True)
    assert len(record["sales"]) == 1
    assert record["cargo"][0]["sold_scu"] == 30


def test_can_delete_only_when_nothing_owed():
    record = _sold_record()
    assert not ledger.can_delete(record)
    ledger.mark_paid(record, member_id=None, seller_id=None, now=11.0)
    assert ledger.can_delete(record)
    assert ledger.can_delete(_record())


def test_aggregation_across_records():
    first = _sold_record()
    second = _record(participants=(2, 3))
    second["id"] = 13
    ledger.add_cargo(second, "Silver", 10, holder_id=2)
    _sell(second, "Silver", scu=4, total=40, now=1.0)
    records = [first, second]

    owed_to_3 = [(r["id"], s["id"], p["amount"]) for r, s, p in ledger.owed_to(records, 3)]
    assert owed_to_3 == [(12, 1, 100), (13, 1, 20)]

    owed_by_1 = [(r["id"], p["user_id"]) for r, _, p in ledger.owed_by(records, 1)]
    assert owed_by_1 == [(12, 2), (12, 3)]

    held = [(r["id"], line["commodity"]) for r, line in ledger.held_by(records, 2)]
    assert held == [(13, "Silver")]
