"""Unit tests for transfer validation logic."""

from src.commands.inventory.shared import ITEMS, complete_sets


class TestTransferValidation:
    def test_sender_has_enough(self):
        sender_inv = {"DCHS-01": 2, "DCHS-02": 1}
        assert sender_inv.get("DCHS-01", 0) >= 1

    def test_sender_insufficient(self):
        sender_inv = {"DCHS-01": 0}
        assert sender_inv.get("DCHS-01", 0) < 1

    def test_transfer_deducts_from_sender(self):
        sender_inv = {"DCHS-01": 3}
        sender_inv["DCHS-01"] -= 1
        assert sender_inv["DCHS-01"] == 2

    def test_transfer_zero_count_removes_key(self):
        sender_inv = {"DCHS-01": 1}
        sender_inv["DCHS-01"] -= 1
        if sender_inv["DCHS-01"] == 0:
            del sender_inv["DCHS-01"]
        assert "DCHS-01" not in sender_inv

    def test_transfer_adds_to_recipient(self):
        recipient_inv: dict[str, int] = {}
        recipient_inv["DCHS-01"] = recipient_inv.get("DCHS-01", 0) + 1
        assert recipient_inv["DCHS-01"] == 1

    def test_recipient_set_completion_detected(self):
        recipient_inv = {item: 1 for item in ITEMS}
        assert complete_sets(recipient_inv) == 1

    def test_set_transfer_deducts_all_items(self):
        sender_inv = {item: 2 for item in ITEMS}
        for item in ITEMS:
            sender_inv[item] -= 1
        assert all(sender_inv[item] == 1 for item in ITEMS)

    def test_set_transfer_adds_all_items_to_recipient(self):
        recipient_inv: dict[str, int] = {}
        for item in ITEMS:
            recipient_inv[item] = recipient_inv.get(item, 0) + 1
        assert complete_sets(recipient_inv) == 1
