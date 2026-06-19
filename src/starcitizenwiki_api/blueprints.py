from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.starcitizenwiki_api._common import DEFAULT_LOCALE, MAX_PAGE_SIZE, extract_data
from src.starcitizenwiki_api.client import NotFoundError, StarCitizenWikiClient

# Blueprints live outside the v2 namespace.
_BASE = "https://api.star-citizen.wiki/api/blueprints"

DEFAULT_PAGE_SIZE = 30
DEFAULT_SORT = "-craft_time_seconds"


@dataclass(frozen=True)
class BlueprintIngredient:
    name: str
    quantity_scu: float | None
    kind: str | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> BlueprintIngredient:
        return cls(
            name=data.get("name") or "Unknown",
            quantity_scu=data.get("quantity_scu"),
            kind=data.get("kind"),
        )


@dataclass(frozen=True)
class Blueprint:
    uuid: str
    name: str
    key: str | None
    craft_time_seconds: int | None
    craft_time_label: str | None
    ingredient_count: int | None
    unlocking_missions_count: int | None
    is_available_by_default: bool | None
    output_class: str | None
    output_type: str | None
    output_type_label: str | None
    ingredients: list[BlueprintIngredient] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> Blueprint:
        output = data.get("output") or {}
        ingredients = [
            BlueprintIngredient.from_api(i)
            for i in (data.get("ingredients") or [])
            if isinstance(i, dict)
        ]
        return cls(
            uuid=data.get("uuid") or "",
            name=data.get("output_name") or output.get("name") or "Unknown",
            key=data.get("key"),
            craft_time_seconds=data.get("craft_time_seconds"),
            craft_time_label=data.get("craft_time_label"),
            ingredient_count=data.get("ingredient_count"),
            unlocking_missions_count=data.get("unlocking_missions_count"),
            is_available_by_default=data.get("is_available_by_default"),
            output_class=data.get("output_class") or output.get("class"),
            output_type=output.get("type"),
            output_type_label=output.get("type_label"),
            ingredients=ingredients,
        )


class Blueprints:
    """Blueprints from the star-citizen.wiki API (``/api/blueprints``)."""

    def __init__(self, client: StarCitizenWikiClient, *, locale: str = DEFAULT_LOCALE) -> None:
        self._client = client
        self._locale = locale

    async def get(self, uuid: str) -> Blueprint:
        """Fetch a single blueprint by UUID.

        Raises :class:`NotFoundError` if no such blueprint exists.
        """
        payload = await self._client.get(f"{_BASE}/{uuid.strip()}")
        data = extract_data(payload)
        if not data:
            raise NotFoundError(f"No blueprint found for {uuid!r}")
        return Blueprint.from_api(data, self._locale)

    async def search(
        self,
        *,
        query: str | None = None,
        output_uuid: str | None = None,
        output_name: str | None = None,
        output_class: str | None = None,
        output_type: str | None = None,
        default: bool | None = None,
        ingredient: str | None = None,
        ingredient_uuid: str | None = None,
        resource_uuid: str | None = None,
        sort: str = DEFAULT_SORT,
        page_size: int = DEFAULT_PAGE_SIZE,
        version: str | None = None,
    ) -> list[Blueprint]:
        """Search and filter blueprints.

        All parameters are optional and map directly to the API query params:

        - ``query`` — partial crafted item name (``filter[query]``)
        - ``output_uuid`` — filter by crafted item UUID (``filter[output.uuid]``)
        - ``output_name`` — filter by crafted item name (``filter[output.name]``)
        - ``output_class`` — filter by crafted item class (``filter[output.class]``)
        - ``output_type`` — filter by crafted item type (``filter[output.type]``)
        - ``default`` — filter by default availability (``filter[default]``)
        - ``ingredient`` — match ingredient by name, key, or UUID (``filter[ingredient]``)
        - ``ingredient_uuid`` — filter by ingredient commodity UUID; comma-separated (``filter[ingredient.uuid]``)
        - ``resource_uuid`` — filter by resource UUID incl. dismantle returns; comma-separated (``filter[resource.uuid]``)
        - ``sort`` — sort field, prefix ``-`` for descending; supports ``craft_time_seconds``,
          ``ingredient_count``, ``unlocking_missions_count`` (default: ``-craft_time_seconds``)
        - ``page_size`` — results per page, max 200 (default: 30)
        - ``version`` — game version code; omit to use the API default
        """
        params: dict[str, Any] = {
            "page[size]": min(page_size, MAX_PAGE_SIZE),
            "sort": sort,
        }
        if query is not None:
            params["filter[query]"] = query
        if output_uuid is not None:
            params["filter[output.uuid]"] = output_uuid
        if output_name is not None:
            params["filter[output.name]"] = output_name
        if output_class is not None:
            params["filter[output.class]"] = output_class
        if output_type is not None:
            params["filter[output.type]"] = output_type
        if default is not None:
            params["filter[default]"] = str(default).lower()
        if ingredient is not None:
            params["filter[ingredient]"] = ingredient
        if ingredient_uuid is not None:
            params["filter[ingredient.uuid]"] = ingredient_uuid
        if resource_uuid is not None:
            params["filter[resource.uuid]"] = resource_uuid
        if version is not None:
            params["version"] = version

        payload = await self._client.get(_BASE, params=params)
        raw = extract_data(payload, [])
        return [Blueprint.from_api(item, self._locale) for item in raw]
