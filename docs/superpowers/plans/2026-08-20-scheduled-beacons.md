# Scheduled Beacons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let members schedule a beacon ahead of time via a new `when` option on every category command; the bot posts an RSVP embed immediately and opens the real beacon thread automatically at the chosen time, auto-joining everyone who RSVP'd.

**Architecture:** A new `beacons:scheduled:*` state namespace (mirroring the existing `beacons:beacon:*` pattern) holds pending scheduled beacons, keyed by their RSVP embed's message ID. A new `scheduled.py` module owns creation, RSVP button handlers, and the reminder/fire logic invoked from the existing 5-minute maintenance sweep. `lifecycle.open_beacon` is refactored to extract its thread-creation core into a reusable `create_beacon_thread` helper so both the instant-open path and the scheduled-fire path share one code path for actually creating a beacon thread.

**Tech Stack:** Python 3, discord.py (`discord.ext.commands`, `discord.app_commands`, `discord.ui`), aiosqlite-backed `StateStore`, pytest + pytest-asyncio.

## Global Constraints

- `when` duration bounds: minimum 5 minutes, maximum 24 hours (see spec "Command surface").
- Reminder fires once, 10 minutes before `open_at` (see spec "Maintenance sweep integration").
- Scheduling is gated by an optional `schedule_role` setting; unset means open to everyone. RSVP/Join is never gated. Beacon admins (`lifecycle.is_beacon_admin`) can always schedule regardless of the gate.
- Cancel is restricted to the requester or a beacon admin.
- Follow existing code conventions in `src/commands/beacons/`: `from __future__ import annotations`, module-level `logger = logging.getLogger(__name__)`, ephemeral ack via `interaction.response.defer(ephemeral=True)` then `interaction.followup.send(...)`, best-effort Discord calls wrapped in `try/except discord.HTTPException` with a `logger.warning`.

---

## File Structure

- Create `src/commands/beacons/duration.py` — relative-duration string parsing (`parse_duration`).
- Modify `src/commands/beacons/store.py` — scheduled-beacon CRUD, the `scheduled_open` index, and a new `schedule_role_id` default setting.
- Modify `src/commands/beacons/lifecycle.py` — extract `create_beacon_thread` from `open_beacon`.
- Modify `src/commands/beacons/embeds.py` — extract a shared field-rendering helper and add `build_scheduled_embed`.
- Create `src/commands/beacons/scheduled.py` — `can_schedule`, `schedule_beacon`, `open_or_schedule`, RSVP button handlers, and `run_scheduled_beacons` (reminder + fire), all called from the maintenance sweep and the new view.
- Modify `src/commands/beacons/views.py` — add `ScheduledBeaconView` (Join/Leave/Cancel).
- Modify `src/commands/beacons/maintenance.py` — call `scheduled.run_scheduled_beacons`.
- Modify `src/commands/beacons/setup_cmd.py` — `schedule_role` option on `/beacon config`.
- Modify `src/commands/beacons/__init__.py` — register `ScheduledBeaconView`, add `when` to all nine category commands via `scheduled.open_or_schedule`, add `schedule_role` to the `config` command.

---

### Task 1: Duration parser

**Files:**
- Create: `src/commands/beacons/duration.py`
- Test: `tests/commands/beacons/test_duration.py`

**Interfaces:**
- Produces: `parse_duration(text: str) -> int | None`, `MIN_SECONDS: int`, `MAX_SECONDS: int`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/commands/beacons/test_duration.py
from src.commands.beacons.duration import MAX_SECONDS, MIN_SECONDS, parse_duration


def test_parses_minutes():
    assert parse_duration("45m") == 45 * 60


def test_parses_hours():
    assert parse_duration("2h") == 2 * 3600


def test_parses_combined_hours_and_minutes():
    assert parse_duration("1h30m") == 90 * 60


def test_parses_days():
    assert parse_duration("1d") == 86400


def test_is_case_insensitive_and_ignores_spaces():
    assert parse_duration(" 1H 30M ") == 90 * 60


def test_rejects_empty_string():
    assert parse_duration("") is None


def test_rejects_unparseable_text():
    assert parse_duration("soon") is None


def test_rejects_below_minimum():
    assert parse_duration("4m") is None


def test_accepts_minimum_boundary():
    assert parse_duration("5m") == MIN_SECONDS


def test_rejects_above_maximum():
    assert parse_duration("25h") is None


def test_accepts_maximum_boundary():
    assert parse_duration("24h") == MAX_SECONDS
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/commands/beacons/test_duration.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.commands.beacons.duration'`

- [ ] **Step 3: Write the implementation**

```python
# src/commands/beacons/duration.py
"""Relative duration parsing for scheduled beacons, e.g. "45m", "2h", "1h30m"."""

from __future__ import annotations

import re

MIN_SECONDS = 5 * 60
MAX_SECONDS = 24 * 60 * 60

_PATTERN = re.compile(r"^(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?$")


def parse_duration(text: str) -> int | None:
    """Parse a relative duration like "1h30m" into seconds.

    Returns None if the text does not parse or the total falls outside
    [MIN_SECONDS, MAX_SECONDS].
    """
    if not text:
        return None
    match = _PATTERN.match(text.strip().lower().replace(" ", ""))
    if not match or not any(match.groups()):
        return None
    days, hours, minutes = (int(group) if group else 0 for group in match.groups())
    total = days * 86400 + hours * 3600 + minutes * 60
    if total < MIN_SECONDS or total > MAX_SECONDS:
        return None
    return total
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/commands/beacons/test_duration.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add src/commands/beacons/duration.py tests/commands/beacons/test_duration.py
git commit -m "feat(beacons): add relative duration parser for scheduled beacons"
```

---

### Task 2: Store layer for scheduled beacons

**Files:**
- Modify: `src/commands/beacons/store.py`
- Test: `tests/commands/beacons/test_store.py`

**Interfaces:**
- Consumes: `src.storage.StateStore` (`.get`, `.set`, `.delete`, `.keys`), same as existing `store.py` functions.
- Produces:
  - `get_scheduled(state, message_id: int) -> dict | None`
  - `save_scheduled(state, message_id: int, scheduled: dict) -> None`
  - `delete_scheduled(state, message_id: int) -> None`
  - `scheduled_beacons(state, guild_id: int) -> list[tuple[int, dict]]`
  - `get_scheduled_open(state, guild_id: int, user_id: int, category: str) -> int | None`
  - `set_scheduled_open(state, guild_id: int, user_id: int, category: str, message_id: int) -> None`
  - `clear_scheduled_open(state, guild_id: int, user_id: int, category: str) -> None`
  - `DEFAULT_SETTINGS["schedule_role_id"]` key (`None` by default)

- [ ] **Step 1: Write the failing tests**

Add to `tests/commands/beacons/test_store.py`:

```python
@pytest.mark.asyncio
async def test_scheduled_roundtrip(state):
    assert await store.get_scheduled(state, 500) is None
    scheduled = {
        "guild_id": 1,
        "channel_id": 10,
        "category": "medic",
        "requester_id": 42,
        "fields": {"location": "Stanton"},
        "open_at": 999.0,
        "rsvp": [],
        "reminded_at": None,
        "created_at": 100.0,
    }
    await store.save_scheduled(state, 500, scheduled)
    assert await store.get_scheduled(state, 500) == scheduled
    await store.delete_scheduled(state, 500)
    assert await store.get_scheduled(state, 500) is None


@pytest.mark.asyncio
async def test_scheduled_beacons_filters_by_guild(state):
    await store.save_scheduled(state, 1, {"guild_id": 10, "category": "medic"})
    await store.save_scheduled(state, 2, {"guild_id": 99, "category": "medic"})
    result = await store.scheduled_beacons(state, 10)
    assert [mid for mid, _ in result] == [1]


@pytest.mark.asyncio
async def test_scheduled_open_index(state):
    assert await store.get_scheduled_open(state, 1, 42, "medic") is None
    await store.set_scheduled_open(state, 1, 42, "medic", 500)
    assert await store.get_scheduled_open(state, 1, 42, "medic") == 500
    assert await store.get_scheduled_open(state, 1, 42, "mining") is None
    await store.clear_scheduled_open(state, 1, 42, "medic")
    assert await store.get_scheduled_open(state, 1, 42, "medic") is None


@pytest.mark.asyncio
async def test_scheduled_open_index_does_not_collide_with_scheduled_beacons_prefix(state):
    await store.save_scheduled(state, 500, {"guild_id": 1, "category": "medic"})
    await store.set_scheduled_open(state, 1, 42, "medic", 500)
    result = await store.scheduled_beacons(state, 1)
    assert [mid for mid, _ in result] == [500]


def test_default_settings_include_schedule_role():
    assert store.DEFAULT_SETTINGS["schedule_role_id"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/commands/beacons/test_store.py -v`
Expected: FAIL with `AttributeError: module 'src.commands.beacons.store' has no attribute 'get_scheduled'` (and similar for the others)

- [ ] **Step 3: Implement the store functions**

In `src/commands/beacons/store.py`, add `"schedule_role_id": None` to `DEFAULT_SETTINGS`:

```python
DEFAULT_SETTINGS: dict[str, Any] = {
    "idle_warn_minutes": 120,
    "idle_close_minutes": 60,
    "escalate_minutes": 15,
    "voice": False,
    "voice_category_id": None,
    "digest_channel_id": None,
    "schedule_role_id": None,
}
```

Then append these functions (near `_beacon_key`/`get_beacon`/`save_beacon`, before the rep-tracking section):

