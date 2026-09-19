# Realmwalker — progress log

Newest session first. Each milestone lists what's new, how to try it, decisions made, and known issues.

## Status at a glance

| Milestone | State |
|---|---|
| M0 — Setup | ✅ Done (2026-09-19) |
| M1 — World and movement | ✅ Done (2026-09-19) |
| M2 — Character | ✅ Done (2026-09-19) |
| M3 — Combat | ⏳ Next |
| M4 — Body and survival | — |
| M5 — Settlements and people | — |
| M6 — Factions and politics | — |
| M7 — Companions and progression | — |
| M8 — Adventure content | — |
| M9 — Death, legacy and release | — |

---

## M2 — Character (done)

**What you can do now**
- After **New World** (or **New Character** on the title screen, for a world without a living character),
  you create your character in eight steps. Each step starts with a sensible choice, so you can press
  **Enter** through anything you don't care about:
  1. **People:** Human (Heartland, Northmarch or Southron culture), Elf, Dwarf, Halfling, Half-Orc, with their
     traits (darkvision, dwarven resilience against poison, halfling luck, half-orc endurance...).
  2. **Calling:** Fighter, Rogue, Cleric, Wizard, with hit dice, saves, proficiencies and features.
  3. **Background:** Soldier, Acolyte, Criminal, Folk Hero, Noble, Sage, Outlander, Guild Artisan: skills,
     tools, gear, money, a background feature, and **social ties**.
  4. **Abilities:** 5e point buy (27 points, 8–15), racial bonuses on top, "S" for a suggested spread.
  5. **Skills & training:** class skills, Rogue expertise, Fighter fighting style, Cleric domain (Life/War),
     and a choice of equipment kits.
  6. **Who you are:** name (type or random), sex, age, looks, and a backstory with personality, ideal, bond
     and flaw. Press **W** to have the Player2 AI write it (one request, about 2 energy), or use built-in text.
  7. **Where you start:** three or four real places in the world that suit your background.
  8. **Begin.**
- **Social ties are real places and people:** a soldier served a named lord whose seat is a real town; a
  criminal has a fence in one town and a bounty in another; a noble belongs to a house seated nearby; and so
  on. (The people and houses become full characters and factions in M5/M6.)
- **Character sheet** (`c`): abilities, saves, all 18 skills (● trained, ♦ expert), HP, AC, speed,
  initiative, passive perception, proficiencies, traits and features, ties, looks, backstory.
- **Inventory** (`i`): everything you carry with weight, value, condition and how long food keeps; filter by
  type, sort, wear/wield/remove, drop. Items lie where you drop them (on the close-up maps) and stay there;
  `g` picks them up.
- **Equipment** (`e`): a paper doll of slots (hands, armour, helmet, cloak, clothes, underclothes, hat,
  gloves, footwear), a body diagram showing which parts your armour protects, total warmth, wind and rain
  protection, and how respectable you look.
- **Weight matters:** 5e carrying limits. Worn armour and clothes count half. Over your limit you walk slower
  (journeys take longer); far over it you can't move. Dwarves and halflings walk a little slower too.
- The side panel shows your HP bar, AC, money and whether you are laden.
- Over 100 base items from data: all 5e weapons and armour, helmets, clothing layers with warmth, gear,
  tools, food (with spoilage) and trade goods.

**How to try it**
1. Double-click `Play.bat`, **New World**, Enter. Walk through the character steps (try the arrow keys
   on each one, and **W** on step 6 if you want an AI backstory).
2. In the game press `c`, `i` and `e`. In the pack, select an item and press Enter to take it off/put it on.
3. Press `>` to enter the land, then in the pack press `d` to drop something, walk away and come back, `g` to
   pick it up.

**What to look for:** Is creation clear? Are the defaults sensible? Is anything on the sheets confusing?

**How it was verified**
- 176 automated tests pass (added: every race × class builds with its defaults, spends all points, starts
  dressed, armed and not overloaded; point-buy limits; racial bonuses and traits; skills and expertise; armour
  class rules; two-handed weapons and shields; stacking; carrying limits slowing and stopping you; clothing
  warmth and status; character save round trip; every background's ties point at real places; dropping and
  picking up; items on the ground surviving a save; an M1-era save still loading).
- Autoplay: 5000 turns with AI off and 5000 with the fake AI, now also creating characters (including AI
  backstories from the fake server), using the character sheet, inventory and equipment screens, and checking
  after every action: HP in range, no negative money, no zero-sized stacks, nothing worn twice, nothing worn
  that isn't carried. Save/load round trips identical. No errors.
