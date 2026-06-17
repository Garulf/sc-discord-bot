"""Inventory tracking for DCHS collectible sets.

Each user's per-guild inventory is persisted in the bot's SQLite StateStore
under a key scoped to the guild. The ``/inventory status`` command resolves
Discord member display names at call time so display names stay current.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

ITEMS = [f"DCHS-{i:02d}" for i in range(1, 8)]
_STATE_KEY_PREFIX = "inventory"
_MAX_EMBED_FIELDS = 25


def _guild_key(guild_id: int) -> str:
    return f"{_STATE_KEY_PREFIX}:{guild_id}"


def _complete_sets(inventory: dict[str, int]) -> int:
    """Minimum count across all 7 items — the number of complete sets."""
    return min(inventory.get(item, 0) for item in ITEMS)


def _format_user_inventory(inventory: dict[str, int]) -> str:
    lines = []
    for item in ITEMS:
        count = inventory.get(item, 0)
        if count > 0:
            lines.append(f"{item}: ×{count}")

    missing = [item.replace("DCHS-", "") for item in ITEMS if inventory.get(item, 0) == 0]
    if missing:
        lines.append(f"Need: {', '.join(missing)}")

    sets = _complete_sets(inventory)
    lines.append(f"**{sets} complete set{'s' if sets != 1 else ''}**" if sets > 0 else "No complete set")
    return "\n".join(lines)


class InventoryCog(commands.Cog):
    """DCHS collectible set inventory tracking."""

    inventory = app_commands.Group(name="inventory", description="DCHS collectible set inventory")

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

    @inventory.command(name="add", description="Add a DCHS item to your inventory")
    @app_commands.describe(item="The DCHS item to add (DCHS-01 through DCHS-07)")
    @app_commands.autocomplete(item=item_autocomplete)
    async def add(self, interaction: discord.Interaction, item: str) -> None:
        if item not in ITEMS:
            await interaction.response.send_message(
                f"**{item}** is not a valid DCHS item. Choose from DCHS-01 through DCHS-07.",
                ephemeral=True,
            )
            return
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        guild_inv = await self._get_guild_inventory(interaction.guild_id)
        user_key = str(interaction.user.id)
        user_inv = dict(guild_inv.get(user_key, {}))
        user_inv[item] = user_inv.get(item, 0) + 1
        guild_inv[user_key] = user_inv
        await self._save_guild_inventory(interaction.guild_id, guild_inv)

        count = user_inv[item]
        sets = _complete_sets(user_inv)
        msg = f"Added **{item}** to your inventory. You now have ×{count}."
        if sets > 0:
            msg += f" You have **{sets} complete set{'s' if sets != 1 else ''}**!"
        await interaction.response.send_message(msg, ephemeral=True)

    @inventory.command(name="remove", description="Remove a DCHS item from your inventory")
    @app_commands.describe(item="The DCHS item to remove")
    @app_commands.autocomplete(item=item_autocomplete)
    async def remove(self, interaction: discord.Interaction, item: str) -> None:
        if item not in ITEMS:
            await interaction.response.send_message(
                f"**{item}** is not a valid DCHS item.", ephemeral=True
            )
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

        user_inv[item] = current_count - 1
        if user_inv[item] == 0:
            del user_inv[item]
        guild_inv[user_key] = user_inv
        await self._save_guild_inventory(interaction.guild_id, guild_inv)

        remaining = user_inv.get(item, 0)
        await interaction.response.send_message(
            f"Removed **{item}** from your inventory. You now have ×{remaining}.",
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

    @inventory.command(
        name="status", description="Show all members' DCHS inventory and complete sets"
    )
    async def status(self, interaction: discord.Interaction) -> None:
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

        embed = discord.Embed(title="DCHS Inventory Status", color=0x5865F2)

        total_sets = 0
        shown = 0
        for user_key, user_inv in active.items():
            total_sets += _complete_sets(user_inv)

            if shown >= _MAX_EMBED_FIELDS:
                continue

            member = guild.get_member(int(user_key))
            if member is None:
                try:
                    member = await guild.fetch_member(int(user_key))
                except (discord.NotFound, discord.HTTPException):
                    continue

            embed.add_field(
                name=member.display_name,
                value=_format_user_inventory(user_inv),
                inline=True,
            )
            shown += 1

        embed.set_footer(text=f"Server total: {total_sets} complete set{'s' if total_sets != 1 else ''}")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(InventoryCog(bot))