```python
def _scheduled_key(message_id: int) -> str:
    return f"beacons:scheduled:{message_id}"


def _scheduled_open_key(guild_id: int, user_id: int, category: str) -> str:
    return f"beacons:scheduled_open:{guild_id}:{user_id}:{category}"


async def get_scheduled(state: StateStore, message_id: int) -> dict[str, Any] | None:
    return await state.get(_scheduled_key(message_id))


async def save_scheduled(state: StateStore, message_id: int, scheduled: dict[str, Any]) -> None:
    await state.set(_scheduled_key(message_id), scheduled)


async def delete_scheduled(state: StateStore, message_id: int) -> None:
    await state.delete(_scheduled_key(message_id))


async def scheduled_beacons(state: StateStore, guild_id: int) -> list[tuple[int, dict[str, Any]]]:
    results = []
    for key in await state.keys("beacons:scheduled:"):
        raw = await state.get(key)
        if not raw or raw.get("guild_id") != guild_id:
            continue
        results.append((int(key.rsplit(":", 1)[-1]), raw))
    return results


async def get_scheduled_open(state: StateStore, guild_id: int, user_id: int, category: str) -> int | None:
    return await state.get(_scheduled_open_key(guild_id, user_id, category))


async def set_scheduled_open(state: StateStore, guild_id: int, user_id: int, category: str, message_id: int) -> None:
    await state.set(_scheduled_open_key(guild_id, user_id, category), message_id)


async def clear_scheduled_open(state: StateStore, guild_id: int, user_id: int, category: str) -> None:
    await state.delete(_scheduled_open_key(guild_id, user_id, category))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/commands/beacons/test_store.py -v`
Expected: PASS (all tests, including the 5 new ones)

- [ ] **Step 5: Commit**

```bash
git add src/commands/beacons/store.py tests/commands/beacons/test_store.py
git commit -m "feat(beacons): add scheduled-beacon storage and schedule_role setting"
```

---

### Task 3: Extract `create_beacon_thread` from `open_beacon`

**Files:**
- Modify: `src/commands/beacons/lifecycle.py:68-153`
- Modify: `tests/commands/beacons/test_lifecycle.py`

**Interfaces:**
- Produces: `create_beacon_thread(cog, guild: discord.Guild, config: dict, requester_id: int, display_name: str, category_key: str, field_values: dict) -> discord.Thread`. Raises `discord.HTTPException` on failure (does not write any state or reply on failure — caller decides how to report it). On success it has already saved the beacon record and both the `open` and `last_open` indexes.
- Consumes (unchanged): `store.get_config/save_beacon/set_open_beacon/set_last_open/set_config`, `CATEGORIES`, `beacon_title`, `build_beacon_embed`.

This task changes `thread.add_user(interaction.user)` to `thread.add_user(discord.Object(id=requester_id))` so the helper does not require a full `discord.Member` object — the scheduled-fire path (Task 7) only has a bare user ID. Update the existing assertion in `test_open_creates_thread_and_saves_state` accordingly.

- [ ] **Step 1: Write the failing test for the extracted helper**

Add to `tests/commands/beacons/test_lifecycle.py`:

```python
@pytest.mark.asyncio
async def test_create_beacon_thread_builds_thread_and_saves_state(make_cog):
    cog = make_cog(config=THREAD_CONFIG)
    thread = MagicMock()
    thread.id = 900
    thread.send = AsyncMock()
    thread.add_user = AsyncMock()
    channel = MagicMock()
    channel.create_thread = AsyncMock(return_value=thread)
    guild = MagicMock()
    guild.id = 1
    guild.get_channel = MagicMock(return_value=channel)
    guild.get_role = MagicMock(return_value=None)

    result = await lifecycle.create_beacon_thread(cog, guild, THREAD_CONFIG, 55, "Nova", "medic", {"location": "Stanton"})

    assert result is thread
    lifecycle.store.save_beacon.assert_awaited_once()
    saved_beacon = lifecycle.store.save_beacon.await_args.args[2]
    assert saved_beacon["requester_id"] == 55
    assert saved_beacon["fields"] == {"location": "Stanton"}
    lifecycle.store.set_open_beacon.assert_awaited_once_with(cog.bot.state, 1, 55, "medic", 900)
    lifecycle.store.set_last_open.assert_awaited_once_with(cog.bot.state, 1, 55, "medic", {"location": "Stanton"})
    added = thread.add_user.await_args.args[0]
    assert added.id == 55


@pytest.mark.asyncio
async def test_create_beacon_thread_raises_on_http_failure(make_cog):
    cog = make_cog(config=THREAD_CONFIG)
    channel = MagicMock()
    channel.create_thread = AsyncMock(side_effect=discord.HTTPException(MagicMock(status=500), "boom"))
    guild = MagicMock()
    guild.id = 1
    guild.get_channel = MagicMock(return_value=channel)
    guild.get_role = MagicMock(return_value=None)

    with pytest.raises(discord.HTTPException):
        await lifecycle.create_beacon_thread(cog, guild, THREAD_CONFIG, 55, "Nova", "medic", {"location": "Stanton"})

    lifecycle.store.save_beacon.assert_not_awaited()
    lifecycle.store.set_open_beacon.assert_not_awaited()
```

Also update the existing assertion in `test_open_creates_thread_and_saves_state` (replace the line `thread.add_user.assert_awaited_once_with(interaction.user)`):

```python
    thread.add_user.assert_awaited_once()
    added = thread.add_user.await_args.args[0]
    assert added.id == interaction.user.id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/commands/beacons/test_lifecycle.py -v`
Expected: the two new tests FAIL with `AttributeError: module 'src.commands.beacons.lifecycle' has no attribute 'create_beacon_thread'`; `test_open_creates_thread_and_saves_state` still passes at this point (unchanged behavior) even though its assertion was edited, since `interaction.user.id == interaction.user.id` trivially — this step is just to confirm the new tests fail before the refactor.

- [ ] **Step 3: Extract the helper and rewrite `open_beacon`**

Replace `open_beacon` in `src/commands/beacons/lifecycle.py` (lines 68-153) with:

```python
async def create_beacon_thread(
    cog,
    guild: discord.Guild,
    config: dict,
    requester_id: int,
    display_name: str,
    category_key: str,
    field_values: dict[str, str],
) -> discord.Thread:
    """Create the beacon thread/forum post, save its record, and set the
    open/last-open indexes. Raises discord.HTTPException on failure and
    writes no state in that case."""
    category = CATEGORIES[category_key]
    channel = guild.get_channel(config["channel_id"])

    opened_at = time.time()
    beacon = {
        "guild_id": guild.id,
        "category": category_key,
        "requester_id": requester_id,
        "members": [],
        "status": STATUS_OPEN,
        "opened_at": opened_at,
        "closed_at": None,
        "closed_by_id": None,
        "fields": field_values,
        "last_activity_at": opened_at,
    }
    name = beacon_title(category_key, display_name, field_values)
    content, dropped_role_note, role_dropped = _resolve_ping_content(guild, config, category_key, category)
    embed = build_beacon_embed(beacon)

    if config["mode"] == "forum":
        tags = [
            tag
            for tag_key in (category_key, "open")
            if (tag := _resolve_tag(channel, config, tag_key)) is not None
        ]
        created = await channel.create_thread(
            name=name,
            content=content or None,
            embed=embed,
            applied_tags=tags,
            view=cog.beacon_view,
        )
        thread = created.thread
    else:
        thread = await channel.create_thread(name=name, type=discord.ChannelType.public_thread)
        await thread.send(content=content, embed=embed, view=cog.beacon_view)
    if dropped_role_note:
        await thread.send(dropped_role_note)
    await thread.add_user(discord.Object(id=requester_id))

    if role_dropped:
        config["roles"].pop(category_key, None)
        await store.set_config(cog.bot.state, guild.id, config)
    await store.save_beacon(cog.bot.state, thread.id, beacon)
    await store.set_open_beacon(cog.bot.state, guild.id, requester_id, category_key, thread.id)
    await store.set_last_open(cog.bot.state, guild.id, requester_id, category_key, field_values)
    return thread


async def open_beacon(cog, interaction: discord.Interaction, category_key: str, field_values: dict[str, str]) -> None:
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    category = CATEGORIES[category_key]

    kinds = _field_kinds(category)
    for key, value in field_values.items():
        if kinds.get(key) in _LOCATION_KINDS and parse_location(value) is None:
            await _reply(
                interaction,
                f"`{value}` is not a valid location. Use the form `system:planet:location`, "
                "for example `Stanton:Hurston:Lorville` (later parts optional).",
            )
            return

    config = await store.get_config(cog.bot.state, guild.id)
    if config is None:
        await _reply(interaction, "Beacons are not set up yet. Ask an admin to run `/beacon setup`.")
        return

    lock = _lock_for(f"open:{guild.id}:{interaction.user.id}:{category_key}")
    async with lock:
        existing = await store.get_open_beacon(cog.bot.state, guild.id, interaction.user.id, category_key)
        if existing is not None:
            await _reply(
                interaction,
                f"You already have an open {category.label} beacon: https://discord.com/channels/{guild.id}/{existing}",
            )
            return

        if guild.get_channel(config["channel_id"]) is None:
            await _reply(interaction, "The beacon channel is missing. Ask an admin to re-run `/beacon setup`.")
            return

        try:
            thread = await create_beacon_thread(
                cog, guild, config, interaction.user.id, interaction.user.display_name, category_key, field_values
            )
        except discord.HTTPException as error:
            logger.exception("Failed to create beacon thread")
            await _reply(interaction, f"Could not create the beacon: {error}. Check the bot's channel permissions.")
            return

        await _reply(interaction, f"Beacon opened: {thread.mention}")
        await _refresh_board(cog, guild)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/commands/beacons/test_lifecycle.py -v`
Expected: PASS (all tests, including the 2 new ones)

- [ ] **Step 5: Run the full beacons test suite to check for regressions**

Run: `pytest tests/commands/beacons/ -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/commands/beacons/lifecycle.py tests/commands/beacons/test_lifecycle.py
git commit -m "refactor(beacons): extract create_beacon_thread from open_beacon"
```

---

### Task 4: Scheduled-beacon embed

**Files:**
- Modify: `src/commands/beacons/embeds.py`
- Modify: `tests/commands/beacons/test_embeds.py`

**Interfaces:**
- Produces: `build_scheduled_embed(scheduled: dict, *, cancelled_by_id: int | None = None, opened_thread_id: int | None = None) -> discord.Embed`.
- Consumes: `CATEGORIES`, `format_breadcrumb` (already imported in `embeds.py`).

