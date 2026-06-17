from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


def _as_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    return bool(value)


@dataclass(frozen=True)
class Commodity:
    id: Optional[int]
    name: str
    code: Optional[str]
    slug: Optional[str]
    kind: Optional[str]
    weight_scu: Optional[float]
    price_buy: Optional[float]
    price_sell: Optional[float]
    is_available: Optional[bool]
    is_buyable: Optional[bool]
    is_sellable: Optional[bool]
    is_mineral: Optional[bool]
    is_raw: Optional[bool]
    is_refined: Optional[bool]
    is_illegal: Optional[bool]
    wiki: Optional[str]

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Commodity":
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
    id: Optional[int]
    name: str
    nickname: Optional[str]
    code: Optional[str]
    type: Optional[str]
    id_star_system: Optional[int]
    star_system_name: Optional[str]
    id_orbit: Optional[int]
    orbit_name: Optional[str]
    id_faction: Optional[int]
    faction_name: Optional[str]
    planet_name: Optional[str]
    moon_name: Optional[str]
    city_name: Optional[str]
    space_station_name: Optional[str]
    max_container_size: Optional[int]
    is_available: Optional[bool]
    has_loading_dock: Optional[bool]
    has_docking_port: Optional[bool]
    has_freight_elevator: Optional[bool]
    is_cargo_center: Optional[bool]
    is_auto_load: Optional[bool]
    is_nqa: Optional[bool]
    is_refuel: Optional[bool]
    is_player_owned: Optional[bool]
    is_space_station: Optional[bool]

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Terminal":
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
    id: Optional[int]
    id_commodity: Optional[int]
    id_terminal: Optional[int]
    commodity_name: Optional[str]
    terminal_name: Optional[str]
    star_system_name: Optional[str]
    planet_name: Optional[str]
    moon_name: Optional[str]
    city_name: Optional[str]
    outpost_name: Optional[str]
    space_station_name: Optional[str]
    price_buy: Optional[float]
    price_buy_avg: Optional[float]
    price_sell: Optional[float]
    price_sell_avg: Optional[float]
    scu_buy: Optional[float]
    scu_sell: Optional[float]
    status_buy: Optional[int]
    status_sell: Optional[int]

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "CommodityPrice":
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
    id: Optional[int]
    name: str
    name_full: Optional[str]
    slug: Optional[str]
    uuid: Optional[str]
    company_name: Optional[str]
    scu: Optional[float]
    crew: Optional[int]
    is_available: Optional[bool]

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Vehicle":
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
    id: Optional[int]
    id_vehicle: Optional[int]
    id_terminal: Optional[int]
    vehicle_name: Optional[str]
    terminal_name: Optional[str]
    price_buy: Optional[float]

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "VehiclePurchasePrice":
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
    id: Optional[int]
    id_vehicle: Optional[int]
    id_terminal: Optional[int]
    vehicle_name: Optional[str]
    terminal_name: Optional[str]
    price_rent: Optional[float]

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "VehicleRentalPrice":
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
    id: Optional[int]
    name: str
    code: Optional[str]
    is_available: Optional[bool]

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "StarSystem":
        return cls(
            id=_as_int(data.get("id")),
            name=data.get("name") or "Unknown",
            code=data.get("code"),
            is_available=_as_bool(data.get("is_available")),
        )
