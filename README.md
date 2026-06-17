# SC Discord Bot

A Star Citizen Discord bot that provides ship info, item lookups, commodity trading routes, and live RSI server status — all via slash commands.

## Commands

### Inventory
| Command | Description |
|---|---|
| `/inventory add <item>` | Add a DCHS item to your inventory (DCHS-01 through DCHS-07) |
| `/inventory remove <item>` | Remove a DCHS item from your inventory |
| `/inventory clear` | Clear all items from your inventory |
| `/inventory status` | Show all members' DCHS items and complete sets |

### Items & Equipment
| Command | Description |
|---|---|
| `/find all <name>` | Search across all item types at once |
| `/find weapon <name>` | Search FPS weapons |
| `/find shipweapon <name>` | Search ship-mounted weapons |
| `/find armor <name>` | Search armor |
| `/find clothes <name>` | Search clothing |
| `/find vehicleitem <name>` | Search vehicle/ship components (cooler, shield, power plant, etc.) |
| `/find weaponattachment <name>` | Search FPS weapon attachments |
| `/find item <name>` | Search miscellaneous items |

### Ships
| Command | Description |
|---|---|
| `/ship <name>` | Ship stats (crew, cargo, speed, hull, signals) and cheapest aUEC buy price |
| `/shipprice <name>` | All in-game buy and rental locations for a ship |

### Trading
| Command | Description |
|---|---|
| `/commodity buy <name>` | Best terminals to buy a commodity |
| `/commodity sell <name>` | Best terminals to sell a commodity |
| `/commodity route` | Top profitable buy→sell routes with optional filters |

### Executive Hangar
| Command | Description |
|---|---|
| `/hangar set` | Set the current hangar phase (charging / open / resetting) |
| `/hangar status` | Show current hangar status |
| `/hangar subscribe` | Post a live auto-updating hangar status in this channel |
| `/hangar unsubscribe` | Remove the live status from this channel |

### RSI Server Status
| Command | Description |
|---|---|
| `/status show` | Show current RSI server status |
| `/status subscribe` | Post RSI status alerts in this channel |
| `/status unsubscribe` | Stop RSI status alerts in this channel |

## Setup

### Prerequisites
- Docker and Docker Compose
- A Discord bot token
- A UEX bearer token (for trading/price commands)

### Configuration

Copy `.env.example` to `.env` and fill in the values:

```env
DISCORD_TOKEN=your_discord_bot_token
UEX_BEARER_TOKEN=your_uex_token
```

### Running

```bash
# Start the bot
docker compose up -d

# Start with live reload on file changes (development)
./run.ps1
```

### Discord Bot Permissions

The bot requires the following when creating its application:
- `applications.commands` scope (slash commands)
- No privileged intents required

## Data Sources

- **[star-citizen.wiki](https://star-citizen.wiki)** — ship stats, weapons, armor, clothing, and other item data
- **[UEX](https://uexcorp.space)** — in-game aUEC prices for commodities, ships, and equipment

## Development

Bot state (hangar schedule, subscriptions, API cache) is stored in a SQLite database at `/app/data/bot.db`, persisted via the `bot-data` Docker volume.
