import pytest

from src.commands.manifest import ledger
from src.commands.manifest.ledger import ManifestError


def _cargo(commodity="Gold", scu=100, est_price=1000.0):
    return {"commodity": commodity, "scu": scu, "est_price": est_price}


def _manifest(crew=(2, 3), carrier=1, cargo=None, costs=None, created_by=1):
    return ledger.new_manifest(
        manifest_id=12,
        guild_id=7,
        created_by=created_by,
        carrier_id=carrier,
        crew_ids=crew,
        cargo=cargo if cargo is not None else [_cargo()],
        costs=costs if costs is not None else [],
        now=100.0,
    )


def _payouts(sale):
    return {p["user_id"]: p["amount"] for p in sale["payouts"]}


def test_new_manifest_shape():
    record = _manifest()
    assert record["id"] == 12
    assert record["guild_id"] == 7
    assert record["carrier_id"] == 1
    assert record["thread_id"] is None
    assert record["card_message_id"] is None
    assert record["beacon_thread_id"] is None
    assert record["sales"] == []


def test_new_manifest_puts_creator_and_carrier_in_crew_once():
    record = _manifest(crew=(3, 2, 3), carrier=4, created_by=1)
    assert ledger.crew_ids(record) == [1, 4, 3, 2]
    assert all(member["weight"] == 1 for member in record["crew"])


def test_new_manifest_requires_cargo():
    with pytest.raises(ManifestError):
        _manifest(cargo=[])


def test_new_manifest_caps_crew():
    with pytest.raises(ManifestError):
        _manifest(crew=range(100, 130))


def test_normalize_fills_missing_fields():
    raw = {"id": 1, "guild_id": 7, "created_by": 5, "created_at": 0.0, "carrier_id": 5, "cargo": []}
    record = ledger.normalize(raw)
    assert record["crew"] == []
    assert record["costs"] == []
    assert record["sales"] == []
    assert record["thread_id"] is None


def test_value_and_profit_use_estimates_before_sales():
    record = _manifest(
        cargo=[_cargo("Gold", 100, 1000.0), _cargo("Tin", 10, None)], costs=[{"label": "Fuel", "amount": 5000}]
    )
    assert ledger.value(record) == 100_000
    assert ledger.total_costs(record) == 5000
    assert ledger.profit(record) == 95_000


def test_value_uses_real_sale_totals_for_sold_scu():
    record = _manifest()
    ledger.record_sale(record, "gold", scu=40, total=60_000, now=1.0)
    assert ledger.value(record) == 60_000 + 60 * 1000
    assert ledger.remaining_value(record) == 60_000


def test_status_moves_open_partial_sold():
    record = _manifest()
    assert ledger.status(record) == ledger.STATUS_OPEN
    ledger.record_sale(record, "Gold", scu=40, total=40_000, now=1.0)
    assert ledger.status(record) == ledger.STATUS_PARTIAL
    ledger.record_sale(record, "Gold", scu=60, total=60_000, now=2.0)
    assert ledger.status(record) == ledger.STATUS_SOLD


def test_sale_splits_evenly_and_carrier_is_paid():
    record = _manifest(crew=(2, 3))
    sale = ledger.record_sale(record, "Gold", scu=10, total=30_000, now=5.0)
    assert _payouts(sale) == {1: 10_000, 2: 10_000, 3: 10_000}
    paid = {p["user_id"]: p["paid_at"] for p in sale["payouts"]}
    assert paid == {1: 5.0, 2: None, 3: None}
    assert sale["seller_id"] == 1
    assert sale["cost_recovered"] == 0


def test_sale_rounding_remainder_goes_to_carrier():
    record = _manifest(crew=(2, 3))
    sale = ledger.record_sale(record, "Gold", scu=10, total=100, now=1.0)
    assert _payouts(sale) == {1: 34, 2: 33, 3: 33}


def test_sale_split_follows_weights():
    record = _manifest(crew=(2, 3))
    ledger.set_weight(record, 2, 2)
    sale = ledger.record_sale(record, "Gold", scu=10, total=40_000, now=1.0)
    assert _payouts(sale) == {1: 10_000, 2: 20_000, 3: 10_000}


def test_costs_are_recovered_first_across_partial_sales():
    record = _manifest(crew=(2, 3), costs=[{"label": "Fuel", "amount": 100_000}])
    first = ledger.record_sale(record, "Gold", scu=10, total=60_000, now=1.0)
    assert first["cost_recovered"] == 60_000
    assert _payouts(first) == {1: 0, 2: 0, 3: 0}
    assert all(p["paid_at"] is not None for p in first["payouts"])
    assert ledger.outstanding_costs(record) == 40_000
    second = ledger.record_sale(record, "Gold", scu=10, total=200_000, now=2.0)
    assert second["cost_recovered"] == 40_000
    assert _payouts(second) == {1: 53_334, 2: 53_333, 3: 53_333}
    assert ledger.outstanding_costs(record) == 0


