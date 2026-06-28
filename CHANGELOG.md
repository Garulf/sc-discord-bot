# Changelog

## [0.4.0](https://github.com/Garulf/sc-discord-bot/compare/v0.3.0...v0.4.0) (2026-06-28)


### Features

* add deploy script with local SSH host config ([2b432bd](https://github.com/Garulf/sc-discord-bot/commit/2b432bdb0b5cd1119ef05c6a52321da97b87a91e))
* add deploy script with local SSH host config ([7bef79d](https://github.com/Garulf/sc-discord-bot/commit/7bef79d7f0c2aa4bc8caba70b19ce97a805a488e))
* **bot:** DM owner on unhandled errors with traceback ([1cb03d2](https://github.com/Garulf/sc-discord-bot/commit/1cb03d203655e58ab814a34df6d9459d650f3f91))
* **bot:** DM owner on unhandled errors with traceback ([d853434](https://github.com/Garulf/sc-discord-bot/commit/d85343448bc24f63b18b47e43bce676e769ee4f4))
* **hangar:** add /hangar global set for bot owner with per-guild override support ([2909660](https://github.com/Garulf/sc-discord-bot/commit/29096606f593f0e50f596c9e04ab28cabe860194))
* **hangar:** clean up warning messages on status change ([9d69068](https://github.com/Garulf/sc-discord-bot/commit/9d690684d8c5bb14488ba1545cd0ed9f015e72db))
* **hangar:** clean up warning messages on status change and add --force flag to run.sh ([51486a4](https://github.com/Garulf/sc-discord-bot/commit/51486a434468435a53dddd3e29a6be0d45898a35))
* **hangar:** post 5-minute advance warnings before open and close ([5c9639a](https://github.com/Garulf/sc-discord-bot/commit/5c9639af9c0861ca7acc8084cf61a6aec5cf3547))
* **inventory:** add refresh loop to update subscribed channels on startup and every 5 minutes ([11c9839](https://github.com/Garulf/sc-discord-bot/commit/11c98396388473abf4cf6f0760987471255a830d))
* **inventory:** add Server total row at bottom of status table showing pooled cards and sets ([877a37e](https://github.com/Garulf/sc-discord-bot/commit/877a37e1c99fdd571cc50b5e49bd0216a950b47c))
* **inventory:** add subscribe/unsubscribe handlers ([f73e19c](https://github.com/Garulf/sc-discord-bot/commit/f73e19c9f6e1eda4ab88e3fa89bc09e1bbb0e45a))
* **inventory:** add subscriptions module with live-status and notification helpers ([276144a](https://github.com/Garulf/sc-discord-bot/commit/276144ae589ec030d707a0b1cdcdb759b0536def))
* **inventory:** add transfer commands and improve error logging ([721b596](https://github.com/Garulf/sc-discord-bot/commit/721b59615aab266352ab2de93c005f1ad852104c))
* **inventory:** add transfer commands and improve error logging ([c95b487](https://github.com/Garulf/sc-discord-bot/commit/c95b48729c2163cdbac1430650c083f5159ae66f))
* **inventory:** apply per-card fields to admin add/remove ([24d94cd](https://github.com/Garulf/sc-discord-bot/commit/24d94cdf0fcb12eabe4cd4653603dc187cc2e7ff))
* **inventory:** broadcast notifications and refresh live status on inventory mutations ([da827e8](https://github.com/Garulf/sc-discord-bot/commit/da827e8801e6e2810f5671bbafb7ce1620931b5d))
* **inventory:** default card count to 1 in /inventory add ([d006793](https://github.com/Garulf/sc-discord-bot/commit/d006793b4026ad6c438484591c97e3540e7b688b))
* **inventory:** one field per card for add and remove item ([e39aeee](https://github.com/Garulf/sc-discord-bot/commit/e39aeeef1f512123270ea7c8029ee09fe4598158))
* **inventory:** only notify on personal complete sets or server pool milestones ([9b64073](https://github.com/Garulf/sc-discord-bot/commit/9b6407334cc08a498e0130ebc326a460ba6d179a))
* **inventory:** register subscribe/unsubscribe commands and add notification cleanup loop ([d512944](https://github.com/Garulf/sc-discord-bot/commit/d512944716a267c7fad9956346524a67cc7de4f9))
* **inventory:** rename /inv status everyone to /inv status server ([2bda842](https://github.com/Garulf/sc-discord-bot/commit/2bda842eabb755607615d80dac5cf4aa16494ce3))
* **inventory:** rename /inv status everyone to /inv status server ([e71a08a](https://github.com/Garulf/sc-discord-bot/commit/e71a08a0271baaea8dffac1c32596554a0446402))
* **inventory:** rename /inventory command group to /inv ([0107a4a](https://github.com/Garulf/sc-discord-bot/commit/0107a4acfe7fcbcc93ae09aedc57a235b9eff8b2))
* **inventory:** rename /inventory to /inv ([7ce962f](https://github.com/Garulf/sc-discord-bot/commit/7ce962f92c3a614102d2bf12d85b070284149237))
* **inventory:** rename add/remove item fields to dchs-01 through dchs-07 ([bc626ab](https://github.com/Garulf/sc-discord-bot/commit/bc626ab6f3000003ce1e8bc577d22c3396ec16e1))
* **inventory:** render live status table as PNG image ([001ea2f](https://github.com/Garulf/sc-discord-bot/commit/001ea2fb7a86d87a5dcc47af978416f211c3d792))
* **inventory:** render live status table as PNG image ([542e4a6](https://github.com/Garulf/sc-discord-bot/commit/542e4a6f9e4feb6c2c3c406d2ee3da474421987d))
* **inventory:** render status as markdown table with users as rows and cards as columns ([2d808bd](https://github.com/Garulf/sc-discord-bot/commit/2d808bdf3c5e7445f29d8db9c1e8853d7439942a))
* **inventory:** render status as thin_compact ASCII table using table2ascii ([60e6b7e](https://github.com/Garulf/sc-discord-bot/commit/60e6b7e2dd8f642563ad323c5a6811fe36741ca0))
* **inventory:** render status as thin_compact ASCII table using table2ascii ([e311b80](https://github.com/Garulf/sc-discord-bot/commit/e311b80b3d494e9f7c9cf19cdbc93a87e9daca7c))
* **inventory:** replace item+count pairs with up to 25 individual item slots ([a3cc7f4](https://github.com/Garulf/sc-discord-bot/commit/a3cc7f4d0ea502118149151c4d8c5fca493c5651))
* **inventory:** support multi-item add and remove-set subcommand ([3f3f58c](https://github.com/Garulf/sc-discord-bot/commit/3f3f58c8e4506102d44b657cb10df13c686dc60a))
* **inventory:** support multi-item remove ([ffdd1f9](https://github.com/Garulf/sc-discord-bot/commit/ffdd1f994e2183171b139a38249934f2bdc70923))
* **inventory:** switch to card+count pairs for add and remove item ([2499799](https://github.com/Garulf/sc-discord-bot/commit/249979920eddcefe9c68e4ca50a0b70e1294b147))
* **inventory:** use autocomplete on /inventory add card fields to default count to 1 ([cbca87f](https://github.com/Garulf/sc-discord-bot/commit/cbca87f553cef08d7fc49111608dc811c2ae85b9))


### Bug Fixes

* **deps:** add table2ascii to pyproject.toml dependencies ([29e838b](https://github.com/Garulf/sc-discord-bot/commit/29e838b83fd6a0cad26ab20823bf43f051d1df59))
* **hangar:** disallow duplicate subscriptions in the same channel ([92db28a](https://github.com/Garulf/sc-discord-bot/commit/92db28ad4d9746bef7066b2fa82c613379e3a20f))
* **hangar:** prevent update loop from dying on transient HTTP errors ([5756488](https://github.com/Garulf/sc-discord-bot/commit/57564887928a5c3756283daeff0694483ac2b04d))
* **inventory:** catch silent exceptions in before_refresh_loop and remove duplicate error handler ([6e656a5](https://github.com/Garulf/sc-discord-bot/commit/6e656a50b338cf86eaa5b3a296ece5d48f0d6325))
* **inventory:** compute server total from pooled inventory ([c0f7bed](https://github.com/Garulf/sc-discord-bot/commit/c0f7bed79aa27e9177c8d14850c827e94e4d6033))
* **inventory:** delete notification messages on unsubscribe ([04a9843](https://github.com/Garulf/sc-discord-bot/commit/04a984337f920f17478abab5011a727734d5d121))
* **inventory:** delete notification messages on unsubscribe ([2d9b465](https://github.com/Garulf/sc-discord-bot/commit/2d9b465127e2c438c990c88d40ca7b1e756ee8cf))
* **inventory:** display cards horizontally per user row in status embeds ([cc42da3](https://github.com/Garulf/sc-discord-bot/commit/cc42da3a33b63ad8efbf5ca92cd9d1807a99b955))
* **inventory:** improve remove confirmation when count reaches zero ([13ce8dc](https://github.com/Garulf/sc-discord-bot/commit/13ce8dc6a71d371a04ae6e21c89417e40d5796b2))
* **inventory:** put username on its own line and bold card numbers in status embeds ([d81425b](https://github.com/Garulf/sc-discord-bot/commit/d81425b85d603c67dbec2956b3435ccade41373f))
* **inventory:** remove dead pool_sets references and add refresh to admin clear ([3840df6](https://github.com/Garulf/sc-discord-bot/commit/3840df6f7da92b178c5ca642b5c19e418669d319))
* **inventory:** remove dead pool_sets references in transfer handlers and add refresh to admin clear ([b188be6](https://github.com/Garulf/sc-discord-bot/commit/b188be68397ea2c4197ca0a9e8ed4e91c59aaa4f))
* **inventory:** remove redundant server total footer line from status messages ([402082a](https://github.com/Garulf/sc-discord-bot/commit/402082af110e675393469942dee8a6aff71b2920))
* **inventory:** replace table format with Discord-native per-user lines in status embeds ([5b510fc](https://github.com/Garulf/sc-discord-bot/commit/5b510fcab2ec9c18edce8446be7c47a09984204c))
* **inventory:** respond to interaction before refreshing live status ([e293f72](https://github.com/Garulf/sc-discord-bot/commit/e293f7215881bdaf61cafd0c5eff33fdadab948d))
* **inventory:** send status as plain message content instead of embed to fix table width ([726d038](https://github.com/Garulf/sc-discord-bot/commit/726d038d79da00be8312dfe1b66efdcb0ceb8aab))
* **inventory:** suppress pool completion message when user also completes a personal set ([db19467](https://github.com/Garulf/sc-discord-bot/commit/db19467d24315466a84f231c8be33058f7605614))
* **inventory:** switch status embed fields to vertical layout for readability ([d331ca9](https://github.com/Garulf/sc-discord-bot/commit/d331ca9c048bdf05b4be2d48e7716cb8b46148ce))
* **inventory:** use plain x prefix in table cells to fix Discord monospace alignment ([850730d](https://github.com/Garulf/sc-discord-bot/commit/850730d8cb04c6b701812699ba7c8b040e5027d6))
* **lint:** fix ruff E402 import order and remove unused imports ([95fec5d](https://github.com/Garulf/sc-discord-bot/commit/95fec5d7e3d6b562a4c3ef243c966ccb0250cf16))
* **lint:** move logger assignments after all imports to fix ruff E402 ([b8fbabb](https://github.com/Garulf/sc-discord-bot/commit/b8fbabbed81311da6dcdc8a11bfd93b9e2847dad))

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
