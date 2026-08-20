# Changelog

## [0.5.0](https://github.com/Garulf/sc-discord-bot/compare/v0.4.0...v0.5.0) (2026-08-20)


### Features

* add /lookup command for RSI citizen profile ([e52d547](https://github.com/Garulf/sc-discord-bot/commit/e52d54743724c750eea9ca8941294713382b87ea))
* add /mine command with autocomplete for mining locations ([#26](https://github.com/Garulf/sc-discord-bot/issues/26)) ([f9568c0](https://github.com/Garulf/sc-discord-bot/commit/f9568c0f87b25d1d5cba098b3e73a8b1241618e3))
* **beacons:** activity tracking, fill counter, voice channels, commendations ([8dbf951](https://github.com/Garulf/sc-discord-bot/commit/8dbf9510858d0b343bee74e2887057ccc9ff7b2d))
* **beacons:** add build_scheduled_embed and share field rendering ([3dc2ffa](https://github.com/Garulf/sc-discord-bot/commit/3dc2ffae329096501c36d7cb629276a5c8dfa624))
* **beacons:** add contested zone category and panel descriptions ([a23ee4c](https://github.com/Garulf/sc-discord-bot/commit/a23ee4ccf81b74706fed9239428755dcf57ae959))
* **beacons:** add escort and transport categories with deterministic fields ([0748e63](https://github.com/Garulf/sc-discord-bot/commit/0748e630d22f623f5c31b5e34358b8b9a54f3fea))
* **beacons:** add lifecycle fields, settings, and store scans ([0f1cf62](https://github.com/Garulf/sc-discord-bot/commit/0f1cf622ec0509e68d2e906693d30bcdd4070bc1))
* **beacons:** add relative duration parser for scheduled beacons ([9b7f948](https://github.com/Garulf/sc-discord-bot/commit/9b7f9485de47c586fc9a3ab90870741e97ff0377))
* **beacons:** add schedule_role setting to /beacon config ([f3948c3](https://github.com/Garulf/sc-discord-bot/commit/f3948c317a616dc447e0c38291cb0b0eca379561))
* **beacons:** add scheduled-beacon creation, role gate, and RSVP handlers ([d8c1fe6](https://github.com/Garulf/sc-discord-bot/commit/d8c1fe6b1fd9a2f707b8225f0d0f91b1d7c8d626))
* **beacons:** add scheduled-beacon storage and schedule_role setting ([e92adc6](https://github.com/Garulf/sc-discord-bot/commit/e92adc60bf440381c6f6f99f02c2f15080dcb811))
* **beacons:** add ScheduledBeaconView with join/leave/cancel buttons ([356a353](https://github.com/Garulf/sc-discord-bot/commit/356a353910db9d649860bb624831ff801fe2528d))
* **beacons:** add when option to schedule beacons ahead of time ([08c84b8](https://github.com/Garulf/sc-discord-bot/commit/08c84b8972db32dfbe1768662579b10085124779))
* **beacons:** area status and crew fields, drop placeholder locations ([1e316b2](https://github.com/Garulf/sc-discord-bot/commit/1e316b2951084dfe8a0b839c96b5297d7a145a98))
* **beacons:** build thread titles from beacon metadata ([bde3d2c](https://github.com/Garulf/sc-discord-bot/commit/bde3d2cbacee04f95d37c1d26300359b456e97bf))
* **beacons:** close, again, and config commands ([374c223](https://github.com/Garulf/sc-discord-bot/commit/374c22317ce1a371a35c91b560d6406b725abfe9))
* **beacons:** configurable discord category for beacon voice channels ([dd16f7c](https://github.com/Garulf/sc-discord-bot/commit/dd16f7c79f9f9e2334849115976211339a031342))
* **beacons:** dedicated leave button; join no longer toggles ([096c801](https://github.com/Garulf/sc-discord-bot/commit/096c801f5b830500ab475aa3ce12cfcc55b8e48e))
* **beacons:** escalation and idle auto-close maintenance loop ([2e2197a](https://github.com/Garulf/sc-discord-bot/commit/2e2197a26befcf44d53b8e219031ea08b1bab77d))
* **beacons:** fire scheduled beacons and send pre-open reminders ([bc3dcbe](https://github.com/Garulf/sc-discord-bot/commit/bc3dcbe2134fa8d72b69069a748deebffc6e76ca))
* **beacons:** let the bot owner join their own beacons for testing ([e238fe1](https://github.com/Garulf/sc-discord-bot/commit/e238fe15845b434a7c66855ac2acf827b6a099b2))
* **beacons:** limit contested zone locations to contested stations ([7f772be](https://github.com/Garulf/sc-discord-bot/commit/7f772becacf429e2f9d9843a8b3cac7a89fd53b0))
* **beacons:** live beacon status board ([e71086a](https://github.com/Garulf/sc-discord-bot/commit/e71086ac20af71b79f607aab072410582c4f941f))
* **beacons:** per-category voice channel creation via beacon config ([2d6a5ec](https://github.com/Garulf/sc-discord-bot/commit/2d6a5ecc77e2152dcc9b9f53dd2c9bbd7c22c946))
* **beacons:** replace area status with danger level field ([5f0ee3e](https://github.com/Garulf/sc-discord-bot/commit/5f0ee3e54b1f212825e0029ac526e7f2a8cc5aba))
* **beacons:** replace claim with join/leave responder lists ([c2f016c](https://github.com/Garulf/sc-discord-bot/commit/c2f016c67bdb9bc32d14a449fc03341c70a01536))
* **beacons:** replace panel buttons with clickable command mentions ([1b9020f](https://github.com/Garulf/sc-discord-bot/commit/1b9020fc91175943d94bcb01618c044c0ef01aa4))
* **beacons:** run the scheduled-beacon sweep from maintenance ([01e9362](https://github.com/Garulf/sc-discord-bot/commit/01e93622a0555b9855cd5024a5c3ff19c1abc30c))
* **beacons:** single location field with combined autocomplete and join nudge ([1ed0f98](https://github.com/Garulf/sc-discord-bot/commit/1ed0f98b3d4d277eb25c824f704bce65f27d56d8))
* **beacons:** stats command with responder leaderboard ([7075e94](https://github.com/Garulf/sc-discord-bot/commit/7075e94bf6badab091bd3f8ec46dd6f428959fbf))
* **beacons:** weekly digest and milestone docs ([94a278b](https://github.com/Garulf/sc-discord-bot/commit/94a278bd50cf0559f01ab40e12d8a821a9564126))
* **devtracker:** add /devtracker post command for on-demand latest entry ([c9fee94](https://github.com/Garulf/sc-discord-bot/commit/c9fee943583f57df9bed68ead1e01f3760867deb))
* **devtracker:** add /devtracker subscribe, unsubscribe, and list commands ([2bafe4a](https://github.com/Garulf/sc-discord-bot/commit/2bafe4af0ce33bfba44dff03faf2bec9c9fbda22))
* **devtracker:** add DevTrackerClient for the getTrackedPosts API ([3e4e704](https://github.com/Garulf/sc-discord-bot/commit/3e4e70433cce7d58eb170c66d9cfa814ec290aa0))
* **devtracker:** parse RSI devtracker HTML into DevPost records ([320839d](https://github.com/Garulf/sc-discord-bot/commit/320839d8d8faa881599d08e46470ef7b56aa00ac))
* **hangar:** add /hangar sync and /hangar global sync commands ([458cedb](https://github.com/Garulf/sc-discord-bot/commit/458cedb00fc3d356dbdbad62ad2fac165619ea52))
* **hangar:** post state-change notifications to subscribed channels ([#24](https://github.com/Garulf/sc-discord-bot/issues/24)) ([e9bfb60](https://github.com/Garulf/sc-discord-bot/commit/e9bfb60b31d38e45ed39a1608280272c237a0af8))
* **hangar:** state-change event notifications with Discord relative timestamps ([#25](https://github.com/Garulf/sc-discord-bot/issues/25)) ([bdda565](https://github.com/Garulf/sc-discord-bot/commit/bdda565e5f50f0144a55b74411a2854afa2f37c1))
* **inventory:** add Transfer Cards user context menu with modal input ([#20](https://github.com/Garulf/sc-discord-bot/issues/20)) ([c71512c](https://github.com/Garulf/sc-discord-bot/commit/c71512c27222bde4d8004d8b4b45daaa7f678aae))
* **inventory:** add transfer notifications to subscribed channels ([#21](https://github.com/Garulf/sc-discord-bot/issues/21)) ([9782603](https://github.com/Garulf/sc-discord-bot/commit/9782603ec5b373dd0ff3a9a195d4ce718ceccfcc))
* **inventory:** cap notifications at 5 per channel, bump older ones to 1hr expiry ([2171592](https://github.com/Garulf/sc-discord-bot/commit/2171592d4264ad28bd2529b26bcf42782eef62b8))
* **inventory:** cap notifications at 5 per channel, expire bumped ones after 1hr ([#22](https://github.com/Garulf/sc-discord-bot/issues/22)) ([2171592](https://github.com/Garulf/sc-discord-bot/commit/2171592d4264ad28bd2529b26bcf42782eef62b8))
* **stream:** add live stream notifications for Twitch, YouTube, TikTok ([85a5e19](https://github.com/Garulf/sc-discord-bot/commit/85a5e19052933d4a8d6162194e02b888c512034d))
* **stream:** keep live notification after stream ends ([a11d666](https://github.com/Garulf/sc-discord-bot/commit/a11d66645a873706c9bf77acc12aaa0327efe47f))
* **stream:** send URL as message content for native Discord video embed ([04ce358](https://github.com/Garulf/sc-discord-bot/commit/04ce358cc4720df32e06eba8a216f19c94a4d810))
* **tickets:** add /ticket commands, setup, and cog wiring ([cd1a9f3](https://github.com/Garulf/sc-discord-bot/commit/cd1a9f358cbd6dc156d5281b1cb6c584427e5693))
* **tickets:** add lifecycle permission rules ([64a24bd](https://github.com/Garulf/sc-discord-bot/commit/64a24bd2bdcd9f79409ed328690f8562eb495ef0))
* **tickets:** add location parsing and autocomplete ([691c949](https://github.com/Garulf/sc-discord-bot/commit/691c949db243373ffb1f6e434de0f02803757b73))
* **tickets:** add open/claim/unclaim/close lifecycle ([2677841](https://github.com/Garulf/sc-discord-bot/commit/267784162f4063c351eb677d9d0a33e4949d1443))
* **tickets:** add panel and ticket embeds ([a8e62a3](https://github.com/Garulf/sc-discord-bot/commit/a8e62a3d5e802d92ed0b0be6864eb7fc004a4842))
* **tickets:** add persistent panel and ticket views ([2a7ada8](https://github.com/Garulf/sc-discord-bot/commit/2a7ada89a1e772473cb20b11a381fd12ad7d2055))
* **tickets:** add ticket category definitions ([ecb328b](https://github.com/Garulf/sc-discord-bot/commit/ecb328b970f0df7a3e67d90a56cd650bb4e19952))
* **tickets:** add ticket state storage ([88a24d2](https://github.com/Garulf/sc-discord-bot/commit/88a24d22b29e1ada4233ba97c00f116d7a411d49))
* **tickets:** open category modals from panel buttons ([1aa63b5](https://github.com/Garulf/sc-discord-bot/commit/1aa63b5416ea10b9e687352f099225b21639810f))
* **tickets:** split location into cascading system, planet, and location options ([931a703](https://github.com/Garulf/sc-discord-bot/commit/931a70345ff900d23545452bcb7b86f035a7413c))
* **twisc:** add /twisc subscribe, unsubscribe, list, and post commands ([d12ffb1](https://github.com/Garulf/sc-discord-bot/commit/d12ffb13c4f27fac153db8a30bd00944487521db))
* **twisc:** add weekly schedule parser ([3049171](https://github.com/Garulf/sc-discord-bot/commit/30491718735f491211e9f4deff6539589db740a0))
* **twisc:** build schedule embed from parsed days ([90c964d](https://github.com/Garulf/sc-discord-bot/commit/90c964dfa51ee8547a18fdd3862643003966d867))


### Bug Fixes

* **beacons:** apply review fixes for migration safety and config drift ([42d9684](https://github.com/Garulf/sc-discord-bot/commit/42d96841f724851555ebae207e499211432ab600))
* **beacons:** close before archive, best-effort sends, locked activity tracking ([5d865a4](https://github.com/Garulf/sc-discord-bot/commit/5d865a4b0228fa54f9454ec314f5ef0ca6e39051))
* **beacons:** honor sc-bot role in can_schedule admin bypass ([a670e67](https://github.com/Garulf/sc-discord-bot/commit/a670e67ae5e1ede23add678dfefbf22f20479057))
* **beacons:** lock and re-read scheduled-beacon records in the sweep, refresh board on fire ([498b720](https://github.com/Garulf/sc-discord-bot/commit/498b72035dd065254ef490a3e82967b5ec0c0d30))
* **beacons:** lock maintenance writes and recover archived beacon threads ([0b2c17f](https://github.com/Garulf/sc-discord-bot/commit/0b2c17f770783d11ec739d597211cc6b5912c018))
* **beacons:** read sibling autocomplete options from the raw payload ([6776dfa](https://github.com/Garulf/sc-discord-bot/commit/6776dfa42b91fe9f409a7ab01af0f061c868196a))
* **beacons:** resolve final review findings for milestone 2 ([851d702](https://github.com/Garulf/sc-discord-bot/commit/851d7028a2bee5bceb8be8871f4c03e776441955))
* **devtracker:** dedupe by seen-id set, fix nested-anchor and payload-shape bugs ([fef423f](https://github.com/Garulf/sc-discord-bot/commit/fef423f641d94619df6caa1bffe48c65270d90ed))
* **devtracker:** keep collecting text field data across nested inline elements ([d221e88](https://github.com/Garulf/sc-discord-bot/commit/d221e881a8a75d7cff1b441402336f4bb106b751))
* **hangar:** reset notify_state and refresh immediately on /hangar set ([cad2efb](https://github.com/Garulf/sc-discord-bot/commit/cad2efbe9371f49c1552f201a7d52a612295583d))
* **inventory:** only expire notifications bumped past the 5-per-channel limit ([#23](https://github.com/Garulf/sc-discord-bot/issues/23)) ([f3c1901](https://github.com/Garulf/sc-discord-bot/commit/f3c1901032db663056ac2f93c6c2166370805f3b))
* **inventory:** refresh live status after admin add/remove ([abf3cef](https://github.com/Garulf/sc-discord-bot/commit/abf3ceffdae741b174be30c354a4553d5a4c0b88))
* **inventory:** remove duplicate startup refresh from before_loop hook ([b8897bc](https://github.com/Garulf/sc-discord-bot/commit/b8897bc97cb8a67833750a11128ec6c5b0dcea9b))
* **lint:** sort imports and format bot.py ([c0cf5b1](https://github.com/Garulf/sc-discord-bot/commit/c0cf5b1ab492dba58ca517d7c38148db75963459))
* **mine:** limit locations to 5 per system ([7574a1d](https://github.com/Garulf/sc-discord-bot/commit/7574a1d8a705407da50488cb0c015e22fa10db5c))
* repair gitignore entry corrupted by missing trailing newline ([9203f58](https://github.com/Garulf/sc-discord-bot/commit/9203f58e3a5f233d4eb9c4f4166b699de258c93b))
* **scripts:** always rebuild in run.sh, log instead of exit on git pull failure ([6191f49](https://github.com/Garulf/sc-discord-bot/commit/6191f495512f6bfbd7f83eb9a6d6c1f0fa97e0b3))
* **scripts:** always rebuild in run.sh, log instead of exit on git pull failure ([aa2f6a9](https://github.com/Garulf/sc-discord-bot/commit/aa2f6a99acef973e0e489b137766e702de1df59c))
* **stream:** detect spontaneous YouTube live streams via /live page scrape ([ee8dbdf](https://github.com/Garulf/sc-discord-bot/commit/ee8dbdf1f832a81bbb4538360a048da006808131))
* **stream:** fix unsubscribe matching and display name backfill ([a99bc32](https://github.com/Garulf/sc-discord-bot/commit/a99bc32683c7c0df033b9aa5ad8ad429debebfdc))
* **stream:** skip YouTube API for channel ID input, fix quota errors ([f19e6e7](https://github.com/Garulf/sc-discord-bot/commit/f19e6e7743bac493e28c519e5d8b3cea50416d23))
* **stream:** stop quota spam, limit YouTube RSS checks to 3 most recent ([12211cb](https://github.com/Garulf/sc-discord-bot/commit/12211cb2f54e6d6a660ff5bfd4a54668c0c38758))
* **stream:** use liveBroadcastContent instead of concurrentViewers for live detection ([f636bdf](https://github.com/Garulf/sc-discord-bot/commit/f636bdfcce8909f1b86d35649315c34f37d9e9f1))
* **tickets:** defer interactions and lock ticket state mutations ([8b013dc](https://github.com/Garulf/sc-discord-bot/commit/8b013dcab523886ab11518e4c5ebbdc973ec14dc))
* **tickets:** guild-scope the ticket command group ([b5d57e2](https://github.com/Garulf/sc-discord-bot/commit/b5d57e2e8b806e685174cc45eff8476df307c669))
* **tickets:** prevent None user_id from gaining close permission ([566265f](https://github.com/Garulf/sc-discord-bot/commit/566265fa32968f618a87f99d9cb3d23b52dbc520))
* **tickets:** resolve forum setup gaps found in review ([837162c](https://github.com/Garulf/sc-discord-bot/commit/837162cba3a2f47ee3429cff8c31773c3fd54876))
* **tickets:** stop mutating shared ticket view and defer config writes ([59c174a](https://github.com/Garulf/sc-discord-bot/commit/59c174a17cc5683738e64099d3a0e01c577b1668))
* **twisc:** restore structural sign-off rule, drop lookahead regression ([86cc7d6](https://github.com/Garulf/sc-discord-bot/commit/86cc7d6e97e465cb204ad2d765a918dddf08124d))
* **twisc:** stop schedule parsing before two-paragraph sign-off ([2f2aca3](https://github.com/Garulf/sc-discord-bot/commit/2f2aca3ca8ba8fda67a64f09203ff7dfe386047a))
* **twisc:** support year-less day headings and harden poll loop ([1707b8d](https://github.com/Garulf/sc-discord-bot/commit/1707b8dc33974933742dfebd7c885e973aec10a3))


### Documentation

* **beacons:** add scheduled beacons design spec ([991d896](https://github.com/Garulf/sc-discord-bot/commit/991d896a3aaef1f1b4d882acdeff7f192817066c))
* **beacons:** add scheduled beacons implementation plan ([e2d6ce0](https://github.com/Garulf/sc-discord-bot/commit/e2d6ce0a7f020635522b7d8625dff21549638d23))
* document the /ticket assistance ticket system ([1adf28b](https://github.com/Garulf/sc-discord-bot/commit/1adf28b10f8059c2358f4db5ecb26ebb6a21d9f5))
* fix ticket thread visibility and autocomplete wording ([2a5f88d](https://github.com/Garulf/sc-discord-bot/commit/2a5f88d90d0f30611fc6d9e430bc804f9fd20a67))
* update README with full command guide ([c13d604](https://github.com/Garulf/sc-discord-bot/commit/c13d6040a0eaac7e85abe5034324c4356c6d6327))

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