- [ ] **Step 1: Write the failing tests**

Add to `tests/commands/beacons/test_embeds.py`:

```python
def _scheduled(**overrides):
    scheduled = {
        "guild_id": 1,
        "channel_id": 10,
        "category": "medic",
        "requester_id": 42,
        "fields": {"location": "Stanton:Hurston:Lorville", "tier": "T2"},
        "open_at": 1000.0,
        "rsvp": [],
        "reminded_at": None,
        "created_at": 100.0,
    }
    scheduled.update(overrides)
    return scheduled


def test_scheduled_embed_shows_category_requester_and_fields():
    from src.commands.beacons.embeds import build_scheduled_embed

    embed = build_scheduled_embed(_scheduled())
    assert "Medical" in embed.title
    assert "scheduled" in embed.title.lower()
    field_names = [f.name for f in embed.fields]
    field_values = [f.value for f in embed.fields]
    assert "Location" in field_names
    assert "Stanton › Hurston › Lorville" in field_values
    assert any("<@42>" in v for v in field_values)


def test_scheduled_embed_pending_status_shows_open_at_timestamp():
    from src.commands.beacons.embeds import build_scheduled_embed

    embed = build_scheduled_embed(_scheduled(open_at=1000.0))
    values = " ".join(f.value for f in embed.fields)
    assert "<t:1000:R>" in values
    assert "<t:1000:f>" in values


def test_scheduled_embed_lists_rsvp():
    from src.commands.beacons.embeds import build_scheduled_embed

    embed = build_scheduled_embed(_scheduled(rsvp=[7, 8]))
    field_names = [f.name for f in embed.fields]
    values = " ".join(f.value for f in embed.fields)
    assert "RSVP (2)" in field_names
    assert "<@7>" in values
    assert "<@8>" in values


def test_scheduled_embed_omits_rsvp_field_when_empty():
    from src.commands.beacons.embeds import build_scheduled_embed

    embed = build_scheduled_embed(_scheduled(rsvp=[]))
    assert not any(f.name.startswith("RSVP") for f in embed.fields)


def test_scheduled_embed_cancelled_status():
    from src.commands.beacons.embeds import build_scheduled_embed

    embed = build_scheduled_embed(_scheduled(), cancelled_by_id=7)
    values = " ".join(f.value for f in embed.fields)
    assert "Cancelled by <@7>" in values


def test_scheduled_embed_opened_status_shows_thread():
    from src.commands.beacons.embeds import build_scheduled_embed

    embed = build_scheduled_embed(_scheduled(), opened_thread_id=999)
    field_names = [f.name for f in embed.fields]
    values = " ".join(f.value for f in embed.fields)
    assert "Opened" in values
    assert "Thread" in field_names
    assert "<#999>" in values
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/commands/beacons/test_embeds.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_scheduled_embed'`

- [ ] **Step 3: Extract the shared field renderer and add `build_scheduled_embed`**

In `src/commands/beacons/embeds.py`, replace the `for spec in category.fields:` loop inside `build_beacon_embed` (lines 81-86) with a call to a new shared helper, and add the new embed builder. Full replacement for the section from `build_beacon_embed` through `build_panel_content`:

```python
def _add_category_fields(embed: discord.Embed, category, fields: dict[str, Any]) -> None:
    for spec in category.fields:
        value = fields.get(spec.key)
        if not value:
            continue
        shown = format_breadcrumb(value) if spec.kind in ("location", "route") else value
        embed.add_field(name=spec.label, value=shown, inline=False)


def build_beacon_embed(beacon: dict[str, Any]) -> discord.Embed:
    category = CATEGORIES[beacon["category"]]
    embed = discord.Embed(
        title=f"{category.emoji} {category.label} beacon",
        color=_STATUS_COLORS[beacon["status"]],
    )
    embed.add_field(name="Requester", value=f"<@{beacon['requester_id']}>", inline=True)
    embed.add_field(name="Status", value=_status_text(beacon), inline=True)
    if beacon["members"]:
        responders = ", ".join(f"<@{member}>" for member in beacon["members"])
        size = beacon["fields"].get("size")
        name = f"Responders ({len(beacon['members'])}/{size})" if size else "Responders"
        embed.add_field(name=name, value=responders, inline=False)
    _add_category_fields(embed, category, beacon["fields"])
    embed.add_field(name="Opened", value=f"<t:{int(beacon['opened_at'])}:R>", inline=True)
    return embed


def _status_text(beacon: dict[str, Any]) -> str:
    if beacon["status"] == STATUS_ACTIVE:
        return "Active"
    if beacon["status"] == STATUS_CLOSED:
        closed_at = int(beacon["closed_at"]) if beacon["closed_at"] else None
        when = f" <t:{closed_at}:R>" if closed_at else ""
        return f"Closed by <@{beacon['closed_by_id']}>{when}"
    return "Open"


def build_scheduled_embed(
    scheduled: dict[str, Any], *, cancelled_by_id: int | None = None, opened_thread_id: int | None = None
) -> discord.Embed:
    category = CATEGORIES[scheduled["category"]]
    embed = discord.Embed(
        title=f"{category.emoji} {category.label} beacon (scheduled)",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Requester", value=f"<@{scheduled['requester_id']}>", inline=True)
    embed.add_field(name="Status", value=_scheduled_status_text(scheduled, cancelled_by_id, opened_thread_id), inline=True)
    if scheduled["rsvp"]:
        rsvp = ", ".join(f"<@{user_id}>" for user_id in scheduled["rsvp"])
        embed.add_field(name=f"RSVP ({len(scheduled['rsvp'])})", value=rsvp, inline=False)
    _add_category_fields(embed, category, scheduled["fields"])
    if opened_thread_id is not None:
        embed.add_field(name="Thread", value=f"<#{opened_thread_id}>", inline=False)
    return embed


def _scheduled_status_text(scheduled: dict[str, Any], cancelled_by_id: int | None, opened_thread_id: int | None) -> str:
    open_at = int(scheduled["open_at"])
    if opened_thread_id is not None:
        return f"Opened <t:{open_at}:R>"
    if cancelled_by_id is not None:
        return f"Cancelled by <@{cancelled_by_id}>"
    return f"Opens <t:{open_at}:R> (<t:{open_at}:f>)"


def build_panel_content(mention) -> str:
    lines = [f"{c.emoji} {mention(c.key)}: {c.description}" for c in CATEGORIES.values()]
    return "**Service Beacons**\nNeed a hand in the verse? Click a command below to open a beacon.\n\n" + "\n".join(
        lines
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/commands/beacons/test_embeds.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add src/commands/beacons/embeds.py tests/commands/beacons/test_embeds.py
git commit -m "feat(beacons): add build_scheduled_embed and share field rendering"
```

---

### Task 5: `scheduled.py` — creation, role gate, and RSVP handlers

**Files:**
- Create: `src/commands/beacons/scheduled.py`
- Test: `tests/commands/beacons/test_scheduled.py`

**Interfaces:**
- Consumes: `store.get_config/get_settings/get_scheduled_open/set_scheduled_open/save_scheduled/get_scheduled/delete_scheduled/clear_scheduled_open`, `lifecycle.open_beacon/is_beacon_admin/lock_for/_reply`-equivalent pattern, `duration.parse_duration/MIN_SECONDS/MAX_SECONDS`, `embeds.build_scheduled_embed`, `categories.CATEGORIES`, `location.parse_location`.
- Produces:
  - `can_schedule(interaction, config: dict) -> bool`
  - `schedule_beacon(cog, interaction, category_key: str, field_values: dict, when_seconds: int) -> None`
  - `open_or_schedule(cog, interaction, category_key: str, field_values: dict, when: str | None) -> None`
  - `handle_scheduled_join(cog, interaction) -> None`
  - `handle_scheduled_leave(cog, interaction) -> None`
  - `handle_scheduled_cancel(cog, interaction) -> None`

These four handlers are consumed by Task 6 (`ScheduledBeaconView`) and `open_or_schedule` is consumed by Task 8 (`__init__.py` wiring).

- [ ] **Step 1: Write the failing tests**

