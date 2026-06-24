# Changelog

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