def test_sale_rejects_overselling_and_bad_totals():
    record = _manifest()
    with pytest.raises(ManifestError, match="Only 100 SCU"):
        ledger.record_sale(record, "Gold", scu=101, total=1, now=1.0)
    with pytest.raises(ManifestError):
        ledger.record_sale(record, "Gold", scu=0, total=1, now=1.0)
    with pytest.raises(ManifestError):
        ledger.record_sale(record, "Gold", scu=1, total=0, now=1.0)
    with pytest.raises(ManifestError, match="no Tin"):
        ledger.record_sale(record, "Tin", scu=1, total=1, now=1.0)


def test_sale_snapshots_crew_and_weights():
    record = _manifest(crew=(2,))
    sale = ledger.record_sale(record, "Gold", scu=10, total=1000, now=1.0)
    ledger.set_crew(record, [2, 3])
    ledger.set_weight(record, 2, 5)
    assert _payouts(sale) == {1: 500, 2: 500}


def test_member_shares_project_unsold_estimates():
    record = _manifest(crew=(2, 3), costs=[{"label": "Fuel", "amount": 30_000}])
    shares = {s.user_id: s for s in ledger.member_shares(record)}
    assert shares[2].projected == 23_333
    assert shares[2].earned == 0
    assert shares[2].weight == 1


def test_member_shares_combine_earned_and_projected():
    record = _manifest(crew=(2, 3))
    ledger.record_sale(record, "Gold", scu=50, total=60_000, now=1.0)
    shares = {s.user_id: s for s in ledger.member_shares(record)}
    assert shares[2].earned == 20_000
    assert shares[2].owed == 20_000
    assert shares[2].projected == 20_000 + 50_000 // 3
    assert shares[1].owed == 0


def test_member_shares_never_go_negative_on_a_loss():
    record = _manifest(crew=(2,), costs=[{"label": "Purchase", "amount": 500_000}])
    shares = {s.user_id: s for s in ledger.member_shares(record)}
    assert shares[2].projected == 0
    assert ledger.profit(record) == -400_000


def test_member_shares_list_former_crew_with_payouts():
    record = _manifest(crew=(2, 3))
    ledger.record_sale(record, "Gold", scu=10, total=3000, now=1.0)
    ledger.set_crew(record, [2])
    shares = {s.user_id: s for s in ledger.member_shares(record)}
    assert shares[3].weight is None
    assert shares[3].earned == 1000
    assert shares[3].projected == 1000


def test_member_shares_flag_disputes():
    record = _manifest(crew=(2,))
    ledger.record_sale(record, "Gold", scu=10, total=2000, now=1.0)
    ledger.mark_paid(record, member_id=2, seller_id=1, now=2.0)
    ledger.dispute(record, user_id=2, now=3.0)
    shares = {s.user_id: s for s in ledger.member_shares(record)}
    assert shares[2].disputed is True
    assert shares[2].owed == 1000


def test_replace_cargo_keeps_sold_amounts_valid():
    record = _manifest(cargo=[_cargo("Gold", 100), _cargo("Tin", 10)])
    ledger.record_sale(record, "Gold", scu=40, total=1, now=1.0)
    with pytest.raises(ManifestError, match="40 SCU of Gold is already sold"):
        ledger.replace_cargo(record, [_cargo("Gold", 30)])
    with pytest.raises(ManifestError, match="Gold has sales"):
        ledger.replace_cargo(record, [_cargo("Tin", 10)])
    ledger.replace_cargo(record, [_cargo("gold", 40, 5.0), _cargo("Quantanium", 3)])
    assert [line["commodity"] for line in record["cargo"]] == ["Gold", "Quantanium"]
    assert ledger.status(record) == ledger.STATUS_PARTIAL


def test_replace_cargo_requires_a_line():
    with pytest.raises(ManifestError):
        ledger.replace_cargo(_manifest(), [])


def test_replace_costs_cannot_drop_below_recovered():
    record = _manifest(costs=[{"label": "Fuel", "amount": 10_000}])
    ledger.record_sale(record, "Gold", scu=1, total=8000, now=1.0)
    with pytest.raises(ManifestError, match="8,000 aUEC of costs is already recovered"):
        ledger.replace_costs(record, [{"label": "Fuel", "amount": 5000}])
    ledger.replace_costs(record, [{"label": "Fuel", "amount": 8000}, {"label": "Repair", "amount": 1}])
    assert ledger.total_costs(record) == 8001


def test_set_crew_keeps_weights_and_core_members():
    record = _manifest(crew=(2, 3), carrier=4)
    ledger.set_weight(record, 2, 3)
    ledger.set_crew(record, [2, 5])
    assert ledger.crew_ids(record) == [1, 4, 2, 5]
    assert {m["user_id"]: m["weight"] for m in record["crew"]}[2] == 3


def test_set_crew_caps_size():
    with pytest.raises(ManifestError):
        ledger.set_crew(_manifest(), range(100, 130))


def test_set_carrier_adds_them_to_crew():
    record = _manifest(crew=(2,))
    ledger.set_carrier(record, 9)
    assert record["carrier_id"] == 9
    assert 9 in ledger.crew_ids(record)


