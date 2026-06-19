"""Unit tests for src.starcitizenwiki_api models and shared helpers.

Covers the pure parsing layer: from_api() constructors, localize(), first_image(),
unique_by_slug(), and _is_base_model() — no HTTP calls involved.
"""

from src.starcitizenwiki_api._common import (
    PurchaseLocation,
    first_image,
    localize,
    unique_by_slug,
)
from src.starcitizenwiki_api.armor import ArmorItem
from src.starcitizenwiki_api.clothes import ClothingItem
from src.starcitizenwiki_api.items import Item
from src.starcitizenwiki_api.ship_weapons import ShipWeapon
from src.starcitizenwiki_api.ships import Vehicle
from src.starcitizenwiki_api.vehicle_items import VehicleItem
from src.starcitizenwiki_api.weapon_attachments import WeaponAttachment
from src.starcitizenwiki_api.weapons import Weapon, _is_base_model

# ── localize ──────────────────────────────────────────────────────────────────


class TestLocalize:
    def test_none_returns_none(self):
        assert localize(None) is None

    def test_plain_string_passthrough(self):
        assert localize("Flight Ready") == "Flight Ready"

    def test_dict_returns_default_locale(self):
        assert localize({"en_EN": "Flight Ready", "de_DE": "Flugbereit"}) == "Flight Ready"

    def test_dict_falls_back_to_en_EN_when_locale_missing(self):
        assert localize({"en_EN": "Ready", "de_DE": "Bereit"}, locale="fr_FR") == "Ready"

    def test_dict_falls_back_to_any_translation_when_en_missing(self):
        assert localize({"de_DE": "Bereit"}) == "Bereit"

    def test_empty_dict_returns_none(self):
        assert localize({}) is None

    def test_dict_with_falsy_values_skips_them(self):
        assert localize({"en_EN": "", "de_DE": "Bereit"}) == "Bereit"


# ── first_image ──────────────────────────────────────────────────────────────


class TestFirstImage:
    def test_none_images_returns_none(self):
        assert first_image(None) is None

    def test_empty_list_returns_none(self):
        assert first_image([]) is None

    def test_non_list_returns_none(self):
        assert first_image("not-a-list") is None

    def test_first_element_not_dict_returns_none(self):
        assert first_image(["string"]) is None

    def test_returns_thumbnail_url_when_present(self):
        images = [{"thumbnail_url": "https://example.com/thumb.jpg", "original_url": "https://example.com/orig.jpg"}]
        assert first_image(images) == "https://example.com/thumb.jpg"

    def test_falls_back_to_original_url_when_no_thumbnail(self):
        images = [{"original_url": "https://example.com/orig.jpg"}]
        assert first_image(images) == "https://example.com/orig.jpg"

    def test_uses_only_first_image(self):
        images = [
            {"thumbnail_url": "https://example.com/first.jpg"},
            {"thumbnail_url": "https://example.com/second.jpg"},
        ]
        assert first_image(images) == "https://example.com/first.jpg"


# ── unique_by_slug ───────────────────────────────────────────────────────────


class TestUniqueBySlug:
    def test_empty_list_returns_empty(self):
        assert unique_by_slug([]) == []

    def test_no_duplicates_passthrough(self):
        items = [{"slug": "aurora-mr"}, {"slug": "cutlass-black"}]
        assert unique_by_slug(items) == items

    def test_deduplicates_by_slug(self):
        items = [{"slug": "aurora-mr", "name": "Aurora MR"}, {"slug": "aurora-mr", "name": "Aurora MR v2"}]
        assert len(unique_by_slug(items)) == 1

    def test_falls_back_to_name_when_no_slug(self):
        items = [{"name": "Aurora MR"}, {"name": "Aurora MR"}]
        assert len(unique_by_slug(items)) == 1

    def test_falls_back_to_uuid_when_no_slug_or_name(self):
        items = [{"uuid": "abc-123"}, {"uuid": "abc-123"}]
        assert len(unique_by_slug(items)) == 1

    def test_preserves_order_of_first_seen(self):
        items = [{"slug": "a"}, {"slug": "b"}, {"slug": "a"}]
        result = unique_by_slug(items)
        assert [r["slug"] for r in result] == ["a", "b"]