- The window smoke test now goes through character creation, the character sheet, inventory, equipment and a
  local map.

**Decisions (and why)**
1. **Worn armour and clothes count half toward carrying limits**, and everyone starts with a blanket (not a
   7 lb bedroll) and two days' rations. With the 5e variant limits, most characters otherwise started
   over-burdened. Weak characters are still close to their limit, which is realistic.
2. **Subclasses:** Fighter Champion/Knight and Rogue Thief/Cutthroat unlock at level 3; Cleric Life/War domains
   at level 1; Wizard Evocation/Abjuration at level 2. The Knight and Cutthroat are simplified originals in
   the spirit of the design's examples. Spells arrive with combat (M3) and levelling (M7).
3. **Backgrounds, features and descriptions are original text**; the 5e rules (point buy, skills, weapon and
   armour stats) follow the free SRD 5.1 (Creative Commons licence; credit added in `docs/CREDITS.md`).
4. **Saves moved to format 2** (characters). M1 saves still load and get a ready-made wanderer.
5. Sex is male/female as the design lists; pronouns in built-in text follow it.

**Known issues**
- Spells are listed as a feature but can't be cast yet (M3).
- Items in the overworld can't be dropped (enter the land first); by design for now.

---

## M1 — World and movement (done)

**What you can do now**
- **New World** on the title screen: pick a name, a seed (same seed = same world), a size (Small / Medium /
  Large), danger and magic levels. The land forms on screen in a few seconds.
- Worlds have a coastline, mountain ranges, hills, forests and pine woods, marshes, a frozen north, lakes,
  and rivers that really run downhill to the sea. Every region, lake and major river has a name.
- Cities, towns, villages, hamlets, dwarven holds and elven halls, placed where people would actually settle
  (rivers, coasts, good farmland), each with a culture (Heartland, Northmarch, Southron, Elven, Dwarven,
  Halfling). Roads join them. Old ruins, caves, barrows and towers lie in the wilds.
- You start as **The Wanderer** (a placeholder until character creation in M2) in a town or village,
  knowing your home district and the roads out of it.
- **Walk the overworld** (arrows / number pad / Home PgUp End PgDn). Each step takes game time:
  about 45 minutes on a road, an hour or more across country, four hours or more in mountains, extra
  to wade a river. Lakes and the sea block you.
- **Enter the land** (`>`) to see any tile up close: town streets, walls and gates, houses with beds,
  hearths and tables, inns, temples, smithies, fields, graveyards, rivers with bridges or fords,
  lakeshores, ruins. Doors open when you walk into them. Walk off the edge or press `<` to leave.
- **Look** (`l`, or hover the mouse) at anything for a description: land type, region, rivers, roads,
  height, how cold it usually is this month, and how dangerous the wilds are.
- **World map** (`m`, `z` to zoom out) and **Travel** (`t`): pick a destination, see the distance and
  walking time, and set out; the journey plays out step by step and any key stops it.
- **Day and night:** a calendar with named months and weekdays; the map darkens and cools at dusk, and on
  foot you see much less at night. In woods you see only about ten steps around you.
- **Message log** at the bottom (`L` for the full history), **map legend** (`/`), **menu** (`Esc`).
- **Saving:** automatic (every few minutes, on entering or leaving places, when you quit). **Continue** on
  the title screen picks up where you left off. Several worlds can exist side by side.

**How to try it**
1. Double-click `Play.bat`, choose **New World**, press Enter.
2. Walk around; press `>` in a town to walk its streets; press `m` then `z` to see the world.
3. Press `t`, move the cursor to a far town, press Enter, then `Y` to travel.
4. Press `Esc`, choose *Save and return to the title screen*, then **Continue**.

**What to look for / tell me about:** does the world look believable? Are travel times and sight ranges
fun? Is anything hard to read (colours, symbols)? Which parts feel dull or confusing?

**How it was verified**
- 135 automated tests pass (added: same seed gives the same world; rivers always reach water; settlements on
  land; roads connect at least 80% of towns; a sensible mix of land types over several seeds; local maps
  repeatable and enterable; calendar; moving, doors, travel; save then load gives back exactly the same
  game; broken or newer saves are refused politely).
- Autoplay: 4000 turns with AI off and 4000 with the fake AI, creating worlds, walking, travelling and
  entering towns, checking after every action that you stand on walkable ground and that time never runs
  backwards; 14 save/reload round trips, all identical. No errors.
- The real window was opened by the smoke test (title, new world, walk, look, local map).

**Decisions (and why)**
1. **Map cells are taller than wide** (it is a text font). Noise on local maps is squashed vertically so
   patches look round on screen. The overworld reveal area looks slightly oval for the same reason.
