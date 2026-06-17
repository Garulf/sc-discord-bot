from __future__ import annotations

import discord
from discord import app_commands

_SC_BOT_ROLE = "sc-bot"


async def admin_or_sc_bot(interaction: discord.Interaction) -> bool:
    """Allow administrators and members with the 'sc-bot' role."""
    member = interaction.user
    if not interaction.guild or not isinstance(member, discord.Member):
        raise app_commands.CheckFailure("This command can only be used in a server.")
    if member.guild_permissions.administrator:
        return True
    if any(role.name.lower() == _SC_BOT_ROLE for role in member.roles):
        return True
    raise app_commands.CheckFailure(
        f"You need the **{_SC_BOT_ROLE}** role or administrator permissions to use this command."
    )