def test_set_weight_validates():
    record = _manifest(crew=(2,))
    with pytest.raises(ManifestError):
        ledger.set_weight(record, 2, 0)
    with pytest.raises(ManifestError):
        ledger.set_weight(record, 2, 11)
    with pytest.raises(ManifestError):
        ledger.set_weight(record, 99, 2)


def test_permissions():
    record = _manifest(crew=(2,), carrier=3, created_by=1)
    assert ledger.can_edit(record, 1, False)
    assert ledger.can_edit(record, 3, False)
    assert not ledger.can_edit(record, 2, False)
    assert ledger.can_edit(record, 2, True)
    assert ledger.can_sell(record, 3, False)
    assert not ledger.can_sell(record, 1, False)
    assert ledger.can_sell(record, 1, True)


def test_is_visible():
    record = _manifest(crew=(2,), created_by=1)
    assert ledger.is_visible(record, 1, False)
    assert ledger.is_visible(record, 2, False)
    assert not ledger.is_visible(record, 9, False)
    assert ledger.is_visible(record, 9, True)


def test_mark_paid_filters_by_seller_and_member():
    record = _manifest(crew=(2, 3))
    ledger.record_sale(record, "Gold", scu=1, total=300, now=1.0)
    with pytest.raises(ManifestError):
        ledger.mark_paid(record, member_id=None, seller_id=5, now=2.0)
    assert ledger.mark_paid(record, member_id=2, seller_id=1, now=2.0) == 1
    assert ledger.owes(record, 1) == [3]
    assert ledger.mark_paid(record, member_id=None, seller_id=None, now=3.0) == 1
    assert ledger.owed_amount(record) == 0
    with pytest.raises(ManifestError, match="Nothing left"):
        ledger.mark_paid(record, member_id=None, seller_id=None, now=4.0)


def test_dispute_reopens_paid_payouts_and_names_sellers():
    record = _manifest(crew=(2,))
    ledger.record_sale(record, "Gold", scu=1, total=200, now=1.0)
    with pytest.raises(ManifestError):
        ledger.dispute(record, user_id=2, now=2.0)
    ledger.mark_paid(record, member_id=2, seller_id=1, now=2.0)
    assert ledger.dispute(record, user_id=2, now=3.0) == [1]
    payout = next(p for p in record["sales"][0]["payouts"] if p["user_id"] == 2)
    assert payout["paid_at"] is None
    assert payout["disputed_at"] == 3.0
    with pytest.raises(ManifestError):
        ledger.dispute(record, user_id=1, now=4.0)


def test_mark_paid_clears_dispute():
    record = _manifest(crew=(2,))
    ledger.record_sale(record, "Gold", scu=1, total=200, now=1.0)
    ledger.mark_paid(record, member_id=2, seller_id=1, now=2.0)
    ledger.dispute(record, user_id=2, now=3.0)
    ledger.mark_paid(record, member_id=2, seller_id=1, now=4.0)
    payout = next(p for p in record["sales"][0]["payouts"] if p["user_id"] == 2)
    assert payout["disputed_at"] is None


def test_undo_last_sale_restores_cargo_and_costs():
    record = _manifest(crew=(2,), costs=[{"label": "Fuel", "amount": 100}])
    ledger.record_sale(record, "Gold", scu=10, total=1000, now=1.0)
    sale = ledger.undo_last_sale(record, user_id=1, is_admin=False)
    assert sale["scu"] == 10
    assert record["sales"] == []
    assert ledger.outstanding_costs(record) == 100
    assert ledger.status(record) == ledger.STATUS_OPEN


def test_undo_guards():
    record = _manifest(crew=(2,))
    with pytest.raises(ManifestError, match="no sales"):
        ledger.undo_last_sale(record, user_id=1, is_admin=False)
    ledger.record_sale(record, "Gold", scu=10, total=1000, now=1.0)
    with pytest.raises(ManifestError, match="Only whoever sold it"):
        ledger.undo_last_sale(record, user_id=2, is_admin=False)
    ledger.mark_paid(record, member_id=2, seller_id=1, now=2.0)
    with pytest.raises(ManifestError, match="already marked paid"):
        ledger.undo_last_sale(record, user_id=1, is_admin=False)
    ledger.dispute(record, user_id=2, now=3.0)
    with pytest.raises(ManifestError, match="disputed"):
        ledger.undo_last_sale(record, user_id=1, is_admin=True)


def test_owed_queries_and_delete():
    record = _manifest(crew=(2,), carrier=1)
    ledger.record_sale(record, "Gold", scu=10, total=1000, now=1.0)
    assert [(r["id"], p["amount"]) for r, _, p in ledger.owed_to([record], 2)] == [(12, 500)]
    assert [p["user_id"] for _, _, p in ledger.owed_by([record], 1)] == [2]
    assert [(r["id"], line["commodity"]) for r, line in ledger.carried_by([record], 1)] == [(12, "Gold")]
    assert ledger.carried_by([record], 2) == []
    assert not ledger.can_delete(record)
    ledger.mark_paid(record, member_id=None, seller_id=None, now=2.0)
    assert ledger.can_delete(record)
    assert ledger.outstanding_payouts(record) == 0
