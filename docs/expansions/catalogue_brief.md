# Brief: the spell catalogue, fourth wave (Expansion 3, task D.4) — spells of level 8 and 9

(Earlier briefs are in git history: D.3 for levels 6 and 7 `git show 4279e05:docs/expansions/catalogue_brief.md`,
D.2 for levels 3 to 5 `git show 1544733:docs/expansions/catalogue_brief.md`.)

You write game data for Realmwalker, a D&D 5e (2024 rules) party RPG in Python. You write **JSON only**: never edit
Python code. The project is at `D:\Project Dawn` (Windows; the Bash tool is Git Bash: `cd "/d/Project Dawn"`; Python is
`.venv/Scripts/python.exe`). Do not commit; the main session joins and commits your work.

## What to write

1. `data/packs/03_demigods_magics/spells.level<N>.json` (your level): `{"_comment": "...", "spells": {id: spell}}`,
   one entry per spell in your list below, ids exactly as listed.
2. `build/d4_codex_level<N>.json`: `{id: {"status": "done" | "adapted", "note": "..."}}` for every spell you wrote.
   "done" only when the spell works as the book says in a fight; otherwise "adapted" and a short note of what is left
   out or changed (style: "the ring wall and the three-quarters cover are left out").

## How a spell is written

Read these first (they are the vocabulary; do not invent ops, buff keys or zone kinds):
- `realmwalker/rules/engine/effects.py`: the docstring at the top lists every op and its parameters (four parts: the
  first wave's, "The second wave (D.2)", "The third wave (D.3)" and "The fourth wave (D.4)" — the fourth is new and
  made for your spells).
- `realmwalker/rules/engine/marks.py`: the docstring lists every buff key a `modifier` op may carry; `BUFF_KEYS` and
  `ZONES` (zone kinds) are the complete sets.
- `realmwalker/data/schemas.py`, `SPELL`: the fields (`fx` must be one of its looks; `area.shape` one of its shapes,
  `area.size` at most 300; `target` one of its targets; `text` at most 300 characters).
- Finished examples: `data/packs/03_demigods_magics/spells.level6.json` and `spells.level7.json` (the third wave),
  `spells.level4.json` (`phantasmal_killer`), `spells.level5.json` (`dominate_person`, `cloudkill`, `wall_of_stone`).

Rules of the house:
- Fields: name, level, school, classes (the 2024 class list from the book, as listed below), target, range (feet,
  "self" or "touch"; "1 mile" is 5280), area if any, cast ("bonus"/"reaction" when not an action), components,
  concentration, rounds (10 = a minute, 100 = ten minutes, 600 = an hour, 4800 = eight hours, 14400 = a day), effects,
  fx, text. `battle_only: true` on spells whose blessing only matters in a fight.
- A costly material component: `"material": {"items": [item id], "consumed": true/false, "text": "<the book's words>"}`.
  The item for this wave: `gilded_reliquary` (Holy Aura). Leave `material` out for components with no cost.
- `text`: plain English for the player, in the game's voice (look at the examples), at most 300 characters; say what
  happens in the fight; mention anything left out only briefly if at all (the codex note carries that).
- A rider the ops cannot say: leave it out and note it ("adapted"). Do NOT invent new op names or keys. If a spell
  cannot be made to work at all, leave it out of the JSON and tell the main session in your final reply why.
- Numbers come from the book. The 2024 Player's Handbook text is extracted page by page in
  `build/codex/phb/p<page>.txt` (page numbers below). The text is OCR and often garbled (5 for 6, l for 1): **check
  every range and number on the page image**: `.venv/Scripts/python.exe tools/codex/extract.py --render phb <page>`
  (writes `build/codex/pages/`), then read the PNG.