```python
# tests/commands/beacons/test_scheduled.py
import time
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from src.commands.beacons import scheduled

THREAD_CONFIG = {"channel_id": 10, "mode": "thread", "panel_message_id": 11, "tag_ids": {}, "roles": {}}


def _role(role_id):
    role = MagicMock()
    role.id = role_id
    role.mention = f"<@&{role_id}>"
    return role


def _interaction(guild_id=1, user_id=42, admin=False, roles=()):
    interaction = MagicMock()
    interaction.guild.id = guild_id
    interaction.user.id = user_id
    interaction.user.display_name = "Garulf"
    interaction.user.guild_permissions.administrator = admin
    interaction.user.roles = list(roles)
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction


@pytest.fixture
def make_cog(monkeypatch):
    def _make(config=None, scheduled_open=None, scheduled_record=None):
        cog = MagicMock()
        cog.bot.state = MagicMock()
        cog.scheduled_beacon_view = MagicMock()
        monkeypatch.setattr(scheduled.store, "get_config", AsyncMock(return_value=config))
        monkeypatch.setattr(scheduled.store, "get_scheduled_open", AsyncMock(return_value=scheduled_open))
        monkeypatch.setattr(scheduled.store, "set_scheduled_open", AsyncMock())
        monkeypatch.setattr(scheduled.store, "save_scheduled", AsyncMock())
        monkeypatch.setattr(scheduled.store, "get_scheduled", AsyncMock(return_value=scheduled_record))
        monkeypatch.setattr(scheduled.store, "delete_scheduled", AsyncMock())
        monkeypatch.setattr(scheduled.store, "clear_scheduled_open", AsyncMock())
        monkeypatch.setattr(scheduled.lifecycle, "open_beacon", AsyncMock())
        return cog

    return _make


def _config_with_role(role_id):
    return {**THREAD_CONFIG, "settings": {"schedule_role_id": role_id}}


def test_can_schedule_open_when_no_role_configured():
    assert scheduled.can_schedule(_interaction(), THREAD_CONFIG) is True


def test_can_schedule_denies_without_matching_role():
    interaction = _interaction(roles=[_role(9)])
    assert scheduled.can_schedule(interaction, _config_with_role(5)) is False


def test_can_schedule_allows_matching_role():
    interaction = _interaction(roles=[_role(5)])
    assert scheduled.can_schedule(interaction, _config_with_role(5)) is True


def test_can_schedule_allows_admin_regardless_of_role():
    interaction = _interaction(admin=True)
    assert scheduled.can_schedule(interaction, _config_with_role(5)) is True


@pytest.mark.asyncio
async def test_schedule_rejects_malformed_location(make_cog):
    cog = make_cog(config=THREAD_CONFIG)
    interaction = _interaction()
    await scheduled.schedule_beacon(cog, interaction, "medic", {"location": "a:b:c:d"}, 3600)
    assert "system:planet:location" in interaction.followup.send.await_args.args[0]
    scheduled.store.save_scheduled.assert_not_awaited()


@pytest.mark.asyncio
async def test_schedule_requires_setup(make_cog):
    cog = make_cog(config=None)
    interaction = _interaction()
    await scheduled.schedule_beacon(cog, interaction, "medic", {"location": "Stanton"}, 3600)
    assert "setup" in interaction.followup.send.await_args.args[0]


@pytest.mark.asyncio
async def test_schedule_rejects_when_role_gated_and_missing_role(make_cog):
    cog = make_cog(config=_config_with_role(5))
    interaction = _interaction(roles=[_role(9)])
    interaction.guild.get_role = MagicMock(return_value=_role(5))
    await scheduled.schedule_beacon(cog, interaction, "medic", {"location": "Stanton"}, 3600)
    msg = interaction.followup.send.await_args.args[0]
    assert "<@&5>" in msg
    scheduled.store.save_scheduled.assert_not_awaited()


@pytest.mark.asyncio
async def test_schedule_rejects_duplicate_pending(make_cog):
    cog = make_cog(config=THREAD_CONFIG, scheduled_open=555)
    interaction = _interaction()
    await scheduled.schedule_beacon(cog, interaction, "medic", {"location": "Stanton"}, 3600)
    assert "already have a pending" in interaction.followup.send.await_args.args[0]
    scheduled.store.save_scheduled.assert_not_awaited()


@pytest.mark.asyncio
async def test_schedule_posts_embed_and_saves_state(make_cog):
    cog = make_cog(config=THREAD_CONFIG)
    interaction = _interaction()
    message = MagicMock()
    message.id = 700
    message.jump_url = "https://discord.com/channels/1/10/700"
    channel = MagicMock()
    channel.send = AsyncMock(return_value=message)
    interaction.guild.get_channel = MagicMock(return_value=channel)
    before = time.time()

    await scheduled.schedule_beacon(cog, interaction, "medic", {"location": "Stanton"}, 3600)

    channel.send.assert_awaited_once()
    assert channel.send.await_args.kwargs["view"] is cog.scheduled_beacon_view
    scheduled.store.save_scheduled.assert_awaited_once()
    saved = scheduled.store.save_scheduled.await_args.args[2]
    assert saved["requester_id"] == 42
    assert saved["rsvp"] == []
    assert saved["open_at"] >= before + 3600
    scheduled.store.set_scheduled_open.assert_awaited_once_with(cog.bot.state, 1, 42, "medic", 700)
    assert "700" in interaction.followup.send.await_args.args[0] or message.jump_url in interaction.followup.send.await_args.args[0]


@pytest.mark.asyncio
async def test_open_or_schedule_calls_open_beacon_when_when_is_none(make_cog):
    cog = make_cog()
    interaction = _interaction()
    await scheduled.open_or_schedule(cog, interaction, "medic", {"location": "Stanton"}, None)
    scheduled.lifecycle.open_beacon.assert_awaited_once_with(cog, interaction, "medic", {"location": "Stanton"})


@pytest.mark.asyncio
async def test_open_or_schedule_rejects_invalid_duration(make_cog):
    cog = make_cog()
    interaction = _interaction()
    await scheduled.open_or_schedule(cog, interaction, "medic", {"location": "Stanton"}, "soon")
    interaction.response.send_message.assert_awaited_once()
    msg = interaction.response.send_message.await_args.args[0]
    assert "soon" in msg
    scheduled.lifecycle.open_beacon.assert_not_awaited()


def _scheduled_record(**overrides):
    record = {
        "guild_id": 1,
        "channel_id": 10,
        "category": "medic",
        "requester_id": 42,
        "fields": {"location": "Stanton"},
        "open_at": 99999.0,
        "rsvp": [],
        "reminded_at": None,
        "created_at": 100.0,
    }
    record.update(overrides)
    return record


def _button_interaction(user_id=42, admin=False):
    interaction = MagicMock()
    interaction.guild.id = 1
    interaction.user.id = user_id
    interaction.user.guild_permissions.administrator = admin
    interaction.user.roles = []
    interaction.message.id = 700
    interaction.message.edit = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction


@pytest.mark.asyncio
async def test_handle_scheduled_join_adds_rsvp(make_cog):
    cog = make_cog(scheduled_record=_scheduled_record())
    interaction = _button_interaction(user_id=7)
    await scheduled.handle_scheduled_join(cog, interaction)
    saved = scheduled.store.save_scheduled.await_args.args[2]
    assert saved["rsvp"] == [7]
    interaction.message.edit.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_scheduled_join_rejects_duplicate(make_cog):
    cog = make_cog(scheduled_record=_scheduled_record(rsvp=[7]))
    interaction = _button_interaction(user_id=7)
    await scheduled.handle_scheduled_join(cog, interaction)
    assert "already" in interaction.followup.send.await_args.args[0]
    scheduled.store.save_scheduled.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_scheduled_leave_removes_rsvp(make_cog):
    cog = make_cog(scheduled_record=_scheduled_record(rsvp=[7]))
    interaction = _button_interaction(user_id=7)
    await scheduled.handle_scheduled_leave(cog, interaction)
    saved = scheduled.store.save_scheduled.await_args.args[2]
    assert saved["rsvp"] == []


@pytest.mark.asyncio
async def test_handle_scheduled_cancel_requires_requester_or_admin(make_cog):
    cog = make_cog(scheduled_record=_scheduled_record())
    interaction = _button_interaction(user_id=999)
    await scheduled.handle_scheduled_cancel(cog, interaction)
    assert "Only the requester" in interaction.followup.send.await_args.args[0]
    scheduled.store.delete_scheduled.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_scheduled_cancel_deletes_record_for_requester(make_cog):
    cog = make_cog(scheduled_record=_scheduled_record())
    interaction = _button_interaction(user_id=42)
    await scheduled.handle_scheduled_cancel(cog, interaction)
    scheduled.store.delete_scheduled.assert_awaited_once_with(cog.bot.state, 700)
    scheduled.store.clear_scheduled_open.assert_awaited_once_with(cog.bot.state, 1, 42, "medic")
    interaction.message.edit.assert_awaited_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/commands/beacons/test_scheduled.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.commands.beacons.scheduled'`

- [ ] **Step 3: Write the implementation**

