# Expansion 6 – Adventures & Events (XL, eleven parts) – Anton's name

*Icon*: an open book whose pages become a road winding up to a dark tower under a red moon. *Tagline*: "Every road a
story. Every story an ending." Branch `dlc/06-adventures-events`; pack `data/packs/06_adventures_events/`; each part
goes to `main` when it meets §5.2 of `docs/EXPANSIONS.md`; the icon and version 1.6.0 come with Part K.

**The design is `docs/ADVENTURES.md`** (Anton asked for this expansion on 2026-10-22, before Tieflings & Warlocks:
"the core gameplay loop is extremely tedious... we need to make this game a dopamine machine"; and widened it on
2026-10-24: quests "rarer... each and every quest being meaningful", "extremely varied, to the point where they barely
have any types at all", and "show don't tell"). Read its §0–§4 once, then the sections each part names. This expansion
is the game's own design more than the books'; it draws on the DMG 2024 (pages 109–146: creating adventures and
campaigns; 84–85 marks of prestige; 96 renown; 98 settlement calamities) and, for structures only, on Ravenloft: The
Horrors Within, Curse of Strahd and the solo-play books in `C:\Users\Alpine\Desktop\dndnstuff` – never their prose.
Because it is a design expansion, this note is longer than §5.0's one page (A.0 records the exception).

## What Anton will see

The world's dangers become **threats** with villains from the world's own history and schemes that move week by week,
with signs on the roads and in the news; ignore one and it wins, and the map changes. Take one on and the game builds
an **adventure**: chapters that send you to new places, a patron, an ally with a stake, a rival after the same prize,
the villain's lieutenants, hidden truths to find (where the relic lies, what the villain fears, who is lying), and a
**finale**: a big, fair fight against a boss you have heard of for hours, made winnable by everything you found. The
villain **notices you** – letters at dawn, tests in the night, invitations to dinner, bargains, revenge on the people
who helped you. A **Storyteller** makes something worth telling happen every day or two of travel, always for a
reason: villains' moves, allies seeking you, the bandit you spared coming back, a coronation with a tournament.
Every ending changes the world (a town freed or emptied, a cult destroyed, a ruler crowned, a statue, a song, a page
in the Legends book) and ends with *What became of them*. You grow in **Legend**: an epithet you choose, lords and
kings who send for you, titles and land, songs. You choose an **Ambition** at creation, woven through your adventures,
and when it is fulfilled you may end your tale and stay in the world as a figure your next character can meet.

The weekly job board is gone. **Quests are situations**: something gone wrong in a real person's life (a son run off
to the gang, an innocent in the stocks, a debt come due), met in the street, assembled from the world so that no two
are alike, rare (one at a time in a town), each with a decision, a way through without blood and an ending you can
see later; many lead into adventures. Contracts and bounties pay the bills. And **you see it happen**: a boy runs up
with a letter in its writer's hand, a crowd gathers under the gibbet, a burned town stays burned (with its dead, its
blood, its new graves and, in a season, its scaffolds), whole towns burn round you in the last chapters, and the world
map shows smoke, sieges, marching hosts and – once in a life – a wound torn across the land by a god, with a
crusaders' camp-city at its edge.

Part by part: **A** one whole adventure (the hunt for a named beast of the history) from its hook to its epilogue;
**B** show, don't tell: scenes on the map, letters and title cards, places that keep what happened to them, the dead
and the blood left by fights, fire; **C** quests reborn: the job board retired, situations from people's lives,
contracts and bounties, favours and contacts; **D** the risen dead king, the outlaw lord, and an opening tale for
every new life; **E** villains who answer you and finales in full; **F** allies, rivals, traitors and the card
reading; **G** the world changes (consequences in full, the land itself, hosts on the roads, new places founded);
**H** battles through a burning town; **I** the Storyteller and the world's events (echoes, coronations, tournaments,
sieges); **J** Legend and ambitions; **K** the rest of the tales, cataclysms, and the release.

## Decisions (details in docs/ADVENTURES.md)

- **Two layers**: threats live in the world (`world.politics["threats"]`, advanced inside `Politics.advance`, so they
  move in the interlude too – at most one stage each); adventures and situations are world-side records as well
  (`world.politics["adventures"]`, `["situations"]`), so a dead hero's story stays in the world for the next. Legend
  lives on the character (`Renown.legend`).
- **A threat's tier comes from its region** (DESIGN.md §6), and its finale is measured for the tier's target level;
  the Storyteller offers threats that fit you first.
- **The world fights back too**: threats also end without the player, dooms are bounded and recoverable, and only two
  untaken threats stir near the hero at once (ADVENTURES.md §5.1).
- **Adventures are forged when a hook is accepted**; an offer is a light record on the threat. At most three at once.
- **Steps reuse the quest machinery** where they can (a step quest is an ordinary quest dict with `adventure` and
  `step`, the patron as giver, a long deadline, no pay of its own); step kinds are a registry of small handlers with a
  `repair`, so nothing is ever stuck. Each part builds the step kinds, beat conditions and ops its content uses.
- **The weekly job offers are retired** (Part C): a quest is a situation, a chapter or a commission; paid work is
  contracts and bounties; the seventeen templates stay as machinery. Situations are assembled from predicaments,
  roles bound to real people, obstacles with ways through, turns and meetings, and their goals are conditions on the
  world, so however the player makes them true, the game recognises it (ADVENTURES.md §5.15–5.16, §8.10).
- **Show, don't tell** is law 11 (ADVENTURES.md §5.17): scenes are played on the map by real townsfolk; places carry
  marks that change their close-up maps and their signs on the world map, and age; the dead and blood of fights are
  written back to the map through `Field.origin`; buildings are marked, never removed; the land itself changes only
  through a ledger that autoplay replays; new places are only ever appended to the world's lists. Figures keep their
  one pose.
