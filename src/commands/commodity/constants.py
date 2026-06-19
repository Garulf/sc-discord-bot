"""Constants and choice lists for the /commodity command group."""
from discord import app_commands

MAX_LOCATIONS_SHOWN = 8
BUY_COLOR = 0x2ECC71
SELL_COLOR = 0xF1C40F
LOSS_COLOR = 0xE74C3C
MAX_ROUTES = 3
ROUTE_COLOR = 0x2ECC71
UEX_ROUTES_URL = "https://uexcorp.space/trade/routes"

SYSTEM_CHOICES = [
    app_commands.Choice(name="Stanton", value="Stanton"),
    app_commands.Choice(name="Pyro", value="Pyro"),
    app_commands.Choice(name="Nyx", value="Nyx"),
]
PLACE_CHOICES = [
    app_commands.Choice(name="Station", value="station"),
    app_commands.Choice(name="Planet", value="planet"),
    app_commands.Choice(name="Outpost", value="outpost"),
]
CONTAINER_CHOICES = [
    app_commands.Choice(name=f"{size} SCU", value=size)
    for size in (1, 2, 4, 8, 16, 24, 32)
]