```python
# src/commands/beacons/scheduled.py
"""Scheduled beacons: an RSVP embed posted ahead of time that opens the real
beacon thread automatically when its scheduled time arrives."""

from __future__ import annotations

import logging
import time

import discord

from . import lifecycle, store
from .categories import CATEGORIES
from .duration import MAX_SECONDS, MIN_SECONDS, parse_duration
from .embeds import build_scheduled_embed
from .lifecycle import is_beacon_admin, lock_for
from .location import parse_location

logger = logging.getLogger(__name__)

_LOCATION_KINDS = {"location", "route"}


def _field_kinds(category) -> dict[str, str]:
    return {spec.key: spec.kind for spec in category.fields}


def can_schedule(interaction: discord.Interaction, config: dict) -> bool:
    role_id = store.get_settings(config)["schedule_role_id"]
    if role_id is None:
        return True
    if is_beacon_admin(interaction):
        return True
    return any(role.id == role_id for role in interaction.user.roles)


async def _reply(interaction: discord.Interaction, message: str) -> None:
    await interaction.followup.send(message, ephemeral=True)


async def open_or_schedule(
    cog, interaction: discord.Interaction, category_key: str, field_values: dict[str, str], when: str | None
) -> None:
    if when is None:
        await lifecycle.open_beacon(cog, interaction, category_key, field_values)
        return
    seconds = parse_duration(when)
    if seconds is None:
        await interaction.response.send_message(
            f"`{when}` is not a valid duration. Use a combination like `45m`, `2h`, or `1d`, "
            f"between {MIN_SECONDS // 60} minutes and {MAX_SECONDS // 3600} hours.",
            ephemeral=True,
        )
        return
    await schedule_beacon(cog, interaction, category_key, field_values, seconds)


async def schedule_beacon(
    cog, interaction: discord.Interaction, category_key: str, field_values: dict[str, str], when_seconds: int
) -> None:
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    category = CATEGORIES[category_key]

    kinds = _field_kinds(category)
    for key, value in field_values.items():
        if kinds.get(key) in _LOCATION_KINDS and parse_location(value) is None:
            await _reply(
                interaction,
                f"`{value}` is not a valid location. Use the form `system:planet:location`, "
                "for example `Stanton:Hurston:Lorville` (later parts optional).",
            )
            return

    config = await store.get_config(cog.bot.state, guild.id)
    if config is None:
        await _reply(interaction, "Beacons are not set up yet. Ask an admin to run `/beacon setup`.")
        return

    if not can_schedule(interaction, config):
        role_id = store.get_settings(config)["schedule_role_id"]
        role = guild.get_role(role_id)
        name = role.mention if role else "the configured role"
        await _reply(interaction, f"Only {name} can schedule a beacon.")
        return

    lock = lock_for(f"schedule_open:{guild.id}:{interaction.user.id}:{category_key}")
    async with lock:
        existing = await store.get_scheduled_open(cog.bot.state, guild.id, interaction.user.id, category_key)
        if existing is not None:
            await _reply(interaction, "You already have a pending scheduled beacon in this category.")
            return

        channel = guild.get_channel(config["channel_id"])
        if channel is None:
            await _reply(interaction, "The beacon channel is missing. Ask an admin to re-run `/beacon setup`.")
            return

        now = time.time()
        scheduled = {
            "guild_id": guild.id,
            "channel_id": channel.id,
            "category": category_key,
            "requester_id": interaction.user.id,
            "fields": field_values,
            "open_at": now + when_seconds,
            "rsvp": [],
            "reminded_at": None,
            "created_at": now,
        }
        embed = build_scheduled_embed(scheduled)
        try:
            message = await channel.send(embed=embed, view=cog.scheduled_beacon_view)
        except discord.HTTPException as error:
            logger.exception("Failed to post scheduled beacon")
            await _reply(interaction, f"Could not schedule the beacon: {error}. Check the bot's channel permissions.")
            return

        await store.save_scheduled(cog.bot.state, message.id, scheduled)
        await store.set_scheduled_open(cog.bot.state, guild.id, interaction.user.id, category_key, message.id)
        await _reply(interaction, f"Beacon scheduled: {message.jump_url}")


async def _load_scheduled(cog, interaction: discord.Interaction) -> dict | None:
    record = await store.get_scheduled(cog.bot.state, interaction.message.id)
    if record is None:
        await _reply(interaction, "This scheduled beacon is no longer tracked.")
        await _disable_view(interaction.message)
    return record


async def _disable_view(message) -> None:
    view = discord.ui.View.from_message(message)
    for item in view.children:
        item.disabled = True
    try:
        await message.edit(view=view)
    except discord.HTTPException:
        logger.warning("Could not disable buttons on scheduled beacon message %s", message.id)


async def handle_scheduled_join(cog, interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    async with lock_for(f"scheduled:{interaction.message.id}"):
        record = await _load_scheduled(cog, interaction)
        if record is None:
            return
        if interaction.user.id in record["rsvp"]:
            await _reply(interaction, "You are already RSVP'd. Use Leave to back out.")
            return
        record["rsvp"].append(interaction.user.id)
        await store.save_scheduled(cog.bot.state, interaction.message.id, record)
        await interaction.message.edit(embed=build_scheduled_embed(record))
        await _reply(interaction, "You're on the list.")


async def handle_scheduled_leave(cog, interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    async with lock_for(f"scheduled:{interaction.message.id}"):
        record = await _load_scheduled(cog, interaction)
        if record is None:
            return
        if interaction.user.id not in record["rsvp"]:
            await _reply(interaction, "You are not RSVP'd to this beacon.")
            return
        record["rsvp"].remove(interaction.user.id)
        await store.save_scheduled(cog.bot.state, interaction.message.id, record)
        await interaction.message.edit(embed=build_scheduled_embed(record))
        await _reply(interaction, "You're off the list.")


async def handle_scheduled_cancel(cog, interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    async with lock_for(f"scheduled:{interaction.message.id}"):
        record = await _load_scheduled(cog, interaction)
        if record is None:
            return
        if interaction.user.id != record["requester_id"] and not is_beacon_admin(interaction):
            await _reply(interaction, "Only the requester or an admin can cancel this scheduled beacon.")
            return
        await store.delete_scheduled(cog.bot.state, interaction.message.id)
        await store.clear_scheduled_open(cog.bot.state, record["guild_id"], record["requester_id"], record["category"])
        embed = build_scheduled_embed(record, cancelled_by_id=interaction.user.id)
        await interaction.message.edit(embed=embed)
        await _disable_view(interaction.message)
        await _reply(interaction, "Scheduled beacon cancelled.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/commands/beacons/test_scheduled.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add src/commands/beacons/scheduled.py tests/commands/beacons/test_scheduled.py
git commit -m "feat(beacons): add scheduled-beacon creation, role gate, and RSVP handlers"
```

---

### Task 6: `ScheduledBeaconView`

**Files:**
- Modify: `src/commands/beacons/views.py`
- Modify: `tests/commands/beacons/test_views.py`

**Interfaces:**
- Consumes: `scheduled.handle_scheduled_join/handle_scheduled_leave/handle_scheduled_cancel` (Task 5).
- Produces: `ScheduledBeaconView(cog)` — persistent view with custom IDs `beacons:sched_join`, `beacons:sched_leave`, `beacons:sched_cancel`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/commands/beacons/test_views.py`:

```python
def test_scheduled_beacon_view_has_join_leave_cancel_buttons():
    from src.commands.beacons.views import ScheduledBeaconView

    view = ScheduledBeaconView(MagicMock())
    assert view.timeout is None
    assert {item.custom_id for item in view.children} == {
        "beacons:sched_join",
        "beacons:sched_leave",
        "beacons:sched_cancel",
    }


@pytest.mark.asyncio
async def test_scheduled_beacon_buttons_delegate_to_scheduled_module(monkeypatch):
    from src.commands.beacons import views as views_module
    from src.commands.beacons.views import ScheduledBeaconView

    join = AsyncMock()
    leave = AsyncMock()
    cancel = AsyncMock()
    monkeypatch.setattr(views_module.scheduled, "handle_scheduled_join", join)
    monkeypatch.setattr(views_module.scheduled, "handle_scheduled_leave", leave)
    monkeypatch.setattr(views_module.scheduled, "handle_scheduled_cancel", cancel)
    cog = MagicMock()
    view = ScheduledBeaconView(cog)
    interaction = MagicMock()

    await next(b for b in view.children if b.custom_id == "beacons:sched_join").callback(interaction)
    join.assert_awaited_once_with(cog, interaction)
    await next(b for b in view.children if b.custom_id == "beacons:sched_leave").callback(interaction)
    leave.assert_awaited_once_with(cog, interaction)
    await next(b for b in view.children if b.custom_id == "beacons:sched_cancel").callback(interaction)
    cancel.assert_awaited_once_with(cog, interaction)


def test_scheduled_beacon_cancel_button_is_danger_styled():
    from discord import ButtonStyle

    from src.commands.beacons.views import ScheduledBeaconView

    view = ScheduledBeaconView(MagicMock())
    button = next(b for b in view.children if b.custom_id == "beacons:sched_cancel")
    assert button.label == "Cancel"
    assert button.style == ButtonStyle.danger
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/commands/beacons/test_views.py -v`
Expected: FAIL with `ImportError: cannot import name 'ScheduledBeaconView'`

- [ ] **Step 3: Write the implementation**

In `src/commands/beacons/views.py`, add `from . import scheduled` to the imports and append at the end of the file:

```python
class _ScheduledJoinButton(discord.ui.Button):
    def __init__(self, cog) -> None:
        super().__init__(label="Join", style=discord.ButtonStyle.primary, custom_id="beacons:sched_join")
        self._cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await scheduled.handle_scheduled_join(self._cog, interaction)


class _ScheduledLeaveButton(discord.ui.Button):
    def __init__(self, cog) -> None:
        super().__init__(label="Leave", style=discord.ButtonStyle.secondary, custom_id="beacons:sched_leave")
        self._cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await scheduled.handle_scheduled_leave(self._cog, interaction)


class _ScheduledCancelButton(discord.ui.Button):
    def __init__(self, cog) -> None:
        super().__init__(label="Cancel", style=discord.ButtonStyle.danger, custom_id="beacons:sched_cancel")
        self._cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await scheduled.handle_scheduled_cancel(self._cog, interaction)


class ScheduledBeaconView(discord.ui.View):
    def __init__(self, cog) -> None:
        super().__init__(timeout=None)
        self.add_item(_ScheduledJoinButton(cog))
        self.add_item(_ScheduledLeaveButton(cog))
        self.add_item(_ScheduledCancelButton(cog))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/commands/beacons/test_views.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add src/commands/beacons/views.py tests/commands/beacons/test_views.py
git commit -m "feat(beacons): add ScheduledBeaconView with join/leave/cancel buttons"
```

---

### Task 7: Reminder and fire logic (`run_scheduled_beacons`)

**Files:**
- Modify: `src/commands/beacons/scheduled.py`
- Modify: `tests/commands/beacons/test_scheduled.py`

**Interfaces:**
- Consumes: `store.scheduled_beacons/get_config/save_beacon/get_beacon`, `lifecycle.create_beacon_thread`, `embeds.build_scheduled_embed`, `rules.STATUS_ACTIVE`.
- Produces: `run_scheduled_beacons(cog, guild, now: float) -> None` — called by the maintenance sweep (Task 8).

- [ ] **Step 1: Write the failing tests**

Add to `tests/commands/beacons/test_scheduled.py`:

```python
def _guild(*, member=None, channel=None, thread_channel=None):
    guild = MagicMock()
    guild.id = 1
    guild.get_member = MagicMock(return_value=member)
    guild.fetch_member = AsyncMock(return_value=member)
    guild.get_channel = MagicMock(return_value=channel or thread_channel)
    return guild


def _member(user_id=42, display_name="Nova"):
    member = MagicMock()
    member.id = user_id
    member.display_name = display_name
    return member


@pytest.fixture
def make_maintenance_cog(monkeypatch):
    def _make(*, records=None, config=THREAD_CONFIG, beacon=None, thread=None, create_error=None):
        records = records or []
        cog = MagicMock()
        cog.bot.state = MagicMock()
        monkeypatch.setattr(scheduled.store, "scheduled_beacons", AsyncMock(return_value=records))
        monkeypatch.setattr(scheduled.store, "get_config", AsyncMock(return_value=config))
        monkeypatch.setattr(scheduled.store, "save_scheduled", AsyncMock())
        monkeypatch.setattr(scheduled.store, "delete_scheduled", AsyncMock())
        monkeypatch.setattr(scheduled.store, "clear_scheduled_open", AsyncMock())
        monkeypatch.setattr(scheduled.store, "get_beacon", AsyncMock(return_value=beacon))
        monkeypatch.setattr(scheduled.store, "save_beacon", AsyncMock())
        if create_error is not None:
            monkeypatch.setattr(scheduled.lifecycle, "create_beacon_thread", AsyncMock(side_effect=create_error))
        else:
            monkeypatch.setattr(scheduled.lifecycle, "create_beacon_thread", AsyncMock(return_value=thread))
        return cog

    return _make


