# Changelog

## [0.4.0](https://github.com/Garulf/sc-discord-bot/compare/v0.3.0...v0.4.0) (2026-06-27)


### Features

* **hangar:** add /hangar global set for bot owner with per-guild override support ([2909660](https://github.com/Garulf/sc-discord-bot/commit/29096606f593f0e50f596c9e04ab28cabe860194))
* **hangar:** post 5-minute advance warnings before open and close ([5c9639a](https://github.com/Garulf/sc-discord-bot/commit/5c9639af9c0861ca7acc8084cf61a6aec5cf3547))
* **inventory:** add refresh loop to update subscribed channels on startup and every 5 minutes ([11c9839](https://github.com/Garulf/sc-discord-bot/commit/11c98396388473abf4cf6f0760987471255a830d))
* **inventory:** add subscribe/unsubscribe handlers ([f73e19c](https://github.com/Garulf/sc-discord-bot/commit/f73e19c9f6e1eda4ab88e3fa89bc09e1bbb0e45a))
* **inventory:** add subscriptions module with live-status and notification helpers ([276144a](https://github.com/Garulf/sc-discord-bot/commit/276144ae589ec030d707a0b1cdcdb759b0536def))
* **inventory:** apply per-card fields to admin add/remove ([24d94cd](https://github.com/Garulf/sc-discord-bot/commit/24d94cdf0fcb12eabe4cd4653603dc187cc2e7ff))
* **inventory:** broadcast notifications and refresh live status on inventory mutations ([da827e8](https://github.com/Garulf/sc-discord-bot/commit/da827e8801e6e2810f5671bbafb7ce1620931b5d))
* **inventory:** one field per card for add and remove item ([e39aeee](https://github.com/Garulf/sc-discord-bot/commit/e39aeeef1f512123270ea7c8029ee09fe4598158))
* **inventory:** only notify on personal complete sets or server pool milestones ([9b64073](https://github.com/Garulf/sc-discord-bot/commit/9b6407334cc08a498e0130ebc326a460ba6d179a))
* **inventory:** register subscribe/unsubscribe commands and add notification cleanup loop ([d512944](https://github.com/Garulf/sc-discord-bot/commit/d512944716a267c7fad9956346524a67cc7de4f9))
* **inventory:** rename add/remove item fields to dchs-01 through dchs-07 ([bc626ab](https://github.com/Garulf/sc-discord-bot/commit/bc626ab6f3000003ce1e8bc577d22c3396ec16e1))
* **inventory:** render status as markdown table with users as rows and cards as columns ([2d808bd](https://github.com/Garulf/sc-discord-bot/commit/2d808bdf3c5e7445f29d8db9c1e8853d7439942a))
* **inventory:** replace item+count pairs with up to 25 individual item slots ([a3cc7f4](https://github.com/Garulf/sc-discord-bot/commit/a3cc7f4d0ea502118149151c4d8c5fca493c5651))
* **inventory:** support multi-item add and remove-set subcommand ([3f3f58c](https://github.com/Garulf/sc-discord-bot/commit/3f3f58c8e4506102d44b657cb10df13c686dc60a))
* **inventory:** support multi-item remove ([ffdd1f9](https://github.com/Garulf/sc-discord-bot/commit/ffdd1f994e2183171b139a38249934f2bdc70923))
* **inventory:** switch to card+count pairs for add and remove item ([2499799](https://github.com/Garulf/sc-discord-bot/commit/249979920eddcefe9c68e4ca50a0b70e1294b147))


### Bug Fixes

* **hangar:** disallow duplicate subscriptions in the same channel ([92db28a](https://github.com/Garulf/sc-discord-bot/commit/92db28ad4d9746bef7066b2fa82c613379e3a20f))
* **hangar:** prevent update loop from dying on transient HTTP errors ([5756488](https://github.com/Garulf/sc-discord-bot/commit/57564887928a5c3756283daeff0694483ac2b04d))
* **inventory:** compute server total from pooled inventory ([c0f7bed](https://github.com/Garulf/sc-discord-bot/commit/c0f7bed79aa27e9177c8d14850c827e94e4d6033))
* **inventory:** display cards horizontally per user row in status embeds ([cc42da3](https://github.com/Garulf/sc-discord-bot/commit/cc42da3a33b63ad8efbf5ca92cd9d1807a99b955))
* **inventory:** improve remove confirmation when count reaches zero ([13ce8dc](https://github.com/Garulf/sc-discord-bot/commit/13ce8dc6a71d371a04ae6e21c89417e40d5796b2))
* **inventory:** put username on its own line and bold card numbers in status embeds ([d81425b](https://github.com/Garulf/sc-discord-bot/commit/d81425b85d603c67dbec2956b3435ccade41373f))
* **inventory:** replace table format with Discord-native per-user lines in status embeds ([5b510fc](https://github.com/Garulf/sc-discord-bot/commit/5b510fcab2ec9c18edce8446be7c47a09984204c))
* **inventory:** respond to interaction before refreshing live status ([e293f72](https://github.com/Garulf/sc-discord-bot/commit/e293f7215881bdaf61cafd0c5eff33fdadab948d))
* **inventory:** switch status embed fields to vertical layout for readability ([d331ca9](https://github.com/Garulf/sc-discord-bot/commit/d331ca9c048bdf05b4be2d48e7716cb8b46148ce))

## [0.3.0](https://github.com/Garulf/sc-discord-bot/compare/v0.2.0...v0.3.0) (2026-06-24)


### Features

* **find:** add /find wikelo command ([a5289c7](https://github.com/Garulf/sc-discord-bot/commit/a5289c7a521a67adddeff4aa33b889d2510897d1))
* **find:** add wikelo embed builder, autocomplete, and handler ([d15ee95](https://github.com/Garulf/sc-discord-bot/commit/d15ee955cd7a1ca7d947bd13dac5d36c65803778))
* **find:** rename wikelo embed 'Hauling Orders' to 'Requirements' ([bdf65fe](https://github.com/Garulf/sc-discord-bot/commit/bdf65fee0653a61162a43e2632e594c3d09f8cbe))
* **find:** rename wikelo embed field 'Hauling Orders' to 'Requirements' ([a609ac7](https://github.com/Garulf/sc-discord-bot/commit/a609ac71894f44c9cac1a95a187d6360db10734a))
* **find:** wire /find wikelo subcommand ([fe9af9c](https://github.com/Garulf/sc-discord-bot/commit/fe9af9ca96f392167c344841cd30e764f08a527d))
* **missions:** add RewardItem, HaulingOrder models and Mission fields ([7f35ea7](https://github.com/Garulf/sc-discord-bot/commit/7f35ea7464c27ac0b29a646e6f0cf686f9086d1e))


### Bug Fixes

* **find:** correct reward match, image, reputation and field truncation in wikelo ([3d7fdaa](https://github.com/Garulf/sc-discord-bot/commit/3d7fdaa54be6dd6bfce769868bec621b237aacbe))
* **find:** use first_image helper in _fetch_item_image for url fallback ([28c39c7](https://github.com/Garulf/sc-discord-bot/commit/28c39c7c00b4e12ef9f698ec7b0f045eac153455))


### Performance Improvements

* **find:** cache Wikelo missions list to avoid N+1 on every autocomplete keystroke ([c0320a1](https://github.com/Garulf/sc-discord-bot/commit/c0320a1c81355df6a0dc281bfb083242ced5f8c2))

## [0.2.0](https://github.com/Garulf/sc-discord-bot/compare/v0.1.0...v0.2.0) (2026-06-21)


### Features

* **timer:** add 'Redo Timer' button to expiry DM notification ([d4685e8](https://github.com/Garulf/sc-discord-bot/commit/d4685e86cda5df4569bcccf38fc0d7776400d778))
* **timer:** add /timer command for key card and vault door timers ([ae65022](https://github.com/Garulf/sc-discord-bot/commit/ae6502241ceedd988b43ba4831e7b7333eba13c7))


### Bug Fixes

* **find blueprint:** filter sentinel titles and fix mid-link truncation ([9ab5fb2](https://github.com/Garulf/sc-discord-bot/commit/9ab5fb23f0fe54d35645062c4881fab0ae4051fd))
* **find mission:** deduplicate autocomplete choices by title ([9be557e](https://github.com/Garulf/sc-discord-bot/commit/9be557e33540e6e7c447928be707345e750bec5d))
* **find mission:** label reward as aUEC instead of UEC ([3d3b0c4](https://github.com/Garulf/sc-discord-bot/commit/3d3b0c4536e8211bc591f66b3bea9822ad2e7948))
* **find mission:** show required reputation rank and fix blueprint links ([5069c68](https://github.com/Garulf/sc-discord-bot/commit/5069c687991685f69a4229d032522a935bae1181))
* **find:** deduplicate blueprint autocomplete by name, matching mission behavior ([02ccdaa](https://github.com/Garulf/sc-discord-bot/commit/02ccdaaec867640b37637abaf71fd1ad7679b3c7))
* **lint:** sort imports and apply ruff UP017 fixes ([b843a0a](https://github.com/Garulf/sc-discord-bot/commit/b843a0a4e18905e375f379640f55937df93cccec))