2. **Overworld tile = 3 miles**; walking speeds follow 5e travel pace (roughly 24 miles in 8 hours on roads).
3. **Local maps are 96×60 cells**, generated on the first visit and stored in the save (doors you open stay open).
4. **Place names, region names and descriptions use built-in text in M1.** With the Player2 energy budget,
   AI writing is best spent on people and conversations; AI place descriptions will be batched (several
   places per request) when towns come alive in M5.
5. **Sight:** single trees and boulders do not block your view (only walls, doors and thickets do); in forests
   and marshes you simply see a short distance all around.
6. **Roads are drawn straight (north-south and east-west) with box lines**, as in Dwarf Fortress.
7. Weather, needs, encounters and daily travel narration arrive with M4 (survival), as the design orders.
8. Saves are zip files (JSON plus plain number arrays), versioned, with a place for future upgrades.

**Known issues**
- The overworld's unexplored areas are plain black; fine for now.
- Coastlines on local maps can look a little blocky.

---

## M0 — Setup (done)

**What you can do now**
- Double-click `Play.bat`. A window opens (maximized) with the title screen and menu.
- **Player2 Connection Test** (press `P`): shows whether Player2 is running, the health ping,
  your remaining AI energy, and request counts. Press `G` to have the AI write a sample tavern
  (name, sign, description, keeper, a line of overheard talk). Press `O` to pretend Player2 is
  closed and see the built-in text instead, or actually close Player2 and press `G`.
- **Settings** (`S`): text size, fullscreen, dice display, AI on/off, text detail, autosave, AI debug log.
- Anywhere: `Ctrl +` / `Ctrl -` text size, `F11` fullscreen, `F12` screenshot, `F1` help.
- `Build_For_Friends.bat` makes `Realmwalker.zip` (about 34 MB). Friends unzip and double-click `Realmwalker.exe`.

**How it was verified**
- 107 automated tests pass (dice, RNG, data validation, AI parsing and fallback, AI service against a fake
  Player2 server in every failure mode, all screens at four window sizes, error recovery, settings).
- Autoplay bot: 3000 turns with AI off and 3000 with a deliberately unreliable fake AI — no errors.
- Real window opened and toured by the smoke test; `Play.bat` launched it; the packaged `.exe` started too.
- One real Player2 generation succeeded: *"The Wet Whetstone"*, keeper Ragnvald Ormsson, a carter
  "found under the switchbacks, throat cut and boots gone" (784 tokens, ~8 s, ~2 energy).

**Decisions (and why)**
1. **Player2 via the local app API, no client ID.** The local API works without one; the header is supported
   if a client ID is ever put in `config.json`. Simplest for you and for friends.
2. **No `response_format` JSON mode** — with it, the current Player2 model returned empty replies. We ask for
   JSON in the prompt and parse it defensively instead.
3. **Generous token allowance (3000) for AI requests.** The model "thinks" silently before answering; with a
   900 cap it thought until the cap and returned nothing, *twice, costing 4 energy*. Empty replies are no
   longer retried automatically (a retry costs the same again).
4. **AI energy is very limited** (see "Needs your attention"). Background pre-generation pauses when energy is
   below 6; text the player is waiting for still uses it. Later milestones will spend AI only on what matters
   most (notable people, conversations, big moments) and use built-in text for the bulk.
5. **Font:** DejaVu Sans Mono (free licence) rendered into a CP437 tileset at runtime, with hand-drawn
   box lines and shading, so any text size works. Letters are taller than wide (like Brogue / Caves of Qud).
6. **Python 3.12** installed alongside your existing Pythons (3.10/3.11/3.13 untouched), in its own `.venv`.
7. Player settings live in `%APPDATA%\Realmwalker\settings.json`; logs in the project's `logs\` folder when
   run from source, and in `%APPDATA%\Realmwalker\logs` for the packaged game.
8. Debug console on the <code>`</code> key (commands: `help`, `ai on|off`, `offline on|off`, `ping`, `status`,
   `font N`, `test-error`). Switched off in friend builds.

**Needs your attention (when you have a moment)**
- **Player2 energy:** your account showed 10 energy at first, and testing used 7. After the daily refill it showed
  **91**, so there is far more room than first feared (a rich AI request costs about 2). Nothing to do.

**Known issues**
- None open.

---

## Ideas parking lot (after v1 — do not build yet)
- more races and classes
- sailing
- owning property
- joining sieges and battles personally
- full crafting and smithing
- NPC voices via Player2 text-to-speech
- romance and relationships
- a player-led warband
- a main story with a growing world threat