@pytest.mark.asyncio
async def test_run_scheduled_beacons_sends_reminder_once(make_maintenance_cog):
    channel = MagicMock()
    channel.send = AsyncMock()
    record = _scheduled_record(open_at=1000.0, rsvp=[7, 8], reminded_at=None)
    cog = make_maintenance_cog(records=[(700, record)])
    guild = _guild(channel=channel)

    await scheduled.run_scheduled_beacons(cog, guild, now=1000.0 - 500)

    channel.send.assert_awaited_once()
    content = channel.send.await_args.args[0]
    assert "<@7>" in content and "<@8>" in content
    saved = scheduled.store.save_scheduled.await_args.args[2]
    assert saved["reminded_at"] == 1000.0 - 500


@pytest.mark.asyncio
async def test_run_scheduled_beacons_does_not_remind_twice(make_maintenance_cog):
    channel = MagicMock()
    channel.send = AsyncMock()
    record = _scheduled_record(open_at=1000.0, rsvp=[7], reminded_at=1000.0 - 550)
    cog = make_maintenance_cog(records=[(700, record)])
    guild = _guild(channel=channel)

    await scheduled.run_scheduled_beacons(cog, guild, now=1000.0 - 500)

    channel.send.assert_not_awaited()
    scheduled.store.save_scheduled.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_scheduled_beacons_does_not_remind_before_window(make_maintenance_cog):
    record = _scheduled_record(open_at=1000.0, rsvp=[7], reminded_at=None)
    cog = make_maintenance_cog(records=[(700, record)])
    guild = _guild(channel=MagicMock())

    await scheduled.run_scheduled_beacons(cog, guild, now=1000.0 - 700)

    scheduled.store.save_scheduled.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_scheduled_beacons_fires_and_auto_joins_rsvp(make_maintenance_cog):
    message = MagicMock()
    message.id = 700
    message.edit = AsyncMock()
    channel = MagicMock()
    channel.fetch_message = AsyncMock(return_value=message)
    thread = MagicMock()
    thread.id = 900
    thread.add_user = AsyncMock()
    beacon = {
        "members": [],
        "status": "open",
        "last_activity_at": 0.0,
        "first_joined_at": None,
    }
    record = _scheduled_record(open_at=1000.0, rsvp=[7, 8])
    cog = make_maintenance_cog(records=[(700, record)], beacon=beacon, thread=thread)
    guild = _guild(member=_member(), channel=channel)

    await scheduled.run_scheduled_beacons(cog, guild, now=1000.0)

    scheduled.lifecycle.create_beacon_thread.assert_awaited_once()
    saved_beacon = scheduled.store.save_beacon.await_args.args[2]
    assert sorted(saved_beacon["members"]) == [7, 8]
    assert saved_beacon["status"] == "active"
    assert thread.add_user.await_count == 2
    scheduled.store.delete_scheduled.assert_awaited_once_with(cog.bot.state, 700)
    scheduled.store.clear_scheduled_open.assert_awaited_once()
    message.edit.assert_awaited_once()
    assert message.edit.await_args.kwargs["view"] is None


@pytest.mark.asyncio
async def test_run_scheduled_beacons_aborts_when_config_missing(make_maintenance_cog):
    message = MagicMock()
    message.id = 700
    message.edit = AsyncMock()
    channel = MagicMock()
    channel.fetch_message = AsyncMock(return_value=message)
    record = _scheduled_record(open_at=1000.0)
    cog = make_maintenance_cog(records=[(700, record)], config=None)
    guild = _guild(member=_member(), channel=channel)

    await scheduled.run_scheduled_beacons(cog, guild, now=1000.0)

    scheduled.lifecycle.create_beacon_thread.assert_not_awaited()
    scheduled.store.delete_scheduled.assert_awaited_once_with(cog.bot.state, 700)
    message.edit.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_scheduled_beacons_aborts_on_create_failure(make_maintenance_cog):
    message = MagicMock()
    message.id = 700
    message.edit = AsyncMock()
    channel = MagicMock()
    channel.fetch_message = AsyncMock(return_value=message)
    record = _scheduled_record(open_at=1000.0)
    cog = make_maintenance_cog(
        records=[(700, record)], create_error=discord.HTTPException(MagicMock(status=500), "boom")
    )
    guild = _guild(member=_member(), channel=channel)

    await scheduled.run_scheduled_beacons(cog, guild, now=1000.0)

    scheduled.store.delete_scheduled.assert_awaited_once_with(cog.bot.state, 700)
    message.edit.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_scheduled_beacons_processes_every_record_in_one_sweep(make_maintenance_cog):
    message = MagicMock()
    message.edit = AsyncMock()
    channel = MagicMock()
    channel.fetch_message = AsyncMock(return_value=message)
    thread = MagicMock()
    thread.id = 900
    thread.add_user = AsyncMock()
    beacon = {"members": [], "status": "open", "last_activity_at": 0.0, "first_joined_at": None}
    first_record = _scheduled_record(open_at=1000.0, rsvp=[])
    second_record = _scheduled_record(open_at=1000.0, rsvp=[])
    cog = make_maintenance_cog(records=[(700, first_record), (701, second_record)], beacon=beacon, thread=thread)
    guild = _guild(member=_member(), channel=channel)

    await scheduled.run_scheduled_beacons(cog, guild, now=1000.0)

    assert scheduled.lifecycle.create_beacon_thread.await_count == 2
    scheduled.store.delete_scheduled.assert_any_await(cog.bot.state, 700)
    scheduled.store.delete_scheduled.assert_any_await(cog.bot.state, 701)


@pytest.mark.asyncio
async def test_run_scheduled_beacons_one_failure_does_not_block_others(make_maintenance_cog):
    message = MagicMock()
    message.edit = AsyncMock()
    channel = MagicMock()
    channel.fetch_message = AsyncMock(return_value=message)
    beacon = {"members": [], "status": "open", "last_activity_at": 0.0, "first_joined_at": None}
    ok_record = _scheduled_record(open_at=1000.0, rsvp=[])
    cog = make_maintenance_cog(
        records=[(700, ok_record)],
        beacon=beacon,
        create_error=discord.HTTPException(MagicMock(status=500), "boom"),
    )
    guild = _guild(member=_member(), channel=channel)

    await scheduled.run_scheduled_beacons(cog, guild, now=1000.0)

    scheduled.store.delete_scheduled.assert_awaited_once_with(cog.bot.state, 700)
    message.edit.assert_awaited_once()
```

This replaces the earlier single "one failure does not block others" test with two focused tests: one confirming every record in a sweep is processed independently, and one confirming a per-record exception (`create_beacon_thread` raising) is contained to that record — mirroring `_process_beacon`'s existing per-thread `try/except` pattern in `maintenance.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/commands/beacons/test_scheduled.py -v`
Expected: FAIL with `AttributeError: module 'src.commands.beacons.scheduled' has no attribute 'run_scheduled_beacons'`

- [ ] **Step 3: Write the implementation**

Append to `src/commands/beacons/scheduled.py` (add `from .rules import STATUS_ACTIVE` to the imports):

```python
_REMINDER_SECONDS = 600


async def run_scheduled_beacons(cog, guild: discord.Guild, now: float) -> None:
    for message_id, record in await store.scheduled_beacons(cog.bot.state, guild.id):
        try:
            await _process_scheduled(cog, guild, message_id, record, now)
        except Exception:
            logger.exception("Scheduled beacon processing failed for message %s", message_id)


async def _process_scheduled(cog, guild: discord.Guild, message_id: int, record: dict, now: float) -> None:
    if now >= record["open_at"]:
        await _fire_scheduled(cog, guild, message_id, record, now)
        return
    if record["reminded_at"] is None and now >= record["open_at"] - _REMINDER_SECONDS:
        await _send_reminder(cog, guild, message_id, record, now)


async def _send_reminder(cog, guild: discord.Guild, message_id: int, record: dict, now: float) -> None:
    channel = guild.get_channel(record["channel_id"])
    if channel is not None and record["rsvp"]:
        mentions = " ".join(f"<@{user_id}>" for user_id in record["rsvp"])
        try:
            await channel.send(f"{mentions} this scheduled beacon opens <t:{int(record['open_at'])}:R>.")
        except discord.HTTPException:
            logger.warning("Could not send scheduled beacon reminder for message %s", message_id)
    record["reminded_at"] = now
    await store.save_scheduled(cog.bot.state, message_id, record)


async def _fetch_scheduled_message(guild: discord.Guild, channel_id: int, message_id: int):
    channel = guild.get_channel(channel_id)
    if channel is None:
        return None
    try:
        return await channel.fetch_message(message_id)
    except discord.HTTPException:
        return None


async def _resolve_display_name(guild: discord.Guild, user_id: int) -> str:
    member = guild.get_member(user_id)
    if member is not None:
        return member.display_name
    try:
        member = await guild.fetch_member(user_id)
        return member.display_name
    except discord.HTTPException:
        return "a member who has left"


async def _abort_scheduled(cog, message_id: int, record: dict, message, reason: str) -> None:
    await store.delete_scheduled(cog.bot.state, message_id)
    await store.clear_scheduled_open(cog.bot.state, record["guild_id"], record["requester_id"], record["category"])
    if message is not None:
        try:
            await message.edit(content=reason, embed=None, view=None)
        except discord.HTTPException:
            logger.warning("Could not update scheduled beacon message %s after abort", message_id)


