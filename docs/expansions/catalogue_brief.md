# Brief: the spell catalogue, third wave (Expansion 3, task D.3) — spells of level 6 and 7

(The D.2 brief for levels 3 to 5 is in git history: `git show 1544733:docs/expansions/catalogue_brief.md`.)

You write game data for Realmwalker, a D&D 5e (2024 rules) party RPG in Python. You write **JSON only**: never edit
Python code. The project is at `D:\Project Dawn` (Windows; the Bash tool is Git Bash: `cd "/d/Project Dawn"`; Python is
`.venv/Scripts/python.exe`). Do not commit; the main session joins and commits your work.

## What to write

1. `data/packs/03_demigods_magics/spells.level<N>.json` (your level): `{"_comment": "...", "spells": {id: spell}}`,
   one entry per spell in your list below, ids exactly as listed.
2. `build/d3_codex_level<N>.json`: `{id: {"status": "done" | "adapted", "note": "..."}}` for every spell you wrote.
   "done" only when the spell works as the book says in a fight; otherwise "adapted" and a short note of what is left
   out or changed (style: "the ring wall and the three-quarters cover are left out").

## How a spell is written

Read these first (they are the vocabulary; do not invent ops, buff keys or zone kinds):
- `realmwalker/rules/engine/effects.py`: the docstring at the top lists every op and its parameters (three parts: the
  first wave's, "The second wave (D.2)" and "The third wave (D.3)" — the third is new and made for your spells).
- `realmwalker/rules/engine/marks.py`: the docstring lists every buff key a `modifier` op may carry; `BUFF_KEYS` and
  `ZONES` (zone kinds) are the complete sets.
- `realmwalker/data/schemas.py`, `SPELL`: the fields (`fx` must be one of its looks; `area.shape` one of its shapes;
  `target` one of its targets; `text` at most 300 characters).
- Finished examples: `data/packs/03_demigods_magics/spells.level3.json`, `spells.level4.json`, `spells.level5.json`
  (the second wave: zones, walls, auras, banishing, `again` follow-ups, `material`) and `spells.level2.json`
  (Suggestion), `data/spells.json` (`fireball`, `hold_monster`, `spiritual_weapon`).

Rules of the house:
- Fields: name, level, school, classes (the 2024 class list from the book, as listed below), target, range (feet,
  "self" or "touch"), area if any, cast ("bonus"/"reaction" when not an action), components, concentration, rounds
  (10 = a minute, 100 = ten minutes, 600 = an hour, 14400 = a day), effects, fx, text. `up` on a damage op = dice
  added per slot level above. `battle_only: true` on spells whose blessing only matters in a fight (as in level 5).
- A costly material component: `"material": {"items": [item id], "consumed": true/false, "text": "<the book's words>"}`.
  The items exist: `black_pearl`, `mushroom_powder`, `ruby_dust`, `miniature_sword`, `forked_rod` (and `diamond`,
  `pearl`, `diamond_dust`). Leave `material` out for components with no cost.
- `text`: plain English for the player, in the game's voice (look at the examples), at most 300 characters; say what
  happens in the fight and what each higher slot adds; mention anything left out only briefly if at all (the codex
  note carries that).
- A rider the ops cannot say: leave it out and note it ("adapted"). Do NOT invent new op names or keys. If a spell
  cannot be made to work at all, leave it out of the JSON and tell the main session in your final reply why.
- Numbers come from the book. The 2024 Player's Handbook text is extracted page by page in
  `build/codex/phb/p<page>.txt` (page numbers below). If the text is garbled, render the page image with
  `.venv/Scripts/python.exe tools/codex/extract.py --render phb <page>` (writes `build/codex/pages/`) and read it.
- Every spell must be castable in a real fight and do something the Auto (the game's own tactics) can value.

## The plan for each spell (the main session made the kernel pieces for these; follow it)

**Level 6 (spells.level6.json), 17 spells:**
- `blade_barrier` [250] cleric: target "direction", range "self", area line 100, concentration, rounds 100; a `zone`
  "blades", save dex, 6d10 force, half, rough, catch. (Adapted: three-quarters cover, the ring wall, the 90-foot range.)
- `chain_lightning` [252] sorcerer, wizard: target "enemy", range 150, `"targets": 4, "targets_up": 1, "leap": 30`;
  a `save` dex 10d8 lightning half. Material: three silver pins (no cost).
- `circle_of_death` [253] sorcerer, warlock, wizard: target "point", range 150, area sphere 60; save con 8d8 necrotic
  half, up 2d8; material black_pearl, not consumed ("the powder of a crushed black pearl worth 500+ GP").
- `conjure_fey` [258] druid: target "point", range 60, concentration, rounds 100; `summon` (token
  "spiritual_weapon") damage 3d12 psychic, up 2d12, add_mod true, `on_hit`: [condition frightened, ends
  "caster_turn_start"]. Text: a bonus action on later turns sends it to strike again.
- `disintegrate` [266] sorcerer, wizard: target "enemy", range 60; save dex, damage "10d6+40" force, up "3d6", no half,
  `"dust": true`. (Adapted: objects and walls of force.)
- `eyebite` [273] bard, sorcerer, warlock, wizard: target "enemy", range 60, concentration, rounds 10; save wis,
  on_fail [condition unconscious, on_damage true] (Asleep); an `again` (cast "action", target "enemy", range 60, the
  same save). (Adapted: always Asleep — Panicked and Sickened left out; the "not again after a success" rule.)
- `flesh_to_stone` [278] druid, sorcerer, wizard: target "enemy", range 60, concentration, rounds 10; save con,
  `"sure_kinds": ["construct"]`, on_fail [condition restrained, `"petrify": true`, "save": "con"], on_save
  [{"op": "slow", "feet": 999}] (speed 0 until the start of your next turn). (Adapted: the permanent stone after a
  full minute.)
- `globe_of_invulnerability` [282] sorcerer, wizard: target "self", range "self", concentration, rounds 10,
  battle_only; a `modifier` rounds 10 with buff `{"aura": {"radius": 10, "grant": {"spell_ward": "$level"}}}` (spells
  below the slot's level are kept out: 5th and lower at level 6, one more per slot above). (Adapted: the barrier moves
  with the caster.)
- `harm` [286] cleric: target "enemy", range 60; save con 14d6 necrotic half, `"max_hp_loss": true`. (Adapted: the
  maximum comes back after the fight.)
- `heal` [287] cleric, druid: target "ally", range 60; `heal` dice "70", per_up 10; then `restore` conditions
  ["blinded", "deafened", "poisoned"].
- `mass_suggestion` [299] bard, sorcerer, wizard: target "enemy", range 60, `"targets": 12`, rounds 14400 (no
  concentration), battle_only; save wis, on_fail [condition incapacitated, on_damage true] — as Suggestion (level 2).
- `otilukes_freezing_sphere` [305] sorcerer, wizard: target "point", range 300, area sphere 60; save con 10d6 cold
  half, up 1d6. (Adapted: freezing water and holding the globe to throw later.)
- `ottos_irresistible_dance` [306] bard, wizard: target "enemy", range 30, concentration, rounds 10; save wis, on_fail
  [condition charmed; modifier buff `{"dancing": true, "dc": "$dc", "by": "$caster"}`], on_save [{"op": "slow",
  "feet": 999}].
- `sunbeam` [332] cleric, druid, sorcerer, wizard: target "direction", range "self", area line 60, concentration,
  rounds 10; save con 6d8 radiant half, on_fail [condition blinded, ends "caster_turn_start"]; an `again` (cast
  "action", the same line and save). Material: a magnifying glass (no cost).
- `true_seeing` [339] bard, cleric, sorcerer, warlock, wizard: target "ally", range "touch", rounds 600, battle_only;
  a `modifier` rounds 600 buff `{"truesight": 120}`; material mushroom_powder, consumed ("mushroom powder worth 25+ GP,
  which the spell consumes").
- `wall_of_ice` [342] wizard: target "point", range 120, area cube 20, concentration, rounds 100; a `zone` "icewall",
  save dex, 10d6 cold, up 2d6, half, catch. (Adapted: the dome and panel shapes, breaking it, the frigid air.)
- `wall_of_thorns` [342] druid: target "direction", range "self", area line 60, concentration, rounds 100; first a
  `save` dex 7d8 piercing half up 1d8 (those in it as it appears), then a `zone` "thorns", save dex, 7d8 slashing,
  up 1d8, half, rough, dark (no catch). (Adapted: the four feet of movement per foot are ordinary difficult terrain.)

**Level 7 (spells.level7.json), 11 spells:**
- `conjure_celestial` [257] cleric: target "point", range 90, area cylinder 10, concentration, rounds 100; a `zone`
  "celestial", save dex, 6d12 radiant, up 1d12, half, `"heal": "4d12", "heal_up": "1d12", "add_mod": true,
  "friends_safe": true, "catch": true`; an `again` (cast "bonus", target "point", range 90, area cylinder 10,
  effects [{"op": "move_zone"}]) as in Conjure Animals (level 3). (Adapted: moved with a bonus action, not as you move.)
- `delayed_blast_fireball` [264] sorcerer, wizard: target "point", range 150, area sphere 20; save dex 12d6 fire half,
  up 1d6; then {"op": "ignite"}. No concentration. (Adapted: the bead bursts at once; its growing and being thrown
  back are left out.)
- `divine_word` [268] cleric: cast "bonus" (check the page), target "self", range "self", area emanation 30, affects
  "enemies"; save cha, on_fail [{"op": "banish", "forever": true, "kinds": ["celestial", "elemental", "fey", "fiend"]},
  {"op": "by_hp", "tiers": [[20, [{"op": "slay"}]], [30, [blinded, deafened, stunned conditions with rounds 600]],
  [40, [blinded, deafened, rounds 100]], [50, [deafened, rounds 10]]]}].
- `finger_of_death` [276] sorcerer, warlock, wizard: target "enemy", range 60; save con, damage "7d8+30" necrotic,
  half. (Adapted: the zombie that rises waits for Part F.)
- `fire_storm` [278] cleric, druid, sorcerer: target "point", range 150, area cube 30, affects "enemies"; save dex
  7d10 fire half; then {"op": "ignite"}. (Adapted: the ten cubes are one block, arranged round your friends.)
- `forcecage` [279] bard, warlock, wizard: target "point", range 100, area cube 10, concentration, rounds 600,
  `"no_dispel": true`; effects [{"op": "banish", "how": "cage"}]; material ruby_dust, consumed. (Adapted: the solid
  box only; the cage of bars and the Charisma save to teleport out are left out.)
- `mordenkainens_sword` [305] bard, wizard: target "point", range 90, concentration, rounds 10; `summon` damage 4d12
  force, add_mod true; material miniature_sword, not consumed.
- `plane_shift` [308] cleric, druid, sorcerer, warlock, wizard: target "enemy", range "touch"; an `attack` melee with
  no damage, on_hit [save cha, on_fail [{"op": "banish", "forever": true}]]; material forked_rod, not consumed.
  (Adapted: travelling with willing friends waits for Part E.)
- `power_word_fortify` [309] bard, cleric: target "all_allies", range 60; `temp_hp` amount 120, `"share": true,
  "count": 6`.
- `prismatic_spray` [310] bard, sorcerer, wizard: target "direction", range "self", area cone 60; one op
  `{"op": "one_of", "die": 8, "choices": [...]}` with seven choices, each a list holding one `save` dex (a `say` op
  first is welcome: "A red ray strikes {name}."): red 12d6 fire half, orange acid, yellow lightning, green poison, blue
  cold (all 12d6, half); indigo: no damage, on_fail [condition restrained, petrify true, save "con"]; violet: no
  damage, on_fail [condition blinded, ends "caster_turn_start", then {"save": "wis", "on_fail": [{"op": "banish",
  "forever": true}]}]. The eighth face (two rays) is the die's own rule.
- `reverse_gravity` [315] druid, sorcerer, wizard: target "point", range 100, area cylinder 50, concentration, rounds
  10; save dex, on_fail [{"op": "lift", "feet": 100}]. (Adapted: those who walk in later, objects.)

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
