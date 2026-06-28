# SC Discord Bot

A Star Citizen Discord bot providing ship info, item lookups, commodity trading routes, live RSI server status, Executive Hangar tracking, and DCHS collectible set inventory — all via slash commands.

## Commands

### DCHS Inventory (`/inv`)

Track Drake Collaborative Housing Set collectible cards across your server.

| Command | Description |
|---|---|
| `/inv add [dchs-01] … [dchs-07]` | Add cards to your inventory (count defaults to 1) |
| `/inv remove item [dchs-01] … [dchs-07]` | Remove cards from your inventory |
| `/inv remove set` | Remove one complete set (DCHS-01 through DCHS-07) |
| `/inv clear` | Clear your entire inventory |
| `/inv transfer item <user> [dchs-01] … [dchs-07]` | Transfer cards to another member |
| `/inv transfer set <user>` | Transfer one complete set to another member |
| `/inv status mine` | Show your own inventory |
| `/inv status server` | Show all members' inventories and complete set counts |
| `/inv subscribe` | Post a live auto-updating inventory status image in this channel |
| `/inv unsubscribe` | Remove the live status from this channel |

**Context menu (right-click a user → Apps):**
| Action | Description |
|---|---|
| Transfer Set | Transfer one complete set to the selected member with a confirmation dialog |

**Admin commands** (`/inv admin`) — requires Administrator permission or the `sc-bot` role:

| Command | Description |
|---|---|
| `/inv admin add <user> [dchs-01] … [dchs-07]` | Add cards to a member's inventory |
| `/inv admin remove <user> [dchs-01] … [dchs-07]` | Remove cards from a member's inventory |
| `/inv admin clear <user>` | Clear a member's inventory |
| `/inv admin clear-all` | Clear all members' inventories |
| `/inv admin transfer-set <sender> <recipient>` | Transfer a complete set between two members |

#### Live Status Channel

Use `/inv subscribe` in a channel to post a PNG image of the current inventory table. It updates automatically whenever cards are added, removed, or transferred.

Subscribed channels also receive event notifications (set completions, transfers). The most recent **5 notifications** are kept; older ones are automatically deleted after **1 hour** of being displaced.

---

### Items & Equipment (`/find`)

| Command | Description |
|---|---|
| `/find all <name>` | Search across all item types |
| `/find weapon <name>` | FPS weapons |
| `/find shipweapon <name>` | Ship-mounted weapons |
| `/find armor <name>` | Armor sets |
| `/find clothes <name>` | Clothing |
| `/find vehicleitem <name>` | Ship/vehicle components (coolers, shields, power plants, …) |
| `/find weaponattachment <name>` | FPS weapon attachments |
| `/find item <name>` | Miscellaneous items |

---

### Ships

| Command | Description |
|---|---|
| `/ship <name>` | Ship stats (crew, cargo, speed, hull, signals) and cheapest aUEC buy price |
| `/shipprice <name>` | All in-game buy and rental locations for a ship |

---

### Trading (`/commodity`)

| Command | Description |
|---|---|
| `/commodity buy <name>` | Best terminals to buy a commodity |
| `/commodity sell <name>` | Best terminals to sell a commodity |
| `/commodity route` | Top profitable buy→sell routes with optional filters |

---

### Executive Hangar (`/hangar`)

| Command | Description |
|---|---|
| `/hangar set` | Set the current hangar phase (charging / open / resetting) |
| `/hangar status` | Show current hangar status and next phase time |
| `/hangar subscribe` | Post a live auto-updating hangar status in this channel |
| `/hangar unsubscribe` | Remove the live status from this channel |
| `/hangar global set` | Set a global hangar schedule for all servers (bot owner only) |

The live status updates automatically as the hangar cycles through phases. Warning messages are posted before each open and close, and cleaned up when the phase changes.

---

### RSI Server Status (`/status`)

| Command | Description |
|---|---|
| `/status show` | Show current RSI server status |
| `/status subscribe` | Post RSI status alerts in this channel |
| `/status unsubscribe` | Stop RSI status alerts in this channel |

---

## Setup

### Prerequisites

- Docker and Docker Compose
- A Discord bot token
- A UEX bearer token (for trading/price commands)

### Configuration

Copy `.env.example` to `.env` and fill in your values:

```env
DISCORD_TOKEN=your_discord_bot_token
UEX_BEARER_TOKEN=your_uex_token
```

### Running

```bash
# Build and start
./scripts/run.sh

# Force rebuild even without new commits
./scripts/run.sh
```

### Discord Bot Permissions

When creating the application in the Discord Developer Portal:

- **Scopes:** `applications.commands`, `bot`
- **Bot permissions:** `Send Messages`, `Embed Links`, `Attach Files`, `Read Message History`, `Manage Messages`
- No privileged intents required

---

## Data Sources

- **[star-citizen.wiki](https://star-citizen.wiki)** — ship stats, weapons, armor, clothing, and item data
- **[UEX](https://uexcorp.space)** — in-game aUEC prices for commodities, ships, and equipment

---

## Development

Bot state (hangar schedule, inventory, subscriptions, API cache) is stored in a SQLite database at `/app/data/bot.db`, persisted via the `bot-data` Docker volume.

### Running Tests

```bash
pip install -r requirements-dev.txt
pytest tests/
```

### Releases

Releases are managed automatically by [release-please](https://github.com/googleapis/release-please). On every merge to `main`, the action opens (or updates) a release PR that bumps the version in `pyproject.toml` and updates `CHANGELOG.md`. Merging that PR creates the git tag and GitHub Release.

### Commit Message Format

Commit messages must follow [Conventional Commits](https://www.conventionalcommits.org/) so release-please can determine the next version:

| Prefix | Effect |
|---|---|
| `fix:` | patch bump (`0.1.0` → `0.1.1`) |
| `feat:` | minor bump (`0.1.0` → `0.2.0`) |
| `feat!:` or `BREAKING CHANGE:` footer | major bump (`0.1.0` → `1.0.0`) |
| `chore:`, `docs:`, `refactor:`, `test:`, `ci:` | no version bump |

To enable local commit-message validation after cloning:

```bash
pre-commit install --hook-type commit-msg
```