- **Bosses and story things are bound to their exact dungeon level when the adventure is forged**
  (`politics["story_sites"]`, keyed by the level's dungeon key), because a level is populated once; the story's hook
  in `populate` runs last and wins. Story creatures carry a `story` tag; `past.on_battle` skips them.
- **Bosses come from creatures the game has**, made bosses by data templates (hit points, Legendary Resistances,
  legendary actions, a second phase) until later expansions bring the Monster Manual's legendary families. So do
  attackers: assaults and the rift's hordes use the dead, raiders, orcs, goblins, gnolls and dragons the game has,
  and demon bands come with Tieflings & Warlocks, the next expansion, as more data.
- **The eleven laws** (ADVENTURES.md §3) are the review checklist for all story content; the content rule (every
  chapter has a step that is not a fight and a choice with a lasting consequence) and the six rules of a quest that
  matters (§5.15) are enforced by `storybook --check`.
- **Saves**: every part that changes what a save holds bumps `FORMAT_VERSION` (19 with Part A) and says that a new
  world is needed. Story records are JSON-native, and a test checks it.
- **The programme is renumbered**: Adventures & Events is 6; Tieflings & Warlocks becomes 7 and so on; Planes &
  Portals (27) stays version 2.0.0. Every expansion's design note now answers *What stories does it tell?* and *What
  does it show?*
- **Words are written in batches by helpers** (two or three at once, on a cheaper model, each with a precise brief and
  finished examples), joined and reviewed by the main session; every family has floors (ADVENTURES.md §9). **Pictures**
  are DCSS picks first and code-drawn the rest, reviewed on `tools/showcase.py`'s contact sheets.

## Parts and tasks

Each task lists its files and its tests. Do them in order; tasks marked *(parallel)* may go to helpers.

### Part A – The story engine, and one whole adventure: the Beast
*Done when*: in a new world, a new character is offered a beast's hook on the first day, and can play The Beast of
{place} from its hook through three chapters, its finale and its epilogue; the beast's figure dies in the history,
the region is safer, the news says so, and an epithet is offered. ADVENTURES.md §5.1–5.3, §5.8–5.9 (first forms),
§5.14, §6.2 (the Beast), §8.1–8.9.

- [x] A.0 **The programme.** Insert §6.6 *Adventures & Events* into `docs/EXPANSIONS.md` (the first three sections of
  this note; the table row `6 | Adventures & Events | threats, adventures, situations, villains who act, places that
  change, the Storyteller, Legend, ambitions | 5 | XL`); renumber the old 6–26 to 7–27 everywhere ADVENTURES.md §10
  lists (§6 and its table with the Needs column, the appendices, §4.1's `pack.json` example, §5.5's STATUS template,
  `CLAUDE.md`, `STATUS.md`; the dated entries of `PROGRESS.md` and old design notes stay as written, with a dated line
  at the top of PROGRESS.md); the version rule (Expansion N is 1.N.0, the last is 2.0.0); add "What stories does it
  tell? What does it show?" to §5.2's definition of done; note in §5.0 that design expansions may have a longer note.
  Codex: a one-off script in `tools/codex/` moves `dlc` and `upgrade_in` 6–26 to 7–27 and assigns the DMG's renown,
  marks of prestige and settlement calamities to 6; the codex README's range; `tests/test_codex.py` green. Rename the
  map key screen's title to *Map key* (`ui/screens/legend.py`), so that "Legend" means one thing.
  `docs/expansions/STATUS.md`: "Current: 06 Adventures & Events · Part A". Branch `dlc/06-adventures-events`;
  `data/packs/06_adventures_events/pack.json` (status planned, order 6). Commit the two design files with it.
- [x] A.1 **Deeds that stick** (ADVENTURES.md §5.14). A gang hideout's boss is the gang's real leader, named
  (`past.boss_for`); killing them goes through `Politics.die(fig, cause, led=gang)` (the succession runs), and with
  the hideout cleared too the gang falls (`Politics.fall`, news). A cult temple's boss is its leader figure (the
  Voice); clearing it ends the cult. `hunt_beast` and beast bounties prefer a living beast of `lairs` within reach
  over the fixed list. `news.prune` and plague exposure leave the `if self.quests:` block of `pass_time`;
  `uniques.daily` runs without companions; `dragons.mark_slain` writes through `history.remember`. Tests:
  `tests/test_quests.py`, `tests/test_past.py`; autoplay's `_check_factions` stays green (no active gang led by the
  dead).
- [x] A.2 **Data kinds.** `threats.json`, `adventures.json`, `villains.json`, `beats.json` (+ fragments): schemas in
  `realmwalker/data/schemas.py` (`DATA_FILES`, `PACK_ONLY`), `Tables` attributes (`world/tables.py`), cross-references
  (`registry.check_cross_references`), and `realmwalker/game/story/check.py` (unknown step kinds, selectors – the
  grammar of ADVENTURES.md §8.5 –, condition keys, ops and finale keys on the data-problems screen, as
  `engine/check.problems` does). Tests: `tests/test_story_data.py`.
- [x] A.3 **Threats** (`realmwalker/world/threats.py`) for the *beast* kind: `seed` after the ages; the record (§8.3);
  `advance` from `Politics.advance` (stages, signs through `world/news.add` at importance ≤2, stage effects, a bounded
  doom: the `emptied` status with a floor of survivors and the `rebuilding` return); the world's own ending (the
  history's beast-hunters keep hunting: a weekly chance by fame); `seed_from` from `beast_comes`; the budget and the
  cap of two untaken threats near the hero; one stage at most per interlude. Tests: `tests/test_threats.py` (same seed
  same threats; seeded on the cached test worlds; an ignored threat reaches its doom and the world stays consistent –
  owners replay from the ledger, no settlement at 0); autoplay `_check_threats`.
