# Brief: the spell catalogue, second wave (Expansion 3, task D.2) — spells of level 3, 4 and 5

You write game data for Realmwalker, a D&D 5e (2024 rules) party RPG in Python. You write **JSON only**: never edit
Python code. The project is at `D:\Project Dawn` (Windows; the Bash tool is Git Bash: `cd "/d/Project Dawn"`; Python is
`.venv/Scripts/python.exe`). Do not commit; the main session joins and commits your work.

## What to write

1. `data/packs/03_demigods_magics/spells.level<N>.json` (your level): `{"_comment": "...", "spells": {id: spell}}`,
   one entry per spell in your list below, ids in snake_case (`evards_black_tentacles`, `otilukes_resilient_sphere`).
2. `build/d2_codex_level<N>.json`: `{id: {"status": "done" | "adapted", "note": "..."}}` for every spell you wrote.
   "done" only when the spell works as the book says in a fight; otherwise "adapted" and a short note of what is left
   out or changed (style: "the disadvantage on one ability's checks and moving it to a new creature are left out").

## How a spell is written

Read these first (they are the vocabulary; do not invent ops, buff keys or zone kinds):
- `realmwalker/rules/engine/effects.py`: the docstring at the top lists every op and its parameters (two parts: the
  first wave's, and "The second wave (D.2)").
- `realmwalker/rules/engine/marks.py`: the docstring lists every buff key a `modifier` op may carry; `BUFF_KEYS` and
  `ZONES` (zone kinds) are the complete sets.
- `realmwalker/data/schemas.py`, `SPELL`: the fields (`fx` must be one of its looks; `area.shape` one of its shapes;
  `target` one of its targets; `text` at most 300 characters).
- Finished examples: `data/packs/03_demigods_magics/spells.level1.json` and `spells.level2.json` (the first wave;
  smites, `again` follow-ups, zones, marks, `$caster`/`$dc`/`$mod`/`$spell`/`$up`/`$level`/`$foe_type`, `per_up`) and
  in `data/spells.json`: `spirit_guardians` (an aura), `fireball`, `hold_monster`, `spiritual_weapon` (a token).

Rules of the house:
- Fields: name, level, school, classes (the 2024 class list from the book), target, range (feet, "self" or "touch"),
  area if any, cast ("bonus"/"reaction" when not an action), components, concentration, rounds (10 = a minute, 100 =
  ten minutes, 600 = an hour), effects, fx, text. `targets_up` for "one more creature for each slot level above".
  `up` on a damage op = dice added per slot level above. `battle_only: true` on smites (as in level 1).
- `text`: plain English for the player, in the game's voice (look at the examples), at most 300 characters; say what
  happens in the fight and what each higher slot adds; mention anything left out only briefly if at all (the codex
  note carries that).
- A rider the ops cannot say: leave it out and note it ("adapted"). Do NOT invent new op names or keys. If a spell
  cannot be made to work at all, leave it out of the JSON and tell the main session in your final reply why.
- Numbers come from the book. The 2024 Player's Handbook text is extracted page by page in
  `build/codex/phb/p<page>.txt` (page numbers below). If the text is garbled, render the page image with
  `.venv/Scripts/python.exe tools/codex/extract.py --render phb <page>` (writes `build/codex/pages/`) and read it.
- Every spell must be castable in a real fight and do something the Auto (the game's own tactics) can value.

## The kernel's new pieces you will use (all in the docstrings)

- Sent away: `{"op": "banish", "how": "banished"}` (Banishment), `"how": "sphere"` (Resilient Sphere),
  `"below_hp": 50` (Banishing Smite's on_hit). Needs `concentration: true` on the spell. Put it in a save's
  `on_fail`, or directly for a sure effect.
- Blink: a `modifier` with buff `{"blink": true}` on the caster for 10 rounds (no concentration).
- Dispel: `{"op": "dispel"}`; spell target "point" (the creature on the square and the ground there).
  Add `"breaker_bonus": true` to Dispel Magic (the Abjurer's Spell Breaker casts it with a bonus action).
- Auras that help friends: a `modifier` on the caster with buff `{"aura": {"radius": 30, "grant": {...}}}` where
  grant is any buff (e.g. `{"hit_extra": "1d4", "hit_type": "radiant", "hit_with": "weapon"}` for Crusader's Mantle;
  `{"resist": ["necrotic"], "rise": true}` for Aura of Life; `{"resist": ["poison"], "immune": ["poisoned"],
  "save_adv_against": ["blinded", "charmed", "deafened", "frightened", "paralyzed", "poisoned", "stunned"]}` for Aura
  of Purity; `{"save_adv_spells": true, "evade_spells": true}` for Circle of Power). Concentration spells.
- Marks: `confused` (Confusion: with `"repeat": "wis", "dc": "$dc"`), `sluggish` (Slow: with `"ac": -2`, `"repeat":
  "wis"`, `"dc": "$dc"`), `haste` (with `"ac": 2`, `"save_adv": ["dex"]`), `thorns` + `thorns_type` (Fire Shield, with
  `resist`), `save_adv` (["wis", "death"] for Beacon of Hope), `heal_max` (Beacon of Hope).
- Ground: a `zone` op with a kind from ZONES and `save`, `damage`/`type`/`up`, `half`, `fail` ("restrained" holds while
  in it, "prone", "retching" = Poisoned and no action that turn, or another condition until the end of the turn),
  `rough` (difficult terrain), `dark` (heavily obscured), `catch: true` (those inside when it appears are caught at
  once). Kinds: tentacles, cloud (Cloudkill), stench (Stinking Cloud), hunger (Hunger of Hadar), insects (Insect
  Plague), sleet (Sleet Storm), radiance (Jallarzi's), spirits (Conjure Animals), elemental (Conjure Elemental), fire
  (Wall of Fire, along a "line" area), wind (Wind Wall, a "line": missiles cannot cross it), stone and force (Wall of
  Stone, Wall of Force: impassable walls on the area's free squares, gone when the spell ends). A zone deals its
  damage when someone enters or starts a turn there, once a turn. Two zone ops on one spell are fine (Hunger of
  Hadar: cold with no save, `"save": "none"`, and acid on a Dexterity save).
- Movable things: an `again` follow-up with `{"op": "move_zone"}` (see Cloud of Daggers, Moonbeam) — Conjure Animals,
  Call Lightning's later bolts are an `again` with a save op at a point.
- Vampiric Touch: an `attack` op with `"drain": 0.5`, and an `again` for the later touches.
- Dominate: a `condition` "charmed" with `"control": true, "damage_save": true` (and `"save": "wis"`) in a save's
  on_fail, concentration.
- Moving a foe: `push` (feet), `pull`; conditions with `repeat_save`; `dot` marks with `dot_save` (Phantasmal Killer),
  `dot_once` (Vitriolic Sphere's later acid); `quarry` (Bestow Curse's extra necrotic, by "$caster");
  `weapon_attack` (Swift Quiver's `again`: two of them); `attack` with `rays` (Steel Wind Strike: 5) ; `teleport`
  (Dimension Door: range 500).

## Lists (book page in brackets)

**Level 3 (spells.level3.json):** Aura of Vitality [247] (an `again` bonus-action heal 2d6 on an ally), Beacon of Hope
[248], Bestow Curse [249] (the extra 1d8 necrotic from the caster's attacks: a `quarry` mark; touch; save Wis),
Blinding Smite [250], Blink [251], Call Lightning [251] (point, then `again` each turn), Conjure Animals [257] (2024:
a pack of spirits, zone "spirits", radius 10 around a point, Dex save 3d10 slashing, moved by an `again` bonus action
with `move_zone`), Conjure Barrage [257], Crusader's Mantle [262], Dispel Magic [267], Elemental Weapon [271] (a
`modifier`: weapon_plus 1 and hit_extra 1d4 of a type; target ally touch), Fear [274] (cone; frightened + `flee`),
Fly [279] (`fly` buff, targets_up), Haste [287], Hunger of Hadar [289], Hypnotic Pattern [290] (charmed +
incapacitated, `on_damage`), Lightning Arrow [295] (a smite on a ranged weapon; on_hit damage and a `save` with
`around: 10`), Protection from Energy [312] (`resist` with "$foe_type"), Sleet Storm [320], Slow [321], Stinking Cloud
[324], Vampiric Touch [340], Wind Wall [344].

**Level 4 (spells.level4.json):** Aura of Life [247], Aura of Purity [247], Banishment [248], Blight [250] (kinds:
plants fail automatically or take max — say what you can), Charm Monster [252] (see Charm Person in level1),
Compulsion [255] (adapt: those failing must spend their move going away from the caster — `flee` without fear, or as
you judge best), Confusion [256], Conjure Minor Elementals [258] (2024: your attacks deal 2d8 more of a chosen type
to creatures within 15 feet: a `modifier` hit_extra with hit_with "any" on the caster), Conjure Woodland Beings [258]
(2024: an `aura` op like Spirit Guardians, 10 feet, Wis save 5d8 force half), Dimension Door [265], Dominate Beast
[268] (kinds ["beast"]), Evard's Black Tentacles [273], Fire Shield [277], Fount of Moonlight [280] (resist radiant
and hit_extra 2d6 radiant melee; the blinding reaction left out), Freedom of Movement [280] (`immune` paralyzed and
restrained; lasts an hour, 600 rounds), Grasping Vine [283] (a `save`/`pull`/grappled at a point and an `again`),
Greater Invisibility [284] (condition invisible on the target, concentration; it does not end on attacking),
Otiluke's Resilient Sphere [306], Phantasmal Killer [307], Staggering Smite [323], Vitriolic Sphere [340], Wall of
Fire [341].

**Level 5 (spells.level5.json):** Antilife Shell [244] (adapt as you best can with the ops: e.g. an aura on the
caster whose grant is warded_kinds for every kind but undead and constructs — say what it really does in the note),
Banishing Smite [248], Bigby's Hand [249] (a `summon` token like Spiritual Weapon: Clenched Fist 5d8 force, `up`
2d8; the other hands left out), Circle of Power [253], Cloudkill [254], Conjure Elemental [257] (2024: zone
"elemental" at a point, Dex save 8d8 of a chosen type, fail restrained), Conjure Volley [258], Contagion [259],
Destructive Wave [264] (an emanation of 30 feet around the caster, affects enemies: Con save, 5d6 thunder + 5d6
radiant, half, prone on a fail), Dispel Evil and Good [266] (warded_kinds; the Dismissal and Break Enchantment
options as you can), Dominate Person [269] (kinds ["humanoid"]), Greater Restoration [284] (`restore`, what the op
allows), Insect Plague [292], Jallarzi's Storm of Radiance [292], Steel Wind Strike [323], Swift Quiver [332], Synaptic
Static [333] (`attack_die` "-1d6" mark with repeat Int), Telekinesis [334] (adapt: Str save or pushed/pulled and
restrained until the end of the caster's next turn, with an `again` each turn), Wall of Force [341], Wall of Stone
[342], Yolande's Regal Presence [346] (an `aura` op 10 feet, Wis save 4d6 psychic; its prone and push as you can).

## Checking your work

- `.venv/Scripts/python.exe -m pytest -q -n 3 tests/test_engine.py tests/test_schema_data.py` (the data loads; every op,
  key and zone kind is known) — use `-n 3`, never more (other helpers run beside you).
- `.venv/Scripts/python.exe -m pytest -q -n 3 tests/test_catalogue.py -k "<your ids, separated by ' or '>"`: every
  spell is cast in a real fight, the fight goes on to its end, and the Auto sees the spell's worth. A worth failure
  may be the main session's to fix (the Auto's valuation code): say which in your reply rather than bending the
  spell. Other failures are yours.
- Your final reply: the ids written, anything left out and why, test results, and any kernel gap you noticed.