# ── PurchaseLocation ──────────────────────────────────────────────────────────


class TestPurchaseLocationFromApi:
    def test_parses_price_buy(self):
        loc = PurchaseLocation.from_api({"price_buy": 1500.0})
        assert loc.price_buy == 1500.0

    def test_parses_terminal_name(self):
        loc = PurchaseLocation.from_api({"terminal_name": "Refinery Desk"})
        assert loc.terminal_name == "Refinery Desk"

    def test_parses_location_name_from_starmap(self):
        data = {"starmap_location": {"name": "Lorville", "star_system_name": "Stanton"}}
        loc = PurchaseLocation.from_api(data)
        assert loc.location_name == "Lorville"
        assert loc.star_system == "Stanton"

    def test_missing_starmap_location_gives_none(self):
        loc = PurchaseLocation.from_api({})
        assert loc.location_name is None
        assert loc.star_system is None

    def test_empty_starmap_location_gives_none(self):
        loc = PurchaseLocation.from_api({"starmap_location": {}})
        assert loc.location_name is None


# ── _is_base_model ────────────────────────────────────────────────────────────


class TestIsBaseModel:
    def test_plain_name_is_base_model(self):
        w = Weapon(
            uuid=None,
            name="P4-AR Rifle",
            slug=None,
            manufacturer=None,
            manufacturer_code=None,
            description=None,
            classification=None,
            weapon_type=None,
            size=None,
            fire_mode=None,
            magazine_size=None,
            rpm=None,
            effective_range=None,
            damage_per_shot=None,
            alpha_damage=None,
            dps=None,
            ammunition_type=None,
            web_url=None,
            image_url=None,
        )
        assert _is_base_model(w)

    def test_quoted_nickname_is_not_base_model(self):
        w = Weapon(
            uuid=None,
            name='P4-AR "Canuto" Rifle',
            slug=None,
            manufacturer=None,
            manufacturer_code=None,
            description=None,
            classification=None,
            weapon_type=None,
            size=None,
            fire_mode=None,
            magazine_size=None,
            rpm=None,
            effective_range=None,
            damage_per_shot=None,
            alpha_damage=None,
            dps=None,
            ammunition_type=None,
            web_url=None,
            image_url=None,
        )
        assert not _is_base_model(w)


# ── Weapon.from_api ───────────────────────────────────────────────────────────


class TestWeaponFromApi:
    def test_defaults_name_to_unknown(self):
        assert Weapon.from_api({}).name == "Unknown"

    def test_parses_name(self):
        assert Weapon.from_api({"name": "P4-AR"}).name == "P4-AR"

    def test_parses_manufacturer_from_nested_dict(self):
        data = {"manufacturer": {"name": "Kastak Arms", "code": "KSAR"}}
        w = Weapon.from_api(data)
        assert w.manufacturer == "Kastak Arms"
        assert w.manufacturer_code == "KSAR"

    def test_parses_alpha_damage_from_nested_damage(self):
        data = {"personal_weapon": {"damage": {"alpha_total": 12.5}}}
        assert Weapon.from_api(data).alpha_damage == 12.5

    def test_parses_dps_from_nested_damage(self):
        data = {"personal_weapon": {"damage": {"dps_total": 42.0}}}
        assert Weapon.from_api(data).dps == 42.0

    def test_parses_rpm_falling_back_to_rof(self):
        data = {"personal_weapon": {"rof": 600}}
        assert Weapon.from_api(data).rpm == 600

    def test_parses_purchase_locations_from_uex_prices(self):
        data = {"uex_prices": {"purchase": [{"price_buy": 500.0, "terminal_name": "Store"}]}}
        w = Weapon.from_api(data)
        assert len(w.purchase_locations) == 1
        assert w.purchase_locations[0].price_buy == 500.0

    def test_ignores_non_dict_purchase_entries(self):
        data = {"uex_prices": {"purchase": ["invalid", None, {"price_buy": 100.0}]}}
        w = Weapon.from_api(data)
        assert len(w.purchase_locations) == 1

    def test_empty_uex_prices_gives_no_locations(self):
        assert Weapon.from_api({}).purchase_locations == []

    def test_localized_description(self):
        data = {"description": {"en_EN": "A reliable rifle."}}
        assert Weapon.from_api(data).description == "A reliable rifle."