- [x] A.4 **The forge** (`game/story/forge.py`, `selectors.py`, `cast.py`, `steps.py`): places, then cast (from the
  world first; made people kept in `story_people` and placed when their town is next populated), hidden variables,
  chapters and steps, three routes per truth, the content rule, scaling to the tier's target level, `story_sites` by
  dungeon key; the Part A step kinds go, search, witness, read, learn, prepare, choose, slay, finale, each with
  `repair`; `story.boss_for` in `dungeon.populate` after `quests.boss_for`, with precedence, returning the full band;
  the `story` tag on spawned creatures (saved with actors); `past.on_battle` skips story creatures; `flags["story"]`
  respected by `people.refresh_travellers` and `quests.daily`. Tests: `tests/test_forge.py` (slow: forge seeds on the
  cached worlds; every role bound, every place reachable, every truth with three routes, record equality per seed).
- [x] A.5 **The Beast** (first form, ADVENTURES.md §6.2) with all its words *(parallel: the main session writes the
  blueprint and one finished example of each word family; helpers write the rest)*: its scheme and signs, its chapter
  openings and reveals, its `choose` (bait or track) and the codeword it leaves; `tools/storybook.py` with `--check`.
  Tests: floors in `tests/test_text_variety.py`; `storybook --check` on three seeds (`tests/test_storybook.py`).
