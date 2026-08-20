# Scheduled Beacons Design

Date: 2026-08-20
Status: Approved design, pending implementation plan

## Purpose

Let members plan a beacon ahead of time instead of only opening one for right-now help. A scheduled beacon posts an RSVP embed immediately and opens the real beacon thread automatically at the chosen time, auto-joining everyone who RSVP'd.

## Command surface

Every existing category command (`/beacon mining`, `/beacon medic`, `/beacon squad`, `/beacon backup`, `/beacon cargo`, `/beacon salvage`, `/beacon escort`, `/beacon transport`, `/beacon contested`) gains one new optional option:

- **`when`** (string): a relative duration, e.g. `45m`, `2h`, `1h30m`, `1d`.
  - Omitted → today's instant-open behavior, unchanged.
  - Present → the beacon is scheduled instead of opened immediately.
  - Bounds: minimum 5 minutes, maximum 24 hours. Out-of-range or unparseable input gets a clear ephemeral error, following the same pattern as the existing location-validation error in `open_beacon`.
- All other options and field validation (location parsing, choice/int fields) behave exactly as they do for instant beacons — scheduling only changes when the thread is created, not what data is collected.

### Role gate

New `schedule_role` setting on `/beacon config`, alongside `idle_warn`, `idle_close`, `escalate`, `voice`, `digest_channel`:

- Unset (default): scheduling is open to everyone, same as instant beacons today.
- Set to a role: only members with that role, or a beacon admin (`is_beacon_admin`), can supply `when`. Using a category command *without* `when` still opens instantly for everyone regardless of this setting.
- RSVP/Join on an already-posted scheduled beacon is open to everyone, never gated by `schedule_role` — the gate only controls who can create a scheduled beacon.
- Rejection is an ephemeral message naming the required role.

## Data model

New state entries in `store.py`, following the existing `beacons:*` key conventions:

- `beacons:scheduled:{message_id}` — the scheduled-beacon record:
  ```
  {
    guild_id, channel_id, category, requester_id, fields,
    open_at,          # unix timestamp
    rsvp: [user_id, ...],
    reminded_at,      # None until the pre-open reminder fires
    created_at,
  }
  ```
  Keyed by the RSVP embed message's ID, mirroring how live beacons are keyed by thread ID — button callbacks look the record up from `interaction.message.id`.
- `beacons:scheduled_open:{guild_id}:{user_id}:{category}` → message_id. Mirrors the existing `beacons:open:*` index; prevents a user from having two pending scheduled beacons in the same category at once. It is independent of the instant-open index — a user may have one open (live) beacon and one scheduled beacon in the same category simultaneously.

### Shared thread-creation helper

`lifecycle.open_beacon` is refactored to extract its thread-creation core (build embed, create thread or forum post, add the requester, save the beacon record, set the open/last-open indexes) into a new function:

```python
async def _create_beacon_thread(cog, guild, user, category_key, field_values) -> discord.Thread
```

`open_beacon` (interaction-driven, instant-open path) and the new scheduled-fire path (triggered from the maintenance sweep, no interaction available) both call this helper, so thread-creation logic exists in exactly one place.

## RSVP embed & UI

Posted directly in the beacon panel channel (`config["channel_id"]`) when `when` is supplied — no thread exists yet, so there's nowhere else to post it.

- Embed content: category emoji/label, requester, the same field summary `build_beacon_embed` renders for live beacons, an RSVP list rendered as mentions, and the scheduled time as Discord native timestamps: `<t:open_at:R>` (relative, auto-updating client-side) and `<t:open_at:f>` (absolute).
- `ScheduledBeaconView` (persistent view, registered at startup like `BeaconView`): **Join**, **Leave**, **Cancel** buttons.
  - **Join** / **Leave**: toggle the caller's membership in `rsvp`, edit the embed in place. Mirrors `handle_join`/`handle_leave` but operates on the scheduled record instead of a live beacon.
  - **Cancel**: allowed for the requester or a beacon admin only (no responders exist yet to extend the permission to). Deletes the `beacons:scheduled:*` record and its open-index entry, edits the embed to show "Cancelled by @user", disables all buttons.

## Maintenance sweep integration

`maintenance.run_maintenance` gains a call to a new `run_scheduled_beacons(cog, guild, now)`, iterating `beacons:scheduled:*` for the guild the same way `store.open_beacons` does for live beacons:

- **Reminder** (once, when `now >= open_at - 10 minutes` and `reminded_at is None`): pings every RSVP'd user by mention in the RSVP embed's channel, sets `reminded_at`.
- **Fire** (when `now >= open_at`):
  1. Call `_create_beacon_thread(cog, guild, requester, category, fields)`.
  2. Add every RSVP'd user to the new beacon's `members` list and to the thread directly (auto-joined, no separate Join click needed) — this includes updating `last_activity_at`/`first_joined_at` as `handle_join` would.
  3. Edit the RSVP message: embed shows "Opened: {thread.mention}", all buttons disabled.
  4. Delete the `beacons:scheduled:*` record and its open-index entry.
  5. Refresh the live board (`board.refresh_board`).
  - If thread creation fails (e.g. the beacon channel or config was removed), edit the RSVP message with the error instead and drop the record — no retry loop.

## Out of scope

- Recurring/templated events (e.g. "every Saturday") — a possible future extension, not part of this design.
- Absolute date/time or timezone-aware input — relative duration only.
- Role-specific RSVP slots (e.g. "need 2 escorts, 1 medic") — RSVP is a flat join/leave list, matching how live-beacon membership already works.
- Spectrum MOTD watching — unrelated feature, deferred to its own future design.