# ── ShipWeapon.from_api ───────────────────────────────────────────────────────


class TestShipWeaponFromApi:
    def test_defaults_name_to_unknown(self):
        assert ShipWeapon.from_api({}).name == "Unknown"

    def test_parses_size(self):
        assert ShipWeapon.from_api({"size": 3}).size == 3

    def test_parses_alpha_damage(self):
        data = {"weapon": {"damage": {"alpha_damage": 100.0}}}
        assert ShipWeapon.from_api(data).alpha_damage == 100.0

    def test_falls_back_alpha_total_when_no_alpha_damage(self):
        data = {"weapon": {"damage": {"alpha_total": 200.0}}}
        assert ShipWeapon.from_api(data).alpha_damage == 200.0

    def test_parses_fire_rate(self):
        data = {"weapon": {"fire_rate": 120}}
        assert ShipWeapon.from_api(data).fire_rate == 120

    def test_falls_back_rpm_when_no_fire_rate(self):
        data = {"weapon": {"rpm": 90}}
        assert ShipWeapon.from_api(data).fire_rate == 90

    def test_parses_grade_and_classification(self):
        data = {"grade": "A", "class": "Military"}
        w = ShipWeapon.from_api(data)
        assert w.grade == "A"
        assert w.classification == "Military"

    def test_empty_data_gives_no_purchase_locations(self):
        assert ShipWeapon.from_api({}).purchase_locations == []


# ── ArmorItem.from_api ────────────────────────────────────────────────────────


class TestArmorItemFromApi:
    def test_defaults_name_to_unknown(self):
        assert ArmorItem.from_api({}).name == "Unknown"

    def test_parses_name(self):
        assert ArmorItem.from_api({"name": "Novikov Helmet"}).name == "Novikov Helmet"

    def test_parses_damage_reduction_from_armor_dict(self):
        data = {"armor": {"damage_reduction": 0.15}}
        assert ArmorItem.from_api(data).damage_reduction == 0.15

    def test_parses_capacity_from_armor_dict(self):
        data = {"armor": {"capacity": 100.0}}
        assert ArmorItem.from_api(data).capacity == 100.0

    def test_parses_manufacturer(self):
        data = {"manufacturer": {"name": "Greycat Industrial"}}
        assert ArmorItem.from_api(data).manufacturer == "Greycat Industrial"

    def test_no_armor_data_gives_none_reduction(self):
        assert ArmorItem.from_api({}).damage_reduction is None

    def test_parses_purchase_locations(self):
        data = {"uex_prices": {"purchase": [{"price_buy": 750.0}]}}
        item = ArmorItem.from_api(data)
        assert len(item.purchase_locations) == 1


# ── ClothingItem.from_api ─────────────────────────────────────────────────────


class TestClothingItemFromApi:
    def test_defaults_name_to_unknown(self):
        assert ClothingItem.from_api({}).name == "Unknown"

    def test_parses_name(self):
        assert ClothingItem.from_api({"name": "Novikov Jacket"}).name == "Novikov Jacket"

    def test_parses_type_localized(self):
        data = {"type": {"en_EN": "Torso"}}
        assert ClothingItem.from_api(data).type == "Torso"

    def test_empty_purchase_locations_when_no_uex(self):
        assert ClothingItem.from_api({}).purchase_locations == []


# ── VehicleItem.from_api ──────────────────────────────────────────────────────


