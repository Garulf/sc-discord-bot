"""Inventory tracking for DCHS collectible sets.

Each user's per-guild inventory is persisted in the bot's SQLite StateStore
under a key scoped to the guild. The ``/inventory status`` command resolves
Discord member display names at call time so display names stay current.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from .checks import admin_or_sc_bot

ITEMS = [f"DCHS-{i:02d}" for i in range(1, 8)]
_STATE_KEY_PREFIX = "inventory"
_MAX_EMBED_FIELDS = 25


def _guild_key(guild_id: int) -> str:
    return f"{_STATE_KEY_PREFIX}:{guild_id}"


def _complete_sets(inventory: dict[str, int]) -> int:
    """Minimum count across all 7 items — the number of complete sets."""
    return min(inventory.get(item, 0) for item in ITEMS)


def _embed_color(inventory: dict[str, int]) -> int:
    if _complete_sets(inventory) > 0:
        return 0x57F287  # green
    if any(inventory.values()):
        return 0x5865F2  # blurple
    return 0x99AAB5      # gray


def _format_field(inventory: dict[str, int]) -> str:
    """Compact per-item lines for embed fields in the everyone view."""
    lines = []
    for item in ITEMS:
        count = inventory.get(item, 0)
        num = item.removeprefix("DCHS-")
        if count > 0:
            suffix = f" ×{count}" if count > 1 else ""
            lines.append(f"✅ {num}{suffix}")
        else:
            lines.append(f"❌ {num}")
    sets = _complete_sets(inventory)
    lines.append(f"🏆 **{sets} set{'s' if sets != 1 else ''}**" if sets else "*no complete set*")
    return "\n".join(lines)


def _format_mine(inventory: dict[str, int]) -> str:
    """Richer per-item lines for the personal mine view."""
    lines = []
    for item in ITEMS:
        count = inventory.get(item, 0)
        if count > 0:
            suffix = f" ×{count}" if count > 1 else ""
            lines.append(f"✅ **{item}**{suffix}")
        else:
            lines.append(f"❌ ~~{item}~~")
    return "\n".join(lines)


class InventoryCog(commands.Cog):
    """DCHS collectible set inventory tracking."""

    inventory = app_commands.Group(name="inventory", description="DCHS collectible set inventory")

    status_group = app_commands.Group(
        name="status",
        description="View DCHS inventory status",
        parent=inventory,
    )

    admin_group = app_commands.Group(
        name="admin",
        description="Manage other members' DCHS inventories (admins/sc-bot only)",
        parent=inventory,
        default_permissions=discord.Permissions(administrator=True),
    )

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _get_guild_inventory(self, guild_id: int) -> dict[str, dict[str, int]]:
        return await self.bot.state.get(_guild_key(guild_id), {})

    async def _save_guild_inventory(self, guild_id: int, data: dict[str, dict[str, int]]) -> None:
        await self.bot.state.set(_guild_key(guild_id), data)

    async def item_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        needle = current.strip().lower()
        return [
            app_commands.Choice(name=item, value=item)
            for item in ITEMS
            if not needle or needle in item.lower()
        ]

    # -------------------------------------------------------------------------
    # Regular user commands (self only)
    # -------------------------------------------------------------------------

    @inventory.command(name="add", description="Add a DCHS item to your inventory")
    @app_commands.describe(
        item="The DCHS item to add (DCHS-01 through DCHS-07)",
        count="How many to add (default 1)",
    )
    @app_commands.autocomplete(item=item_autocomplete)
    async def add(self, interaction: discord.Interaction, item: str, count: int = 1) -> None:
        if item not in ITEMS:
            await interaction.response.send_message(
                f"**{item}** is not a valid DCHS item. Choose from DCHS-01 through DCHS-07.",
                ephemeral=True,
            )
            return
        if count < 1:
            await interaction.response.send_message("Count must be at least 1.", ephemeral=True)
            return
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        guild_inv = await self._get_guild_inventory(interaction.guild_id)
        user_key = str(interaction.user.id)
        user_inv = dict(guild_inv.get(user_key, {}))
        user_inv[item] = user_inv.get(item, 0) + count
        guild_inv[user_key] = user_inv
        await self._save_guild_inventory(interaction.guild_id, guild_inv)

        total = user_inv[item]
        sets = _complete_sets(user_inv)
        msg = f"Added ×{count} **{item}** to your inventory. You now have ×{total}."
        if sets > 0:
            msg += f" You have **{sets} complete set{'s' if sets != 1 else ''}**!"
        await interaction.response.send_message(msg, ephemeral=True)

    @inventory.command(name="remove", description="Remove a DCHS item from your inventory")
    @app_commands.describe(
        item="The DCHS item to remove",
        count="How many to remove (default 1)",
    )
    @app_commands.autocomplete(item=item_autocomplete)
    async def remove(self, interaction: discord.Interaction, item: str, count: int = 1) -> None:
        if item not in ITEMS:
            await interaction.response.send_message(
                f"**{item}** is not a valid DCHS item.", ephemeral=True
            )
            return
        if count < 1:
            await interaction.response.send_message("Count must be at least 1.", ephemeral=True)
            return
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        guild_inv = await self._get_guild_inventory(interaction.guild_id)
        user_key = str(interaction.user.id)
        user_inv = dict(guild_inv.get(user_key, {}))
        current_count = user_inv.get(item, 0)
        if current_count <= 0:
            await interaction.response.send_message(
                f"You don't have **{item}** in your inventory.", ephemeral=True
            )
            return

        removed = min(count, current_count)
        user_inv[item] = current_count - removed
        if user_inv[item] == 0:
            del user_inv[item]
        guild_inv[user_key] = user_inv
        await self._save_guild_inventory(interaction.guild_id, guild_inv)

        remaining = user_inv.get(item, 0)
        await interaction.response.send_message(
            f"Removed ×{removed} **{item}** from your inventory. You now have ×{remaining}.",
            ephemeral=True,
        )

    @inventory.command(name="clear", description="Clear all DCHS items from your inventory")
    async def clear(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        guild_inv = await self._get_guild_inventory(interaction.guild_id)
        user_key = str(interaction.user.id)
        if not guild_inv.get(user_key):
            await interaction.response.send_message(
                "Your inventory is already empty.", ephemeral=True
            )
            return

        guild_inv.pop(user_key, None)
        await self._save_guild_inventory(interaction.guild_id, guild_inv)
        await interaction.response.send_message("Your inventory has been cleared.", ephemeral=True)

    @status_group.command(name="mine", description="Show your own DCHS inventory")
    async def status_mine(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        guild_inv = await self._get_guild_inventory(interaction.guild_id)
        user_inv = guild_inv.get(str(interaction.user.id), {})

        sets = _complete_sets(user_inv)
        types_collected = sum(1 for item in ITEMS if user_inv.get(item, 0) > 0)

        embed = discord.Embed(
            title=f"{interaction.user.display_name}'s DCHS Inventory",
            description=_format_mine(user_inv) if user_inv else "*Your inventory is empty.*",
            color=_embed_color(user_inv),
        )
        embed.add_field(name="Types Collected", value=f"{types_collected} / {len(ITEMS)}", inline=True)
        embed.add_field(name="Complete Sets", value=str(sets) if sets else "None", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @status_group.command(
        name="everyone", description="Show all members' DCHS inventory and complete sets"
    )
    async def status_everyone(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        await interaction.response.defer()
        guild_inv = await self._get_guild_inventory(guild.id)
        active = {uid: inv for uid, inv in guild_inv.items() if inv}

        if not active:
            await interaction.followup.send("No inventory data found for this server.")
            return

        total_sets = sum(_complete_sets(inv) for inv in active.values())
        embed = discord.Embed(
            title="DCHS Inventory Status",
            color=0x57F287 if total_sets > 0 else 0x5865F2,
        )
        embed.set_footer(text=f"Server total: {total_sets} complete set{'s' if total_sets != 1 else ''}")

        sorted_active = sorted(active.items(), key=lambda kv: _complete_sets(kv[1]), reverse=True)

        shown = 0
        for user_key, user_inv in sorted_active:
            if shown >= _MAX_EMBED_FIELDS:
                break

            member = guild.get_member(int(user_key))
            if member is None:
                try:
                    member = await guild.fetch_member(int(user_key))
                except (discord.NotFound, discord.HTTPException):
                    continue

            embed.add_field(
                name=member.display_name,
                value=_format_field(user_inv),
                inline=True,
            )
            shown += 1

        await interaction.followup.send(embed=embed)

    # -------------------------------------------------------------------------
    # Admin subgroup — hidden from non-admins by default_member_permissions;
    # runtime check also allows the sc-bot role.
    # -------------------------------------------------------------------------

    @admin_group.command(name="add", description="Add a DCHS item to a member's inventory")
    @app_commands.describe(
        member="The member to add the item for",
        item="The DCHS item to add (DCHS-01 through DCHS-07)",
        count="How many to add (default 1)",
    )
    @app_commands.autocomplete(item=item_autocomplete)
    async def admin_add(
        self, interaction: discord.Interaction, member: discord.Member, item: str, count: int = 1
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return
        try:
            await admin_or_sc_bot(interaction)
        except app_commands.CheckFailure as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        if item not in ITEMS:
            await interaction.response.send_message(
                f"**{item}** is not a valid DCHS item. Choose from DCHS-01 through DCHS-07.",
                ephemeral=True,
            )
            return
        if count < 1:
            await interaction.response.send_message("Count must be at least 1.", ephemeral=True)
            return

        guild_inv = await self._get_guild_inventory(interaction.guild_id)
        user_key = str(member.id)
        user_inv = dict(guild_inv.get(user_key, {}))
        user_inv[item] = user_inv.get(item, 0) + count
        guild_inv[user_key] = user_inv
        await self._save_guild_inventory(interaction.guild_id, guild_inv)

        total = user_inv[item]
        sets = _complete_sets(user_inv)
        msg = f"Added ×{count} **{item}** to {member.display_name}'s inventory. They now have ×{total}."
        if sets > 0:
            msg += f" They have **{sets} complete set{'s' if sets != 1 else ''}**!"
        await interaction.response.send_message(msg, ephemeral=True)

    @admin_group.command(name="remove", description="Remove a DCHS item from a member's inventory")
    @app_commands.describe(
        member="The member to remove the item from",
        item="The DCHS item to remove",
        count="How many to remove (default 1)",
    )
    @app_commands.autocomplete(item=item_autocomplete)
    async def admin_remove(
        self, interaction: discord.Interaction, member: discord.Member, item: str, count: int = 1
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return
        try:
            await admin_or_sc_bot(interaction)
        except app_commands.CheckFailure as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        if item not in ITEMS:
            await interaction.response.send_message(
                f"**{item}** is not a valid DCHS item.", ephemeral=True
            )
            return
        if count < 1:
            await interaction.response.send_message("Count must be at least 1.", ephemeral=True)
            return

        guild_inv = await self._get_guild_inventory(interaction.guild_id)
        user_key = str(member.id)
        user_inv = dict(guild_inv.get(user_key, {}))
        current_count = user_inv.get(item, 0)
        if current_count <= 0:
            await interaction.response.send_message(
                f"{member.display_name} doesn't have **{item}** in their inventory.",
                ephemeral=True,
            )
            return

        removed = min(count, current_count)
        user_inv[item] = current_count - removed
        if user_inv[item] == 0:
            del user_inv[item]
        guild_inv[user_key] = user_inv
        await self._save_guild_inventory(interaction.guild_id, guild_inv)

        remaining = user_inv.get(item, 0)
        await interaction.response.send_message(
            f"Removed ×{removed} **{item}** from {member.display_name}'s inventory. They now have ×{remaining}.",
            ephemeral=True,
        )

    @admin_group.command(name="clear", description="Clear all DCHS items from a member's inventory")
    @app_commands.describe(member="The member whose inventory to clear")
    async def admin_clear(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return
        try:
            await admin_or_sc_bot(interaction)
        except app_commands.CheckFailure as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        guild_inv = await self._get_guild_inventory(interaction.guild_id)
        user_key = str(member.id)
        if not guild_inv.get(user_key):
            await interaction.response.send_message(
                f"{member.display_name}'s inventory is already empty.", ephemeral=True
            )
            return

        guild_inv.pop(user_key, None)
        await self._save_guild_inventory(interaction.guild_id, guild_inv)
        await interaction.response.send_message(
            f"{member.display_name}'s inventory has been cleared.", ephemeral=True
        )

    @admin_group.command(name="clear-all", description="Clear all members' inventories")
    async def admin_clear_all(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return
        try:
            await admin_or_sc_bot(interaction)
        except app_commands.CheckFailure as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        await self._save_guild_inventory(interaction.guild_id, {})
        await interaction.response.send_message(
            "All inventories have been cleared.", ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(InventoryCog(bot))