- Every spell must be castable in a real fight and do something the Auto (the game's own tactics) can value.

## The plan for each spell (the main session made the kernel pieces for these; follow it)

**Level 8 (spells.level8.json), 11 spells:**
- `antimagic_field` [244] cleric, wizard: target "self", range "self", area emanation 10, concentration, rounds 600;
  effects [{"op": "zone", "zone": "antimagic", "follow": true, "save": "none"}]. (Adapted: spells already on creatures
  in it go on working; area spells may still catch those inside.)
- `befuddlement` [249] bard, druid, warlock, wizard: target "enemy", range 150; save int 10d12 psychic half, on_fail
  [modifier rounds 14400 buff {"befuddled": true}]. (Adapted: it lasts a day, not until a 30-day save.) Read the page
  for its components.
- `dominate_monster` [268] bard, sorcerer, warlock, wizard: as `dominate_person` (level 5) without its `kinds`;
  concentration, rounds 600.
- `earthquake` [270] cleric, druid, sorcerer: target "point", range 500, area cylinder 100, affects "enemies",
  concentration, rounds 10; a `zone` "quake", save dex, fail "prone", breaks true, rough true, catch true,
  friends_safe true. (Adapted: it spares the caster's side, as if cast from afar; the save comes as creatures enter or
  start a turn there rather than at the end of the caster's turns; fissures and falling structures are left out.)
- `holy_aura` [289] cleric: target "self", range "self", concentration, rounds 10, battle_only; a `modifier` rounds 10
  with buff {"aura": {"radius": 30, "grant": {"holy": "$dc", "save_adv": ["str", "dex", "con", "int", "wis", "cha"]}}};
  material gilded_reliquary, not consumed ("a reliquary worth 1,000+ GP").
- `incendiary_cloud` [291] druid, sorcerer, wizard: target "point", range 150, area sphere 20, concentration, rounds
  10; a `zone` "embers", save dex, 10d8 fire, half, dark true, catch true. (Adapted: the cloud does not drift 10 feet
  away each turn.)
- `maze` [299] wizard: target "enemy", range 60, concentration, rounds 100; effects [{"op": "banish", "escape":
  {"skill": "investigation", "dc": 20}}]. No save (the book has none).
- `mind_blank` [301] bard, wizard: target "ally", range "touch", rounds 14400, battle_only; a `modifier` rounds 14400
  buff {"immune_damage": ["psychic"], "immune": ["charmed"]}. (Adapted: the protections against divination and
  scrying wait for Part E.)
- `power_word_stun` [309] bard, sorcerer, warlock, wizard: target "enemy", range 60; effects [{"op": "by_hp", "tiers":
  [[150, [{"op": "condition", "condition": "stunned", "repeat_save": true, "save": "con"}]], [999999, [{"op": "slow",
  "feet": 999}]]]}]. Look at how `repeat_save` is written in other spells and follow it.
- `sunburst` [332] cleric, druid, sorcerer, wizard: target "point", range 150, area sphere 60; save con 12d6 radiant
  half, on_fail [condition blinded, rounds 10, repeat_save con]. (The darkness it dispels: adapted.)
- `tsunami` [339] druid: target "direction", range "self", area line 300, concentration, rounds 6 (or the book's);
  a `save` str 6d10 bludgeoning half, on_fail [{"op": "push", "feet": 50}] (look up how `push` is written). (Adapted:
  the wall sweeps once as it is raised; its rolling on over later rounds and the swimming are left out.)

**Level 9 (spells.level9.json), 9 spells (Wish is the main session's):**
- `foresight` [279] bard, druid, warlock, wizard: target "ally", range "touch", rounds 4800, battle_only; a `modifier`
  rounds 4800 buff {"foresight": true}. Material: a hummingbird feather (no cost).
- `mass_heal` [299] cleric: target "all_allies", range 60 (check the image); effects [{"op": "heal", "dice": "0",
  "pool": 700, "restore": ["blinded", "deafened", "poisoned"]}].
- `meteor_swarm` [301] sorcerer, wizard: target "point", range 5280, area sphere 40, `"spheres": 4`; a `save` dex with
  damage [{"dice": "20d6", "type": "fire"}, {"dice": "20d6", "type": "bludgeoning"}] half (see how a list of damage is
  written: Ice Storm, Flame Strike); then {"op": "ignite"}.
- `power_word_heal` [309] bard, cleric: target "ally", range "touch"; effects [{"op": "heal", "dice": "0", "full":
  true, "restore": ["charmed", "frightened", "paralyzed", "poisoned", "stunned", "prone"]}]. (Adapted: it stands up
  without spending its reaction.)
- `power_word_kill` [309] bard, sorcerer, warlock, wizard: target "enemy", range 60 (check the image); effects
  [{"op": "by_hp", "tiers": [[100, [{"op": "slay"}]], [999999, [{"op": "damage", "damage": "12d12", "type":
  "psychic"}]]]}] (see how the `damage` op names its dice).
- `prismatic_wall` [311] bard, wizard: target "point", range 60, area cube 30 (a block standing for the 90-foot wall
  or the globe), rounds 100 (no concentration), `no_dispel` true; a `zone` "prismatic", save "none", near 20,
  near_save "con", near_fail "blinded", lasts 10. (Adapted: the wall stops everyone, friends too; its seven layers are
  never crossed, as nothing would live through them; the glare blinds foes only.)
- `storm_of_vengeance` [324] druid: target "point", range 5280, area cylinder 300, affects "enemies", concentration,
  rounds 10; first a `save` con 2d6 thunder (no half), on_fail [condition deafened]; then a `zone` "storm", save
  "none", friends_safe true, stages [
  {"say": "Acid rain pours from the storm.", "ops": [{"op": "damage", "damage": "4d6", "type": "acid"}]},
  {"say": "Lightning lances down from the storm.", "count": 6, "ops": [{"op": "save", "ability": "dex", "damage":
  "10d6", "type": "lightning", "half": true}]},
  {"say": "Hailstones hammer down.", "ops": [{"op": "damage", "damage": "2d6", "type": "bludgeoning"}]},
  {"say": "Freezing rain and gusts lash the ground.", "rough": true, "dark": true, "ops": [{"op": "damage", "damage":
  "1d6", "type": "cold"}]}]. (Adapted: it spares the caster's side, as if cast from afar; ranged attacks through the
  last turns' wind are left out.)
- `time_stop` [337] sorcerer, wizard: target "self", range "self"; effects [{"op": "time_stop", "dice": "1d4+1"}].
  (Adapted: moving 1,000 feet away is not possible on a battlefield.)
- `weird` [344] wizard: target "point", range 120, area sphere 30, affects "enemies", concentration, rounds 10; a
  `save` wis 10d10 psychic half, on_fail [condition frightened; modifier rounds 10 buff {"dot": "5d10", "dot_type":
  "psychic", "dot_at": "end", "dot_save": "wis", "save_first": true, "dc": "$dc", "by": "$caster", "dot_name": "the
  phantasms"}] (as Phantasmal Killer, level 4).

For every spell, read its page: the numbers, the class list and the components (V, S, M) come from the book. The plan
above says how to build it; if the book disagrees with a number in the plan, the book wins (say so in your reply).

## Checking your work

- `.venv/Scripts/python.exe -m pytest -q -n 3 tests/test_engine.py tests/test_schema_data.py` (the data loads; every op,
  key and zone kind is known) — use `-n 3`, never more (another helper runs beside you).
- `.venv/Scripts/python.exe -m pytest -q -n 3 tests/test_catalogue.py -k "<your ids, separated by ' or '>"`: every
  spell is cast in a real fight, the fight goes on to its end, and the Auto sees the spell's worth. A worth failure
  may be the main session's to fix (the Auto's valuation code): say which in your reply rather than bending the
  spell. Other failures are yours.
- Your final reply: the ids written, anything left out and why, test results, and any kernel gap you noticed.