class TestVehicleItemFromApi:
    def test_defaults_name_to_unknown(self):
        assert VehicleItem.from_api({}).name == "Unknown"

    def test_parses_name_and_slug(self):
        data = {"name": "Quantum Drive MK1", "slug": "quantum-drive-mk1"}
        item = VehicleItem.from_api(data)
        assert item.name == "Quantum Drive MK1"
        assert item.slug == "quantum-drive-mk1"

    def test_parses_grade(self):
        assert VehicleItem.from_api({"grade": "A"}).grade == "A"

    def test_parses_classification(self):
        assert VehicleItem.from_api({"class": "Military"}).classification == "Military"


# ── Item.from_api ─────────────────────────────────────────────────────────────


class TestItemFromApi:
    def test_defaults_name_to_unknown(self):
        assert Item.from_api({}).name == "Unknown"

    def test_parses_size(self):
        assert Item.from_api({"size": 2}).size == 2

    def test_parses_uuid(self):
        assert Item.from_api({"uuid": "abc-123"}).uuid == "abc-123"

    def test_empty_purchase_locations_when_no_uex(self):
        assert Item.from_api({}).purchase_locations == []


# ── WeaponAttachment.from_api ─────────────────────────────────────────────────


class TestWeaponAttachmentFromApi:
    def test_defaults_name_to_unknown(self):
        assert WeaponAttachment.from_api({}).name == "Unknown"

    def test_parses_name(self):
        assert WeaponAttachment.from_api({"name": "4× Scope"}).name == "4× Scope"

    def test_parses_sub_type_localized(self):
        data = {"sub_type": {"en_EN": "Optics"}}
        assert WeaponAttachment.from_api(data).sub_type == "Optics"

    def test_parses_grade(self):
        assert WeaponAttachment.from_api({"grade": "B"}).grade == "B"


# ── Vehicle (SC wiki ship).from_api ───────────────────────────────────────────


class TestVehicleFromApi:
    def test_defaults_name_to_unknown(self):
        assert Vehicle.from_api({}).name == "Unknown"

    def test_parses_name(self):
        assert Vehicle.from_api({"name": "Cutlass Black"}).name == "Cutlass Black"

    def test_falls_back_to_game_name(self):
        assert Vehicle.from_api({"game_name": "Cutlass"}).name == "Cutlass"

    def test_parses_manufacturer_from_nested_dict(self):
        data = {"manufacturer": {"name": "Drake Interplanetary", "code": "DRAK"}}
        v = Vehicle.from_api(data)
        assert v.manufacturer == "Drake Interplanetary"
        assert v.manufacturer_code == "DRAK"

    def test_parses_crew_min_and_max(self):
        data = {"crew": {"min": 1, "max": 2}}
        v = Vehicle.from_api(data)
        assert v.crew_min == 1
        assert v.crew_max == 2

    def test_parses_speed_from_nested_dict(self):
        data = {"speed": {"scm": 185.0, "max": 1200.0}}
        v = Vehicle.from_api(data)
        assert v.scm_speed == 185.0
        assert v.max_speed == 1200.0

    def test_parses_cargo_capacity(self):
        assert Vehicle.from_api({"cargo_capacity": 46.0}).cargo_capacity == 46.0

    def test_parses_deflection_from_nested_armor(self):
        data = {"armor": {"deflection": {"physical": 0.5, "energy": 0.3}}}
        v = Vehicle.from_api(data)
        assert v.deflection_physical == 0.5
        assert v.deflection_energy == 0.3

    def test_parses_dimensions_from_dimension_dict(self):
        data = {"dimension": {"length": 30.0, "width": 18.0, "height": 8.0}}
        v = Vehicle.from_api(data)
        assert v.length == 30.0
        assert v.width == 18.0
        assert v.height == 8.0

    def test_foci_list_localized(self):
        data = {"foci": [{"en_EN": "Combat"}, {"en_EN": "Transport"}]}
        v = Vehicle.from_api(data)
        assert v.foci == ["Combat", "Transport"]

    def test_foci_empty_when_none(self):
        assert Vehicle.from_api({}).foci == []

    def test_image_url_from_images_list(self):
        data = {"images": [{"thumbnail_url": "https://example.com/ship.jpg"}]}
        assert Vehicle.from_api(data).image_url == "https://example.com/ship.jpg"