- [x] A.6 **Hooks, Part A set** (ADVENTURES.md §8.4): `story.daily` (catch-up stamp), `on_travel` (a simple director:
  due and scheduled beats, a target quiet gap, at most one villain move in two days), `on_arrive`, `on_enter_town`,
  `on_night` (camp and inn), `on_descend`, `on_chest`/`on_feature`/`on_search`, `on_battle` (outside `if game.quests:`),
  `on_quest_end`, `on_read`, `on_legends_page`, adventure answers in `divining.questions`; dialogue `story.talk_choices`
  and `STORY_CHOICES` (witnesses, sages, the patron's briefing and reward); map marks; the journal's Adventures tab
  (and step quests left out of Work); notice boards hooking every stirring threat within a week's walk; the beast's
  bounty on the board as its hook (and, until Part C retires the offers, a hunt-beast job whose beast belongs to a
  threat opens its hook when done); the cap of three adventures; a minimal `story.on_death` (orphan the hero's
  adventures, clear the pending beat) and `story.begin` (reset the director; offer a fitting hook near the start town).
  Tests: `tests/test_story_hooks.py` (each listener moves its step in a real game state).
- [x] A.7 **The beat screen and the first beats**: `ui/screens/beat.py` (pages, numbered choices with checks and costs,
  results, chapter title cards; `autoplay_keys`); `game.beat` in `GameState.busy` and in
  `GameScreen._open_event_screen` after the level-up branch; the pending beat in `politics["director"]`; conditions
  where, time, adventure, attention, `villain.*`, flag, cooldown, once; ops: all of `events.apply_outcome` plus clue,
  key, flag, step_done, attention, clock, schedule, named_fight, item, companions; checks through
  `Conversation.check` with a speaker, `camp.check` without. **Minimal attention**: +1 a step done, +2 a lieutenant
  slain, −1 a fortnight, and one villain reaction per chapter: for the beast an omen, a carcass left at your camp,
  a test by night. Tests: `tests/test_beats.py`; `tests/test_graphics_ui.py` draws the screen.
- [x] A.8 **The finale, first form**: boss templates for tiers 1–2 (`villains.json`); keys `no_legendary_resistance`,
  `vulnerable`, `frightened`, `ally_fights`, `minions`, `surprise`, applied by `story.finale.prepare` from
  `fight.start_battle`; the second phase at half hit points (a kernel handler); the pending finale card (`game.finale`,
  set in `GameState._move_local` and `_creatures_act` before the battle starts; `ui/screens/finale.py`, "Fight" / "Not
  yet"; story boss actors never hunt); legendary actions and resistances in a real fight, used well by
  `rules/tactics.py`; boss templates in `tools/arena.py`'s scenarios (arena coverage green). Tests:
  `tests/test_finale.py`.
- [x] A.9 **Endings, first form**: the ordered ending list with its default (ADVENTURES.md §8.6); the consequence ops
  the Beast needs (`beast_slain`, `clear_site`, `danger`, `fame`, `history`, `news`, `emptied`, `sequel`,
  `threat_free`); `ui/screens/epilogue.py`; the epithet offer kept in `Renown.legend`. Tests: `tests/test_endings.py`
  (every Beast ending on a test world leaves it consistent).
- [x] A.10 **Pictures and sounds of Part A** (`tools/tile_art.py`, `tools/build_sounds.py`): map marks (a story place,
  a sign), the title-card frame, a camp-at-night beat backdrop; sounds `chapter`, `reveal`, `sign`; the music mood
  `story/omen` in `data/music.json` (falling back to an existing mood until the player adds tunes); contact sheet
  looked at; `tests/test_audio.py` green.
- [x] A.11 **Save and the bot**: `Renown.legend` in `to_dict` and its loader, the `story` tag on actors, FORMAT_VERSION
  19; the JSON-native and round-trip test; autoplay's `_check_adventures` and the bot's story moves (take hooks,
  follow steps, answer beats, fight finales); `tools/storyplay.py` (basic). Measures: the Beast finishes in at least
  90% of 20 storyplay runs; a hook is offered on the first game day (`tests/test_first_hour.py`).
- [x] A.12 **Verify** (§5.2; the smoke test shows the beat screen, the Adventures tab, the finale card and the
  epilogue); the fresh reviewer reads ten storybook synopses against the eleven laws and plays one adventure in
  storyplay's log; Part A to `main`.

### Part B – Show, don't tell: the stage, pictures, places that change
*Done when*: in a new world, a town burned by the politics engine looks burned the first time you enter it, and its
smoke rises on the world map; a besieged town is ringed with tents there; a fight in a street leaves its dead and its
blood where they fell, and the town buries its own; a runner can run up to you with a letter that opens as a page in
its writer's hand; the Beast's chapters open on title cards over pictures; a burning street burns, on the map and on
the battle mat. ADVENTURES.md §5.17–5.19, §5.21 (signs), §8.11–8.14, §8.16 (signs), §8.17–8.18.

- [x] B.1 **The stage** (`game/story/stage.py`, `scenes.json`; ADVENTURES.md §8.11): the scene record in
  `politics["director"]`; the cues of §5.18; errands (`npc.flags["errand"]`, read first in `townlife.goal`; runners
  two steps a tick), openers (`Conversation.greet`), gatherings (`Town.flags["gathering"]`), story words whatever the
  Text detail (`townlife.speak`), the hand-over drawn between two figures, the camera's focus (LocalView), arrivals
  with `flags["placed"]`. Driving: `townlife.tick` calls `stage.tick` and `townlife.settle` calls `stage.settle`
  (never both `town_tick` and `_people_act`, which already call each other); a holding scene sets `game.held`
  (moves wait, Space or Escape skips) and leaves `busy` alone, so the town clock keeps running, and `time_flows` is
  true while a scene holds even when "Time in towns" waits; `animations` copied onto `game` as `verbosity` is, with
  "off" completing movement cues at once; a save in the middle of a scene skips it to its end on load; outside towns
  scenes advance on the player's steps, and at a road camp the camp screen plays them in its picture. Tests:
  `tests/test_stage.py` (every cue on a town of each people; a runner reaches you through a crowded street; the town
  clock runs while a scene holds; the townlife 30 ms test with a scene of twenty actors; never two people on one
  square).
- [x] B.2 **Pictures for stories** (ADVENTURES.md §8.12): `ui/gfx/vignette.py` (the fourteen backdrops, figures from
  the real people, props, light, atmospheres); a picture panel on the beat screen and the event screen (a `picture`
  key in beats and in `travel_events.json`); `ui/screens/titlecard.py` (the Beast's chapters open with it);
  `ui/screens/letter.py` (one or two OFL handwriting faces in `assets/fonts` and `typefaces.py`, parchment, seals,
  letters as items with a `letter:<id>` tag whose page opens again from the inventory); the held letter layer
  (`tools/figure_gear.py`); the boss entrance on the battle mat. Tests: `tests/test_graphics_ui.py` draws them all.
- [x] B.3 **Marks** (`world/marks.py`, `marks.json`; ADVENTURES.md §8.13): today's statuses become marks (siege,
  sacked, burned, plague, famine, raided, tribute, beast) and the first new ones (burning, rebuilding, emptied, beset,
  memorial, festival); every place that writes a status writes it through `marks.add`; `siege` stays a war's own
  (autoplay's check), `beset` for a ring with no war behind it; aging in `Politics.expire_status` (burned → rebuilding
  → gone); their words in `describe.settlement_line`, `settlement_troubles`, `people.town_moment` and
  `Town.description` (beast and tribute too). Tests: `tests/test_place_marks.py` (`tests/test_marks.py` already
  tests the marks spells leave on creatures): each Politics path writes its mark; marks age by the clock; old
  day-number values still read.
- [x] B.4 **Stamping** (`game/placemarks.py`): marks dressed on close-up maps in `enter_local` right after
  `get_local_map` (before bands and people are placed) and in `people.prepare_town` between the map and its people,
  and again when a mark changes while you are there (people and bands step off changed cells first); the cells each
  mark changed recorded with their old ids in `lm.meta["marks"]` (the Passwall pattern); building looks (roofless
  shells; charred walls: a `charred` palette in `roofs.WALLS` and in houses'), scatter, lights, and the people's
  changes (mourning dress, shut trades, a bread queue); restore and re-stamp as marks age; afterwards
  `lm._building_grid` reset, `townlife.forget()`, posts and homes moved out of blocked cells; no trade in a burnt
  shell (`economy.shop_spec`, `services`). Tests: every mark stamped on a test town of every people keeps
  `check_works` (`tests/test_towns.py`'s rules); stamping then restoring gives back the original terrain exactly.
- [x] B.5 **The fallen, blood and graves** (`game/remains.py`): `lm.meta["bodies"]` (who they were, never doll
  parts: LocalView composes the figure), `["decals"]` and `["graves"]`; LocalView's decal layer and the fallen drawn as
  turned, darkened dolls with a pool of blood; the write-back in `fight.finish_battle` through `Field.origin`
  (`Battle.blood` filled where slashing and piercing damage lands); the party stands where its leader stood when the
  fight ended; the town carries its dead off after a day (a scene if you are there) and gives each of its own a fresh
  grave; in the wild, crows and then bones; the unused DCSS blood picked in `build_tiles.py`. Tests:
  `tests/test_remains.py` (a street fight's dead lie on the right squares; graves appear; the caps hold).
- [x] B.6 **Eavesdropping, tailing and tracks** (on B.1 and B.5's decals): the scenes `overhear` and `follow` (a
  `look_back` DC against the party's Stealth, the law's sneaking rules), track decals to the map's edge and the next
  square lit on the world map.
- [x] B.7 **Fire** (`game/fire.py`; ADVENTURES.md §8.14): live fire as an overlay (`lm.meta["fire"]` =
  `{"x,y": [stage, ticks]}`, never a Python set) with one mask that townlife's walk grid (cell by cell, dropping only
  the paths that cross a newly burning cell), `move_actors` and the player's moves respect; cells lit only when nobody
  stands on them; burn-outs written to terrain in batches and patched cell by cell (`LocalArt.patch`); the new
  terrains (embers, scorched, charred floor and wall, fallen beam, broken door, barricade, gallows, pyre, scaffold,
  fresh grave, ritual circle, cage) with their pictures; `townlife.tick` calls `fire.tick`, `townlife.settle` and
  leaving call `fire.settle`; fire spreads only on town maps; flames, smoke columns and glow over burning roofs
  (`_roofs`); fire light by day; frames for the ground and over layers (the survey's gap); atmospheres
  (`ui/gfx/atmosfx.py`). In battle: ownerless fire and smoke zones laid after `arena.build`, `Battle.round_hooks` for
  spreading and for walls that fall (telegraphed), houses' materials flammable only on fields marked burning (not by
  widening `grid.FLAMMABLE`, which `Battle._ignite` uses in every fight), `_ignite`'s numbers; the field's fire
  written back. Tests: `tests/test_fire.py` (spread stops at stone and water; nobody ever stands on a burning cell; a
  battle in a burning street burns and writes back; a Fireball in an ordinary inn starts no blaze; under 1 ms a tick
  on a great city); autoplay: nobody on a burning cell.
- [ ] B.8 **Signs on the world map for marks** (`ui/gfx/mapsigns.py` in `WorldView.draw`): smoke over burning, burned
  and sacked towns; a ring of tents round a besieged or beset one; the black flag of plague; a dragon's shadow over
  tribute; festival lanterns; memorial marks. Tests: drawn headless; under 2 ms a frame.
- [ ] B.9 **The Beast, shown** *(parallel words)*: its scenes (the survivor's account told at the kill site with a
  crowd round; the carcass at your camp at dawn, in the camp screen's picture; the hunter ally's runner), title cards
  for its chapters, its doom stage as a mark (a burned farmstead), vignettes on its epilogue pages;
  `tools/showcase.py` (first form) and the debug console's `showcase`, `mark` and `scene`; frame timing
  (`tests/test_frame_time.py`); FORMAT_VERSION +1; verify (the smoke tour shows a burned town, a title card and a
  letter; Anton looks at the showcase sheet); Part B to `main`.

### Part C – Quests reborn: situations, lives and honest work
*Done when*: the weekly job board is gone; the towns near the hero carry lives; every ten to twenty days a town within
reach shows a new situation – met in a scene, assembled from its people's troubles and the world's threats, with
ways through that the game recognises however they are done and endings that leave something to see; contracts and
bounties pay as jobs did; favours and contacts are kept and used; `storybook` prints situations, and the variety,
rarity and income measures pass. ADVENTURES.md §5.15–5.16, §6.7–6.11, §7, §8.10.

- [ ] C.1 **The reference** (before anything changes): the income of storyplay's careful player over thirty days on
  the build before Part C (the same player the income measure uses later), kept in `tests/data/income_ref.json`.
- [ ] C.2 **The end of the weekly offers**: `quests.offer_for` rolls no more offers; `offers_in` and
  `GameScreen._think_of_work` go; "Is there any work?" goes; people with a contract, a commission or a role in a
  situation have their own choice. **The builders are split** into a picker (today's choice of target) and
  `make(game, giver, target, rng)`, so that situations, contracts and steps give the target; the listeners stay.
  Faction commissions from goals (`work.json`). What leans on the offers moves with them: the bot's work through
  `offer_for` (`tools/autoplay.py`) becomes contracts and situations; rank trials (`quests.mark_trial`) and fence work
  (`shadows.guild_work`) become commissions; the first-day hint (`state.py`), the help (`help.py`) and the journal's
  empty Work tab (`journal.py`) are rewritten. Tests: `tests/test_quests.py` (no offers rolled; every builder's
  `make` builds for a given target), and the tests that look for work today (`test_first_hour.py`, `test_app_ui.py`,
  `test_followers.py`) look for situations and contracts instead.
- [ ] C.3 **Paid work** (`game/story/work.py`): one contract a town (two in a city or a great city), from its trade and
  roads, its faiths and its known raiders, renewed every 14–28 days, each naming a real danger on its way (a threat's
  servants, a gang, a lair's beasts) so it can turn into a situation; built through `make` for `escort`, `deliver` and
  `defend`, paid by `base_quest`; bounties on real gangs, beasts with lairs and threats' servants; the Work tab shows
  terms. The muster and the levy wait for Under the Banner (K.3). Tests: `tests/test_work.py`.
- [ ] C.4 **Lives** (`game/story/lives.py`, `lives.json`): `npc.flags["life"]` made by `lives.ensure` when a town near
  the hero is populated (notables and up to twelve others); ties (kin are names first), wants, fears, secrets (the
  cults' hidden members among them), things of note; `npc.profile` written from the life; weekly life events within
  30 tiles (at most three a town) that show by themselves (mourning at the well, a shop shut with a sign, a new grave,
  a christening crowd). Tests: `tests/test_lives.py`.
- [ ] C.5 **The goal language** (`game/story/goals.py`): the predicates of ADVENTURES.md §8.10 with `all`, `any` and
  `not`, checked at start-up; `goals.notify` from a conversation's end, battles, captives' fates, the law, items
  changing hands, entering and leaving towns and buildings, and the day; ways through recorded by kind. Tests:
  `tests/test_goals.py` (each predicate made true by each way the game has).
- [ ] C.6 **Situations** (`game/story/situations.py`, `situations.json` + fragments): forged only in towns that have
  their people (on entering one, or when its gap has passed), from roots (lives, threats' signs, marks and wars,
  faction goals, the history, the land, companions; happenings and echoes come in Part I), the first twenty
  predicaments of §6.7, roles bound to real people, stakes and clocks, obstacles and their ways (§6.8), a first twelve
  turns (§6.9), meetings always played as scenes (§6.10), endings with the people ops (`npc_fate`, `tie`, `grave`,
  `mark`, `favour`, `contact`, `xp_story`, `shop`, `move`); the world's own outcome when a clock runs out (`lapsed`);
  the rarity rules (one live situation a town, two in a great city, 10–20 days between, at most three live within 30
  tiles of the hero); a story person takes the place of the generated person of their job when a town is populated;
  when the hero dies, live situations drop their quest dicts and go back to `latent`; **Troubles** in the journal's
  Adventures tab, in the hero's own notes. Tests: `tests/test_situations.py`.
- [ ] C.7 **Favours and contacts** (`game/story/favours.py`): favours spent as ways through; contacts who send word by
  runner, deal at night and warn of the law; both in the People tab.
- [ ] C.8 **Experience from stories**: the `xp_story` op by encounter budgets; the *Experience* setting (fights and
  stories, or stories only) in the Settings screen, copied onto `game.experience` as `verbosity` is, and read by
  `fight.finish_battle`.
- [ ] C.9 **Vignettes**: the first twenty hand-made (§6.11) with their scenes *(parallel words)*.
- [ ] C.10 **Situations inside adventures and the proof**: the Beast's witness and hunter steps become situations;
  `storybook` prints situations (§7) and `--check` holds the six rules of §5.15; the variety measure (among thirty met,
  no two share root, predicament, turn and meeting; with Part C's twenty predicaments, twelve different predicaments
  and twelve meetings at least), the rarity
  measure and the income measure (0.7–1.3 times the reference); the likeness score (§9) under its bound; words
  *(parallel; floors of §8.8)*; FORMAT_VERSION +1;
  the fresh reviewer reads thirty situations as a player would; Part C to `main`.

### Part D – The Risen, the Outlaw Lord, and the opening
*Done when*: both blueprints play end to end in their first forms, shown as well as told, and every new life starts
with an opening tale. ADVENTURES.md §5.12 (the first hour), §6.2.
- [ ] D.1 Threat kinds *risen* (from `tombs` and `scars`; the barrow at least two levels deep) and *outlaw lord* (from
  active gangs), with schemes, signs (as marks and scenes where they can be: the emptied hamlet, the dead on the road
  at night), bounded dooms and the world's own endings (politics already hangs gangs).
- [ ] D.2 Step kinds rescue, fetch, defeat, capture (through `story.on_fate` from `fight.decide_captive`), recruit,
  rally, hold (waves as successive battles with no rest, at a settlement or a road tile laid by `game/arena.build`, on
  a set night: the calendar's new moon if it has one, else "in N days"), rite, escort, confront – written on Part C's
  goal predicates where they fit, and able to carry a situation (§8.10); the Part D selectors.
- [ ] D.3 The Risen and the Outlaw Lord, first forms, with all their words *(parallel)*; their scenes (the dead at
  the camp's edge by night; a warning nailed to your door; the inside man followed through the streets at midnight);
  their arenas (the ford at night with burning carts across the road, fire on the field; the hideout); their
  villains' minimal reactions (a letter in an old hand, as a page; a test on the road).
- [ ] D.4 The opening (ADVENTURES.md §5.12): arriving into a crisis (the gate shut and a crowd at the mill), a summons
  (a letter), present terror (waking as the gang's captive), built on the threats near the start town and staged;
  `story.begin` offers it. Tests: `tests/test_first_hour.py`.
- [ ] D.5 Pictures (barrow and hideout backdrops for the vignettes), sounds; floors; storyplay: each blueprint finishes
  in at least 90% of runs; FORMAT_VERSION +1; verify; Part D to `main`.

### Part E – Villains who act; the finale in full
ADVENTURES.md §5.4, §5.5, §5.8.
- [ ] E.1 Attention in full and the whole move set with tempers' weights, spies that steal tokens and tailored next
  moves, wrath after a setback; the limits (one move in two days; beasts never write). Tests: `tests/test_villain.py`.
- [ ] E.2 Visits staged on the map (at camp or inn by night: the fire dims, a figure steps out of the dark; never at
  full strength), letters as pages in the villain's own hand, invitations under safe conduct (op `invite`: no
  encounters on the way) and the dinner beat at the villain's hall (its vignette), bargains and wedges (the dark
  endings wired), reprisals that are seen (a helper on the gibbet in the square: a mark and a crowd; a burned
  farmhouse), frames (`law.commit` with false witnesses), kidnaps (`step_add` a rescue).
- [ ] E.3 Lieutenants who remember: escapes, scars, grudges, promotion, turning; their epilogue lines.
- [ ] E.4 Escapes once per adventure, anchors, returning villains, early ends (contingencies, a lieutenant's
  succession, "the cat is away"); step kind `endure`.
- [ ] E.5 The finale in full: arenas (a burning village with fire that spreads, a ritual circle, a throne hall, a
  bridge, a tower top), phases with lines that change the arena (`Field.set_terrain`: sarcophagi open, a floor
  falls), telegraphed great attacks, boss entrances, boss templates for tiers 3–4, a "command its minions" legendary
  action (a kernel handler), every key of ADVENTURES.md §8.6, the retreat rule, defeat as content
  (`story.on_defeat` in `fight.finish_battle`'s defeat branch: taken alive, an escape chapter).
- [ ] E.6 The fairness measure (`tests/test_story_balance.py`, slow): every key ≥80% wins, no key ≤45%, the retreat
  works; the careful player's deaths measured before and after (`tools/balance.py`).
- [ ] E.7 Words for every move and temper *(parallel; floors of §9)*; pictures (villain silhouettes for the journal,
  the letter's seals, the hall); sounds (`villain`); FORMAT_VERSION +1; verify; Part E to `main`.

### Part F – The cast and the Reading
ADVENTURES.md §5.3, §5.6, §5.7.
- [ ] F.1 Allies with stakes, join conditions (often a situation of their own) and three-beat arcs; the new bond
  `oath` (companions.json); the full party case (`Battle.add_ally`); their fates. Tests: `tests/test_cast.py`.
- [ ] F.2 Rivals: bands with their own clocks (race, theft, ambush, truce, plea, sale to the villain, found dead – a
  scene in the lair) and a relation from −2 to 2.
- [ ] F.3 Patrons' hidden motives (a betrayal at most once in a hero's life), traitors with at least two tells,
  innocents' fates; step kinds `deliver`, `infiltrate`.
- [ ] F.4 The Reading: `reading.json` (the Wayfarer's Deck – twenty great cards and four suits, original names and
  meanings), seers (a people.json job; crossroads camps, hermits at wonders), the reading staged at the seer's fire
  with the cards laid out as a picture, riddles written from the true places' own pasts, silent cards, the villain's
  card; the cards' imagery planted in the world and pointed out; card faces.
- [ ] F.5 Words *(parallel)*, pictures, tests; the blueprints' full forms gain their rivals and traitors;
  FORMAT_VERSION +1; Part F to `main`.

### Part G – The world changes
*Done when*: every ending's consequences are applied and seen; marks run their whole course (a burned town rebuilds
and regrows, a memorial stands); the land itself can change through the ledger and the map repaints; hosts march on
the roads; a camp can be founded and grow. ADVENTURES.md §5.1, §5.9, §5.19, §5.21, §8.13, §8.16.
- [ ] G.1 Full sign sets for every threat kind's stages, as news, scenes, marks and map signs; overlays on road
  encounters (`story.overlay` from `encounters.roll_encounter`), on prices (marks read by `game/economy`) and on the
  land's flavour (only the extra lines behind Text detail).
- [ ] G.2 Waking dormant threats (triggers, the Storyteller's need, chance); `seed_from` from every `Politics` method
  that can make one; threats in the interlude's "what changed"; the world's own endings for every kind.
- [ ] G.3 Every consequence op of ADVENTURES.md §8.6: owners (`Politics.set_owner`), successions, relations, laws,
  emptying and rebuilding, **ruin in full** (designed here: a `ruined` mark, a floor of survivors, the townsfolk's
  fates, the map re-stamped), monuments (a thing on the town map with Look words: the memorial mark), renaming, songs
  (a work by a real bard figure, sung at inns after some weeks), relics, land, rights; the marks' whole course
  (rebuilding with scaffolds, newcomers through `Politics.regrow` and `people.make_npc`, haunted, cursed, occupied); the
  ledger replay stays true.
- [ ] G.4 The epilogue in full, with vignettes of the places as they now are; adventures as named chapters of the
  history in the Legends book; sequel threats.
- [ ] G.5 Rumours, letters and notice boards that lead somewhere (`reveal_hook` repurposed, `reveal_clue` added to
  dialogue's OUTCOMES).
- [ ] G.6 **Land changes** (`world/reshape.py`): the ledger and its records, apply (never under the party's square or
  the map it is on) and undo, the new biomes (`biomes.json`), `game.land_changed()` (`_biome_remap`, `_cost_cache`,
  `_remaps`, the route), the repaint of only what changed (`WorldPainter.refresh(cells)`, `ChunkCache` queuing the
  touched chunks again and restarting its thread, a version per chunk in its key; the old pictures standing in), the
  painter's rift, blight, scorch, drowned land and crater, and `local.patch_land` for maps already built. Tests:
  `tests/test_reshape.py` (the ledger replays; travel and caches follow; a built map takes the change; a weekly blight
  repaints only its chunks; the repaint recorded headless); autoplay `_check_land`.
- [ ] G.7 **Hosts** (`world/hosts.py`): armies marching to their sieges, threats' hordes, crusades; `hosts.advance` by
  its own stamp from `story.daily` and `Politics.advance`; arrival through the war code (`sieges`, `take`) for armies,
  `raid` for a tribe's warband, and the world layer's `hosts.strike` (marks such as `beset`, losses with the floor,
  refugees, news) for hordes, the dead and crusades; encounters near them; `news.faction_place`; drawn by `mapsigns`
  as a column of figures behind a banner, with dust; refugee columns on the roads. Tests:
  `tests/test_hosts.py`; autoplay `_check_hosts`.
- [ ] G.8 A threat's reach washed on the map once known (the `overlays` hook, cached by reach and version).
- [ ] G.9 **Founding** (`world/founding.py`) by the checklist of ADVENTURES.md §8.16; `politics["styles"]` read by
  `plan.style_for` and `worldview.town_mark` (both gaining a `world` argument); the **encampment** layout, built on the
  `camp` layout's method, and the canvas tent form (`ui/gfx/houses.py`); its stages (a camp → a fortified camp → a
  town), each a re-stamp; its world-map composite in `mapsigns`, growing with it; the first use: a refugee camp
  outside a besieged city. Tests:
  `tests/test_founding.py` (autoplay's invariants hold; the camp's map passes `check_works`; the ownership ledger
  replays); autoplay `_check_founded`.
- [ ] G.10 Showcase pages for all of it; FORMAT_VERSION +1; tests; Part G to `main`.

### Part H – Assaults: battles through a living town
*Done when*: a sack by politics while the player is in the town, and an adventure's assault, play as a battle through
the living town – attackers from the gates or a portal in the square, fire spreading street by street, townsfolk
running for refuges or falling where they stand, objectives to choose among, fights that nearby bands join – and the
aftermath is counted, named and kept: the town stays burned where it burned. ADVENTURES.md §5.20, §8.15.
- [ ] H.1 The assault record (`politics["assaults"]`, `assaults.json`), its tick inside townlife's loop
  (`townlife.tick` calls `assault.tick`, `townlife.settle` calls `assault.settle` for the minutes that pass in a
  wait, a talk or a fight), its phases and clock; waves as `LocalActor`s with new ids and a `goal`; the attackers
  from what the game has (the dead, raiders, orc and goblin warbands, gnolls, a dragon, a summoner's imps and quasits;
  demon bands come with Tieflings & Warlocks as more groups in `assaults.json`); the abstract resolution when the
  player is away, through `hosts.strike`; arriving in the middle of one.
- [ ] H.2 Townsfolk in an assault: `flee_to` refuges, deaths away from a battle (`assault.kill`), defenders to their
  points, militia; bands no longer stand on townsfolk.
- [ ] H.3 Fights in an assault: reinforcements (`Battle.add_foes` at a round, from the nearest edge; while bands are
  still due, `Battle._check_end` does not call the fight won, and if the field is cleared first they come in at the
  start of the next round), defenders beside you (bond `defender`), fire laid on the field, fleeing a few streets away
  instead of out of the town.
- [ ] H.4 Objectives: the children led out, the bell rung, the doors held, the summoner slain, the fire put out round
  the well; each with its key and its line in the tally.
- [ ] H.5 The aftermath: tallies to marks (only the buildings that burned), population and the named dead, refugees,
  `Town.description`, the epilogue's lines; optional assaults for the Risen (the dead over the wall) and the Outlaw
  Lord (a sack); the burning village arena reused.
- [ ] H.6 Showcase (an assault at three moments); frame timing on a burning great city with six bands (§8.18);
  autoplay `_check_assaults`; FORMAT_VERSION +1; Part H to `main`.

### Part I – The Storyteller and events
ADVENTURES.md §5.10, §8.6.
- [ ] I.1 The beat language completed (every condition and op of §8.6 not yet built, checked at start-up); multi-page
  beats; follow-ups.
- [ ] I.2 The Storyteller: tension, the quiet clock, opportunities, choosing by weight × specificity × tension fit ×
  novelty; the setting (Steady, Restless, Gentle, Off) in `ui/screens/settings_screen.py`; travel events and
  encounters rarer when a beat is due; situations' gaps under its hand. The pacing measure through storyplay.
- [ ] I.3 Beat families: signs, relief, companion moments, reveals *(parallel; floors of §9)*.
- [ ] I.4 Echoes: `reputation.deed(..., tags=, subject=)`, `fight.decide_captive` and `law.commit` seeds, echo beats,
  staged where they can be (the spared bandit's runner; the widow in the market).
- [ ] I.5 Happenings (`happenings.json`, `game/story/happenings.py`): coronation and tournament (bouts on the battle
  mat through the existing duels of `game/shadows.py`, a purse and fame), wedding, funeral, muster, siege, refugees,
  quarantine, fairs and holy days; the town shows them (the *festival* mark, crowds, processions); notices;
  happenings and echoes become roots of situations; tests; FORMAT_VERSION +1; Part I to `main`.

### Part J – Legend and ambitions
ADVENTURES.md §5.11–5.13.
- [ ] J.1 Legend tiers (`legend.json`) and what each changes (greetings, audiences, prices, petitioners, rivals,
  lesser foes' morale); tier-up beats staged (a herald at the gate; your name in the street's barks); the Legend page
  (`ui/screens/sheets.py`); the infamy track. The DMG's renown and marks of prestige codex entries settled (adapted).
- [ ] J.2 Epithets chosen from those earned; titles through the existing `reputation.grant_title` (and law.json
  titles) granted by Legend and endings; a small holding (a house, an income); rights and letters; a statue in a
  square (a memorial mark).
- [ ] J.3 Rulers' own commissions, strongroom gifts and realm-tier adventures from Legend 2–3; a steward (a new
  people.json job) hears petitions and gives the hall's contracts before that.
- [ ] J.4 Ambitions (`ambitions.json`): the creation step (`ui/screens/creation.py`; the smoke tour presses Enter
  through it); the twelve ambitions, each making what it binds and writing it into the history (ADVENTURES.md §5.12);
  their sagas; ending a tale (`death.retire`: `politics["retired"]`, the hero made a figure and an NPC, the life's
  epilogue).
- [ ] J.5 The first hour completed: openings by background, ambition and town. Tests: `tests/test_first_hour.py`.
- [ ] J.6 Death and legacy: the villain remembers the fallen; "Take up the fallen's task" at creation;
  FORMAT_VERSION +1; Part J to `main`.

### Part K – The catalogue, cataclysms and the release
ADVENTURES.md §5.22, §6.
- [ ] K.1 The Hidden Circle, Fire on the Valley, A Crown in Shadow (data, words, beats, scenes, arenas, endings;
  storybook and storyplay green) *(parallel words)*.
- [ ] K.2 The Shadow of the Dragon, The Hunt for a relic, The Death, The Mage of the tower.
- [ ] K.3 The Grief of a house, Blood Between Houses, Under the Banner, A Companion's Tale (replacing the half-pay
  personal quests).
- [ ] K.4 The Master of a domain (tier 3–4); the twists and full forms left over from Parts A and D; a first handful
  of dark gifts.
- [ ] K.5 **The Wound in the World** (ADVENTURES.md §6.13): the great event (`game.shake`, the sky's tint on the world
  map and in close-up light, the news from every road), the rift as a land change and a wonder made while you play
  (`wonders.SHAPERS["rift"]`; its drifting ash and red pulse on the map), its depths as a `rift` site with the
  `rift_depths` dungeon style, hordes as hosts (the dead and the things of the deep: zombies, ghouls, wights, trolls,
  giant spiders; fiends join them when Tieflings & Warlocks adds them), the corruption spreading as a region (a wash
  and blighted land, repainting only its chunks), refugees, the crusaders' camp-city founded and growing on the world
  map (or falling), assaults on the camp, the descent, the heart, and its endings that leave the land changed; the
  world option to begin a new world in a time of cataclysm; the other cataclysms' first (the fallen star). Tests:
  `tests/test_cataclysm.py` (the land ledger replays after every stage; founding keeps autoplay's invariants; the
  camp's map passes `check_works` at every stage; storyplay finishes the Wound in at least 80% of runs).
- [ ] K.6 The situations' catalogue completed: all forty predicaments, twenty-five turns, twenty-five meetings and
  forty vignettes *(parallel words)*; the variety measure on the full catalogue.
- [ ] K.7 Balance in band; every Expansion 6 codex entry settled; the icon; `pack.json` released; release v1.6.0
  (`docs/PROGRESS.md`, release notes: a new world is needed).