async def _add_rsvp_members(cog, thread: discord.Thread, record: dict) -> None:
    beacon = await store.get_beacon(cog.bot.state, thread.id)
    now = time.time()
    changed = False
    for user_id in record["rsvp"]:
        if user_id == record["requester_id"] or user_id in beacon["members"]:
            continue
        beacon["members"].append(user_id)
        changed = True
        try:
            await thread.add_user(discord.Object(id=user_id))
        except discord.HTTPException:
            logger.warning("Could not add RSVP'd user %s to beacon thread %s", user_id, thread.id)
    if changed:
        beacon["status"] = STATUS_ACTIVE
        beacon["last_activity_at"] = now
        if beacon["first_joined_at"] is None:
            beacon["first_joined_at"] = now
        await store.save_beacon(cog.bot.state, thread.id, beacon)


async def _fire_scheduled(cog, guild: discord.Guild, message_id: int, record: dict, now: float) -> None:
    message = await _fetch_scheduled_message(guild, record["channel_id"], message_id)
    config = await store.get_config(cog.bot.state, guild.id)
    if config is None or guild.get_channel(config["channel_id"]) is None:
        await _abort_scheduled(cog, message_id, record, message, "This beacon channel is no longer set up.")
        return

    display_name = await _resolve_display_name(guild, record["requester_id"])
    try:
        thread = await lifecycle.create_beacon_thread(
            cog, guild, config, record["requester_id"], display_name, record["category"], record["fields"]
        )
    except discord.HTTPException as error:
        logger.exception("Failed to open scheduled beacon")
        await _abort_scheduled(cog, message_id, record, message, f"Could not open this beacon: {error}")
        return

    await _add_rsvp_members(cog, thread, record)
    await store.delete_scheduled(cog.bot.state, message_id)
    await store.clear_scheduled_open(cog.bot.state, record["guild_id"], record["requester_id"], record["category"])
    if message is not None:
        try:
            await message.edit(embed=build_scheduled_embed(record, opened_thread_id=thread.id), view=None)
        except discord.HTTPException:
            logger.warning("Could not update scheduled beacon message %s after opening", message_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/commands/beacons/test_scheduled.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add src/commands/beacons/scheduled.py tests/commands/beacons/test_scheduled.py
git commit -m "feat(beacons): fire scheduled beacons and send pre-open reminders"
```

---

### Task 8: Wire the maintenance sweep

**Files:**
- Modify: `src/commands/beacons/maintenance.py`
- Modify: `tests/commands/beacons/test_maintenance.py`

**Interfaces:**
- Consumes: `scheduled.run_scheduled_beacons(cog, guild, now)` (Task 7).

- [ ] **Step 1: Write the failing test**

Add to `tests/commands/beacons/test_maintenance.py`:

```python
@pytest.mark.asyncio
async def test_run_maintenance_calls_scheduled_sweep(monkeypatch, make_cog):
    cog = make_cog(config=SETTINGS_CONFIG, beacons=[])
    run_scheduled = AsyncMock()
    monkeypatch.setattr(maintenance.scheduled, "run_scheduled_beacons", run_scheduled)
    guild = MagicMock()
    guild.id = 1

    await maintenance.run_maintenance(cog, guild, now=123.0)

    run_scheduled.assert_awaited_once_with(cog, guild, 123.0)


@pytest.mark.asyncio
async def test_run_maintenance_survives_scheduled_sweep_failure(monkeypatch, make_cog):
    cog = make_cog(config=SETTINGS_CONFIG, beacons=[])
    monkeypatch.setattr(maintenance.scheduled, "run_scheduled_beacons", AsyncMock(side_effect=RuntimeError("boom")))
    guild = MagicMock()
    guild.id = 1

    await maintenance.run_maintenance(cog, guild, now=123.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/commands/beacons/test_maintenance.py -v`
Expected: FAIL with `AttributeError: module 'src.commands.beacons.maintenance' has no attribute 'scheduled'`

- [ ] **Step 3: Wire it in**

In `src/commands/beacons/maintenance.py`, change the import line and the end of `run_maintenance`:

```python
from . import board, digest, scheduled, store
```

```python
async def run_maintenance(cog, guild, now: float) -> None:
    config = await store.get_config(cog.bot.state, guild.id)
    settings = store.get_settings(config)
    beacons = await store.open_beacons(cog.bot.state, guild.id)
    for thread_id, _beacon in beacons:
        try:
            await _process_beacon(cog, guild, config, settings, thread_id, now)
        except Exception:
            logger.exception("Beacon maintenance failed for thread %s", thread_id)
    try:
        await board.refresh_board(cog, guild, entries=beacons)
    except Exception:
        logger.exception("Beacon board refresh failed for guild %s", guild.id)
    try:
        await digest.maybe_post_digest(cog, guild, now)
    except Exception:
        logger.exception("Beacon digest failed for guild %s", guild.id)
    try:
        await scheduled.run_scheduled_beacons(cog, guild, now)
    except Exception:
        logger.exception("Scheduled beacon sweep failed for guild %s", guild.id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/commands/beacons/test_maintenance.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add src/commands/beacons/maintenance.py tests/commands/beacons/test_maintenance.py
git commit -m "feat(beacons): run the scheduled-beacon sweep from maintenance"
```

---

### Task 9: `schedule_role` on `/beacon config`

**Files:**
- Modify: `src/commands/beacons/setup_cmd.py`
- Modify: `tests/commands/beacons/test_setup_cmd.py`

**Interfaces:**
- Consumes: `store.get_settings/set_config` (unchanged signatures).
- Produces: `handle_config(..., schedule_role: discord.Role | None = None, clear_schedule_role: bool | None = None)` — extends the existing `handle_config` signature.

- [ ] **Step 1: Write the failing tests**

Add to `tests/commands/beacons/test_setup_cmd.py`:

```python
@pytest.mark.asyncio
async def test_config_sets_schedule_role(monkeypatch):
    config = {"channel_id": 1, "mode": "thread", "panel_message_id": 2, "tag_ids": {}, "roles": {}}
    monkeypatch.setattr(setup_cmd.store, "get_config", AsyncMock(return_value=config))
    saved = {}
    monkeypatch.setattr(setup_cmd.store, "set_config", AsyncMock(side_effect=lambda s, g, c: saved.update(c)))
    interaction = MagicMock()
    interaction.guild.id = 1
    interaction.response.send_message = AsyncMock()
    role = MagicMock()
    role.id = 77
    role.mention = "<@&77>"

    await setup_cmd.handle_config(
        MagicMock(),
        interaction,
        idle_warn=None,
        idle_close=None,
        escalate=None,
        voice=None,
        digest_channel=None,
        clear_digest=None,
        schedule_role=role,
        clear_schedule_role=None,
    )

    assert saved["settings"]["schedule_role_id"] == 77
    reply = interaction.response.send_message.await_args.args[0]
    assert "<@&77>" in reply


@pytest.mark.asyncio
async def test_config_clears_schedule_role(monkeypatch):
    config = {
        "channel_id": 1,
        "mode": "thread",
        "panel_message_id": 2,
        "tag_ids": {},
        "roles": {},
        "settings": {"schedule_role_id": 77},
    }
    monkeypatch.setattr(setup_cmd.store, "get_config", AsyncMock(return_value=config))
    saved = {}
    monkeypatch.setattr(setup_cmd.store, "set_config", AsyncMock(side_effect=lambda s, g, c: saved.update(c)))
    interaction = MagicMock()
    interaction.guild.id = 1
    interaction.response.send_message = AsyncMock()

    await setup_cmd.handle_config(
        MagicMock(),
        interaction,
        idle_warn=None,
        idle_close=None,
        escalate=None,
        voice=None,
        digest_channel=None,
        clear_digest=None,
        schedule_role=None,
        clear_schedule_role=True,
    )

    assert saved["settings"]["schedule_role_id"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/commands/beacons/test_setup_cmd.py -v`
Expected: FAIL with `TypeError: handle_config() got an unexpected keyword argument 'schedule_role'`

- [ ] **Step 3: Implement**

In `src/commands/beacons/setup_cmd.py`, replace `handle_config`:

```python
async def handle_config(
    cog,
    interaction: discord.Interaction,
    *,
    idle_warn: int | None,
    idle_close: int | None,
    escalate: int | None,
    voice: bool | None,
    voice_category: discord.CategoryChannel | None = None,
    digest_channel: discord.TextChannel | None,
    clear_digest: bool | None,
    schedule_role: discord.Role | None = None,
    clear_schedule_role: bool | None = None,
) -> None:
    config = await store.get_config(cog.bot.state, interaction.guild.id)
    if config is None:
        await interaction.response.send_message("Run `/beacon setup` first.", ephemeral=True)
        return
    settings = dict(config.get("settings") or {})
    if idle_warn is not None:
        settings["idle_warn_minutes"] = idle_warn
    if idle_close is not None:
        settings["idle_close_minutes"] = idle_close
    if escalate is not None:
        settings["escalate_minutes"] = escalate
    if voice is not None:
        settings["voice"] = voice
    if voice_category is not None:
        settings["voice_category_id"] = voice_category.id
    if clear_digest:
        settings["digest_channel_id"] = None
    elif digest_channel is not None:
        settings["digest_channel_id"] = digest_channel.id
    if clear_schedule_role:
        settings["schedule_role_id"] = None
    elif schedule_role is not None:
        settings["schedule_role_id"] = schedule_role.id
    config["settings"] = settings
    await store.set_config(cog.bot.state, interaction.guild.id, config)
    effective = store.get_settings(config)
    digest_value = effective["digest_channel_id"]
    digest_line = f"<#{digest_value}>" if digest_value else "not set"
    voice_category_id = effective["voice_category_id"]
    voice_category_line = f"<#{voice_category_id}>" if voice_category_id else "same as beacon channel"
    schedule_role_id = effective["schedule_role_id"]
    schedule_role_line = f"<@&{schedule_role_id}>" if schedule_role_id else "everyone"
    lines = [
        f"Idle warn: {effective['idle_warn_minutes']} minutes",
        f"Idle close: {effective['idle_close_minutes']} minutes",
        f"Escalate: {effective['escalate_minutes']} minutes",
        f"Voice channels: {'on' if effective['voice'] else 'off'}",
        f"Voice category: {voice_category_line}",
        f"Digest channel: {digest_line}",
        f"Can schedule beacons: {schedule_role_line}",
    ]
    await interaction.response.send_message("\n".join(lines), ephemeral=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/commands/beacons/test_setup_cmd.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add src/commands/beacons/setup_cmd.py tests/commands/beacons/test_setup_cmd.py
git commit -m "feat(beacons): add schedule_role setting to /beacon config"
```

---

### Task 10: Wire `when` into every category command, register the view, and expose `schedule_role`

**Files:**
- Modify: `src/commands/beacons/__init__.py`
- Modify: `tests/commands/beacons/test_init.py`

**Interfaces:**
- Consumes: `scheduled.open_or_schedule` (Task 5), `ScheduledBeaconView` (Task 6), `handle_config` with `schedule_role`/`clear_schedule_role` (Task 9).

- [ ] **Step 1: Write the failing test**

First read `tests/commands/beacons/test_init.py` to match its existing fixture/mock style, then add:

```python
@pytest.mark.asyncio
async def test_mining_command_schedules_when_when_is_given(monkeypatch):
    from src.commands.beacons import BeaconsCog

    dispatch = AsyncMock()
    monkeypatch.setattr("src.commands.beacons.scheduled.open_or_schedule", dispatch)
    cog = BeaconsCog(MagicMock())
    interaction = MagicMock()

    await cog.mining.callback(cog, interaction, location="Stanton", when="2h")

    dispatch.assert_awaited_once()
    args = dispatch.await_args.args
    assert args[0] is cog
    assert args[1] is interaction
    assert args[2] == "mining"
    assert args[4] == "2h"


@pytest.mark.asyncio
async def test_config_command_forwards_schedule_role(monkeypatch):
    from src.commands.beacons import BeaconsCog

    handle_config = AsyncMock()
    monkeypatch.setattr("src.commands.beacons.setup_cmd.handle_config", handle_config)
    cog = BeaconsCog(MagicMock())
    interaction = MagicMock()
    role = MagicMock()

    await cog.config.callback(
        cog,
        interaction,
        idle_warn=None,
        idle_close=None,
        escalate=None,
        voice=None,
        voice_category=None,
        digest_channel=None,
        clear_digest=None,
        schedule_role=role,
        clear_schedule_role=None,
    )

    handle_config.assert_awaited_once()
    assert handle_config.await_args.kwargs["schedule_role"] is role


@pytest.mark.asyncio
async def test_cog_load_registers_scheduled_beacon_view(monkeypatch):
    from src.commands.beacons import BeaconsCog

    monkeypatch.setattr("src.commands.beacons.store.migrate_legacy_keys", AsyncMock())
    bot = MagicMock()
    bot.state = MagicMock()
    bot.add_view = MagicMock()
    bot.tree.fetch_commands = AsyncMock(return_value=[])
    cog = BeaconsCog(bot)
    cog.maintenance_loop.start = MagicMock()

    await cog.cog_load()

    from src.commands.beacons.views import ScheduledBeaconView

    assert isinstance(cog.scheduled_beacon_view, ScheduledBeaconView)
    assert any(isinstance(call.args[0], ScheduledBeaconView) for call in bot.add_view.call_args_list)
```

Note: `bot.add_view` is a plain (non-async) method on `discord.ext.commands.Bot`, so this asserts against `call_args_list`, not `await_args_list`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/commands/beacons/test_init.py -v`
Expected: FAIL — `mining` command has no `when` parameter yet, `config` has no `schedule_role` parameter, and `cog_load` never constructs a `ScheduledBeaconView`.

- [ ] **Step 3: Wire everything in `src/commands/beacons/__init__.py`**

Change the imports (replace the `.lifecycle` and `.views` import lines):

```python
from .lifecycle import handle_again, handle_close_command, handle_thread_message
from .scheduled import open_or_schedule
from .views import BeaconView, CommendView, ScheduledBeaconView
```

In `cog_load`, register the new view alongside the existing ones:

```python
    async def cog_load(self) -> None:
        await store.migrate_legacy_keys(self.bot.state)
        await self._warn_stale_configs()
        self.beacon_view = BeaconView(self)
        self.bot.add_view(self.beacon_view)
        self.bot.add_view(BeaconView(self, legacy=True))
        self.bot.add_view(CommendView(self))
        self.scheduled_beacon_view = ScheduledBeaconView(self)
        self.bot.add_view(self.scheduled_beacon_view)
        await self.refresh_command_mentions()
        self.maintenance_loop.start()
```

For each of the nine category commands, add a `when: str | None = None` parameter, a `when="Schedule this beacon instead of opening it now (e.g. \"45m\", \"2h\")"` describe line, and replace the trailing `await open_beacon(self, interaction, "<category>", fields)` with `await open_or_schedule(self, interaction, "<category>", fields, when)`. Apply this identically to all nine commands; `mining` shown in full, the rest are the same shape with their own field-building bodies already present in the file:

```python
    @beacon.command(name="mining", description="Request mining assistance")
    @app_commands.describe(
        location="Where you are (system:planet:location)",
        need="What you need",
        crew="Crew members needed",
        notes="Extra details",
        when='Schedule this beacon instead of opening it now (e.g. "45m", "2h")',
    )
    @app_commands.autocomplete(location=location_autocomplete)
    async def mining(
        self,
        interaction: discord.Interaction,
        location: str,
        need: Literal["Extra mining ship", "Refining help", "Escort", "Equipment"] | None = None,
        crew: app_commands.Range[int, 1, 50] | None = None,
        notes: str | None = None,
        when: str | None = None,
    ) -> None:
        fields = {"location": location}
        if need:
            fields["need"] = need
        if crew:
            fields["size"] = str(crew)
        if notes:
            fields["notes"] = notes
        await open_or_schedule(self, interaction, "mining", fields, when)
```

Apply the same three changes (new `when` param + describe line, `when: str | None = None` in the signature, and swapping the final `open_beacon(...)` call for `open_or_schedule(..., when)`) to `medic`, `squad`, `backup`, `cargo`, `salvage`, `escort`, `transport`, and `contested`. `contested`'s location option uses fixed choices rather than autocomplete but the same three edits apply — add `when` to its `@app_commands.describe(...)`, add the `when: str | None = None` parameter, and change its final line to `await open_or_schedule(self, interaction, "contested", fields, when)`.

Finally, extend the `config` command:

```python
    @beacon.command(name="config", description="View or change beacon settings")
    @app_commands.rename(voice_category="voice-category", schedule_role="schedule-role", clear_schedule_role="clear-schedule-role")
    @app_commands.describe(
        idle_warn="Minutes idle before a warning (5-1440)",
        idle_close="Minutes idle before auto-closing (5-1440)",
        escalate="Minutes with no responders before pinging the category role (1-1440)",
        voice="Auto-create a voice channel when a beacon fills",
        voice_category="Discord category to create voice channels in",
        digest_channel="Channel to post the weekly digest in",
        clear_digest="Unset the digest channel",
        schedule_role="Role required to schedule a beacon (unset means everyone can)",
        clear_schedule_role="Unset the schedule role, opening scheduling to everyone",
    )
    @app_commands.check(admin_or_sc_bot)
    async def config(
        self,
        interaction: discord.Interaction,
        idle_warn: app_commands.Range[int, 5, 1440] | None = None,
        idle_close: app_commands.Range[int, 5, 1440] | None = None,
        escalate: app_commands.Range[int, 1, 1440] | None = None,
        voice: bool | None = None,
        voice_category: discord.CategoryChannel | None = None,
        digest_channel: discord.TextChannel | None = None,
        clear_digest: bool | None = None,
        schedule_role: discord.Role | None = None,
        clear_schedule_role: bool | None = None,
    ) -> None:
        await handle_config(
            self,
            interaction,
            idle_warn=idle_warn,
            idle_close=idle_close,
            escalate=escalate,
            voice=voice,
            voice_category=voice_category,
            digest_channel=digest_channel,
            clear_digest=clear_digest,
            schedule_role=schedule_role,
            clear_schedule_role=clear_schedule_role,
        )
```

This requires `handle_config` to remain imported from `.setup_cmd` — the existing `from .setup_cmd import handle_config, handle_role, handle_setup` line is unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/commands/beacons/ -v`
Expected: PASS (full beacons test suite, including all tasks in this plan)

- [ ] **Step 5: Run the full project test suite**

Run: `pytest tests/ -v`
Expected: PASS (no regressions elsewhere)

- [ ] **Step 6: Update the README**

In `/volume3/docker/sc-discord-bot/README.md`, under the "Beacons" section's command table (after the `contested` row, before the "Every non-notes option is constrained..." paragraph), add a line noting the new option, and document `schedule_role` alongside the other `/beacon config` settings and add a short "Scheduling a beacon" subsection describing the `when` option, the RSVP embed, and the reminder/auto-join behavior — mirroring the level of detail already used for "Panel and Beacon Lifecycle".

- [ ] **Step 7: Commit**

```bash
git add src/commands/beacons/__init__.py tests/commands/beacons/test_init.py README.md
git commit -m "feat(beacons): add when option to schedule beacons ahead of time"
```

---

## Self-Review Notes

- **Spec coverage:** `when` option + bounds (Task 1, 10), `schedule_role` gate (Task 2, 5, 9, 10), storage keys (Task 2), shared thread-creation helper (Task 3), RSVP embed (Task 4), Join/Leave/Cancel view (Task 6), reminder + fire + auto-join (Task 7), maintenance wiring (Task 8) — every section of the spec maps to at least one task.
- **Type consistency:** `create_beacon_thread(cog, guild, config, requester_id, display_name, category_key, field_values)` is defined in Task 3 and consumed identically in Task 5 (not directly — only `open_beacon` calls it there) and Task 7 (`lifecycle.create_beacon_thread(cog, guild, config, record["requester_id"], display_name, record["category"], record["fields"])`) — argument order and names match. `open_or_schedule(cog, interaction, category_key, field_values, when)` is defined in Task 5 and consumed with matching argument order in Task 10.
- **Out of scope confirmed:** recurring events, absolute/timezone input, and per-role RSVP slots are explicitly not implemented by any task here, matching the spec's "Out of scope" section.
