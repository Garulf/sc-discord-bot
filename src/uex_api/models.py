from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


@dataclass(frozen=True)
class Commodity:
    id: int | None
    name: str
    code: str | None
    slug: str | None
    kind: str | None
    weight_scu: float | None
    price_buy: float | None
    price_sell: float | None
    is_available: bool | None
    is_buyable: bool | None
    is_sellable: bool | None
    is_mineral: bool | None
    is_raw: bool | None
    is_refined: bool | None
    is_illegal: bool | None
    wiki: str | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Commodity:
        return cls(
            id=_as_int(data.get("id")),
            name=data.get("name") or "Unknown",
            code=data.get("code"),
            slug=data.get("slug"),
            kind=data.get("kind"),
            weight_scu=_as_float(data.get("weight_scu")),
            price_buy=_as_float(data.get("price_buy")),
            price_sell=_as_float(data.get("price_sell")),
            is_available=_as_bool(data.get("is_available")),
            is_buyable=_as_bool(data.get("is_buyable")),
            is_sellable=_as_bool(data.get("is_sellable")),
            is_mineral=_as_bool(data.get("is_mineral")),
            is_raw=_as_bool(data.get("is_raw")),
            is_refined=_as_bool(data.get("is_refined")),
            is_illegal=_as_bool(data.get("is_illegal")),
            wiki=data.get("wiki"),
        )


@dataclass(frozen=True)
class Terminal:
    id: int | None
    name: str
    nickname: str | None
    code: str | None
    type: str | None
    id_star_system: int | None
    star_system_name: str | None
    id_orbit: int | None
    orbit_name: str | None
    id_faction: int | None
    faction_name: str | None
    planet_name: str | None
    moon_name: str | None
    city_name: str | None
    space_station_name: str | None
    max_container_size: int | None
    is_available: bool | None
    has_loading_dock: bool | None
    has_docking_port: bool | None
    has_freight_elevator: bool | None
    is_cargo_center: bool | None
    is_auto_load: bool | None
    is_nqa: bool | None
    is_refuel: bool | None
    is_player_owned: bool | None
    is_space_station: bool | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Terminal:
        return cls(
            id=_as_int(data.get("id")),
            name=data.get("name") or "Unknown",
            nickname=data.get("nickname"),
            code=data.get("code"),
            type=data.get("type"),
            id_star_system=_as_int(data.get("id_star_system")),
            star_system_name=data.get("star_system_name"),
            id_orbit=_as_int(data.get("id_orbit")),
            orbit_name=data.get("orbit_name"),
            id_faction=_as_int(data.get("id_faction")),
            faction_name=data.get("faction_name"),
            planet_name=data.get("planet_name"),
            moon_name=data.get("moon_name"),
            city_name=data.get("city_name"),
            space_station_name=data.get("space_station_name"),
            max_container_size=_as_int(data.get("max_container_size")),
            is_available=_as_bool(data.get("is_available")),
            has_loading_dock=_as_bool(data.get("has_loading_dock")),
            has_docking_port=_as_bool(data.get("has_docking_port")),
            has_freight_elevator=_as_bool(data.get("has_freight_elevator")),
            is_cargo_center=_as_bool(data.get("is_cargo_center")),
            is_auto_load=_as_bool(data.get("is_auto_load")),
            is_nqa=_as_bool(data.get("is_nqa")),
            is_refuel=_as_bool(data.get("is_refuel")),
            is_player_owned=_as_bool(data.get("is_player_owned")),
            is_space_station=_as_bool(data.get("id_space_station")),
        )


@dataclass(frozen=True)
class CommodityPrice:
    id: int | None
    id_commodity: int | None
    id_terminal: int | None
    commodity_name: str | None
    terminal_name: str | None
    star_system_name: str | None
    planet_name: str | None
    moon_name: str | None
    city_name: str | None
    outpost_name: str | None
    space_station_name: str | None
    price_buy: float | None
    price_buy_avg: float | None
    price_sell: float | None
    price_sell_avg: float | None
    scu_buy: float | None
    scu_sell: float | None
    status_buy: int | None
    status_sell: int | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> CommodityPrice:
        return cls(
            id=_as_int(data.get("id")),
            id_commodity=_as_int(data.get("id_commodity")),
            id_terminal=_as_int(data.get("id_terminal")),
            commodity_name=data.get("commodity_name"),
            terminal_name=data.get("terminal_name"),
            star_system_name=data.get("star_system_name"),
            planet_name=data.get("planet_name"),
            moon_name=data.get("moon_name"),
            city_name=data.get("city_name"),
            outpost_name=data.get("outpost_name"),
            space_station_name=data.get("space_station_name"),
            price_buy=_as_float(data.get("price_buy")),
            price_buy_avg=_as_float(data.get("price_buy_avg")),
            price_sell=_as_float(data.get("price_sell")),
            price_sell_avg=_as_float(data.get("price_sell_avg")),
            scu_buy=_as_float(data.get("scu_buy")),
            scu_sell=_as_float(data.get("scu_sell")),
            status_buy=_as_int(data.get("status_buy")),
            status_sell=_as_int(data.get("status_sell")),
        )

    @property
    def place_type(self) -> str:
        if self.space_station_name:
            return "station"
        if self.outpost_name:
            return "outpost"
        if self.city_name:
            return "city"
        if self.moon_name:
            return "moon"
        if self.planet_name:
            return "planet"
        return "other"


@dataclass(frozen=True)
class Vehicle:
    id: int | None
    name: str
    name_full: str | None
    slug: str | None
    uuid: str | None
    company_name: str | None
    scu: float | None
    crew: int | None
    is_available: bool | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Vehicle:
        return cls(
            id=_as_int(data.get("id")),
            name=data.get("name") or "Unknown",
            name_full=data.get("name_full"),
            slug=data.get("slug"),
            uuid=data.get("uuid"),
            company_name=data.get("company_name"),
            scu=_as_float(data.get("scu")),
            crew=_as_int(data.get("crew")),
            is_available=_as_bool(data.get("is_available")),
        )


@dataclass(frozen=True)
class VehiclePurchasePrice:
    id: int | None
    id_vehicle: int | None
    id_terminal: int | None
    vehicle_name: str | None
    terminal_name: str | None
    price_buy: float | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> VehiclePurchasePrice:
        return cls(
            id=_as_int(data.get("id")),
            id_vehicle=_as_int(data.get("id_vehicle")),
            id_terminal=_as_int(data.get("id_terminal")),
            vehicle_name=data.get("vehicle_name"),
            terminal_name=data.get("terminal_name"),
            price_buy=_as_float(data.get("price_buy")),
        )


@dataclass(frozen=True)
class VehicleRentalPrice:
    id: int | None
    id_vehicle: int | None
    id_terminal: int | None
    vehicle_name: str | None
    terminal_name: str | None
    price_rent: float | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> VehicleRentalPrice:
        return cls(
            id=_as_int(data.get("id")),
            id_vehicle=_as_int(data.get("id_vehicle")),
            id_terminal=_as_int(data.get("id_terminal")),
            vehicle_name=data.get("vehicle_name"),
            terminal_name=data.get("terminal_name"),
            price_rent=_as_float(data.get("price_rent")),
        )


@dataclass(frozen=True)
class StarSystem:
    id: int | None
    name: str
    code: str | None
    is_available: bool | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> StarSystem:
        return cls(
            id=_as_int(data.get("id")),
            name=data.get("name") or "Unknown",
            code=data.get("code"),
            is_available=_as_bool(data.get("is_available")),
        )
