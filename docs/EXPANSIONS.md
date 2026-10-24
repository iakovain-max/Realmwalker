# Realmwalker – The Expansion Programme

*Architecture and step-by-step instructions for Claude Code. Prepared on 2026-10-11 for Anton from a read-only survey of the game (`D:\Project Dawn`, branch `world-variety`, about 59,000 lines of Python, 1,108 tests) and of his three D&D books (`C:\Users\Alpine\Desktop\5.5e DND`).*

> **Kick-off line for every later session:** "Continue the expansion programme: read `docs/expansions/STATUS.md`, then the current expansion's section of `docs/EXPANSIONS.md` and its design note in `docs/expansions/`, and carry on from the first unticked step."

---

## 0. Read this first

You are Claude Code, working on Realmwalker for Anton. **Anton is not a programmer.** He wants everything in his three D&D books – the *Player's Handbook* (2024), the *Dungeon Master's Guide* (2024) and the *Monster Manual* (2025) – that can sensibly live in a PC game brought into Realmwalker, and delivered as a series of themed expansions ("DLCs"), each named after two related things in the style he chose: *Demigods & Magics*, *Tieflings & Warlocks*. Each finished expansion adds a small picture to the right of the main menu; pointing at it with the mouse shows the expansion's name and what it added.

This document is the master plan for that programme. It does not replace `CLAUDE.md` (the rules of the codebase) or `docs/DESIGN.md` (the base game's design). Where this plan and `DESIGN.md` disagree about D&D rules, this plan wins (Anton asked for the books' rules); where they disagree about tone, simulation or presentation, `DESIGN.md` wins.

### 0.1 Your first session

1. **Never work alongside another session.** When this plan was written (2026-10-11, 14:40) a Claude Code session was in the middle of the *World Variety* work: branch `world-variety`, plan `docs/superpowers/plans/2026-10-11-world-variety.md`, design `docs/WORLD_VARIETY.md`, with uncommitted changes (`data/cultures.json`, `realmwalker/world/cultures.py`, `realmwalker/world/names.py`, edits to `names.json`, `place_names.json`, `races.json`, `factions.json`, `history.json`, `law.json`, `schemas.py`, `registry.py`, `tables.py`). If this plan was pasted into *that same* session, simply finish World Variety first (point 4). If you are a *new* session and `git status` shows uncommitted changes you did not make, first ask Anton, in one short message, whether another Claude Code session is still working in this folder. While one is, do nothing in the folder – no commits, stashes, resets or branch switches; this is the one thing worth waiting for. Once he says no other session is running, those uncommitted changes are World Variety's unfinished work: continue them from their own plan, on their own branch.
2. If this plan reached you as a pasted message, save it **verbatim** as `docs/EXPANSIONS.md` and commit it on the branch you are working on (`world-variety` while you finish that; the plan is documentation and may ride along with it). From then on re-read sections of that file rather than relying on memory. It is long: read §0–§5 fully once; afterwards read only the section of the expansion you are on and the appendices it points to.
3. Read `CLAUDE.md`, `docs/CLOUD_HANDOFF.md` (its rules for long unattended work apply on Anton's PC as well; where it speaks of pull requests, the friends' build or Player2, this plan replaces it), the newest entries of `docs/PROGRESS.md`, and `docs/WORLD_VARIETY.md`.
4. **World Variety comes first.** The peoples, towns and dress of the expansions are built on its culture registry (`data/cultures.json`, `world/cultures.py`), name forge (`world/names.py`), biome families, town styles (`data/towns.json`, `world/towns/`), townsfolk life and dress-by-people. Finish it by its own plan and send it to GitHub as §0.3 describes (merged into `main` and pushed), unless Anton has already merged it. Where this plan names a World Variety file or function that ended up named differently, use what World Variety actually built.
5. **Clear the decks** (§0.4): remove the friends' build, the Player2 AI writer, letters mode and the code kept alive for old saves and old worlds, and set up faster test tools.
6. Create `docs/expansions/STATUS.md` from the template in §5.5 and keep it current at the end of every working step: it is how the next session, and Anton, know where things stand.
7. Begin Expansion 1, *Dice & Destiny* (§6.1). Work through the expansions in the order of §6 unless Anton reorders them; the "Needs" column of the table in §6 says what truly has to come first.

### 0.2 Every later session

"Continue the expansion programme" means: read `docs/expansions/STATUS.md`, then the current expansion's section here, and its design note and task list in `docs/expansions/`, and carry on from the first unticked step.

### 0.3 How Anton likes to work

- He is usually away while you work and cannot try each small tweak. Take a whole expansion and finish it. Do not stop to ask what you can decide from the books, the code, this plan or a sensible default; write down what you assumed (in `STATUS.md` and the release notes) and carry on. Stop only for a decision that would waste the work if guessed wrong, and even then do everything that does not depend on it first.
- Explain everything in terms of what changes when he plays. Never ask him to edit code. When he must do something, give Windows click-by-click steps.
- **Each finished piece goes straight to GitHub.** Work on one branch per expansion (`dlc/NN-short-name`, from `main`) and push it as you go, as a backup. Commit after every working step with its own tests green. When the expansion – or one of its parts (§5.0) – meets the definition of done (§5.2), merge it into `main` and push `main` to GitHub. When the whole expansion is done, also tag it (`v1.N.0`), push the tag, and publish a GitHub release whose notes are written for Anton (§5.3) – with `gh release create` if the GitHub CLI is installed, otherwise the tag plus the same notes in `docs/PROGRESS.md`. Do not wait for Anton to merge anything: `Update_And_Play.bat` brings each release to his PC, and friends download the game from GitHub. (There are no pull requests and no stacked branches any more.)
- **`main` is what Anton and his friends play.** Never merge anything into it that has not passed §5.2. If something on `main` turns out broken, fix it at once or revert the merge, then carry on.
- `CLAUDE.md` says to stop for feedback after a milestone "unless the user said to keep going". For this programme Anton has said to keep going: when an expansion is on GitHub, carry straight on with the next one unless he asks you to pause.

### 0.4 Clearing the decks (after World Variety, before Expansion 1)

Anton asked for these clear-outs before the expansions begin. Do them on one branch, `prep/clear-the-decks`, and send it to GitHub (§0.3) when everything is green. It gets no icon.

**A. No more friends' build.** Friends will download the game from GitHub instead. Delete `Build_For_Friends.bat`, `tools/build_friends.py`, `realmwalker.spec` and `pyinstaller` (from `requirements.txt`). Remove the code that only the packaged `.exe` needed (the "frozen" branches in `realmwalker/paths.py` and whatever calls them) if the tests stay green without it; otherwise leave those few lines and say why. Remove the friend-build mentions from `CLAUDE.md`, `docs/CLOUD_HANDOFF.md` and the tests; keep `assets/icon.ico` if the game window uses it. On Anton's disk, delete the old build output – `dist/`, `Realmwalker.zip` and PyInstaller's work folder `build/realmwalker/` (check first that it is that) – but **keep everything else in `build/`**: the tile and sound sources live there. Turn `README_FRIENDS.txt` into `README.md`, the repository's front page on GitHub: what the game is; how to get it (on GitHub, Code → Download ZIP and unzip it, or `git clone`); double-click `Play.bat`, which sets everything up the first time; how to update (with a ZIP, download the newest one; with `git clone`, double-click `Update_And_Play.bat`, which needs Git for Windows); the keys; the credits. Make sure a fresh download really runs this way.

**B. No more Player2 AI writer, for now.** Every AI task already has built-in text behind it, and the smoke test already plays with the AI switched off, so it can go safely. Before removing anything, tag the last commit that still has it (`before-ai-removal`) and push the tag, so it can be brought back one day. Then:
- every place that asks the AI – backstories at creation, conversations, settlement, region and dungeon descriptions, travel days, the chronicle, obituaries, magic item names and stories, quest-givers' words – uses its built-in text directly;
- delete `realmwalker/ai/`, `ai/prompts/`, `tools/mock_player2.py`, the Player2 test screen and its title-menu entry, the AI settings (AI on/off, AI extras, AI debug log), the `player2_*` and `ai_workers` config fields, the AI status in the side panel, the debug console's AI commands, the AI-only tests and the AI halves of mixed tests, and autoplay's pretend-AI mode;
- keep a store of generated text only if built-in text also uses it (move it out of `ai/`); remove AI-only data fields (such as `ai_style` in `cultures.json`) together with their schemas; bump `FORMAT_VERSION`;
- then read the built-in text in each of those places as a player would, over many runs: wherever it is thin or repetitive, write more. The `tests/test_text_variety.py` floors are the minimum, not the goal;
- update `CLAUDE.md` and `docs/CLOUD_HANDOFF.md` (no Player2 section; the "AI writes words" rule goes; "AI" now means only the game's tactics). Leave `docs/DESIGN.md` as it is – it is Anton's own text – and record the change in `docs/PROGRESS.md`.

**C. Faster tools.** Add `requirements-dev.txt` (`pytest-xdist`, `pypdf`, `pypdfium2`); make the suite pass in parallel (`pytest -n auto`, fixing any test that shares files or state); mark slow tests (`@pytest.mark.slow`) so that `pytest -m "not slow"` is a quick check; autoplay now has one mode.

**D. No more letters mode.** Pictures are now the only way the game is drawn. Remove the Letters choice (`config.GRAPHICS_CHOICES`, `Settings.graphics`, the Graphics row in Settings), the letters drawing of maps (`ui/map_render.py`), and every `canvas.gfx is None` alternative – in the screens, the battle board, the side panel, the map legend, and the title screen's block-letter logo and drawn backdrop; autoplay's `--letters` option; and data fields that only letters used (such as `glyph` and `fg` on site, settlement and creature types – keep any field the pictures also use). The text of menus, logs and panels stays: it is part of the picture mode. Tests and autoplay then draw everything through a headless recording graphics context, as `tests/test_graphics_ui.py` already does, so every screen's pictures are exercised in every run. If a PC cannot start the picture renderer, show a clear message that says so (and log it) instead of falling back to letters.

**E. No more old saves and old worlds.** Anton does not mind updates breaking saves, and keeping old ones alive must never hold the design back. Remove the save migration chain (`MIGRATIONS` and the `_v*_to_*` functions in `game/save.py`): a save of an older format is refused with the friendly message – never a crash, never a deleted file. Remove the code that exists only for old saves and old worlds: the "told" history for worlds made before the lived ages (`world/history.py`), factions added to worlds made before them (`world/factions.py`), the way down added to maps made before dungeons (`world/dungeon.py`), the readers in `game/past.py`, `world/legends.py` and `world/ages/ties.py` that cope with worlds without the ages, packs put on characters made before packs were worn, companions' coin from older saves, and every other such branch (search for "older", "old save", "made before"). Every world is now made fresh with everything the game knows. **Keep** the id lists stored beside index arrays (`remap_for`, `_biome_remap`): they are not for old versions – they stop an ordinary change to a data file from silently scrambling a current save.

**F. Other leftovers.** The creatures' `rank` field (front or back) belongs to the old two-rank combat; Expansion 1, Part C replaces it with each creature's role and preferred range (§4.7). Move the `docs/PROGRESS.md` entries from before version 1.0 into `docs/PROGRESS_ARCHIVE.md`, so the file each session reads stays short. Anything else that exists only for an older version of the game goes the same way. List everything removed in the `docs/PROGRESS.md` entry.

**Done when**: the full suite, autoplay and the window smoke test pass; the game starts, plays, saves and loads with no AI, no packaging, no letters mode and no old-save code left; a save of an older format is refused kindly; a fresh download from GitHub plays through `Play.bat`; `README.md` reads well on GitHub; `docs/PROGRESS.md` says in Anton's words what went and why.

---

## 1. What "everything from the books" means

### 1.1 In scope

**Player's Handbook (2024)**: all 12 classes to level 20 and all 48 subclasses; all 10 species with their lineages, legacies and ancestries; all 16 backgrounds; all feats (origin, general, fighting style, epic boons); all equipment (weapons with Weapon Mastery, armour, adventuring gear, tools and what they are used for, mounts and vehicles, services, trinkets); crafting (gear, potions of healing, spell scrolls); every spell (about 390, cantrips to 9th level); multiclassing and starting at higher levels; the whole Rules Glossary (conditions, actions, areas of effect, cover, hiding and invisibility, flying, swimming, climbing, jumping, falling, suffocation, grappling and shoving, unarmed strikes, mounted and underwater combat, Heroic Inspiration, Bloodied, exhaustion, resting and the rest); the creature stat blocks of Appendix B (familiars, steeds, summoned forms, Wild Shape beasts, primal companions); the multiverse of Appendix A.

**Monster Manual (2025)**: every stat block – about 500 – with traits, actions, bonus actions, reactions, legendary actions and resistances, lairs and their regional effects, spellcasting, habitats, treasure themes and groups.

**Dungeon Master's Guide (2024)**: every magic item (several hundred entries, many with variants), artifacts, sentient and cursed items, the treasure and random-magic-item tables, magic item crafting; the DM's Toolbox systems that can run inside a game – chases, curses and magical contagions, environmental effects, fear and mental stress, firearms and explosives (as limited in §1.3), hazards, mobs, objects, poisons, siege equipment, supernatural gifts (blessings and charms), traps, renown and marks of prestige, settlement traits and calamities, travel; encounter building and XP budgets; bastions; the cosmology (as reachable planar realms, Expansion 27).

### 1.2 The Realmwalker filter

Nothing is pasted in raw. Every class, species, spell, monster and item answers five questions before its codex entry may be marked done:

1. **Where does it live?** In the world – a people, a habitat, a lair, a shop, a hoard, a temple, a history – not only in a list.
2. **How rare is it?** Scaled by the world's *Magic* and *Danger* settings and by place. Magic stays "real, rare, costly and politically charged" (DESIGN.md §1 and §14); legendary things are few and have histories; enemies scale with the danger of the region, not with the party's level (DESIGN.md §6), so some fights should be avoided.
3. **How does the game play it?** Rules in code, content in data, and the enemy AI knows how to use it well (§4.7).
4. **What does it look and sound like?** A picture (sprite, doll layers or an effect) and a sound cue.
5. **What words describe it?** Original text in the game's own voice (never the book's prose), with enough variants where the player reads it often (`tests/test_text_variety.py` floors).

### 1.3 Adapted or left out (decided; Anton may change these – Appendix F)

- **Greyhawk** (DMG chapter 5), the **Lore Glossary** (DMG Appendix A) and the named gods and powers of the D&D multiverse are not transplanted: Realmwalker's worlds are generated and have their own faiths. Proper names that are part of game items (the Wand of Orcus, the Eye of Vecna, the Sword of Kas) keep their names; who made them and where they went is generated per world.
- **DM advice** (most of DMG chapters 1, 2, 4 and 5) is used as design guidance – attitudes, travel pace, encounter difficulty, rewards – not as content.
- **Firearms and explosives**: the Renaissance items only, as rare gnomish inventions (Expansion 18). The DMG's modern and futuristic weapons and its alien technology are left out; they break the setting.
- **The DMG's tools for the DM's own creations** (creating a background, a creature, a magic item or a spell, in chapter 3) are used as guidance whenever Realmwalker invents something of its own, and recorded as `omitted` with that reason. **Alignment** stays a field of stat blocks and sentient items (and matters on the planes, Expansion 27); there is no alignment system for the player.
- **The DMG's Appendix B maps** are not copied; they are used as archetypes for new site and dungeon styles (barrow crypt, caravan encampment, dragon's lair, dungeon hideout, keep, manor, mine, roadside inn, ship, spooky house, Underdark warren, volcanic caves, wizard's tower...).
- **Rules that would remove a Realmwalker system**: the game's own health (wounds, blood, infection, injuries, pain), survival (hunger, thirst, cold, wetness) and death rules stay on top of the book's hit point rules. A long rest restores hit points, Hit Point Dice and features as the 2024 rules say, but wounds still need tending and a body still needs food and warmth. Record every such adaptation in the codex (§4.2).

### 1.4 The 2024 rules replace the 2014 ones

Today the game follows SRD 5.1 (2014). The programme moves it to the 2024 rules throughout: species without ability score increases (these move to backgrounds); origin feats; Weapon Mastery; the 2024 conditions and exhaustion (−2 per exhaustion level on every d20 test and −5 ft of speed per level, death at 6); 2024 surprise (disadvantage on initiative instead of a lost turn); 2024 grappling and shoving (the target makes a saving throw); the Influence, Magic, Search, Study and Utilize actions; Heroic Inspiration; Bloodied; the 2025 monster stat blocks. Re-measure the game's balance after every rule change (§4.14): some changes make it gentler (surprise), some harsher (exhaustion), and the "fair chances" goals (`docs/PROGRESS.md`, Fair Chances) still stand.

### 1.5 Words and pictures we may use

- The PDFs are Anton's reference copies. **Never copy their prose** – descriptions, flavour, lore, sidebars – into the repository. Numbers, mechanics and names are fine. Write every description in the game's own voice. Tables whose entries are prose (the trinkets, the Wild Magic Surge table, curse and bastion event tables) are rewritten entry by entry in the game's voice, keeping each entry's mechanics. The "rules text" a player sees on hover is likewise the game's own summary.
- Text you extract from the PDFs goes to `build/codex/` only (git-ignored), never into a committed file.
- Pictures: the Dungeon Crawl Stone Soup tile pack (CC0, already used; 1,282 monster tiles are in `build/tiles_src`), pictures you draw in code, and other packs only if their licence is CC0 or CC-BY (credited in `docs/CREDITS.md` and `README.md`). Never NC, ND, "free for personal use", ripped assets or anything whose licence is unclear.
- Many monster and item names (beholder, mind flayer, githyanki, displacer beast...) belong to Wizards of the Coast. That is fine for Anton's own free game, shared with his friends through GitHub. Say in `docs/CREDITS.md` and `README.md` that the rules content is adapted from the D&D 2024 core books and that the game is a free fan project; never sell it or add anything paid without raising this with Anton first.

---

## 2. Where things are

| What | Where |
|---|---|
| The game | `D:\Project Dawn` (git; `main` is what Anton plays) |
| Player's Handbook 2024 | `C:\Users\Alpine\Desktop\5.5e DND\Player's Handbook 5-5e.pdf` (389 pages) |
| Dungeon Master's Guide 2024 | `C:\Users\Alpine\Desktop\5.5e DND\Dungeon_Masters_Guide_-_Wizards_of_the_Coast.pdf` (388 pages) |
| Monster Manual 2025 | `C:\Users\Alpine\Desktop\5.5e DND\Monster Manual.pdf` (390 pages, 330 MB) |

**Never write anything into the books' folder.**

### 2.1 Reading the books

All three PDFs are scans with an OCR text layer. The text layer is good enough for finding things but noisy: G is often read as C ("Ciant"), B as 8 ("8oar"), l, I and 1 and O and 0 are confused, small capitals come out garbled ("Fenr Lrsr" for "Feat List"), and two-column pages interleave. So:

- Write `tools/codex/extract.py` in Expansion 1 (using `pypdf`, listed in a new `requirements-dev.txt`, not in the game's `requirements.txt`) to dump the text of each page to `build/codex/<phb|dmg|mm>/p###.txt` for searching.
- **Every number that goes into data must be checked against the page image**, not only against the OCR text: open the page with your Read tool on the PDF (`pages: "N"`) and look. Stat blocks, tables and spell headers above all. If the Read tool cannot open a PDF that large (the Monster Manual is 330 MB), render the pages you need to PNG under `build/codex/pages/` with `pypdfium2` (also in `requirements-dev.txt`) and read those.
- **The books live on Anton's PC.** In a cloud session without them, do only work that needs no new numbers from the books (kernel, tests, pictures, world systems), or ask Anton to attach the pages you need. Never fill in book numbers from memory.
- Page numbers below are **PDF pages** (the printed page number + 3 in the PHB and the MM, + 4 in the DMG). Verify them ±1.

### 2.2 Page map (PDF pages)

**Player's Handbook**: Playing the Game 9–34 · Creating a Character 35–50 (Level Advancement 44, Starting at Higher Levels 46, Multiclassing 47–48, Trinkets 49–50) · Classes 51–178: Barbarian 53–60, Bard 61–70, Cleric 71–80, Druid 81–92, Fighter 93–102, Monk 103–110, Paladin 111–120, Ranger 121–130, Rogue 131–140, Sorcerer 141–154, Warlock 155–166, Wizard 167–178 · Backgrounds 180–188 · Species 189–200 · Feats 202–214 (feat list 202–203, origin feats from 203, general feats from 205, fighting style feats 212–213, epic boons 213–214) · Equipment 216–236 (weapons and mastery properties, armour, tools, adventuring gear, mounts and vehicles, services, crafting) · Spellcasting rules 238–241 · Spell descriptions 242–346 · The Multiverse 347–348 · Creature Stat Blocks 349–362 · Rules Glossary 363–380 · Index 381–389.

**Dungeon Master's Guide**: The Basics 9–24 · Running the Game 25–56 (travel pace about 42–43) · DM's Toolbox 57–108 (Chases 57–58, Curses and Magical Contagions 64–66, Environmental Effects 72–73, Fear and Mental Stress 74–75, Firearms and Explosives 76–78, Hazards 80–83, Marks of Prestige 84–85, Mobs about 86, Poison 94–95, Renown 96, Settlements 97–99, Siege Equipment 100–101, Supernatural Gifts 102–103, Traps 104–107) · Creating Adventures 109–130 (encounter difficulty and the XP budget per character 118–119, adventure rewards and treasure 124–127) · Creating Campaigns 131–176 (Greyhawk 147–176) · Cosmology 177–216 · Treasure 217–338 (magic item rules about 217–235, Magic Items A–Z about 236–329, the random magic item tables by theme – Arcana, Armaments, Implements, Relics – and rarity 330–338) · Bastions 339–357 · Lore Glossary 358–370 · Maps 371–388.

**Monster Manual**: introduction (parts of a stat block, running a monster) 4–12 · Monsters A–Z 13–350 · Appendix A, Animals 351–376 · Appendix B, Monster Lists 377–387 (2014→2025 stat block conversions 377, monsters by habitat 378–381, by creature type 382–384, by group 384, by Challenge Rating 385–387). Every monster entry names its **Habitat** and its **Treasure** theme; both are used (§4.6, §4.8).

---

## 3. Ground rules for this programme (in addition to CLAUDE.md)

- **Everything in `CLAUDE.md` still holds**: logic never imports UI; one seeded RNG per world (`rng.child("purpose")`, streams keyed on stable counters); data-driven with schemas validated at startup; code owns every number; never make the player wait; never crash; arrays indexed [x, y]; `data/*.json` is hand-formatted (targeted edits, never re-dump a file – the one deliberate exception is the one-off conversion of `spells.json` in Expansion 1, whose output must be laid out by hand-style rules, one spell to a few lines, as today); new save fields bump `FORMAT_VERSION`.
- **"AI" in this plan means only the game's own tactics** – the enemy's choices and Auto (§4.7). The Player2 language-model writer is removed in §0.4, and no expansion adds AI-written text: every word the player reads is written into the game.
- **Option lists come from data.** A feature, feat or spell that chooses among spells, beasts or other creatures (Magic Initiate, Polymorph, Find Familiar, Wild Shape, Create Undead, Conjure...) reads its choices from the loaded data, so it gains options as later expansions add them. It counts as done when it works with the options present, and its codex entry notes which later expansion widens it.
- **New content goes into content packs** (§4.1), not into the big base files, so that each expansion's data is its own small, readable set of files.
- **No special cases in the combat code.** New features, spells, traits and items are data on the rules kernel (§4.3). A Python handler only where data cannot express a rule, registered by id – never another `if feature == "..."` branch in `rules/combat.py`.
- **The codex is the checklist** (§4.2). An expansion is not finished while any codex entry assigned to it is still `todo`.
- **The player and the AI have the same options.** The battle screen and the enemy AI read the same list of possible actions (§4.3.7): whatever a player can do, the AI can do, and the reverse.
- **Original text only** (§1.5). A data description is one or two sentences in the game's voice plus the numbers the player needs.
- **Performance budgets** (measure them; put them in tests where practical): the game starts with every pack loaded in under 3 s on Anton's PC; an enemy's turn is decided in under 150 ms (95th percentile) and never over 400 ms; world creation stays inside World Variety's budgets (a large world with 1,000 years in under 30 s); the full test suite, run in parallel (`pytest -n auto`), finishes in under 10 minutes, and the quick subset (`pytest -m "not slow"`) in under 3.
- **Determinism**: same seed, same world, same fight. Every new random stream goes through `rng.child`.
- **Saves may break.** Anton does not mind updates breaking saves: never hold back a design to keep old saves working, and write no migrations. When what a save holds changes, bump `FORMAT_VERSION`, so that an older save is refused with the friendly message – never a crash, never a deleted file. Say at the top of the release notes when a new character or world is needed.
- **The books' folder is read-only. So is any work of another session** (§0.1).

---
## 4. Architecture

What the game is today, in one paragraph: Python 3.12, python-tcod with its SDL renderer, numpy, Pillow; all content in `data/*.json`, validated by `realmwalker/data/schemas.py` and loaded by `realmwalker/data/registry.py`; four classes (fighter, rogue, cleric, wizard) to level 10 with two subclasses each; five races; 41 spells resolved by a `kind` field; 35 creatures in SRD 5.1 form; magic items built procedurally from a property budget (`data/magic.json`, `game/magic_items.py`); battles on a grid in `rules/combat.py` (a ~3,000-line `Battle` class whose features are hand-written branches), the enemy's choices in `rules/tactics.py`; the lived history in `world/ages/`; pictures from the Dungeon Crawl pack and code-drawn art baked by `tools/build_tiles.py`. The architecture below keeps everything that works and adds what is needed to carry roughly ten times as much rules content.

### 4.1 Content packs and the expansion registry

```
data/
  *.json                       the base game, as today
  packs/
    01_dice_destiny/
      pack.json                the expansion's record (below)
      conditions.json          a new kind of file this pack introduces
      creatures.json           a fragment with the same shape as data/creatures.json
      ...
    07_tieflings_warlocks/
      pack.json
      classes.json  races.json  cultures.json  names.json  place_names.json  towns.json
      creatures.json  magic_items.json  history.json  quests.json  travel_events.json
      sprites.json  appearance.json  sounds.json ...
```

- The registry loads each base file, then **merges** the fragment of the same name from every pack, in pack `order`. Dictionaries merge by key. A key defined twice is a data error unless the later entry carries `"_replace": true` (for a pack that upgrades base content – Expansion 1 re-statting the old wolf, for instance). Lists merge only where the schema marks them appendable. Validation and cross-reference checks run on the merged result, so the existing schemas keep working unchanged.
- The registry records **provenance** – which pack each entry came from (`registry.origin(kind, entry_id)`) – so the main-menu tooltip can count what an expansion added and the codex test can check it.
- A pack may introduce a new kind of data file (`conditions.json`, `magic_items.json`, `bastions.json`...). Its schema is registered in `schemas.DATA_FILES` like any other.
- Packs are chapters of the game, not optional add-ons: every pack present is loaded. A pack under construction (`"status": "planned"`) may already hold data.
- `realmwalker/expansions.py` (logic, no UI) reads every `pack.json` and answers: the released expansions in order; each one's name, tagline, icon, accent colour, version, date and "adds" lines; live counts of what it added (from provenance).
- A pack may split one kind of file into several fragments – `creatures.devils.json`, `creatures.demons.json` – merged the same way. This lets parallel helpers (§5.0) each write their own file without stepping on one another.

`pack.json`, for example:

```json
{
  "id": "tieflings_warlocks", "order": 7,
  "name": "Tieflings & Warlocks",
  "tagline": "Born of old bargains. Sworn to new ones.",
  "icon": "dlc/tieflings_warlocks", "accent": [150, 64, 170],
  "status": "planned", "version": "1.7.0", "released_on": "",
  "adds": [
    "The Tieflings: three infernal legacies, their own names and quarters in the great cities, and a few cities still ruled by an old pact",
    "The Warlock, levels 1–20: four patrons, every eldritch invocation, the three pacts and the mystic arcana",
    "Every fiend of the Monster Manual – devils, demons, yugoloths and their kin – called up by cults in the world's history",
    "Infernal treasures, and contracts with a devil's small print"
  ]
}
```

Setting `"status": "released"` is the last step of an expansion (§5.1). Tests: every pack has a valid record; ids and orders are unique; every released pack has its icon in the tile atlas.

### 4.2 The codex: the books as a checklist

`docs/expansions/codex/` holds machine-readable lists of everything in the books – names and page numbers only, never book text:

| File | One entry per |
|---|---|
| `classes.json` | class; subclass; every class and subclass feature by level; every option list (maneuvers, invocations, metamagic, Wild Shape rules, Brutal Strike effects, Hunter's options...) |
| `species.json` | species; lineage, legacy or ancestry; trait |
| `backgrounds.json`, `feats.json` | background; feat |
| `equipment.json` | weapon; mastery property; armour; adventuring gear; tool; mount; vehicle; service; trinket table |
| `spells.json` | spell (level, school, classes, page) |
| `rules.json` | Rules Glossary entry; each PHB rules section; each DMG Toolbox system |
| `monsters.json` | stat block (type, size, CR, habitat, treasure, page), from the MM **and** the PHB's Appendix B; a creature printed in both books is one entry with both sources |
| `magic_items.json` | magic item (category, rarity, attunement, theme table, page); artifact; sentient and cursed item rules |
| `world.json` | bastion facilities, orders and events; planes and planar effects; settlement traits and calamities; supernatural gifts |

Every entry has `dlc` (the expansion that delivers it, from §6 and Appendices A–B), `status` (`todo`, `done`, `adapted`, `omitted`), `game` (the id or ids that implement it), `note` (required for `adapted` and `omitted`: what changed and why; an `omitted` entry must cite a §1.3 reason) and, where it applies, `upgrade_in` (the later expansion that completes an entry delivered in a simpler form – a spell whose full use needs ships, a feat whose subject arrives later). Each expansion checks the entries whose `upgrade_in` names it, and finishes them.

- **Build the whole codex in Expansion 1** from the books' own lists – the PHB's class tables, feat list and spell chapter; the MM's Appendix B (types, habitats, groups, CR); the DMG's Magic Items A–Z and random item tables – correcting the OCR by looking at the pages, and assign every entry to an expansion by the rules of §6 and Appendices A and B. Then the size of the whole programme is known from the start.
- `tests/test_codex.py`: every `done`/`adapted` entry's `game` ids exist in the loaded data; no released expansion still has `todo` entries; no entry belongs to two expansions; `omitted` and `adapted` entries have notes.
- `tools/codex/coverage.py` prints coverage by book and category ("Monster Manual: 212 of 503 done, 3 adapted"). Put its output in every release's notes.

### 4.3 The rules kernel

`rules/combat.py` resolves features with hand-written branches (`class_abilities`, `do_ability`, the `cast` method switching on `spell["kind"]`, `has_trait("...")` checks scattered through the file). That carried four classes and 41 spells. It cannot carry 12 classes, 48 subclasses, about 75 feats, about 390 spells, about 500 monsters and hundreds of items. Expansion 1 builds a small rules kernel and moves combat onto it piece by piece, with the existing tests green after every step.

#### 4.3.1 Layout

```
realmwalker/rules/engine/
  events.py       hook points and the dispatcher
  effects.py      effect operations ("ops") and apply()
  query.py        every derived number: AC, attack and save bonuses, speed, resistances, advantage...
  conditions.py   the 2024 conditions and exhaustion, defined as data (conditions.json)
  durations.py    how long things last and how they end (rounds, minutes, a save, concentration, dispelled)
  resources.py    pools and their recovery (spell slots, pact slots, rage, focus, sorcery points,
                  superiority dice, bardic inspiration, channel divinity, lay on hands, recharge 5–6, per day)
  targeting.py    target specifications and the 2024 areas (cone, cube, cylinder, emanation, line, sphere)
                  on top of rules/grid.py
  actions.py      the list of everything a creature can do right now (§4.3.7)
  reactions.py    reaction windows and decisions that pause the battle (§4.3.5)
  statblocks.py   a 2025 stat block turned into a creature's options (§4.3.8)
  transform.py    Wild Shape, Polymorph, Shapechange, lycanthropes, Large Form
  summons.py      familiars, steeds, primal companions, summoned and animated allies
  handlers/       Python for what data cannot say, by id: spells.py, <class>.py, monsters.py, items.py
```

The `Battle` keeps its outside shape (`start`, `step`, `pending_party`, the `do_*` methods, `events`, `result`) so the battle screen, `game/fight.py`, `game/arena.py`, `tools/balance.py` and the tests keep working while the inside changes.

#### 4.3.2 Content as data

A class feature, species trait, feat, spell, magic item property or monster action is a **definition**: what it costs, how it is aimed, its **effects** (built from a fixed vocabulary of operations), its **hooks** (when it applies) and how long it lasts. The shapes below are a guide; settle the exact schema in Expansion 1 and document it in `CLAUDE.md`.

```json
"hunters_mark": {
  "name": "Hunter's Mark", "level": 1, "school": "divination", "classes": ["ranger"],
  "cast": "bonus", "range": 90, "components": ["V"], "concentration": true, "duration": {"hours": 1},
  "target": {"kind": "creature", "seen": true},
  "effects": [
    {"op": "mark", "mark": "hunters_mark", "on": "target"},
    {"op": "hook", "event": "attack_hit",
     "if": {"attacker": "caster", "target_has": "hunters_mark", "attack": "weapon"},
     "do": [{"op": "damage", "dice": "1d6", "type": "force"}]}
  ],
  "upcast": {"duration": {"3": {"hours": 8}, "5": {"hours": 24}}},
  "fx": {"style": "mark", "color": "force"},
  "text": "You mark your quarry; your weapon finds it for an extra 1d6 force damage. Move the mark when it falls."
}
```

```json
"rage": {
  "name": "Rage", "use": "bonus", "cost": {"resource": "rage"},
  "duration": {"rounds": 1, "renew_on": ["attacked_enemy", "forced_save", "bonus_action"], "max_minutes": 10},
  "effects": [
    {"op": "modifier", "resist": ["bludgeoning", "piercing", "slashing"]},
    {"op": "modifier", "advantage": {"check": ["str"], "save": ["str"]}},
    {"op": "modifier", "damage_bonus": {"table": "rage_damage", "if": {"attack": "str_weapon_or_unarmed"}}},
    {"op": "modifier", "forbid": ["concentration", "casting"]}
  ],
  "ends_if": ["heavy_armor", "incapacitated"]
}
```

**Operations** (the starting vocabulary; add a new one only when a real piece of content needs it): `damage`, `heal`, `temp_hp`, `attack` (a weapon or spell attack with `on_hit` / `on_miss`), `save` (with `on_fail` / `on_success`, and half damage), `check` and `contest`, `condition` (apply or end, with how it ends), `modifier` (timed numbers and flags: AC, bonuses, advantage and disadvantage by scope, resistance, immunity, vulnerability, speed by mode, reach, size, critical range, senses, forbidden things), `mark`, `hook` (a temporary rule: event + condition + effects), `zone` (an area that stays: difficult terrain, obscurement, light or darkness, damage on entering or at the start or end of a turn, walls that block movement or sight), `move` (teleport, push, pull, swap places, fly, jump, forced movement), `summon`, `transform`, `resource` (spend, regain, convert), `choice` (the actor chooses one of several effects – on the player's screen, or by the AI), `each` / `repeat`, `table` (roll on a table: Wild Magic Surge, Prismatic Spray, a curse), `dispel`, `counter`, `reveal`, `hide`, `invisible`, `illusion` (a figure or object that blocks sight until someone sees through it with a Study or Investigation check), `revive`, `restore` (end conditions, exhaustion, curses, diseases – through the game's health system), `light`, `object` (break, open, lock, create), `special` (calls a registered handler).

Unknown operations and unknown handler ids are **data errors at startup** (the friendly data-problems screen, as today). A test loads every definition in every pack and checks that every operation and handler resolves.

#### 4.3.3 Events (hook points)

`battle_start`, `round_start`, `turn_start`, `turn_end`, `round_end`; `initiative`; `d20_before` (advantage, bonuses, replacing a roll – Portent) and `d20_after` (rerolls and additions to a failed roll – Lucky, Bardic Inspiration, Indomitable, Heroic Inspiration, Cutting Words, Bend Luck); `attack_declared`, `attack_hit`, `attack_missed`, `critical`; `damage_incoming` (reductions: resistance, Uncanny Dodge, Deflect Attacks, Arcane Ward, Interception, Stone's Endurance) and `damage_taken` (concentration, Hellish Rebuke, Armor of Agathys, Retaliation); `hp_zero` (Relentless Endurance, Relentless Rage, Undead Fortitude, Death Ward) and `killed` (Dark One's Blessing, Great Weapon Master's Hew); `spell_declared` (Counterspell, Mage Slayer) and `spell_cast` (Wild Magic Surge, War Magic, Arcane Ward); `saving_throw` (auras, Magic Resistance, Legendary Resistance, Evasion); `condition_applied` and `condition_ended`; `move_step`, `leave_reach` (opportunity attacks), `enter_reach` (Polearm Master, Sentinel); `ally_attacked` (Protection, Interception); `healed`; `legendary_window` (right after another creature's turn); and outside battle `short_rest`, `long_rest`, `dawn`.

Dispatch is deterministic (initiative order, then fighter id), and every hook declares whether it uses a reaction.

#### 4.3.4 Numbers through one door

`query.py` computes every derived number from the base sheet plus everything active on the creature – conditions, features, spells, items, zones, auras – with the 2024 stacking rules: the same effect from two sources does not stack (the most potent applies), differently named bonuses add up, advantage and disadvantage cancel. `Fighter.ac`, `save_bonus`, `speed`, the battle screen's attack preview ("62% to hit – half cover, advantage from Faerie Fire") and the AI's estimates all call it, so they can never disagree.

#### 4.3.5 Reactions and decisions that pause the battle

Today opportunity attacks and Shield fire by themselves. With Counterspell, Absorb Elements, Hellish Rebuke, Parry, Riposte, Cutting Words, Deflect Attacks, Uncanny Dodge, Interception, Sentinel, Portent and the rest, the player must be able to choose. Make the resolution of an action **resumable**: an action resolves in stages, and at a *reaction window* the battle can stop with a `pending_decision` – who may react, with what, at what cost, and the numbers – exactly as it stops today at `pending_party()`. The battle screen shows a compact prompt ("The cult fanatic casts Hold Person on Mira. Counterspell? [Yes – a 3rd-level slot] [No]"). Enemies and Auto companions answer at once through the AI (§4.7). Python generators (a resolution that `yield`s a prompt and is resumed with the answer) suit this; whatever you choose, the interface must never block, and tests must be able to answer prompts.

A new setting, **Reactions** (in Settings, after "Companions in a fight"): *Ask me* – the default: asks for spells and anything that spends a limited resource, while free and obvious reactions (an opportunity attack on a fleeing enemy) happen by themselves – *Ask for everything*, or *Decide for me*.

#### 4.3.6 Movement in three dimensions, and the rest of the battlefield

- **Elevation**: `Fighter.z` in feet. Flying (and hovering), levitating, jumping (long and high jumps from Strength), climbing; falling – a flier knocked prone, at speed 0 or incapacitated falls unless it hovers – with the 2024 falling damage. Distance and reach are measured in three dimensions on the 5-5-5 grid (the larger of the horizontal and vertical distance). The battle board draws fliers lifted above a shadow with a small height label. (Height of the ground itself – ledges, stairs, balconies – is welcome where maps have it, but not required.)
- Swimming and burrowing speeds; underwater rules (Expansion 23); mounted rules (Expansion 10).
- **Size and space**: Tiny creatures and swarms may share squares; squeezing through narrow spaces; Huge (3×3) and Gargantuan (4×4) footprints.
- **Senses**: blindsight, darkvision, tremorsense, truesight; lightly and heavily obscured areas; magical darkness; the 2024 Invisible condition and hiding (a creature that hides successfully is Invisible until found). **Telepathy** as a way of speaking (it matters for parley, Command and silenced casters).
- **Changing sides**: a charmed, dominated or possessed creature can act for another side until freed – including a companion, whom the AI then plays against the party. Many expansions need this (Dominate Person, fiends' and ghosts' possession, vampires, mind flayers), so it is built here.
- **Antimagic**: an area where spells, magic item properties and summoned creatures are suppressed (Antimagic Field; later the beholder's cone).
- **Objects** on the field (doors, chests, barrels, carts) have AC and hit points as in the DMG's "Objects"; they can be broken, burned, or opened by spells.
- **The missing actions**: Ready (with a trigger the player picks from a short list), Study (it replaces today's automatic knowledge checks at the start of a fight with a choice: learn a creature's resistances, immunities and tricks), Search, Influence (parley and intimidation in battle, and conversation outside it), Utilize, Magic.

#### 4.3.7 One list of possible actions

`engine.actions.options(battle, fighter)` returns everything the fighter can do now: moves; the Attack action with each weapon and its mastery; every action, bonus action and reaction granted by features, spells and items; each with its cost, its legal targets, an area preview and an estimate (chance to hit or to fail the save, expected damage, who would be caught in the area). The battle screen's action bar and menus, the in-battle spell list, Auto and the enemy AI all read this list. `class_abilities`, `bonus_options` and `do_ability` become thin wrappers around it, and then go away.

#### 4.3.8 Stat blocks

`statblocks.py` reads the 2025 stat block format from data: initiative (bonus and score), AC, hit points (dice), speeds (walk, fly, hover, swim, climb, burrow), abilities and saving throws, skills, senses, languages, CR, XP and proficiency bonus, resistances, vulnerabilities, damage and condition immunities, gear, traits, actions, bonus actions, reactions; **Multiattack** in the 2025 wording ("two Rend attacks"; "three attacks, using Bite or Claw in any combination; it can replace one attack with a use of Spellcasting"); **Recharge** ("Recharge 5–6", rolled at the start of its turn); uses per day; **Spellcasting** the 2025 way (at will and N/day lists, no slots) and the old way with slots for creatures that keep them; **Legendary Resistance** ("3/Day, or 4/Day in Lair"); **Legendary Actions** ("Legendary Action Uses: 3 (4 in Lair)", spent right after another creature's turn – the 2025 book has no separate lair actions on initiative 20); **lair effects**, the regional effects a legendary creature has on the land around its lair (§4.10).

Expansion 1 re-stats the game's existing 35 creatures to their 2025 versions, using the MM's conversion table (PDF 377): the old orc becomes a Tough or Warrior Infantry of the Orc species, the hobgoblin a Hobgoblin Warrior, the thug a Tough, the deserter a Warrior Infantry, and so on (Appendix A, "Expansion 1"). Rename ids freely, updating every reference in the data and the code (`history.json` beasts, the encounters); saved worlds do not matter.

**Species templates for people.** The MM's humanoid stat blocks (Bandit, Guard, Knight, Mage, Priest, Scout, Spy, Tough, Warrior...) describe people of any species. `apply_species(statblock, species)` adds the species' senses, resistances, traits and size and gives the doll the right body, so a dwarven guard, a drow mage and an orc warrior are each one stat block plus one species. Townsfolk, guards, soldiers, bandits and cultists everywhere are made this way, by the people of the place.

#### 4.3.9 Moving combat onto the kernel without breaking it

1. Build the engine beside the old code, with its own tests.
2. Route conditions and the `query.py` numbers first (AC, saving throws, advantage); compare old and new results in tests.
3. Convert `data/spells.json` from `kind` to `effects` (a one-off script whose output you check by hand); keep the old reader until every spell passes through the new one.
4. Move class features, monster traits and item properties to definitions and handlers, one at a time; delete each old branch when its tests pass on the new path.
5. Keep `battle.events` and their meaning, because `ui/gfx/battlefx.py` (animation) and `audio/cues.py` (sound) read them; every new kind of event gets a fallback picture and sound.

Balance must not drift during the refactor: run `tools/balance.py` before and after, and keep `tests/test_balance.py` green without widening its bands.

### 4.4 Characters and progression to level 20

- `data/rules.json`: `max_level` 20; the 2024 XP table (300, 900, 2,700 ... 355,000) and proficiency bonus to +6; level 19 grants an Epic Boon feat (or another feat).
- Class data runs to level 20 with the 2024 features, each one a definition (§4.3.2).
- **Choices** generalize `Character.pending` and `rules/progression.py`: subclass; ability score increase *or* a feat; epic boon; fighting style feat; Weapon Mastery picks; expertise; cantrips and spells (prepared casters change their prepared spells after a long rest; wizards also add to their spellbook); maneuvers; eldritch invocations; metamagic; pact boon; Wild Shape forms known; primal companion; Hunter's options; and every other option list in the books. `auto_resolve` makes sensible picks for companions by archetype and role, never at random.
- `Character` gains `feats` (with their own choices), `choices` (option picks per feature), `resources` (current pools – today's `uses`), `masteries`, `heroic_inspiration`, `species` and `lineage` (replacing `race`), and `classes` – a list of {class, subclass, level} for multiclassing (Expansion 15). Store it as a list from the start, with one entry.
- **Backgrounds (2024)**: ability score increases (+2/+1 or +1/+1/+1 among the three abilities the background names), an origin feat, two skills, a tool, equipment or gold – plus Realmwalker's own social ties and starting places, which stay. The eight existing backgrounds map onto 2024 ones (Folk Hero → Farmer, Outlander → Guide, Guild Artisan → Artisan; Soldier, Acolyte, Criminal, Noble and Sage keep their names) and the other eight are added (Charlatan, Entertainer, Guard, Hermit, Merchant, Sailor, Scribe, Wayfarer).
- **Species (2024)**: traits only; a size choice where the book offers one; lineage, legacy or ancestry as a choice; lineage spells. The character's people (`culture`, from World Variety) stays a separate choice: a goliath can be born among the Northmen.
- **Character creation** follows the 2024 order (class → background → species → languages → ability scores → details and looks), keeping point buy and adding the standard array and rolling 4d6.
- **Screens for twenty levels**: the character sheet gets tabs (Features, Resources, Feats, Spells, Proficiencies); the level-up screen handles every kind of choice with a description and a "Suggest" button; the spell screen filters by level, school, concentration, ritual and prepared; every feature shows its rules text and numbers on hover; every page fits at three window sizes (`tests/test_screens_fit.py`).

### 4.5 Spells, in battle and out of it

In battle a spell is a definition (§4.3.2): targeting, area, casting time, components, concentration, duration, upcasting, and an `fx` entry for the battle board (§4.11). **Components matter**: verbal and somatic components can be prevented (gagged, bound, Silence); costly material components are spent from the pack (Revivify's diamond) and must be bought; Subtle Spell hides a casting from witnesses, which the law system cares about. Rituals take ten extra minutes and no slot. Casting in public meets the law of the place (`law.json`: magic legal, licensed or forbidden).

Out of battle, spells plug into Realmwalker's own systems; **Appendix C** lists each group and its hook. In short: healing and restoration through `rules/health.py` (wounds, diseases, poison, exhaustion, curses); food, water and shelter magic through survival and camp; disguise, invisibility and enchantment through the law and conversation systems (whitelisted outcomes, and people who remember having been charmed); speaking with the dead, animals and plants as conversations (written lines, varied by who is speaking); languages against the game's languages; locks, traps and secret doors through `game/dungeon.py`; divinations answered from the world's real history (`world.politics`, the Legends book data); finding and scrying on the world map; Sending to people the party knows; teleportation and other fast travel (with the book's mishap chances, and the survival clock still running); Control Weather overriding the weather function for a region and time; resurrection through `game/death.py`.

**Death stays grim.** Raise Dead, Resurrection, True Resurrection and Reincarnate exist, but they are high level, need costly components and a body, and temples sell them at great prices and only to those in good standing. When the player character dies, the game offers a last chance only if someone in the party can cast such a spell in time, with what it needs; otherwise death is final, as now. Revivify keeps its one minute.

### 4.6 Monsters

- Every MM stat block becomes a creature definition (§4.3.8) in its expansion's pack, with: `habitat` mapped to the game's biomes – Arctic → tundra, glacier; Coastal → coast; Desert → desert, dunes, salt flat, badlands; Forest → forest, pine forest, jungle, fey forest; Grassland → plains, steppe, savanna; Hill → hills; Mountain → mountains, high mountains, volcanic; Swamp → marsh; Underdark → deep dungeon levels and the Underdark (Expansion 20); Underwater → sea and lakes (Expansion 23); Urban → towns; Planar → planar realms (Expansion 27) – and its `treasure` theme, `groups` (whom it is found with), `morale` (the game's types: beast, bandit, soldier, coward, warrior, fanatic, mindless), `ai` hints (§4.7), `art` (§4.11), names and epithets where it can be a named individual, and original descriptions.
- **Encounters are built, not only hand-listed.** The DMG 2024 XP budget (low, moderate and high difficulty per character, DMG PDF 118–119) sets a budget from the region's danger, and a group is chosen from the creatures of the habitat by family templates: a pack, a band, a lone hunter, a lair guardian, a patrol, a swarm, a master with its servants. The hand-written encounters in `creatures.json` stay. Each family template gets intro lines (at least four variants), and the generator fills in the creatures' names.
- **Lairs**: every legendary monster has a lair site and a dungeon style; fought there, it has its in-lair uses; its regional effects change the land around it (§4.10).

### 4.7 Tactics 2.0: an enemy that plays the whole game

The current AI (`rules/tactics.py`) already weighs squares and attacks well. It must now use every option of §4.3.7, and use them strategically.

**How a turn is chosen.** Generate the creature's options and prune them to the possible and plausible; estimate each with the same numbers the player sees; choose the best plan for the turn (movement, action and bonus action together, keeping the reaction in mind); act.

- *Damage*: chance to hit or to fail the save × average damage × resistances, summed over everyone caught, minus friends caught (callous creatures care less), plus a bonus for finishing someone off.
- *Control*: chance it lands × expected rounds × how dangerous the victim is per round (Hold Person on the paladin is worth more than on the commoner) × not already controlled.
- *Support*: healing where it keeps an ally standing; buffs by allies × attacks × rounds; summons by their expected damage over their duration.
- *Position*: cover; flanking; distance from melee for archers and casters; chokepoints; not bunching up against enemies that have area spells (smart creatures only); hazards and drops to shove enemies into.
- *Cost*: spell slots and limited uses are spent when the fight matters. A fight's importance is its threat compared with the creature's own strength: bosses and losing sides spend freely; a trivial fight is won with cantrips.
- *Concentration*: start a new concentration spell only if it beats the one being held; protect its own concentration (keep distance, Shield, Dodge); go after enemy casters who are concentrating.
- *Targets*: by threat, vulnerability, role (healer, controller, concentrating caster) and reach. Smart creatures focus their attacks; beasts go for the nearest or the weakest.

**How smart.** From the stat block: Intelligence and Wisdom set *smarts* (beasts and mindless creatures do not counterspell or read the battlefield; Intelligence 12+ uses combinations and focuses its attacks; 16+ plans around the party's casters), and the morale type sets nerve. Data may add `ai` hints: `role` (brute, skirmisher, artillery, controller, leader, support, lurker, solo), preferred `range`, `combos` ("grapple, then bite"; "Mind Blast, then Extract Brain on the stunned"), `opens_with`, `avoid`. A few signature behaviours need handlers: the beholder turns its antimagic cone onto casters and away from its own eye rays; dragons breathe first, fly out of reach and spend legendary actions between the party's turns; vampires charm the strongest; liches use Power Word Kill on the wounded; giants throw rocks from range; hags act as a coven; oozes engulf and split; mind flayers stun, then feed; swarms flow over the weakest.

**Teams.** At the start of each round each side picks a focus and roles: leaders buff, controllers do not stack the same effect, guards stay beside their leader to Protect or Intercept.

**Reactions and legendary choices** use the same estimates: Shield when it turns a hit; Counterspell what matters (3rd level or higher, healing on a dying ally, anything that would decide the fight); Legendary Resistance against save-or-lose effects, keeping the last one for the worst; legendary actions timed between the party's turns.

**Auto** (party members playing themselves, setting "Companions in a fight") uses the same planner with the party's weights: protect friends, never catch them in areas, keep resources for the rest of the day.

**Proof.** `tools/arena.py` fights seeded battles – each monster against parties of fitting level, and mixed groups against each other – and reports how often each option was used. `tests/test_tactics_coverage.py` asserts that every non-passive monster option is chosen at least once in a scenario built for it, that no illegal action is ever taken, that no fight hangs, and the timing budget of §3.

### 4.8 Magic items and treasure

- **The framework (Expansion 1).** Magic items are definitions on the kernel: properties as effects; **attunement** (three items at most; a short rest to attune; some only for a class or species); **charges** that recover at dawn by the book's dice; activation by the Magic action, a bonus action or a reaction; spells cast from items; **cursed** items (today's curses in `magic.json` fold into this); identification the 2024 way (handling an item through a short rest, Identify, or Detect Magic's aura); and the DMG's rules for **artifacts** (major and minor properties rolled per world, destruction) and **sentient items** (senses, communication, personality, purpose, conflict), so that any expansion can deliver a themed artifact or sentient weapon complete. `rules/magic.total(...)` becomes a thin reader over the kernel.
- **Realmwalker's own procedural items** (`game/magic_items.make`, named from the built-in word lists) stay as a family of their own – one-off heirlooms and "blades with a story" built from the same effects and rarity budgets – alongside the book's named items.
- **Treasure follows DMG chapters 4 and 7** (Expansion 1): individual treasure and hoards by Challenge Rating (Expansion 16 adds only the sizing of dragons' hoards by age and the business of carrying one away); magic items by the four themes – Arcana, Armaments, Implements, Relics – and rarity, rolled on the random tables (DMG PDF 330–338); each monster's own treasure theme from the MM; "magic items awarded by level" as a guide for quest rewards. An item not in the game yet is skipped and rerolled, so treasure grows richer as the expansions land.
- **Rarity and the world**: the world's *Magic* setting scales how often magic items appear. Common and uncommon items can be bought in cities (DMG prices by rarity, under the local law and suspicion); rare and better ones are found, earned or made; artifacts are placed in the world's history (Expansion 25).
- Each expansion brings the items of its theme (Appendix B); Expansions 24 and 25 bring the rest.

### 4.9 Peoples in the world

World Variety gives every people a culture record (`data/cultures.json`), names (`data/names.json` and the name forge), place names and geography words, realms and titles, laws, faith, a town style, dress (`data/sprites.json` figures "cultures"), a place in the history (`data/history.json` peoples) and a home climate. A species expansion adds, for each new people:

1. **The species** (`races.json`, 2024 traits, lineages/legacies/ancestries) and its **looks** (`appearance.json`: skins, eyes, hair, horns, tails, scales, markings – each option with a picture and a colour; `tests/test_looks.py`).
2. **A body** (`sprites.json` figures bodies; `tools/figure_art.py`) and **features** as doll layers (horns, tails, tusks, crests, scales, wings for transformations).
3. **One or more cultures**, distinct from every other: their own names (at least 150 given names per sex and 150 family or clan names, with the people's naming customs), place-name parts and geography words, realms and titles, laws, succession and growth, faith, dress and armour (new garments in `tools/figure_gear.py`), and a **town style** where they build towns (§6 says which).
4. **A place in the history**: how they came to be where they are, what they founded, fought and made, and events that belong only to them.
5. **Where they live today**: homelands on the culture map; minorities in other peoples' towns, with standing between peoples; companions and heroes of that people; Legends book pages.
6. **Words**: enough built-in descriptions, greetings and lines that people of that culture sound like themselves.

### 4.10 Monsters in the world

Each monster expansion places its creatures in:

- **Encounters** on the roads and in the wild, by habitat and danger (§4.6), by day and by night, with intro lines.
- **Dungeons and sites**: inhabitants by dungeon style (`creatures.json` `site_inhabitants`, `data/sites.json` dungeon styles), and new site and dungeon styles where a family needs one – a giant's steading, a vampire's castle, a lich's tower, a beholder's lair, a hag's hut, a drow city – each with its own map rules, furnishings and light.
- **The lived history** (`world/ages/`, `history.json` "beasts" and tribes): named legendary monsters with lairs, deeds, victims and slayers; monster societies as tribes and factions (goblinoid warbands, gnoll packs, kobold warrens, giant clans, hag covens, sahuagin raiders, drow houses, fiend cults, vampire courts); events (raids, abductions, a dragon's tribute, a lich's rise, a vampire court taking a town by night, an infernal pact).
- **While you play**: news and rumours at inns, travel events (`travel_events.json`), quest templates (`quests.json`: hunts, rescues, bargains, lifting curses), notice boards, a beast coming down on the farms (`Politics.beast_comes`), and **regional effects** around legendary lairs (a green dragon's woods grow mazy, a lich's land goes cold and quiet, a kraken's coast loses its boats).
- **The Legends book** gives named monsters their pages; the death screen and the obituary know what killed you.

### 4.11 Pictures, effects and sounds

- **Monsters**, in order of preference: (1) the Dungeon Crawl pack (1,282 monster tiles in `build/tiles_src`), mapped in `tools/build_tiles.py` `CREATURES` and recoloured where one picture serves several (the ten dragon colours, the mephits' elements, the slaadi); (2) people and humanoid monsters as **dressed dolls** (`sprites.json` figures "creatures") on their species' bodies; (3) everything else **drawn in code** in a new `tools/monster_art.py` (palette ramps, outlines, shading and dithering helpers in the manner of `tile_art.py`); (4) other CC0 or CC-BY art, only as §1.5 allows.
- **Style**: 32×32 base tiles toned by the `GRADES` of `build_tiles.py`; a one-pixel dark outline; light from the top left; silhouettes that read at game size. Large and bigger creatures are drawn at 32×32 and scaled up by their footprint, as today, unless the atlas supports bigger sources – then draw Huge and Gargantuan ones at 64×64.
- **Look at your art.** `build_tiles.py --preview` writes a contact sheet; enlarge it four times and open the PNG with your Read tool. Redraw anything that does not read at game size. Anton judges the look on Windows: list in the release notes where to see each new picture.
- **Adapt, do not paste.** Borrowed tiles pass through an adaptation step in `build_tiles.py` so that they look like Realmwalker's own art, not another game's: colours mapped onto the game's palette (keeping each creature's colour relationships); a consistent one-pixel dark outline; light from the top left (a highlight and shade pass); the pack's glows and background artefacts removed; size and foot line set to the game's figure scale (a wolf smaller than a man, feet on the same line as the dolls). Per creature, small improvements in code where they help: recolouring regions, adding or removing a part, combining two tiles (an owlbear from a bear and an owl). Any tile can opt out of a step that makes it worse. The contact sheet shows each borrowed tile before and after, side by side. The pass is built in Expansion 1 and applied to the creatures already in the game too, so old and new match. Full hand-redraws of borrowed tiles are not required for now.
- **Spell and ability effects**: every spell and visible ability has an `fx` entry – `bolt`, `ray`, `beam`, `burst`, `cone`, `line`, `aura`, `wall`, `rain`, `zone`, `summon`, `teleport`, `heal`, `buff`, `curse`, `mark`, `transform`... – coloured by damage type. `ui/gfx/battlefx.py` draws them generically, with special treatment for the great spells (Meteor Swarm, Prismatic Spray, Wish, Storm of Vengeance).
- **Condition, status and mark icons**: small pictograms over figures, with their cards (§4.15), drawn in `tile_art.py`.
- **Sounds**: every new effect maps to a sound in `data/sounds.json` through `audio/cues.py` (by damage type and effect style); new monster families get a voice (growl, hiss, moan, roar) family. New sounds follow the existing pipeline (`tools/build_sounds.py`, CC0 sources, one loudness).
- **Expansion icons**: §4.13.

### 4.12 The interface at full size

- **Battle**: the action bar groups options (Attack, Spells, Features, Items, Move, Other) with hotkeys and a filter; spells offer the slot level; reaction prompts (§4.3.5); an enemy's card shows its legendary actions and resistances left and what the party knows about it (Study); fliers and their height are shown.
- **Character**: the sheet's tabs; resources as pips; feats and choices; a level-up screen for every choice kind.
- **Spellbook**: filters, prepared lists, rituals, scrolls to copy, casting outside battle.
- **Creation**: the 2024 order; pictures of species and lineages; backgrounds with their feats; culture chosen separately from species.
- **Tooltips and status icons** on everything (§4.15).
- Everything works with the keyboard alone; every new screen goes into the autoplay bot's key lists and the window smoke test's tour.

### 4.13 The expansion shelf (main-menu icons)

- **Where**: on the title screen (`ui/screens/title.py`; the painted path is `_render_painted`), a column of framed icons along the right edge, top to bottom in release order, wrapping into a second column when the window is short. Each icon is 32×32 pixel art in a 40×40 frame (64 in a 72 frame on big windows); the frame takes the expansion's accent colour.
- **Pointing at an icon** shows a rich panel beside it (`ui/gfx/theme.panel`, like the menu's glass pane): the name in the title typeface; the tagline in italics; "Adds:" and the `adds` lines; live counts where they help ("1 class · 4 subclasses · 49 fiends"); "Version 1.6 · 2 November 2026". Clicking an icon, or pressing **E** on the title screen, opens the **Expansions** screen: every released expansion with its icon and full text. Planned expansions do not appear – they are surprises.
- A new icon glints softly until it has been pointed at once (the ids already seen are kept in Settings).
- **Data**: `realmwalker/expansions.py` (§4.1). Icons are drawn in `tools/tile_art.py` (a `dlc_icons()` group) and baked by `build_tiles.py` into the atlas as `dlc/<id>`. Icon style: 32×32, a single centred emblem, at most six colours plus the outline, the accent colour dominant, readable at actual size.
- **Tests**: every released expansion has an icon tile and a tooltip that fits; the title screen registers a hit area per icon at three window sizes; the Expansions screen renders; the autoplay bot visits it; the smoke test screenshots the shelf with a tooltip open.
- The shelf itself arrives with Expansion 1, whose icon is the first on it.

### 4.14 Testing, balance and proof

- **Per definition**: a parametrized test loads every spell, feature, trait, feat, monster action and magic item and resolves it in a tiny battle (or its out-of-battle hook) without error, and checks that its declared numbers (damage dice, DC formula, area) reach the right targets.
- **Golden tests** for the hard rules: counterspell chains, concentration, Wild Shape and its temporary hit points, Polymorph, Legendary Resistance, multiattack with Spellcasting, reaction prompts, elevation and falling, swarms, attunement limits, multiclass spell slots.
- **Balance**: `tools/balance.py` grows from levels 1 and 3 to levels 1, 3, 5, 8, 11, 14, 17 and 20, with parties of four built by `auto_resolve`, against encounters built to the DMG budget (low, moderate, high). `tests/test_balance.py` holds bands: a moderate fight is won most of the time without deaths, at every level; a high one is dangerous. Repeat the "careful player over many lives" measurement from the Fair Chances work after every rule change.
- Arena coverage (§4.7); codex coverage (§4.2); text variety floors; looks and pictures tests (`dolls.problems()`); screens fit; autoplay with new invariants (nobody stands inside a wall; summoned creatures leave when their time is up; resources never go negative; nobody is attuned to more than three items; no creature acts while incapacitated); the window smoke test with new screenshots for every expansion.

### 4.15 Tooltips and status icons

Anton wants far more information on hover, above all in battle. Build it once (Expansion 1, Part E) and let every later expansion feed it.

- **One card system.** Logic produces the content and the interface draws it, so logic still never imports UI. A logic module (`realmwalker/rules/describe.py`, or `game/describe.py` extended) builds a *card* for anything that can be pointed at – a creature, a condition or status, an action option, a spell, a feature, a feat, an item, a square of terrain, a zone, a line of the battle log: a title, a subtitle, an icon id, a few short lines with markup and numbers, and a footer (source, time left). `ui/tooltips.py` draws cards as small panels (`ui/gfx/theme.panel`, the icon beside the title). A card appears after a short hover (about 0.3 s), stays inside the window, never covers what is pointed at, and keeps to about a dozen lines (with "more on the sheet" when there is more). `canvas.hit(..., tip=...)` takes a function, so a card is only built when it is shown. For the keyboard, the same card appears in the side panel for whatever the cursor or Look has selected.
- **Status icons.** Small pictograms (10×10, drawn in `tools/tile_art.py`, doubled on big windows) for every condition (the fifteen of 2024, and exhaustion with its level), Bloodied, Realmwalker's own states (bleeding, wounded, infected, in pain, drunk, poisoned; and out of battle hungry, thirsty, cold, wet, exhausted, sick), and every mark, aura and lasting effect (concentrating, raging, hidden, invisible, flying with its height, dodging, a readied action, Hunter's Mark or Hex, blessed or baned, inspired, temporary hit points, Heroic Inspiration, slowed, sapped or vexed by a mastery, burning, grappling or grappled, stable, dying with its death-save pips). They show as a row above each figure's health bar on the battle board (up to four, then "+N"), on figures on the close-up maps where it matters, beside each party member in the side panel, and on the character and health screens. Each icon has its card: what it does in a line or two, who caused it, rounds or hours left, and how to end it.
- **Creature cards.** Pointing at a creature on the battlefield, or at its place in the turn order, shows: its name and what it is (size, type); its health as a bar and in words ("Bloodied"); its conditions; then a short stat block – AC, speeds, notable senses, resistances, immunities and vulnerabilities, each trait and action as one line, legendary actions and resistances left, recharge abilities ready or not, and its CR. A setting, *Creature details*: **Full** (the default) or **What my character knows** (details unlock through Study, knowledge checks and having fought that kind of creature before, remembered per character).
- **Combat tooltips everywhere.** Action bar buttons and spells (cost, range, chance to hit or save DC, damage, area, concentration, and the chance against the creature pointed at); squares (terrain, cover, light, zones and their effects); area previews (who would be caught); the path (feet used, opportunity attacks risked); the turn order bar; floating damage numbers (type, and whether it was resisted or doubled); and **the battle log**: pointing at a line shows its roll ("d20 15 + 5 = 20 against AC 16; advantage from flanking").
- **Outside battle too**: features, feats, resources, skills and saving throws on the sheet; items (their cards gain properties, charges and attunement); people and places on the maps.
- **Tests**: every condition, status, mark and resource has an icon and card text; every action option and every creature produces a card; cards fit inside the window at three sizes.

---
## 5. How each expansion is built

### 5.0 Working fast without cutting corners

Quality comes first: everything must work, and work correctly. Speed comes from not wasting effort, never from skipping checks.

- **The design is decided here.** No brainstorming and no long specifications: the design note is one page at most, and the task list is a checklist. (A design expansion, one that is more the game's own design than the books' – Adventures & Events – may have a longer note, with its full design in its own document.)
- **Big expansions come in parts.** Each XL expansion below lists its parts. A part is a self-contained piece that meets §5.2 on its own and goes to GitHub when it does; the expansion's icon appears with its last part. An L expansion may be split the same way, usually into "the class and the people" and "the monsters and the world".
- **Helpers in parallel.** Use subagents for independent batches – one family of monsters, one batch of spells, one batch of items, one batch of pictures, one chapter of the codex – each writing its own fragment files (§4.1). Give each a precise brief: its codex entries, the schema, one finished example entry, the book pages, and the rule that every number is checked on the page image. Each returns a list of what it did and anything it was unsure of. Run up to about four at once. The main session owns the kernel, joins the pieces, runs the tests and reviews.
- **Templates after the first time.** After the first class, people, monster family and item batch, write short checklists in `docs/expansions/templates/` (what a class needs, a people, a monster family, an item batch), so that later expansions follow them step by step.
- **Generate what repeats.** For families that share a shape (the dragons by colour and age, the mephits, the golems, the modrons, the +N items), check the numbers on the pages into a small table, generate the data from it with a script in `tools/codex/`, check the result, and commit the result.
- **Read the books once.** Expansion 1 extracts all three books into `build/codex/`. Later, look things up there and open page images only to check numbers.
- **Test smart.** While working, run only the tests for what you touched (`pytest tests/test_x.py -k ...`, `-m "not slow"`). The full suite (`pytest -n auto`), autoplay, the balance runs (fewer runs while tuning, full runs at the end) and the window smoke test run before each merge into `main`, not after every commit. Every commit still leaves its own tests green.
- **One fresh review at the end.** Before merging, a reviewer subagent that has not seen the work checks the changes against the codex entries and §5.2; fix what it finds.
- **Work on Anton's PC when possible.** There the books and the game window are at hand, and nothing is left "owed on Windows".
- **No gold-plating.** Build what the books say plus what the Realmwalker filter (§1.2) needs. Good ideas beyond that go to an "Ideas" list in `STATUS.md` for later.
- **Keep `CLAUDE.md` a concise map.** It is read at the start of every session; long notes belong in `docs/expansions/NN-short-name.md`.

### 5.1 Steps

1. **Branch** `dlc/NN-short-name` from `main`; push it as you go.
2. **Design note and task list** in `docs/expansions/NN-short-name.md`: what Anton will see, the decisions taken, its parts, the codex entries it delivers, and the checklist of tasks with their files and tests.
3. **Book pages**: from `build/codex/`; page images only to check numbers.
4. **Kernel work** it needs (new operations, events, handlers), with tests.
5. **Content data** in its pack (in parallel batches); codex entries to `done` or `adapted`.
6. **World**: peoples, places, encounters, dungeons, history, events, quests, news, shops, treasure.
7. **Tactics** for every new option; arena coverage green.
8. **Pictures and sounds**; contact sheets looked at.
9. **Words, tooltips and icons**: descriptions, intros, events, rumours; a card for everything new and an icon for every new status (§4.15).
10. **Verify** (§5.2), ending with the fresh review.
11. **Send to GitHub**: merge into `main` and push.
12. **Release** (with the last part): in `pack.json` set `status` "released", the version and date, and the `adds` lines in Anton's language; draw and bake its icon; set `__version__` and `MILESTONE` in `realmwalker/__init__.py` (Expansion N is version 1.N.0, and the last, Planes & Portals, is 2.0.0; the milestone is the expansion's name); write the `docs/PROGRESS.md` entry and the release notes (§5.3); update `CLAUDE.md` with the new systems and rules, `README.md` and `docs/expansions/STATUS.md`; merge, push, tag `v1.N.0`, push the tag, publish the GitHub release.

### 5.2 Definition of done (before anything is merged into `main`)

- [ ] Every codex entry assigned to it (or to this part) is `done`, `adapted` (with a note) or `omitted` (with a §1.3 reason).
- [ ] The full suite is green (`pytest -n auto`), with new tests for its rules, content, tactics coverage, world placement, screens, tooltips and pictures.
- [ ] Autoplay is clean (`RESULT: OK`), with the expansion's new invariants.
- [ ] `tools/balance.py` is inside its bands; any band that changed is explained in the notes.
- [ ] The window smoke test passes, with screenshots of the new things. (In a cloud session that cannot open a window: the headless picture tests must pass, and the notes say plainly that the look is still to be checked on Windows.)
- [ ] The performance budgets of §3 hold.
- [ ] Everything new has a picture, a sound cue, original text, a tooltip card, and icons for its statuses.
- [ ] If what a save holds changed, `FORMAT_VERSION` is bumped and an older save is refused kindly (never a crash, never a deleted file); the notes say whether a new character or world is needed.
- [ ] Its design note answers *What stories does it tell?* and *What does it show?*, and what it says is in the game (from Expansion 6 on: villains, blueprints, beats, happenings or ambitions; marks, scenes, map signs or backdrops).
- [ ] The fresh reviewer's findings are fixed.
- [ ] With the last part: the icon is on the shelf and its tooltip reads well.

### 5.3 Release notes (the GitHub release and the `docs/PROGRESS.md` entry)

In Anton's language: **What is different when you play** (grouped by theme, in game terms) · **How to see it** (which screen, which key, whether a new world or a new character is needed) · **What could not be checked** · **Anything assumed** · the codex coverage table (`tools/codex/coverage.py`).

### 5.4 When something is genuinely unclear

Decide from the books, the design and the game's tone; write the assumption in `STATUS.md` and the release notes; carry on (§0.3).

### 5.5 Template for `docs/expansions/STATUS.md`

```
# Expansion programme – status
Current: 07 Tieflings & Warlocks · part B (the fiends) · branch dlc/07-tieflings-warlocks · step 6 (world) of §5.1
On GitHub (main): 01 Dice & Destiny (v1.1.0) · 02 Blades & Backgrounds (v1.2.0) · ... · 07 part A
Codex coverage: PHB 61% · MM 23% · DMG 18%
Assumptions waiting for Anton: ...
Ideas for later: ...
Next session starts at: task B.4 in docs/expansions/07-tieflings-warlocks.md
```

---

## 6. The expansions

Every expansion is named *Thing & Related Thing*, in Anton's style; his own names – *Demigods & Magics*, *Adventures & Events* and *Tieflings & Warlocks* – are kept. The order below keeps the game playable and improving at every step: first the rules everything else needs (Act I), then the new classes and peoples (Act II), then the monster families and the places they live (Act III), and last the treasures, strongholds and other planes (Act IV). Within an act the order may change if Anton prefers; the "Needs" column is what must truly come first. Sizes are relative (S, M, L, XL).

| # | Expansion | Mainly adds | Needs | Size |
|---|---|---|---|---|
| | **Act I – The Rules of the Realm** | | | |
| 1 | Dice & Destiny | the 2024 rules kernel, conditions and actions; Tactics 2.0; magic item and treasure framework; the codex; the main-menu shelf | World Variety | XL |
| 2 | Blades & Backgrounds | Weapon Mastery and all PHB equipment; 16 backgrounds; all feats; the old peoples in 2024 form | 1 | L |
| 3 | Demigods & Magics | levels 11–20; epic boons; the 2024 fighter, rogue, cleric and wizard; every PHB spell | 2 | XL |
| 4 | Steel & Shadows | Battle Master, Eldritch Knight, Arcane Trickster; poisons; spies and assassins | 3 | M |
| 5 | Schools & Domains | Diviner, Illusionist, Light and Trickery domains; mages and priests of the world | 3 | M |
| 6 | Adventures & Events | threats, adventures, situations, villains who act, places that change, the Storyteller, Legend, ambitions | 5 | XL |
| | **Act II – New Blood** | | | |
| 7 | Tieflings & Warlocks | the Tiefling; the Warlock; every fiend | 3 | L |
| 8 | Dragonborn & Sorcerers | the Dragonborn; the Sorcerer; kobolds and lesser dragon-kin | 3 | L |
| 9 | Orcs & Barbarians | the Orcs as a full people; the Barbarian; war-bands and mobs | 3 | L |
| 10 | Aasimar & Paladins | the Aasimar; the Paladin; every celestial; mounted combat; blessings and charms | 3 | L |
| 11 | Elves & Rangers | the elven lineages in full; the Ranger; the fey and goblinkind | 3 | L |
| 12 | Druids & Beasts | the Druid; every beast and the plant-folk; Wild Shape | 3 | XL |
| 13 | Bards & Brigands | the Bard; the people of towns and roads; chases; settlement life | 3 | L |
| 14 | Monks & Elementals | the Monk; every elemental and genie; environmental effects | 3 | L |
| 15 | Callings & Crossroads | multiclassing; starting at higher levels | 6–14 | S |
| | **Act III – The Monstrous World** | | | |
| 16 | Dragons & Hoards | every true dragon; legendary lairs; hoards | 8 | XL |
| 17 | Goliaths & Giants | the Goliath; every giant; the mountain beasts | 3 | L |
| 18 | Gnomes & Golems | the Gnome; every construct; firearms and explosives | 3 | M |
| 19 | Crypts & Curses | every undead; lycanthropes and blights; curses, contagions, fear and stress | 3 | XL |
| 20 | Drow & the Underdark | the world below; the drow cities; the Underdark's creatures | 11 | XL |
| 21 | Mind Flayers & Psionics | Psi Warrior and Soulknife; every aberration; the gith | 20 | L |
| 22 | Traps & Terrors | traps and hazards; mythic monsters and oozes | 3 | L |
| 23 | Ships & Sea Monsters | ships and sea travel; underwater combat; the creatures of the sea | 12, 14 | XL |
| | **Act IV – Treasures, Strongholds and Other Worlds** | | | |
| 24 | Potions & Scrolls | every consumable magic item; crafting gear, potions, scrolls and magic items | 3 | L |
| 25 | Rings & Relics | every remaining magic item; artifacts; sentient and cursed items | 24 | XL |
| 26 | Bastions & Banners | bastions; siege equipment and sieges | 9, 18, 24 | L |
| 27 | Planes & Portals | the planes as reachable realms; planar travel; slaadi, modrons and the tarrasque | 7, 10, 11, 14, 20, 21 | XL |

Each section below lists: the icon and the tooltip's tagline; what Anton will notice; and the work under **Rules**, **Content**, **World**, **Tactics**, **Pictures**, **Books**, and **Done when** (in addition to §5.2). XL expansions list their **parts** (§5.0). Monster lists are in Appendix A and item rules in Appendix B; they are part of each section.

---

### 6.1 Dice & Destiny (Expansion 1, XL – five parts)

*Icon*: a twenty-sided die showing a small star, under a thin arc of light. *Tagline*: "The rules of the realm, made whole."

**For Anton**: fights, checks and conditions follow the 2024 Player's Handbook; the creatures already in the game are re-made from the 2025 Monster Manual; enemies think harder; reactions ask you first; loot follows the Dungeon Master's Guide; small icons show every state (bleeding, stunned, raging...), and pointing at anything in a fight tells you what it is and what it can do; borrowed monster pictures are reworked to match the game's own art; the main menu gets its shelf of expansions.

**Part A – Foundations**: content packs, provenance and `realmwalker/expansions.py` (§4.1); the shelf and the Expansions screen (§4.13); the codex, complete for all three books and assigned to all 26 expansions (§4.2), with `tools/codex/extract.py`, `coverage.py` and `tests/test_codex.py`.

**Part B – The kernel**: the rules kernel (§4.3.1–4.3.4, 4.3.8) with combat moved onto it (§4.3.9). The 2024 Rules Glossary (all but mounted and underwater combat): d20 tests; advantage and disadvantage; proficiency; the conditions Blinded, Charmed, Deafened, Exhaustion (2024), Frightened, Grappled, Incapacitated, Invisible, Paralyzed, Petrified, Poisoned, Prone, Restrained, Stunned, Unconscious, and Bloodied; the actions Attack, Dash, Disengage, Dodge, Help, Hide, Influence, Magic, Ready, Search, Study, Utilize; unarmed strikes (damage, grapple, shove, the 2024 way); initiative and surprise (2024); Heroic Inspiration; concentration (2024 DC); temporary hit points; resistance, vulnerability and immunity in the right order; falling; suffocation; burning; areas of effect including Emanation; cover; obscurement and darkness; objects. Exhaustion and dehydration/malnutrition in 2024 form, mapped onto the game's body and survival systems (`rules/body.py`, `game/survival.py`), with the "careful player" measurement re-run. The existing 35 creatures re-statted to their 2025 versions (Appendix A, Expansion 1) (renaming ids freely, §4.3.8); the existing 41 spells converted to definitions in their 2024 versions; the existing class features and magic item properties moved onto the kernel unchanged (the classes' 2024 versions come in Expansion 3). Legendary actions and resistance, recharge, uses per day, 2025-style spellcasting and multiattack (§4.3.8) proven on test creatures, used for real from the first expansion that brings a legendary creature.

**Part C – Reactions and Tactics 2.0**: reactions that pause the battle and the *Reactions* setting (§4.3.5); the rest of §4.3.6 (elevation, flying, jumping and climbing, senses, telepathy, changing sides, antimagic, the missing actions); one list of possible actions (§4.3.7); Tactics 2.0 core (§4.7) over today's creatures and spells, with the creatures' old front/back `rank` replaced by their role and preferred range; `tools/arena.py`; `tests/test_tactics_coverage.py`.

**Part D – Treasure and encounters**: the magic item framework, including the rules for artifacts, sentient and cursed items, and DMG treasure and hoards (§4.8); the encounter builder and the DMG XP budget (§4.6); the DMG's travel pace (fast, normal, slow, with their effects on noticing threats and stealth) aligned with `game/journey.py`, and its starting attitudes (Indifferent, Friendly, Hostile) feeding the Influence action and conversations.

**Part E – Tooltips, icons and pictures**: §4.15 in full (cards, status icons, creature cards, the battle log's rolls); the picture adaptation pass (§4.11), applied to the creatures already in the game; the generic effect styles of §4.11 for today's spells; fliers drawn with their height; this expansion's icon on the shelf.

**Books**: PHB 9–34, 363–380; MM 4–12, 377, and the pages of the 35 converted creatures; DMG 25–56, 109–130, 217–235, 330–338.

**Done when**: every codex entry assigned to Expansion 1 is done or adapted; the old hand-written branches in `combat.py` for today's features are gone (any left are listed in `STATUS.md` with the reason); balance re-measured and in band; every state a fight can produce has an icon and a card; "Dice & Destiny" is on the shelf.

---

### 6.2 Blades & Backgrounds (Expansion 2, L)

*Icon*: a sword laid across a rolled scroll tied with a cord. *Tagline*: "Where you come from. What you carry."

**For Anton**: every weapon has its own trick (a mace that knocks people down, a rapier that leaves an opening, a greataxe that cleaves into the next foe); armour, gear and tools are the 2024 book's; sixteen backgrounds, each with a feat; at levels 4 and 8 you may take a feat instead of raising abilities; humans, elves, dwarves, halflings and orcs in their 2024 form.

**Rules**
- **Weapon Mastery**: Cleave, Graze, Nick, Push, Sap, Slow, Topple, Vex; mastery picks for fighters and rogues now (the 2024 numbers), later for barbarians, paladins and rangers.
- **Equipment** (PHB 216–236) complete: weapons and their properties; armour and shields; adventuring gear with its 2024 uses (Utilize) – except the Potion of Healing and the Spell Scroll, which Expansion 3 brings in every strength and level; tools with their checks and uses (making things with them is crafting, Expansion 24); barding; land mounts and vehicles (riding horse, draft horse, warhorse, pony, mule, camel; cart, wagon, carriage, chariot, sled); services and lifestyle; the trinkets table (starting gear and loot).
- **Backgrounds**: the 16 of the 2024 book (§4.4), each with Realmwalker ties and starting places.
- **Feats**: every origin feat, general feat and fighting style feat (the epic boons come with Expansion 3). Feats that grant spells (Magic Initiate, Fey-Touched, Shadow-Touched, Ritual Caster) read their choices from the spell data, so their options grow by themselves when Expansion 3 adds the spells. Feats whose subject arrives later – Poisoner (poisons, Expansion 4), Mounted Combatant (mounted combat, Expansion 10), Crafter (crafting, Expansion 24) – work in a basic form now and carry `upgrade_in` in the codex.
- **Species** in 2024 form: Human (Resourceful, Skillful, Versatile), Elf (the Drow, High Elf and Wood Elf lineages as a choice, with their spells; their full cultures arrive in Expansions 11 and 20), Dwarf, Halfling, and **Orc** replacing the Half-Orc (Adrenaline Rush, Relentless Endurance, darkvision 120 ft; the orcs' full culture arrives in Expansion 9). Ability bonuses move from species to backgrounds.
- **Languages** in 2024 form (standard and rare languages), merged with the game's regional tongues, which become dialects of Common or languages of their own as World Variety decided.
- **Character creation** in the 2024 order, with standard array and rolling.

**Content**: +1/+2/+3 weapons, armour, shields and ammunition, adamantine and mithral armour (the basics of the Armaments tables), so treasure has them from now on; the mount stat blocks (riding horse, draft horse, warhorse, pony, mule, camel, mastiff).

**World**: shops stock the new gear by settlement size and people; tools used at camp (`camping.json` crafts); trinkets in pockets and chests; the new backgrounds' ties and starting places; townsfolk and soldiers carry mastery weapons.

**Tactics**: masteries used on purpose – topple then strike the prone, push into hazards or out of reach, sap the biggest hitter, slow to kite, vex to chain hits, cleave into clusters; the combat feats (Great Weapon Master, Sharpshooter, Polearm Master, Sentinel, Shield Master, Charger, Crusher, Piercer, Slasher, Mage Slayer, Defensive Duelist, Dual Wielder, Grappler, Mounted Combatant...) in Auto's hands and in those NPCs who have them.

**Pictures**: every item has a picture and, if worn or held, its doll layer (`figure_gear.py`); mastery effects (a knock-down, a push, a slowing mark, a sapped stagger); **a real horse picture at last** (today a recoloured yak stands in) and the other mounts.

**Books**: PHB 35–50, 180–200, 202–214, 216–236, 349–362 (mounts); DMG Armaments tables (330–338).

**Done when**: every codex entry assigned to Expansion 2 is done or adapted; a level 4 fighter can take Great Weapon Master and it works in battle, in the enemy's hands and in Auto's.

---

### 6.3 Demigods & Magics (Expansion 3, XL) – Anton's name

*Icon*: a crowned silhouette rising out of an open book that spills light. *Tagline*: "Twenty levels of power. Every spell under the sky."

**For Anton**: fighters, rogues, clerics and wizards in their 2024 form up to level 20; epic boons at 19; every spell in the Player's Handbook, cantrips to 9th level – for you, your companions, your enemies, and on scrolls and wands; spells that matter outside a fight, from Goodberry to Teleport.

**Parts** (§5.0), each sent to GitHub when it meets §5.2; the icon appears with the last:

- **A. Twenty levels**: XP, proficiency, hit points, epic boons (all of them); companions choose sensibly; the world's danger tiers extended so that levels 11–20 have somewhere to go (deeper dungeon levels, the most dangerous regions, legendary lairs).
- **B. The four classes in 2024 form, levels 1–20**, every feature; their existing subclasses in 2024 form – Champion, Thief, Life Domain, War Domain, Evoker, Abjurer; the Cutthroat becomes the 2024 **Assassin**; the **Knight** stays as a Realmwalker subclass, extended to level 18 in its own spirit (mark it `original` in the codex).
- **C. Spellcasting complete** (§4.5): prepared spells, spellbooks, rituals, components and costly components, upcasting, concentration, reaction spells, using spell scrolls (2024 rules) of every level.
- **D. The spell catalogue** – every PHB spell, in four waves: cantrips to 2nd level; 3rd to 5th; 6th and 7th; 8th and 9th. Spells of classes not yet in the game are still in: on scrolls and wands, in enemies' spell lists, through feats.
- **E. Spells outside battle** (Appendix C).
- **F. The PHB's Appendix B stat blocks**, all of them: familiars, the Otherworldly Steed, the summoned spirits, animated dead and the beasts printed there for Wild Shape and Polymorph. A creature printed both there and in the MM (the imp, quasit, pseudodragon, sprite, sphinx of wonder, slaad tadpole and many beasts) is delivered here as a stat block; its family expansion later places it in the world.
- **G. Enemy casters**: every caster's stat block uses the catalogue; spellcasting services at temples and mages' guilds (PHB services prices, the local law of magic); spell scrolls in shops by rarity.

**Tactics**: casters choose among dozens of spells (§4.7); every spell with a battle use is cast by the AI in at least one arena scenario.

**Pictures**: an `fx` for every spell; pictures for every summoned creature; condition icons for every condition a spell can cause.

**Books**: PHB 35–50, 71–80, 93–102, 131–140, 167–178, 213–214, 238–346, 349–362.

**Done when**: every PHB spell and every feature of the four classes is done or adapted; a level 20 wizard can cast Wish (its safe uses and its stress) and Meteor Swarm; a test caster of each level 1–9 casts in arena fights without hangs.

---

### 6.4 Steel & Shadows (Expansion 4, M)

*Icon*: a steel gauntlet gripping a dagger whose blade fades into shadow. *Tagline*: "Masters of the blade, and of the knife in the dark."

**For Anton**: three new paths for fighters and rogues – the Battle Master with his maneuvers, the Eldritch Knight who mixes sword and spell, the Arcane Trickster – and poisons that can be bought, harvested and brewed.

**Rules**: Battle Master (superiority dice, every maneuver in the book, Student of War, Know Your Enemy, Relentless); Eldritch Knight (2024: War Bond, War Magic, Eldritch Strike, Arcane Charge, Improved War Magic); Arcane Trickster (Mage Hand Legerdemain, Magical Ambush, Versatile Trickster, Spell Thief). **Poisons** (DMG 94–95): every poison, buying it (where the law allows), harvesting it from creatures, applying it; with the Poisoner feat and the Assassin's tools.

**Content**: the Assassin, Spy and Spy Master stat blocks; fighter and rogue themed magic items (Appendix B).

**World**: thieves' and assassins' guilds offer work and poisons; black markets in cities; spies in the service of realms (politics: a spy discovered at court); duels of honour between knights where the culture has them.

**Tactics**: maneuvers used well (Trip so allies get advantage, Precision on a near miss, Riposte and Parry as reactions, Menacing on the caster); Cunning Strike choices; spies and assassins hide and strike first.

**Pictures**: maneuver effects; the Arcane Trickster's spectral hand; spy and assassin dolls.

**Books**: PHB 93–102, 131–140; DMG 94–95; MM entries.

---

### 6.5 Schools & Domains (Expansion 5, M)

*Icon*: an open grimoire under a radiant sun-disc. *Tagline*: "Every school of the arcane. Every domain of the divine."

**For Anton**: the Diviner who sees the dice before they fall, the Illusionist whose phantoms block arrows, the Light domain's burning dawn and the Trickery domain's double; real mages and priests in the world's towers and temples.

**Rules**: Diviner (Portent, Expert Divination, The Third Eye, Greater Portent); Illusionist (Improved Illusions, Phantasmal Creatures, Illusory Self, Illusory Reality – illusions as battlefield objects, §4.3.2); Light Domain (Warding Flare, Radiance of the Dawn, Corona of Light); Trickery Domain (Blessing of the Trickster, Invoke Duplicity, Trickster's Transposition, Improved Duplicity). The DMG's gods and divine intervention guidance folded into the game's faiths.

**Content**: Mage Apprentice, Mage, Archmage, Priest, Archpriest stat blocks (Priest Acolyte came in Expansion 1); wizard and cleric themed items (staffs, wands, robes, holy symbols – Appendix B).

**World**: wizards' towers as a site and dungeon style (the DMG's wizard's tower archetype) with their guardians and wards; mages' circles and temples staffed by real casters; apprenticeships as quests; the history's tower mages and high priests use these stat blocks.

**Tactics**: diviners spend Portent on the rolls that decide a fight; illusionists cut sight lines; trickery clerics flank with their duplicate; NPC mages Counterspell and Shield; priests keep their side standing.

**Pictures**: portent dice, illusion shimmer, duplicates, mage and priest dolls by culture.

**Books**: PHB 71–80, 167–178; DMG gods and powers (about 78–79); MM entries.

---

### 6.6 Adventures & Events (Expansion 6, XL – eleven parts) – Anton's name

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

**What Anton will see**

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

**Decisions** (details in `docs/ADVENTURES.md`)

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


**Parts and tasks**: `docs/expansions/06-adventures-events.md`.

---

### 6.7 Tieflings & Warlocks (Expansion 7, L) – Anton's name

*Icon*: a curling horned silhouette before a violet eye ringed with sigils. *Tagline*: "Born of old bargains. Sworn to new ones."

**For Anton**: the tieflings – people with a fiend somewhere in their blood – to play and to meet; the Warlock and their four patrons; every devil and demon of the Monster Manual, summoned by the world's cults; bargains with fiends that have small print.

**Parts**: A – the Tiefling and the Warlock; B – the fiends and their place in the world.

**Species**: Tiefling – the Abyssal, Chthonic and Infernal legacies with their resistances and spells, Otherworldly Presence. Looks: human skin tones and also reds, purples, blues and ash-greys; horns (at least six shapes), tails, solid-coloured eyes.

**Culture**: tieflings have no homeland of their own by default. They live as a marked minority in the cities of every people (named in that people's style, often with a chosen "virtue name" – an original list), with their own quarter in big cities. Where the history made one, a **pact-city**: a city whose founder struck a bargain with a fiend, ruled by a tiefling house, with its own law, a distinct town look (dark stone, red lanterns, brass and iron), dress and faith. Standing: suspicion in most realms, outright restriction in some (`law.json`).

**Class**: Warlock, levels 1–20 – Pact Magic (slots recovered on a short rest), every eldritch invocation in the book, the pacts of the Blade, Chain and Tome, Magical Cunning, Contact Patron, Mystic Arcanum, Eldritch Master; patrons Archfey, Celestial, Fiend and Great Old One. **A patron is a real power in the world**: a fiend named in the history's cults, an archfey of a fey forest, a celestial of a faith, or a nameless thing from beyond; it notices the warlock's deeds and now and then asks for something (light-touch: news, a dream at camp, an offered task).

**Monsters**: every fiend (Appendix A) – devils, demons, yugoloths, cambion, succubus and incubus, hell hound, nightmare, night hag, rakshasa, oni, lamia, larvae, jackalwere, spirit naga, the gnolls of the demon lord, the Fiend Cultist.

**Rules**: **Demonic Possession** (the DMG's curse) – a possessed person can be met, exorcised (Remove Curse, Dispel Evil and Good, a temple), and can possess a companion.

**World**: fiend cults in the history gain real fiends (a summoning that worked; a pit fiend as the hidden power behind a realm; a demonic incursion where a cult succeeded and a town fell); **infernal contracts** in conversation (a devil offers a bargain with whitelisted terms and real consequences, read before signing); demon-gnoll packs as tribes; hell hounds kept by cults; night hags visiting dreams at camp; summoning circles in cult dungeons.

**Items**: infernal, abyssal and pact items (Appendix B), including the Wand of Orcus and the Demonomicon of Iggwilv as the history's darkest relics.

**Tactics**: Eldritch Blast with Repelling Blast into hazards; Hex; devils fight in disciplined pairs (bone devils sting from the air, erinyes shoot, pit fiends lead); demons are savage (vrocks' spores, marilith's many blades, glabrezu's grapples); imps and quasits turn invisible and sting; rakshasa and oni change shape; succubi charm the strongest.

**Pictures**: tiefling bodies and features; the Dungeon Crawl pack's demons and devils (more than a hundred tiles) mapped and recoloured; drawn: yugoloths, demon-gnolls, night hag, rakshasa, lamia; the pact-city's town look.

**Books**: PHB 155–166, 189–200 (Tiefling); DMG 64–66 (possession); MM fiend entries.

---

### 6.8 Dragonborn & Sorcerers (Expansion 8, L)

*Icon*: a dragon-headed silhouette breathing a spiral of wild sparks. *Tagline*: "Magic in the blood. Fire in the breath."

**For Anton**: the dragonborn and their clan-holds; the Sorcerer, whose magic is born, not learned, including wild magic that can go spectacularly wrong; kobolds, wyverns, pseudodragons and faerie dragons.

**Species**: Dragonborn – the ten draconic ancestries (black acid, blue lightning, brass fire, bronze lightning, copper acid, gold fire, green poison, red fire, silver cold, white cold), Breath Weapon (in place of an attack, as a cone or a line), damage resistance, darkvision, Draconic Flight at 5th level. Looks: scale colours by ancestry, snouts, crests, horns, frills.

**Culture**: **clan-realms** in hills, mountains, deserts and coasts – fortified stone clan-holds (a new town style: a citadel with a great hall, a dragon-temple and terraced courtyards), honour-bound law, clan name before personal name, a childhood name and an adult name; lamellar of scales and tabards with clan sigils; two original dragon-faiths (the metal and the chromatic); in the history, clans born of an ancient dragon empire, clan wars and blood oaths.

**Class**: Sorcerer, levels 1–20 – Innate Sorcery, Font of Magic, every Metamagic option, Sorcerous Restoration, Sorcery Incarnate, Arcane Apotheosis; subclasses Aberrant, Clockwork, Draconic, Wild Magic (the Wild Magic Surge table – every result – Tides of Chaos, Bend Luck, Controlled Chaos, Tamed Surge).

**Monsters**: Kobold Warrior, Winged Kobold, Half-Dragon, Pseudodragon, Faerie Dragon Youth and Adult, Wyvern.

**World**: kobold warrens (a dungeon style) devoted to a dragon; wyverns over mountain passes; sorcerers in society, feared or courted, under the law of magic; wild magic stronger near strange wonders (the drifting stones).

**Items**: draconic and sorcerous items (Appendix B).

**Tactics**: metamagic chosen well (Quickened with Twinned, Careful when friends are in the blast, Heightened against a strong saver); wild surges handled; dragonborn NPCs breathe when it catches several; kobolds swarm with pack tactics and traps.

**Pictures**: dragonborn heads and bodies (drawn in `figure_art.py`, with the Dungeon Crawl draconian parts as reference), wings for Draconic Flight; kobolds and the wyvern from the pack; pseudodragon and faerie dragons drawn.

**Books**: PHB 141–154, 189–200 (Dragonborn); MM entries.

---

### 6.9 Orcs & Barbarians (Expansion 9, L)

*Icon*: a tusked face behind crossed axes, streaked with red. *Tagline*: "The fury of the blood, and the people who own it."

**For Anton**: the orcs become a whole people with realms, laws and a history, not just raiders; the Barbarian and their rage; big fights against war-bands that move as one.

**Species and culture**: the Orc (2024 traits from Expansion 2) gets its full people: **strongholds** (a new town style: palisaded hill-forts, great longhouses of hide and timber, a war-totem plaza, smithies) and mountain holds; succession by deed and challenge; names (the orcish pools enlarged to the World Variety standard); an original war-god and hearth-mother; hide, bone, iron scale and war paint. Orc realms rise, raid, trade and settle in the history; long feuds with dwarves and elves (standing) that can end in alliance. Orc raiders stay in the world as people: Warrior stat blocks of the Orc species.

**Class**: Barbarian, levels 1–20 – Rage, Unarmored Defense, Weapon Mastery, Danger Sense, Reckless Attack, Primal Knowledge, Extra Attack, Fast Movement, Feral Instinct, Instinctive Pounce, Brutal Strike and its improvements, Relentless Rage, Persistent Rage, Indomitable Might, Primal Champion; paths of the Berserker, the Wild Heart (every animal aspect), the World Tree and the Zealot.

**Rules**: **Mobs** (DMG about 86): large groups of the same weak creatures fought as mobs, so big fights stay quick – used here for war-bands and later for sieges (Expansion 26).

**Monsters**: Warrior Veteran, Warrior Commander, Berserker Commander (Warrior Infantry came in Expansion 1).

**World**: war-bands in the history and in live politics; orc mercenaries and companions; berserker lodges; barbarian companion archetypes in every wild culture.

**Tactics**: barbarians rage when it pays (not to kill a rat), go Reckless when the enemy cannot punish it, choose Brutal Strike effects; mobs advance, surround and break as one.

**Pictures**: orc bodies and looks (from the half-orc's, extended); barbarian outfits by culture; a red rage outline; mob banners.

**Books**: PHB 53–60, 189–200 (Orc); DMG about 86; MM warrior entries.

---

### 6.10 Aasimar & Paladins (Expansion 10, L)

*Icon*: a winged helm before an upright radiant sword. *Tagline*: "Oaths sworn in light. Wings unfolded in wrath."

**For Anton**: the aasimar, born with a spark of heaven; the Paladin and their oaths; angels, unicorns, sphinxes and other celestials; fighting from horseback; blessings and charms granted by gods and saints.

**Species**: Aasimar – Celestial Resistance, darkvision, Healing Hands, Light Bearer, Celestial Revelation at 3rd level (Heavenly Wings, Inner Radiance, Necrotic Shroud). Looks: luminous eyes, a faint glow, a metallic sheen to hair or skin; wings and radiance as transformations.

**Culture**: not a nation – aasimar are born to any people, rarely, and often raised by temples; they carry their birth people's names, with a temple epithet. The **Radiant Orders**: monastic-knightly orders in the history with temple-fortresses (a site style: the sanctuary), saints and martyrs, and a few aasimar heroes in every long history.

**Class**: Paladin, levels 1–20 – Lay on Hands, Weapon Mastery, Fighting Style, Paladin's Smite, Channel Divinity, Faithful Steed, Aura of Protection, Abjure Foes, Aura of Courage, Radiant Strikes, Restoring Touch, Aura Expansion; oaths of Devotion, Glory, the Ancients and Vengeance.

**Rules**: **Mounted combat** (PHB Rules Glossary): mounting and dismounting, controlled and independent mounts, being knocked off, mounts in battle with the party's own horses (`game/mounts.py`) and the warhorse with barding; **Supernatural Gifts** (DMG 102–103): every blessing and charm, granted by gods, saints, celestials and great deeds.

**Monsters**: every celestial (Appendix A) – deva, planetar, solar, couatl, empyrean and empyrean iota, pegasus, unicorn, the four sphinxes, guardian naga, giant eagle, giant owl, giant elk – and the Knight and Questing Knight stat blocks.

**World**: celestials are rare: a unicorn in a fey forest, a couatl guarding a jungle temple, sphinxes guarding the secrets of wonders (riddles in conversation, the Study action), an angel answering a Divine Intervention or a saint's miracle in the history. Questing knights roam under oaths. Temples grant blessings for great deeds.

**Items**: holy items (Holy Avenger, Sun Blade, Mace of Disruption, the Book of Exalted Deeds; Appendix B); barding (from Expansion 2) now matters.

**Tactics**: paladins smite on criticals and on blows that kill; they stand where their aura covers friends and lay on hands to raise the fallen; angels heal their side and hunt fiends; sphinxes use their lairs and legendary actions; unicorns teleport and heal.

**Pictures**: aasimar features and wings; celestials from the pack's holy creatures, sphinxes and titans, and drawn ones (couatl, empyrean, pegasus, unicorn, from the horse of Expansion 2); riders on horseback.

**Books**: PHB 111–120, 189–200 (Aasimar), 363–380 (mounted combat); DMG 102–103; MM celestial entries.

---

### 6.11 Elves & Rangers (Expansion 11, L)

*Icon*: a leaf-shaped arrowhead crossing a crescent moon above treetops. *Tagline*: "The old blood of the woods, and those who walk its edges."

**For Anton**: high elves and wood elves as distinct peoples, and drow wanderers from below; the Ranger and their beast companions; pixies, dryads, satyrs, centaurs, hags – and the rest of goblinkind (hexers, warlords, stalkers) as the fey they are in the new Monster Manual (the common goblin, hobgoblin and bugbear were re-made in Expansion 1).

**Species and cultures**: the elf lineages in full – High Elves (the elven halls), Wood Elves (the groves of World Variety's grove style), and Drow (playable from Expansion 2; their cities arrive in Expansion 20, so until then drow are exiles and wanderers on the surface). Each lineage gets its own culture: names, dress, law, faith and a place in the history (the elder peoples' sub-peoples).

**Class**: Ranger, levels 1–20 – Favored Enemy (Hunter's Mark), Weapon Mastery, Deft Explorer, Fighting Style, Roving, Expertise, Tireless, Relentless Hunter, Nature's Veil, Precise Hunter, Feral Senses, Foe Slayer; Beast Master (the primal companions of land, sea and sky, commanded in battle), Fey Wanderer, Gloom Stalker, Hunter. Outside battle rangers find paths, forage and hunt better (camp and wayfinding), and can follow tracks to a quarry.

**Monsters**: the fey (Appendix A) – goblin minion and hexer, hobgoblin captain and warlord, bugbear stalker, green hag, sea hag, arch-hag, pixie and pixie wonderbringer, sprite, dryad, satyr and revelmaster, blink dog, centaur trooper and warden, bullywug warrior and bog sage, worg and dire worg – and the forest monstrosities (displacer beast, ettercap, phase spider), with the Scout Captain.

**World**: World Variety's enchanted forests become small fey realms – fey courts, crossings where time runs strangely, fey bargains in conversation; goblinoid warbands and hobgoblin legions as tribes and realms in the history; bugbears stalking roads at night; hag covens in swamps and woods (bargains, curses, stolen children) in the history and in quests; centaur clans on the plains.

**Items**: elven and woodland items (Elven Chain, Cloak and Boots of Elvenkind, Bracers of Archery, Oathbow, Quiver of Ehlonna, Arrows of Slaying; Appendix B).

**Tactics**: rangers move their mark as targets fall and command the companion with a bonus action; fey teleport, charm and vanish; goblins strike and slip away; hobgoblins hold formation; hags work as a coven; displacer beasts exploit their displacement; blink dogs blink behind you.

**Pictures**: lineage looks and dress; fey from the pack (goblins, hobgoblins, bugbear, satyr, dryad, centaur, warg) and drawn (pixie, sprite, hags as dolls, bullywug, displacer beast, blink dog, ettercap, phase spider).

**Books**: PHB 121–130, 189–200 (Elf); MM fey entries.

---

### 6.12 Druids & Beasts (Expansion 12, XL)

*Icon*: an antlered head made of leaves, a paw print beneath. *Tagline*: "Every beast of the wild, and the druids who become them."

**For Anton**: the Druid, who turns into the animals of the world; every animal of the Monster Manual – lions on the savanna, polar bears on the glaciers, crocodiles in the marsh rivers, sharks off the coast, dinosaurs in the deepest jungles – plus owlbears, treants and shambling mounds.

**Parts**: A – the Druid and Wild Shape, with the beasts Wild Shape needs most; B – the rest of the beasts; C – the plant-folk, the natural monstrosities and the world.

**Class**: Druid, levels 1–20 – Druidic, Primal Order (Magician or Warden), **Wild Shape** (forms known, the CR limits, temporary hit points, the 2024 rules), Wild Companion, Wild Resurgence, Elemental Fury, Beast Spells, Archdruid; circles of the Land (the land types mapped to the world's biomes), the Moon, the Sea and the Stars. **Wild Shape uses the beast's real stat block** (§4.3, `transform.py`): the druid's doll becomes the beast's picture; gear melds; out of battle a druid can travel, swim, fly, scout and hunt as a beast.

**Monsters**: every beast in the MM and its Appendix A (Appendix A of this plan), the swarms and the dinosaurs; the plant-folk (awakened shrub and tree, shambling mound, treant); the natural monstrosities (owlbear and primeval owlbear, axe beak and giant axe beak, giant vulture, peryton, hippogriff, ankheg, flying snake, swarm of stirges); the Animal Lord; the Druid stat block.

**World**: animals by biome in encounters, in hunting and fishing at camp (`game/camp.py` uses the real beasts), as herds, predators and pests; dinosaurs only where plausible (jungle, volcanic lands, a "lost valley" in some jungle worlds); druid circles and sacred groves in the history; treants and awakened trees in the oldest forests; the Animal Lord as a legend of the wildest land.

**Items**: nature items (Staff of the Woodlands, Figurine of Wondrous Power, Bag of Tricks, Ring of Animal Influence; Appendix B).

**Tactics**: beasts act like beasts – packs encircle, predators take the weak, herbivores flee, swarms flow over the fallen; druids pick forms for the moment (a bear to hold the line, a wolf to knock down, an eagle to scout or fly), and summon.

**Pictures**: the pack's animals (many) mapped; drawn: owlbear, axe beak, peryton, the dinosaurs the pack lacks, awakened shrub, shambling mound; the change of shape as an effect.

**Books**: PHB 81–92, 349–362; MM beast entries and Appendix A (351–376).

---

### 6.13 Bards & Brigands (Expansion 13, L)

*Icon*: a lute crossed with a hooked knife beneath a single coin. *Tagline*: "Songs in the tavern. Knives in the alley."

**For Anton**: the Bard, whose music inspires friends and cuts down foes; towns and roads full of real people – gladiators, guard captains, crime lords, con artists, performers, toughs; chases through streets and across country; towns with character and troubles of their own.

**Class**: Bard, levels 1–20 – Bardic Inspiration, Expertise, Jack of All Trades, Font of Inspiration, Countercharm, Magical Secrets, Superior Inspiration, Words of Creation; colleges of Dance, Glamour, Lore (Cutting Words) and Valor. Outside battle a bard performs in inns for money and fame (the existing music use of instruments), lifts companions' spirits (loyalty), hears more news and rumours, and talks better.

**Monsters and people**: Bandit Crime Lord, Bandit Deceiver, Gladiator, Guard Captain, Noble Prodigy, Performer, Performer Maestro, Performer Legend, Cultist Hierophant; the doppelganger and the kenku (Appendix A). Every humanoid stat block is a person of the place's people (§4.3.8).

**Rules**: the DMG's **Nonplayer Characters** section guides how townsfolk are made and behave; **Chases** (DMG 57–58): fleeing the watch, running down a thief, escaping a lost battle, with the urban and wilderness complications; **Settlements** (DMG 97–99): every town has defining traits that shape its news, quests and mood (its calamities came with Adventures & Events, Expansion 6, as threat seeds); the **Influence** action deepened with the DMG's attitudes.

**World**: performers on tour; gladiatorial arenas in great cities (fights for money); thieves' guilds and crime lords as figures in politics; con artists' schemes as events; doppelgangers replacing townsfolk (a quest); kenku messengers and thieves.

**Items**: the Instruments of the Bards and other performers' and rogues' items (Appendix B).

**Tactics**: bards inspire before the big swing and spend Cutting Words on the hit that matters; Glamour bards reposition the party; crime lords hide behind their toughs; deceivers parley and feint; chases pursued or escaped sensibly.

**Pictures**: performers', gladiators' and town officers' dolls by culture; kenku and doppelganger drawn; chase scenes.

**Books**: PHB 61–70; DMG 57–58, 97–99; MM humanoid entries.

---

### 6.14 Monks & Elementals (Expansion 14, L)

*Icon*: a closed fist wreathed in flame, wave, wind and stone, one in each quarter. *Tagline*: "The body as weapon. The four elements unbound."

**For Anton**: the Monk; every elemental and genie (the water weird apart: it lives in the seas of Expansion 23) – fire spirits in the volcanoes, air spirits on the great peaks, a djinni who grants a bargained wish; heat, cold, wind, storms and thin air that bite as the Dungeon Master's Guide says.

**Class**: Monk, levels 1–20 – Martial Arts, Unarmored Defense, Monk's Focus (Flurry of Blows, Patient Defense, Step of the Wind), Unarmored Movement, Uncanny Metabolism, Deflect Attacks, Slow Fall, Extra Attack, Stunning Strike, Empowered Strikes, Evasion, Acrobatic Movement, Heightened Focus, Self-Restoration, Deflect Energy, Disciplined Survivor, Perfect Focus, Superior Defense, Body and Mind; Warriors of Mercy, Shadow, the Elements and the Open Hand. Monasteries as sites, schools in the history, monk companions.

**Monsters**: every elemental but the water weird (Appendix A) – air, earth, fire and water elementals and the elemental cataclysm; djinni, efreeti, dao and marid; the six mephits; magmin; salamander, salamander fire snake and inferno master; azer sentinel and pyromancer; gargoyle, galeb duhr, xorn, invisible stalker; aarakocra skirmisher and aeromancer; lizardfolk geomancer and sovereign; the Elemental Cultist.

**Rules**: **Environmental Effects** (DMG 72–73) – extreme cold and heat, frigid and deep water, heavy precipitation, high altitude, strong wind – merged with the game's own weather and body systems (re-run the careful-player measurement).

**World**: elemental places at the wonders (salamanders, azers, efreet and magma mephits in volcanoes; air elementals and aarakocra eyries on the great peaks; marids in great lakes and waterfalls; xorn, galeb duhr and dao deep in mines and mountains); genies as rare legendary beings who strike bargains (bounded wishes, in conversation and in the history); four elemental cults in the history with temples in dungeons; lizardfolk tribes in marshes and jungles.

**Items**: elemental items (Efreeti Bottle, Efreeti Chain, Ring of Djinni Summoning, the bowl, brazier, censer and stone of controlling elementals, Elemental Gems, Flame Tongue, Frost Brand, Ring of Elemental Command; Appendix B).

**Tactics**: monks flurry and stun the casters, use Step of the Wind to reach the back line, deflect and send missiles back; elementals engulf (water) and whirl (air), earth elementals burrow and ambush; genies fly and cast; mephits die where their bursts catch the most.

**Pictures**: the pack's elementals, efreet, salamanders and gargoyles; drawn: djinni, dao and marid, the mephits, azers, xorn, galeb duhr; aarakocra and lizardfolk as dolls with their own bodies; monk outfits by culture; martial arts effects.

**Books**: PHB 103–110; DMG 72–73; MM elemental entries.

---
### 6.15 Callings & Crossroads (Expansion 15, S)

*Icon*: a signpost with twelve small arrows pointing every way. *Tagline*: "Walk more than one road."

**For Anton**: at level-up you may take a level in another class; a new character can begin as a seasoned veteran.

**Rules**: **Multiclassing** (PHB 47–48): ability prerequisites, the proficiencies a new class grants, spell slots by combined caster level, Pact Magic beside them, Extra Attack and Unarmored Defense that do not stack, Channel Divinity uses, and every other multiclass note in the book; the level-up screen offers "a level in another class"; companions multiclass when their archetype calls for it. **Starting at Higher Levels** (PHB 46): a new-character option to begin at level 5, 10 or 15 with the book's starting gear and money – natural for a new life in an old world (`game/interlude.py`).

**Tactics**: Auto plays multiclassed characters; arena tests for common combinations (paladin/warlock, fighter/wizard, rogue/ranger, cleric/druid...).

**Books**: PHB 46–48.

**Done when**: every pair of classes can be combined; the slot table and every non-stacking rule are tested.

---

### 6.16 Dragons & Hoards (Expansion 16, XL)

*Icon*: a coiled dragon asleep on a heap of coins, a crown on top. *Tagline*: "Ten colours of dragon. A hoard for every one."

**For Anton**: dragons of every colour and age, each with a lair that changes the land around it and a hoard worth the risk; the metallic dragons, who may be bargained with, or may hide among people.

**Parts**: A – the chromatic dragons and their lairs; B – the metallic and shadow dragons, the dracolich, hoards and the dragons' place in the world.

**Monsters**: every true dragon – black, blue, green, red, white, brass, bronze, copper, gold and silver, each as wyrmling, young, adult and ancient (40 stat blocks, of which the young red was re-made in Expansion 1); the shadow dragons; the dracolich – with legendary actions and resistances, in-lair uses and regional effects (Appendix A).

**World**: generalize today's dragon (`game/dragons.py`, `world.politics["dragons"]`, `history.json` beasts "dragon") to all of them. Colour follows the land: red in mountains and volcanoes, blue in deserts, green in forests, black in swamps, white in the frozen north, brass in deserts, bronze on coasts, copper in hills, gold by lakes and rivers of the plains, silver on high peaks. Temperament follows colour: chromatic dragons raid, extort tribute, take lairs and sometimes whole realms; metallic ones are rare, often hidden in mortal shape, open to bargains, and may help against a chromatic neighbour (conversations and quests) – they are not hostile by default. Ages matter: wyrmlings in nests, young dragons raiding, adults ruling a region (its regional effects), ancients as legends behind the history's "Age of Dragons". Dragon cults with kobolds and half-dragons; dragonslayers in the history and the Legends book; dragon fear in a region's news.

**Hoards**: the DMG's hoard tables are already in the game (Expansion 1); here a dragon's hoard is sized by its age and its colour's tastes. Carrying a hoard away takes time, carts and strength (the game's carry rules).

**Items**: dragon items (Dragon Scale Mail of each colour, Dragon Slayer, the Orb of Dragonkind; Appendix B).

**Tactics**: breath first where it catches most (already); fly out of reach and spend legendary actions between the party's turns; tail and wing against those surrounding it; Frightful Presence early; land only when it pays; young dragons flee when Bloodied; ancient dragons use their spellcasting; the dracolich and shadow dragons their own tricks.

**Pictures**: the pack's dragons (22 tiles: red, golden, ice, swamp, shadow, bone, storm, iron, pearl, quicksilver and more) mapped and recoloured to ten colours, sized by age (wyrmling on one square, young 2×2, adult 3×3, ancient 4×4); breath effects by damage type; lairs by colour (volcanic cave, desert canyon, forest hollow, sunken swamp ruin, ice cavern, and the metallic dragons' hidden halls), after the DMG's dragon's lair archetype.

**Books**: MM dragon entries; DMG 124–127 and chapter 7.

---

### 6.17 Goliaths & Giants (Expansion 17, L)

*Icon*: a stone-grey giant's fist around a boulder, peaks behind. *Tagline*: "The children of giants, and their towering kin."

**For Anton**: the goliaths of the high peaks; giants of hill, stone, frost, fire, cloud and storm in their steadings; rocs, yetis, remorhazes and winter wolves in the mountains and the frozen north.

**Species**: Goliath – Giant Ancestry (Cloud's Jaunt, Fire's Burn, Frost's Chill, Hill's Tumble, Stone's Endurance, Storm's Thunder), Large Form from 5th level, Powerful Build. Looks: tall and broad, grey to brown skins with darker markings, bald or braided.

**Culture**: high-mountain clans – nomadic peak camps and **stone circles** (a new town style: rings of standing stones, hide shelters, cairns, a throwing line; a few hewn halls on the summits); a law of fair contest where deeds are counted; a birth name, an earned name and a clan name (original pools); hide, fur, markings, bone and bronze; reverence for sky, stone and giant ancestors (an original faith). In the history: contests remembered for centuries, rivalries, and old alliances or wars with the giants.

**Monsters**: every giant (Appendix A) – hill, stone, frost, fire, cloud and storm giants; ettin; cyclops sentry and oracle; fomorian; ogrillon ogre; troll limb (the ogre and troll were re-made in Expansion 1) – and the beasts of the heights and the cold: roc, griffon, yeti, abominable yeti, remorhaz and young remorhaz, winter wolf, behir, harpy.

**World**: giant **steadings** as sites, one style per kind (hill giants' lodges, stone giants' caverns, frost giants' glacier halls, fire giants' forge-fortresses in volcanoes, cloud giants' castles on the great peaks, storm giants' sea-cliff halls); an old order of rank among the giants (original) behind their politics in the history; giant raids on the lowlands; trolls under bridges; rocs carrying off cattle; yetis in blizzards.

**Items**: giant items (every Belt of Giant Strength, Gauntlets of Ogre Power, Giant Slayer, Hammer of Thunderbolts, Potions of Giant Strength; Appendix B).

**Tactics**: giants throw rocks from range, stomp and sweep, grab and hurl the small; rocs seize and fly; trolls are burned or soaked in acid by a smart party and avoid fire themselves; goliaths time their Large Form.

**Pictures**: goliath bodies and markings, and Large Form; giants from the pack's giants and titans; roc and griffon from the pack; drawn: yeti, remorhaz, behir; winter wolf from the pack's warg recoloured.

**Books**: PHB 189–200 (Goliath); MM giant entries.

---

### 6.18 Gnomes & Golems (Expansion 18, M)

*Icon*: a gnome's pointed hat beside a riveted golem head with glowing eyes. *Tagline*: "Tinkers, tricksters, and the things they build."

**For Anton**: the gnomes – hidden forest villages and clattering tinker towns; golems, animated armour and flying swords guarding towers and vaults; the first rare gnomish firearms.

**Species**: Gnome – Gnomish Cunning; the Forest Gnome (Minor Illusion, Speak with Animals) and Rock Gnome (Mending, Prestidigitation, clockwork devices) lineages.

**Cultures**: forest gnomes in **hidden warrens** under hills and old trees, guarded by illusions (a new town style); rock gnomes in **tinker towns** of workshops, mill-wheels, clockwork and chimneys (a new town style); gnomish engineers and guildsfolk in other peoples' cities. Many names and nicknames each, an original faith, a history whose "works" (the history's works list) are inventions and discoveries; liked, and underestimated.

**Monsters**: every construct but the modrons (Appendix A) – animated armour, broom, flying sword and rug of smothering; homunculus; scarecrow; shield guardian; helmed horror; flesh, clay, stone and iron golems; gorgon and brazen gorgon; colossus.

**Rules**: **Firearms and explosives** (DMG 76–78), Renaissance items only (§1.3), as rare and expensive gnomish make: loud (they wake the whole dungeon), slow to reload; bombs and gunpowder. Rock gnomes' clockwork devices as items.

**World**: golems guard wizards' towers and old vaults; animated objects haunt arcane and haunted places; rich lords buy shield guardians (with their amulets); the colossus stands as a wonder's legendary guardian; tinker towns sell better goods (economy).

**Items**: construct and clockwork items (Manual of Golems, Iron Bands, the Apparatus, Immovable Rod, Cube of Force; Appendix B) and firearms.

**Tactics**: golems trust their immunities and smart enemies pick damage types against them; a shield guardian protects its master; a helmed horror shrugs off its chosen spells; gnomes hide behind illusions.

**Pictures**: gnome bodies and lineage looks; golems from the pack (nine tiles); drawn: the animated objects (from their item pictures), homunculus, gorgon, colossus; firearms, smoke and muzzle flash.

**Books**: PHB 189–200 (Gnome); DMG 76–78; MM construct entries.

---

### 6.19 Crypts & Curses (Expansion 19, XL)

*Icon*: a skull under a cracked tombstone, lit by a green ghost-light. *Tagline*: "The dead that walk, and the curses that raise them."

**For Anton**: every kind of undead – vampires and their courts, liches in their towers, mummy lords in desert tombs, death knights, banshees and ghosts; werewolves and the curse that spreads them; plagues, curses and terror that wear on the mind.

**Parts**: A – the undead; B – curses and contagions, lycanthropes and blights, fear and stress; C – the courts, towers, tombs and hauntings of the world.

**Monsters**: every undead not placed elsewhere, the lycanthropes, the blights and the Death Cultist and Vampire Familiar (Appendix A).

**Rules**: **Curses and Magical Contagions** (DMG 64–66): every curse and contagion – contagions such as cackle fever, sewer plague and sight rot join the health system's diseases (`rules/health.py`); **lycanthropy** as a curse the player can catch, with the book's rules for it and its cure; **Fear and Mental Stress** (DMG 74–75) as written – fear effects and stress that hurt – woven into the body and health systems; the DMG's thoughts on death (death scenes, the imprisoned, the raised) in `game/death.py`.

**World**: undead in the history – a tower mage who lived too long rises as a lich; a vampire court takes a town by night (people vanish, then the news, then the quests); mummy lords in desert tombs (the barrow system extended to the desert); death knights as fallen heroes of the history (a famous paladin who betrayed his oath in a war); haunted battlefields (`politics["scars"]`) gain specters and banshees; ghosts of named dead from the Legends book haunt their homes (a "spooky house" site style, after the DMG archetype); werewolf curses spreading through villages (news, hunts); blights around a vampiric tree corrupting a forest (a regional effect). Lairs: lich tower, vampire castle, mummy tomb, haunted manor.

**Items**: undead and death-cursed items (Sword of Life Stealing, Nine Lives Stealer, Talisman of Ultimate Evil, the Book of Vile Darkness, the Eye and Hand of Vecna, the Sword of Kas, and the cursed items whose curse is death or undeath; the other cursed items come in Expansion 25; Appendix B).

**Tactics**: vampires charm, bite and turn to mist; liches counterspell, use their power words and legendary actions; banshees wail when many can hear; ghosts possess (a possessed companion fights for the ghost until freed); wraiths raise specters from the slain; mummies' dreadful glare; mindless undead press on, smart undead plan; incorporeal undead pass through walls.

**Pictures**: the pack's undead (lich, vampire, mummy, wraith, ghosts, skeletons, zombies, death knight, revenant, shadow, wight and more); drawn: banshee, poltergeist (an effect), crawling claw, flameskull, will-o'-wisp (a light), the blights, and the lycanthropes' hybrid forms.

**Books**: DMG 64–66, 74–75; MM undead, lycanthrope and blight entries.

---

### 6.20 Drow & the Underdark (Expansion 20, XL)

*Icon*: a spider hanging over a faintly glowing mushroom, framed by stalactites. *Tagline*: "Below the deepest mine, another world."

**For Anton**: below some mountains, caves, mines and dwarven holds lies the Underdark – vast caverns with fungus forests, black lakes and chasms – and in it the drow cities, kuo-toa shrines, myconid circles and the things that hunt in the dark.

**Parts**: A – the Reaches; B – the drow and the other peoples below; C – the Underdark's creatures.

**World layer – the Underdark**: the deepest levels of certain sites open into **Reaches** – huge cavern regions, each several large levels deep, with fungus forests, underground lakes, chasms and bridges, glowing lichens, crystals, and *faerzress* (zones of strange magic where teleportation fails and divinations blur). A world has a few Reaches (more in larger worlds), entered through deep sites and linked to one another by slow underground roads. They are part of the history (drow raids, deep wars, lost dwarven delvings), of the Legends book, and of the world map as a simple "below" view. Underdark travel uses the survival systems (no sun, darkness, getting lost, fungus to eat).

**Peoples**: the **drow** cities – a drow culture of their own (names; law of rival noble houses; an original spider faith; spider-silk, dark mail and white hair; a new town style of stalagmite spires, faerie-fire lanterns, webs and mushroom fields) – raiding the surface in the history and while you play; drow exiles on the surface (since Expansion 11). Others below: dwarven deep holds (World Variety's holds reaching down), kuo-toa shrines, myconid circles.

**Monsters**: the Underdark's aberrations, monstrosities and fungi (Appendix A) – grimlocks, kuo-toa, gricks, ropers, piercers, darkmantles, hook horrors, umber hulks, quaggoths, troglodytes, carrion crawlers, purple worms, driders, myconids, gas spores, shriekers, violet fungi.

**Items**: Underdark and drow items (Cloak of Arachnida, Gem of Seeing, Lantern of Revealing, drow poison from Expansion 4; Appendix B).

**Tactics**: grimlocks fight by sound; hook horrors hunt by echo; umber hulks confuse with their gaze; ropers reel prey in; piercers drop from the ceiling; darkmantles smother light; myconids spread spores and share minds; purple worms swallow; drow cast darkness, shoot poisoned bolts and levitate out of reach.

**Pictures**: an Underdark tile set (fungus, lichens, crystals, webs, chasm edges, glowing water) in the style of `tile_art.py`; drow dolls; monsters from the pack where they exist (worms, troglodytes, spiders) and drawn (umber hulk, hook horror, quaggoth, myconids, carrion crawler, roper, piercer, darkmantle, grimlock, kuo-toa, drider).

**Books**: PHB 189–200 (the Drow lineage); MM entries; the DMG's Underdark warren archetype.

---

### 6.21 Mind Flayers & Psionics (Expansion 21, L)

*Icon*: a tentacled head in profile with a violet swirl where the brain would be. *Tagline*: "Minds that devour minds, and the warriors who fight with thought."

**For Anton**: two psionic paths – the Psi Warrior (fighter) and the Soulknife (rogue); mind flayers, beholders, aboleths and the other aberrations; the githyanki and githzerai.

**Rules**: Psi Warrior (Psionic Power, Protective Field, Psionic Strike, Telekinetic Movement, Telekinetic Adept, Guarded Mind, Bulwark of Force, Telekinetic Master); Soulknife (Psionic Power, Psychic Blades, Soul Blades, Psychic Veil, Rend Mind); the beholder's antimagic cone and the mind flayers' mind control on the kernel's antimagic and changing sides (Expansion 1); the mind flayer's brain extraction as the game's deadliest blow.

**Monsters**: every aberration not placed in the Underdark (Appendix A) – mind flayer and arcanist, intellect devourer, beholder, death tyrant, spectator, beholder zombie, aboleth, chuul, cloaker, gibbering mouther, grell, nothic, otyugh, flumph, githyanki soldier, knight and dracomancer, githzerai monk, psion and zerth – with the thri-kreen and the Aberrant Cultist.

**World**: mind flayer colonies deep in the Reaches; beholders in isolated lairs (each a paranoid tyrant with regional effects); aboleths beneath deep lakes, remembering the whole history (they can answer Legends questions, at a price); githyanki raiders arriving through rare portals (their full home comes in Expansion 27), some riding red dragons; githzerai monasteries hidden in remote mountains (monk companions); thri-kreen nomads in deserts and savannas; Great Old One warlocks and aberrant cults finally have something to serve; otyughs in sewers and refuse pits; cloakers in deep caves.

**Items**: psionic and aberrant items (the githyanki silver sword if the DMG has it, Helm of Telepathy, Ring of Mind Shielding; Appendix B).

**Tactics**: mind flayers Mind Blast the cluster, then feed on the stunned; beholders choose eye rays and aim the antimagic cone; intellect devourers steal bodies; aboleths enslave; gith teleport psionically; nothics use their rotting gaze and weird insight; cloakers fill the dark with phantasms.

**Pictures**: drawn: mind flayer (doll body, its own head), beholder (from the pack's great orb of eyes), spectator, death tyrant, intellect devourer, aboleth, chuul, gibbering mouther, grell, nothic, otyugh, flumph, cloaker, thri-kreen; gith as dolls with their own features; psionic effects.

**Books**: PHB 93–102, 131–140; MM aberration entries.

---

### 6.22 Traps & Terrors (Expansion 22, L)

*Icon*: a spiked pit below a treasure chest that has teeth. *Tagline*: "The dungeon wants you dead. So does everything living in it."

**For Anton**: the Dungeon Master's Guide's traps and hazards – rolling stones, falling nets, green slime, quicksand, razorvine – that you can find, avoid, disarm and set yourself; medusas, basilisks, hydras, chimeras, mimics and gelatinous cubes.

**Rules**: **Traps** (DMG 104–107): the parts of a trap (trigger, duration, effect, countermeasures, severity by level), every example trap (collapsing roof, falling net, fire-casting statue, hidden pit, poisoned darts, poisoned needle, rolling stone, spiked pit) and the rules for building more – the game's existing traps rebuilt on these rules, with severity by depth and danger; the party can **set traps** at camp and in dungeons. **Hazards** (DMG 80–83): every hazard in the chapter (brown mold, green slime, yellow mold, razorvine, quicksand, webs, rockslide, inferno, slippery and thin ice and the rest) on the battle grid and the close-up maps. **Dungeons and doors** (DMG toolbox): doors, portcullises, secret doors, shrines and the rest improve dungeon generation; Search and Study find traps.

**Monsters**: mythic and dungeon monsters – mimic, rust monster, basilisk, cockatrice and cockatrice regent, medusa, chimera, manticore, hydra, bulette and bulette pup, minotaur of Baphomet, death dog, yuan-ti infiltrator, malison and abomination – and every ooze (black pudding, gray ooze, psychic gray ooze, ochre jelly, gelatinous cube, blob of annihilation) (Appendix A).

**World**: medusa lairs with statue gardens – petrified adventurers whose names are in the Legends book; basilisk caves; hydra marshes; chimera and manticore crags; bulettes under the plains (events: "the ground opens"); yuan-ti serpent temples in jungles and deserts, and yuan-ti infiltrators in courts (politics); minotaurs in labyrinth ruins (a labyrinth dungeon style); mimics in every old dungeon.

**Items**: dungeon and utility items (Bag of Devouring, Portable Hole, Rope of Climbing and of Entanglement, Chime of Opening, Gem of Brightness, Sphere of Annihilation, Talisman of the Sphere; Appendix B).

**Tactics**: mimics wait disguised (Study or Investigation reveals them); rust monsters go for metal; the medusa's gaze – and the player's option to fight with eyes averted; basilisk and cockatrice petrification; gelatinous cubes engulf in corridors; hydras grow heads; yuan-ti charm, poison and change shape.

**Pictures**: trap and hazard tiles (molds, slime, razorvine, quicksand, rolling stone, nets, darts); from the pack: manticore, basilisk, medusa, hydra (heads drawn by count), minotaur, jellies; drawn: mimic (several chests), rust monster, bulette, chimera, cockatrice, death dog, yuan-ti, gelatinous cube (transparent, with things inside).

**Books**: DMG 80–83, 104–107 and the toolbox's dungeon pages; MM entries.

---

### 6.23 Ships & Sea Monsters (Expansion 23, XL)

*Icon*: a ship's prow cutting a wave, a tentacle rising beside it. *Tagline*: "Set sail. Something vast is waiting below."

**For Anton**: sailing between ports – booking passage or owning a ship; fights on deck and under water; pirates, sahuagin, merfolk, merrow, the dragon turtle and the kraken.

**Parts**: A – ships and sea travel; B – underwater and deck battles; C – the sea's creatures and their place in the world.

**Rules**: **Vehicles** (PHB 216–236): rowboat, keelboat, longship, sailing ship, galley and warship, with their speeds, crews, cargo and prices (the land vehicles came in Expansion 2); **sea travel** between ports on the world map (World Variety's coasts, islands and bays) – passage, or your own ship with crew wages and upkeep; days at sea with weather and storms; sea events; ports and docks in coastal towns; **underwater combat** (PHB Rules Glossary): melee disadvantage except with the right weapons, ranged attacks that fail beyond normal range, resistance to fire, swimming speeds, holding breath and suffocation; **ship battles** on deck maps and boarding actions (ship-mounted ballistas and mangonels join in when Expansion 26 adds siege equipment; mark them `upgrade_in` 25).

**Monsters**: the kraken, merrow, sahuagin warrior, priest and baron, merfolk skirmisher and wavebender, water weird, dragon turtle, lacedon ghoul, and the pirates (pirate, pirate captain, pirate admiral) (Appendix A); the sea beasts of Expansion 12 (sharks, the killer whale, giant octopus and squid, plesiosaurus, archelon, piranhas) now appear at sea.

**World**: pirate factions and havens (piracy in the history and the news; a pirate admiral as a figure); sahuagin raids on coastal villages; the kraken as a legendary beast of the deep (its regional effect: ships lost); a dragon turtle in warm seas; merfolk and marids (from Expansion 14) as rare undersea peoples to trade with or quarrel with; shipwrecks as dungeons (explored with water breathing); lighthouses and harbours as sites (after the DMG's ship archetype).

**Items**: sea items (Cap of Water Breathing, Cloak of the Manta Ray, Trident of Fish Command, Folding Boat, Ring of Swimming, Ring of Water Walking, Decanter of Endless Water, Necklace of Adaptation; Appendix B).

**Tactics**: sahuagin blood frenzy; the kraken grapples and drags ships; pirates board in waves and cut rigging; merrow harpoon and pull; everything moves in three dimensions under water.

**Pictures**: ships on the world map and as deck tiles; water battle tiles; the pack's kraken (27 tiles), merfolk, sharks; drawn: sahuagin, merrow, dragon turtle, octopus and squid where the pack lacks them, the water weird.

**Books**: PHB 216–236, 363–380; MM entries; the DMG's ship archetype.

---

### 6.24 Potions & Scrolls (Expansion 24, L)

*Icon*: a stoppered flask beside a scroll with a wax seal, a few sparks. *Tagline*: "Every draught, every scroll, and the craft to make them."

**For Anton**: every potion, oil, elixir, dust and scroll of the Dungeon Master's Guide; making things – gear with tools, potions of healing with herbs, spell scrolls with ink, and magic items with time, gold and the right materials; shops where alchemists and scribes sell them.

**Content**: every consumable magic item not already delivered (potions, oils, philters, elixirs, dusts, beads, candles, magic ammunition and special arrows, and items used up with their charges; Appendix B) – the Potions of Healing and Spell Scrolls came with Expansion 3, the +N ammunition with Expansion 2, the Potions of Giant Strength with Expansion 17.

**Rules**: **Crafting** – the PHB's crafting of gear with tools (time and cost), brewing potions of healing (herbalism kit), scribing spell scrolls; the DMG's crafting of magic items (time and cost by rarity, the recipe, the tools and spells it needs) – at camp, in workshops and in towns, through `game/camp.py` crafts and the services system; **magic shops** (alchemists, scriveners) by settlement size and the world's *Magic* setting; identifying and attuning made easy on the item card.

**World**: alchemists' and scriveners' guilds; a potion trade; an alchemist's shop that explodes now and then (an event).

**Tactics**: enemies drink potions (healing, invisibility, giant strength), throw oils and alchemist's fire, read scrolls.

**Pictures**: a picture for every consumable (the pack has many potions and scrolls).

**Books**: PHB 216–236 (crafting); DMG chapter 7 (crafting and items).

---

### 6.25 Rings & Relics (Expansion 25, XL)

*Icon*: a gold ring set with a red stone before an ancient crowned relic. *Tagline*: "The magic that remains, and the relics that shaped history."

**For Anton**: every remaining magic item of the Dungeon Master's Guide; the remaining artifacts – the Axe of the Dwarvish Lords, Blackrazor, Wave and Whelm and their kind – woven into each world's history, as the themed ones (the Orb of Dragonkind, the Eye and Hand of Vecna...) were by their own expansions; swords that talk back; cursed things that will not let go; the Deck of Many Things.

**Parts**: A – the items; B – artifacts in the history, sentient and cursed items, the treasure tables in full.

**Content**: every permanent magic item not delivered by a themed expansion – rings, rods, staffs, wands, weapons, armour and wondrous items (Appendix B).

**Rules**: the artifact, sentient and cursed item rules already exist (Expansion 1, §4.8); this expansion delivers every artifact not placed by a themed expansion, with its major and minor properties rolled per world and its means of destruction; **artifacts in the history** (for every artifact, themed ones included): when a world is made, some of the history's own named artifacts *are* these (a dwarven hold's crown-axe is the Axe of the Dwarvish Lords, broken in a war and scattered; the Orb of Dragonkind passes through a dragon war), so the Legends book tells where they went and the lost-treasure system (`game/past.py`) can lead you to them; **Sentient items**: every remaining one – each speaks in written lines chosen by its personality, purpose and the moment, and a sentient weapon can argue, refuse, or seize control on a lost conflict; **Cursed items**: every remaining one, revealed on attunement; the random magic item tables complete; magic items awarded by level in quest rewards; legendary items as quest goals.

**World**: famous items in the Legends book; artifact hunts as quests; realms that covet an artifact and go to war for it (politics).

**Tactics**: enemies use their wands, staffs and rings (through the kernel); artifact-bearers as bosses.

**Pictures**: a picture for every item (the pack has hundreds of rings, amulets, wands, staffs and rods); drawn pictures for every artifact; worn looks (`item.magic["look"]`) for the new items.

**Books**: DMG chapter 7 (217–338).

---

### 6.26 Bastions & Banners (Expansion 26, L)

*Icon*: a small keep tower flying a banner, a ballista before it. *Tagline*: "A home to hold. A war to wage."

**For Anton**: a bastion of your own – a keep, a manor, a tower or a temple – with rooms you build, hirelings who work there and events that happen while you are away; siege engines, and joining real sieges of the world's wars; titles, land and medals from the realms you serve.

**Rules**: **Bastions** (DMG 339–357): gaining one at 5th level (or buying or being granted land), basic facilities, every special facility by level, hirelings, the orders (Craft, Empower, Harvest, Maintain, Recruit, Research, Trade), a bastion turn every seven days of game time, every bastion event, defenders, attacks, and the fall of a bastion – a real place on the world map with its own close-up map, visitors and defenders (this is the "owning property" idea in the PROGRESS parking lot); a stronghold's own marks of prestige (fortifications and training; the DMG's **Marks of Prestige** and **Renown** came with Adventures & Events, Expansion 6, as Legend, titles and rights); **Siege Equipment** (DMG 100–101): ballista, cannon (gnomish, from Expansion 18), mangonel, trebuchet, ram, siege tower, cauldron and every other engine in the section, crewed on the battle grid; **joining sieges** – the politics engine's sieges can be joined on either side, as large battles with mobs (Expansion 9) and engines.

**World**: bastions attacked by enemies the player made; realms granting land to heroes; the history's sieges now use engines; hirelings come from the world's people.

**Tactics**: crews work their engines; mobs storm walls; defenders hold them; attackers choose where to breach.

**Pictures**: bastion facility tiles; siege engines; banners by realm.

**Books**: DMG 84–86, 96, 100–101, 339–357.

---

### 6.27 Planes & Portals (Expansion 27, XL – version 2.0.0)

*Icon*: a ring-shaped portal with a starry void inside, two different horizons on either side. *Tagline*: "Beyond the edge of the world, other worlds."

**For Anton**: the planes of the D&D multiverse as places you can reach – the Feywild, the Shadowfell, the elemental planes, the Nine Hells, the Abyss, the Upper Planes, the Astral Sea – through portals at the world's wonders, a cult's summoning gone wrong, or the spells of a great mage; slaadi, modrons, and the tarrasque.

**Parts**: A – the planar framework, the Feywild and the Shadowfell; B – the elemental planes, the Hells, the Abyss, the Upper Planes and the Astral, with their creatures; C – the tarrasque and the planes' place in the world's history.

**Rules**: **Cosmology** (DMG 177–216; PHB 347–348): each plane as a **planar realm** – not a whole world, but a large special region built like the Underdark's Reaches, several levels deep, with its own terrain, light, weather and **planar effects** (every effect the DMG lists, such as the Feywild's strange time, the Shadowfell's despair, Arcadian Vitality and Gehennan Cruelty); planar travel through portals, Plane Shift, Gate, Teleportation Circle, Astral Projection, Etherealness and Demiplane – now fully working; planar hazards.

**Monsters**: the slaadi (tadpole, red, blue, green, gray, death), the modrons (monodrone to pentadrone) and the tarrasque (Appendix A); planar versions of the fiends, celestials, elementals and fey already in the game live here.

**World**: portals at wonders (the drifting stones, glowing lakes, the giant tree) and in the history; portals opened by cults (Expansion 7), archmages (Expansion 5) and aberrant rifts (Expansion 21); rare planar incursions late in long histories (a githyanki raid, a slaad plague, a modron march); the tarrasque as a doom asleep beneath the world that a history may wake – the game's greatest fight; the Legends book's pages on other worlds.

**Tactics**: planar creatures' teleports and gates; slaadi spread their chaos (the slaad's implanted eggs as a contagion); modrons move in formation.

**Pictures**: planar tile sets (fey colours, shadow greys, hellish reds, abyssal violet, the starfield of the Astral, the four elements); drawn: the slaadi, the modrons and the tarrasque.

**Books**: DMG 177–216; PHB 347–348; MM entries.

**Done when**: the whole codex is done, adapted or omitted with reasons – the programme is complete.

---
## Appendix A – Every Monster Manual stat block, by expansion

Cleaned from the Monster Manual's own lists (Appendix B, PDF 377–387) and checked against its entries; the codex (§4.2) is the final authority, so correct any name the scan misread. "Re-made" means a creature the game already has, converted to its 2025 stat block in Expansion 1 (rename ids freely, updating every reference).

**Expansion 1 – Dice & Destiny (re-made)**: Wolf; Dire Wolf; Jackal (today's wild dog); Boar; Black Bear; Brown Bear; Giant Rat; Giant Spider; Stirge; Bandit; Scout (today's bandit archer); Bandit Captain; Tough (thug); Warrior Infantry (deserter; and orc raiders, with the Orc species); Tough Boss (orc warchief, with the Orc species) – until Expansion 2 adds the Orc species, orc raiders keep today's half-orc look and traits; Cultist; Cultist Fanatic; Skeleton; Zombie; Ghoul; Wight; Gnoll Warrior; Hobgoblin Warrior; Bugbear Warrior; Berserker; Goblin Warrior; Goblin Boss; Ogre; Troll; Young Red Dragon (today's young dragon); Commoner; Guard; Priest Acolyte (acolyte); Noble.

**Expansion 2 – Blades & Backgrounds**: Riding Horse, Draft Horse, Warhorse, Pony, Mule, Camel, Mastiff.

**Expansion 4 – Steel & Shadows**: Assassin, Spy, Spy Master.

**Expansion 5 – Schools & Domains**: Mage Apprentice, Mage, Archmage, Priest, Archpriest.

**Expansion 7 – Tieflings & Warlocks** (every fiend): *devils* – Imp, Lemure, Swarm of Lemures, Spined Devil, Bearded Devil, Barbed Devil, Chain Devil, Bone Devil, Horned Devil, Erinyes, Ice Devil, Pit Fiend; *demons* – Manes, Manes Vaporspawn, Dretch, Swarm of Dretches, Quasit, Shadow Demon, Barlgura, Chasme, Vrock, Hezrou, Glabrezu, Yochlol, Nalfeshnee, Marilith, Goristro, Balor; *yugoloths* – Mezzoloth, Nycaloth, Arcanaloth, Ultroloth; *others* – Cambion, Succubus, Incubus, Hell Hound, Nightmare, Night Hag, Rakshasa, Oni, Lamia, Larva, Swarm of Larvae, Jackalwere, Spirit Naga; *the demon lord's gnolls* – Gnoll Pack Lord, Gnoll Demoniac, Gnoll Fang of Yeenoghu; Fiend Cultist.

**Expansion 8 – Dragonborn & Sorcerers**: Kobold Warrior, Winged Kobold, Half-Dragon, Pseudodragon, Faerie Dragon Youth, Faerie Dragon Adult, Wyvern.

**Expansion 9 – Orcs & Barbarians**: Warrior Veteran, Warrior Commander, Berserker Commander.

**Expansion 10 – Aasimar & Paladins** (every celestial): Deva, Planetar, Solar, Couatl, Empyrean, Empyrean Iota, Pegasus, Unicorn, Sphinx of Lore, Sphinx of Secrets, Sphinx of Valor, Sphinx of Wonder, Guardian Naga, Giant Eagle, Giant Owl, Giant Elk; Knight, Questing Knight.

**Expansion 11 – Elves & Rangers** (the fey and the forest): Goblin Minion, Goblin Hexer, Hobgoblin Captain, Hobgoblin Warlord, Bugbear Stalker, Green Hag, Sea Hag, Arch-hag, Pixie, Pixie Wonderbringer, Sprite, Dryad, Satyr, Satyr Revelmaster, Blink Dog, Centaur Trooper, Centaur Warden, Bullywug Warrior, Bullywug Bog Sage, Worg, Dire Worg; Displacer Beast, Ettercap, Phase Spider; Scout Captain.

**Expansion 12 – Druids & Beasts**: *beasts* – Allosaurus, Ankylosaurus, Ape, Archelon, Baboon, Badger, Bat, Blood Hawk, Cat, Constrictor Snake, Crab, Crocodile, Deer, Eagle, Elephant, Elk, Frog, Giant Ape, Giant Badger, Giant Bat, Giant Boar, Giant Centipede, Giant Constrictor Snake, Giant Crab, Giant Crocodile, Giant Fire Beetle, Giant Frog, Giant Goat, Giant Hyena, Giant Lizard, Giant Octopus, Giant Scorpion, Giant Seahorse, Giant Shark, Giant Squid, Giant Toad, Giant Venomous Snake, Giant Wasp, Giant Weasel, Giant Wolf Spider, Goat, Hawk, Hippopotamus, Hunter Shark, Hyena, Killer Whale, Lion, Lizard, Mammoth, Octopus, Owl, Panther, Piranha, Plesiosaurus, Polar Bear, Pteranodon, Rat, Raven, Reef Shark, Rhinoceros, Saber-Toothed Tiger, Scorpion, Seahorse, Spider, Swarm of Bats, Swarm of Insects, Swarm of Piranhas, Swarm of Rats, Swarm of Ravens, Swarm of Venomous Snakes, Tiger, Triceratops, Tyrannosaurus Rex, Venomous Snake, Vulture, Weasel (and any other animal of the MM's Appendix A not named elsewhere here); *plants* – Awakened Shrub, Awakened Tree, Shambling Mound, Treant; *monstrosities* – Owlbear, Primeval Owlbear, Axe Beak, Giant Axe Beak, Giant Vulture, Peryton, Hippogriff, Ankheg, Flying Snake, Swarm of Stirges; Animal Lord; Druid.

**Expansion 13 – Bards & Brigands**: Bandit Crime Lord, Bandit Deceiver, Gladiator, Guard Captain, Noble Prodigy, Performer, Performer Maestro, Performer Legend, Cultist Hierophant; Doppelganger, Kenku.

**Expansion 14 – Monks & Elementals** (every elemental): Air Elemental, Earth Elemental, Fire Elemental, Water Elemental, Elemental Cataclysm; Djinni, Efreeti, Dao, Marid; Dust Mephit, Ice Mephit, Magma Mephit, Mud Mephit, Smoke Mephit, Steam Mephit; Magmin; Salamander, Salamander Fire Snake, Salamander Inferno Master; Azer Sentinel, Azer Pyromancer; Gargoyle, Galeb Duhr, Xorn, Invisible Stalker; Aarakocra Skirmisher, Aarakocra Aeromancer; Lizardfolk Geomancer, Lizardfolk Sovereign; Elemental Cultist.

**Expansion 16 – Dragons & Hoards**: Black, Blue, Green, Red and White Dragons and Brass, Bronze, Copper, Gold and Silver Dragons, each as Wyrmling, Young, Adult and Ancient (the Young Red was re-made in Expansion 1); Juvenile Shadow Dragon, Shadow Dragon; Dracolich.

**Expansion 17 – Goliaths & Giants**: Hill Giant, Stone Giant, Frost Giant, Fire Giant, Cloud Giant, Storm Giant, Ettin, Cyclops Sentry, Cyclops Oracle, Fomorian, Ogrillon Ogre, Troll Limb; Roc, Griffon, Yeti, Abominable Yeti, Remorhaz, Young Remorhaz, Winter Wolf, Behir, Harpy.

**Expansion 18 – Gnomes & Golems**: Animated Armor, Animated Broom, Animated Flying Sword, Animated Rug of Smothering, Homunculus, Scarecrow, Shield Guardian, Helmed Horror, Flesh Golem, Clay Golem, Stone Golem, Iron Golem, Gorgon, Brazen Gorgon, Colossus.

**Expansion 19 – Crypts & Curses**: *undead* – Banshee, Bone Naga, Crawling Claw, Swarm of Crawling Claws, Death Knight, Death Knight Aspirant, Demilich, Flameskull, Flaming Skeleton, Ghast, Ghast Gravecaller, Ghost, Revenant, Graveyard Revenant, Haunting Revenant, Lich, Minotaur Skeleton, Mummy, Mummy Lord, Ogre Zombie, Poltergeist, Shadow, Specter, Vampire, Vampire Spawn, Vampire Nightbringer, Vampire Umbral Lord, Warhorse Skeleton, Will-o'-Wisp, Wraith; *lycanthropes* – Werewolf, Wererat, Wereboar, Weretiger, Werebear; *blights* – Twig Blight, Needle Blight, Vine Blight, Tree Blight, Gulthias Blight; Death Cultist, Vampire Familiar.

**Expansion 20 – Drow & the Underdark**: Grimlock; Kuo-toa, Kuo-toa Whip, Kuo-toa Monitor, Kuo-toa Archpriest; Grick, Grick Ancient; Roper, Piercer, Darkmantle; Hook Horror, Umber Hulk, Quaggoth, Quaggoth Thonot, Troglodyte, Carrion Crawler, Purple Worm, Drider; Myconid Sprout, Myconid Adult, Myconid Sovereign, Myconid Spore Servant, Gas Spore Fungus, Shrieker Fungus, Violet Fungus, Violet Fungus Necrohulk.

**Expansion 21 – Mind Flayers & Psionics**: Mind Flayer, Mind Flayer Arcanist, Intellect Devourer; Beholder, Death Tyrant, Spectator, Beholder Zombie; Aboleth, Chuul, Cloaker, Gibbering Mouther, Grell, Nothic, Otyugh, Flumph; Githyanki Soldier, Githyanki Knight, Githyanki Dracomancer; Githzerai Monk, Githzerai Psion, Githzerai Zerth; Thri-kreen Marauder, Thri-kreen Psion; Aberrant Cultist.

**Expansion 22 – Traps & Terrors**: Mimic, Rust Monster, Basilisk, Cockatrice, Cockatrice Regent, Medusa, Chimera, Manticore, Hydra, Bulette, Bulette Pup, Minotaur of Baphomet, Death Dog, Yuan-ti Infiltrator, Yuan-ti Malison, Yuan-ti Abomination; *oozes* – Black Pudding, Gray Ooze, Psychic Gray Ooze, Ochre Jelly, Gelatinous Cube, Blob of Annihilation.

**Expansion 23 – Ships & Sea Monsters**: Kraken, Merrow, Sahuagin Warrior, Sahuagin Priest, Sahuagin Baron, Merfolk Skirmisher, Merfolk Wavebender, Water Weird, Dragon Turtle, Lacedon Ghoul, Pirate, Pirate Captain, Pirate Admiral.

**Expansion 27 – Planes & Portals**: Slaad Tadpole, Red Slaad, Blue Slaad, Green Slaad, Gray Slaad, Death Slaad; Modron Monodrone, Modron Duodrone, Modron Tridrone, Modron Quadrone, Modron Pentadrone; Tarrasque.

**Anything the codex finds that is not listed above** goes by its creature type: Aberration → 20 (19 if its habitat is the Underdark); Beast → 11; Celestial → 9; Construct → 17; Dragon → 15; Elemental → 13; Fey → 10; Fiend → 6; Giant → 16; Humanoid → 12; Monstrosity → by habitat (Underdark 19, Underwater or Coastal 22, Mountain or Arctic 16, Forest or Grassland 11, otherwise 21); Ooze → 21; Plant → 11 (19 if Underdark); Undead → 18; a creature that lives only on the planes → 26. Write the choice into the codex.

The PHB's own stat blocks (its Appendix B: familiars, the Otherworldly Steed, summoned spirits, animated dead and the beasts printed there) all arrive in Expansion 3 – including those the MM also prints, whose family expansion above then only places them in the world. The Beast Master's primal companions, printed in the ranger chapter, arrive with Expansion 11.

---

## Appendix B – Which expansion brings which magic item

Apply these rules in order when building the codex; the first that fits decides. Write every assignment into `magic_items.json` in the codex; when an item could go two ways, choose the expansion whose part of the world it belongs to and say so in the note.

1. **Artifacts** → Expansion 25, except: the Wand of Orcus and the Demonomicon of Iggwilv → 7; the Book of Exalted Deeds → 10; the Orb of Dragonkind → 16; the Book of Vile Darkness, the Eye and Hand of Vecna and the Sword of Kas → 19. (Axe of the Dwarvish Lords, Blackrazor, Wave, Whelm and any other artifact → 25.)
2. **Plain enhancement**: +1/+2/+3 weapons, armour, shields and ammunition; adamantine and mithral armour → 2. Potions of Healing (all) and Spell Scrolls (all levels) → 3.
3. **Themed items**, by what they are for:
   - fiends, the Hells and the Abyss, pacts, warlocks → 7
   - sorcery, wild magic, draconic bloodlines → 8; dragons themselves (Dragon Scale Mail, Dragon Slayer and other dragon-named items) → 16
   - rage, berserkers, war-bands → 9
   - holy and radiant things, celestials, paladins, barding, smiting the undead → 10
   - elves, the fey, archery and rangers → 11
   - beasts, animals, plants, druids, the wild → 12
   - instruments, performers, disguise and confidence tricks → 13
   - elements and genies, elemental weapons (Flame Tongue, Frost Brand), monks and unarmed fighting → 14
   - giants and ogres, thunder and storm-giant things, Potions of Giant Strength → 17
   - constructs, golems, clockwork and machinery, gnomes, firearms → 18
   - undeath, necromancy, life-stealing, vampires, ghosts, and cursed items whose curse is death or undeath → 19
   - spiders, darkness, the Underdark, seeing what is hidden → 20
   - the mind, telepathy, psionics, the gith, aberrations → 21
   - dungeon delving: ropes, opening and closing, holes and spheres, devouring bags → 22
   - water, swimming, breathing, boats and the sea → 23
   - poison, stealth, thievery, assassins, fighters' and rogues' weapons with a trick → 4
   - wizards' and clerics' tools of the trade: staffs, wands, rods, robes, spellbooks, pearls, spell-storing → 5
   - fortresses, banners, war-horns, siege → 26
   - planes, portals, the Astral and Ethereal, gates → 27
4. **Consumables** not placed by rules 2–3 (potions, oils, philters, elixirs, dusts, beads, candles, magic ammunition and arrows, other single-use items) → 24.
5. **Everything else** (rings, cloaks, boots, belts, amulets, ioun stones, decks, figurines, wondrous items of every kind, the remaining cursed items) → 25.

---

## Appendix C – Spells outside battle

From Expansion 3 every spell works in battle. Outside battle, these groups plug into Realmwalker's systems. Where the system a spell needs arrives in a later expansion (ships, planes, bastions), the spell works in battle and in a simpler way until then, recorded as `adapted` in the codex with that note, and gains its full use when the system lands.

| Group | Examples | Where it plugs in |
|---|---|---|
| Healing and restoration | Cure Wounds, Healing Word, Prayer of Healing, Aid, Lesser and Greater Restoration, Remove Curse, Heal, Regenerate, Mass Heal | `rules/health.py`, `game/care.py`: hit points, wounds, blood, infection, diseases, poison, exhaustion, curses; Regenerate regrows lost limbs |
| Return from death | Spare the Dying, Revivify, Gentle Repose, Raise Dead, Reincarnate, Resurrection, True Resurrection | `game/death.py` (§4.5), temples (`game/services.py`), costly components |
| Food, water and the body | Goodberry, Create or Destroy Water, Purify Food and Drink, Create Food and Water, Heroes' Feast | `game/survival.py`, `game/camp.py`, `rules/body.py` |
| Shelter and watch | Alarm, Leomund's Tiny Hut, Rope Trick, Mordenkainen's Magnificent Mansion, Private Sanctum, Demiplane, Guards and Wards | camp (a safe night, no night encounters), dungeon rests, bastions (26) |
| Travel and movement | Longstrider, Jump, Feather Fall, Spider Climb, Levitate, Fly, Water Walk, Water Breathing, Pass without Trace, Phantom Steed, Wind Walk, Tree Stride, Transport via Plants, Teleport, Teleportation Circle, Word of Recall, Find the Path | `game/journey.py`, wayfinding, the world map; ships (23); planes (27); the survival clock keeps running |
| Finding and seeing | Detect Magic, Detect Evil and Good, Detect Poison and Disease, Detect Thoughts, Locate Animals or Plants, Locate Object, Locate Creature, Arcane Eye, Clairvoyance, Scrying, See Invisibility, True Seeing, Identify | the world map, dungeons (traps, secret doors), magic items, people's secrets |
| Asking the powers | Augury, Divination, Commune, Commune with Nature, Contact Other Plane, Legend Lore | answered from the world's real history and state (`world.politics`, the Legends book data, quests); vague where the truth is vague |
| Talking | Message, Comprehend Languages, Tongues, Speak with Animals, Speak with Plants, Speak with Dead, Sending, Animal Messenger, Rary's Telepathic Bond, Dream, Telepathy | conversations (written lines), languages, people the party knows, news, companions |
| Moving minds | Friends, Charm Person, Command, Calm Emotions, Suggestion, Zone of Truth, Compulsion, Geas, Dominate Person, Modify Memory, Mass Suggestion | conversation outcomes (whitelisted), `game/law.py` (enchanting people is a crime where magic is forbidden; victims remember being charmed), quests (Geas) |
| Disguise and stealth | Minor Illusion, Silent Image, Disguise Self, Alter Self, Invisibility, Silence, Major Image, Greater Invisibility, Nondetection, Seeming, Mind Blank | `game/law.py` (disguise, witnesses, bounties), stealth in towns and dungeons |
| Locks, stone and making | Mage Hand, Mending, Prestidigitation, Thaumaturgy, Unseen Servant, Knock, Arcane Lock, Stone Shape, Passwall, Wall of Stone, Fabricate, Creation, Move Earth, Glyph of Warding, Hallow, Forbiddance, Symbol | `game/dungeon.py` (locks, walls, secret ways, traps you set), crafting (24), bastions (26) |
| Weather and land | Druidcraft, Plant Growth, Control Water, Control Weather, Hallucinatory Terrain, Earthquake, Mirage Arcane, Storm of Vengeance | `world/weather.py` (an override of the weather function for a region and a time), harvests and the economy, close-up maps |
| Lasting protections | Mage Armor, Aid, Protection from Energy, Freedom of Movement, Death Ward, Stoneskin, Foresight | the existing lasting spells (`rules/spells.lasting`), carried into the next fight |
| Servants and summons | Find Familiar, Find Steed, Animate Dead, Create Undead, Planar Binding | `game/followers.py` (they follow and are seen by the law), mounts (`game/mounts.py`), scouting |
| Great magic | Plane Shift, Etherealness, Astral Projection, Gate, Magic Jar, Clone, Simulacrum, True Polymorph, Imprisonment, Wish | planes (27), death (Clone), companions (Simulacrum), Wish's safe uses and its stress |

---

## Appendix D – What becomes of what the game already has

| Today | Becomes | When |
|---|---|---|
| Fighter, Rogue, Cleric, Wizard (levels 1–10) | their 2024 versions, levels 1–20 | 3 (Weapon Mastery in 2) |
| Champion, Thief, Life, War, Evocation, Abjuration | Champion, Thief, Life Domain, War Domain, Evoker, Abjurer (2024) | 3 |
| Cutthroat | the Assassin (2024) | 3 |
| Knight | kept as a Realmwalker subclass, extended to level 18 | 3 |
| Human, Elf, Dwarf, Halfling | their 2024 versions (elf lineages chosen) | 2; full elven cultures 11, drow cities 20 |
| Half-Orc | the Orc (2024) | 2; the orcs' full culture 9 |
| Backgrounds (8) | 2024 backgrounds (16): Folk Hero → Farmer, Outlander → Guide, Guild Artisan → Artisan | 2 |
| Spells (41) and thrown flasks | definitions on the kernel, 2024 numbers | 1 (the full catalogue in 3) |
| Creatures (35) | their 2025 stat blocks (Appendix A), ids renamed freely | 1 |
| Items (172) | the 2024 equipment list | 2 |
| Magic item properties, curses | effects on the kernel; the procedural "blades with a story" kept as a family | 1 |
| Conditions, exhaustion, surprise, grappling | 2024 rules | 1 |
| Companion archetypes, unique companions | 2024 classes; new archetypes for every new class | 3 and each class expansion |
| Dragons (`game/dragons.py`) | all ten colours and four ages | 16 |
| History beasts and tribes (`history.json`) | extended by every monster expansion | 7–23 |
| Dungeon traps | rebuilt on the DMG's trap rules | 22 |
| Battle formation, morale, wounds, parley, surrender, death saves | kept – they are Realmwalker's own – and connected to the kernel | 1 |
| Player2 AI writer (descriptions, conversations, names, chronicle, obituaries) | removed for now; the built-in text everywhere, strengthened where thin; restorable from the `before-ai-removal` tag | §0.4 |
| Friends' build (`Build_For_Friends.bat`, the `.exe`, `README_FRIENDS.txt`) | removed; friends download from GitHub; `README.md` is the front page | §0.4 |
| Letters mode | removed; pictures are the only look; tests draw through a headless picture context | §0.4 |
| Save migrations and code for worlds made before the lived history, factions, dungeons or packs | removed; older saves are refused kindly | §0.4 |
| The creatures' front/back `rank` (from two-rank combat) | each creature's role and preferred range | 1 |
| Pull requests and stacked branches | each finished part merged into `main` and pushed; each finished expansion tagged and released on GitHub | §0.3 |

---

## Appendix E – Every rules system in the books, by expansion

| Book | System | Expansion |
|---|---|---|
| PHB | Playing the Game; the Rules Glossary (all but mounted and underwater combat); Heroic Inspiration; exhaustion; surprise; telepathy, changing sides and antimagic as kernel rules | 1 |
| PHB | Weapon Mastery; weapons, armour, gear, tools; land mounts and vehicles; services; trinkets | 2 |
| PHB | Backgrounds; origin, general and fighting style feats; creating a character | 2 |
| PHB | Level advancement to 20; epic boons; spellcasting; every spell; Appendix B stat blocks | 3 |
| PHB | Mounted combat | 10 |
| PHB | Multiclassing; starting at higher levels | 15 |
| PHB | Water vehicles; underwater combat | 23 |
| PHB | Crafting gear, potions of healing and spell scrolls | 24 |
| PHB | The multiverse | 27 |
| DMG | Travel pace; starting attitudes; objects; encounter difficulty and XP budget; adventure rewards; treasure and hoard tables; magic item rules, including the rules for artifacts, sentient items and cursed items | 1 |
| DMG | Poison | 4 |
| DMG | Gods and divine intervention | 5 |
| DMG | Renown; marks of prestige; settlement calamities; creating adventures and campaigns (as the story engine's guidance) | 6 |
| DMG | Demonic possession | 7 |
| DMG | Mobs | 9 |
| DMG | Supernatural gifts (blessings and charms) | 10 |
| DMG | Chases; settlements; Nonplayer Characters and attitudes in depth | 13 |
| DMG | Environmental effects | 14 |
| DMG | Dragons' hoards by age, and carrying them off | 16 |
| DMG | Firearms and explosives (Renaissance only) | 18 |
| DMG | Curses and magical contagions; fear and mental stress; death | 19 |
| DMG | Hazards; traps; doors and dungeons | 22 |
| DMG | Crafting magic items; consumable items | 24 |
| DMG | The remaining artifacts, sentient and cursed items; the random magic item tables in full | 25 |
| DMG | Bastions; siege equipment | 26 |
| DMG | Cosmology; planar travel; planar effects | 27 |
| DMG | Greyhawk; Lore Glossary; DM advice; maps; creating backgrounds, creatures, magic items and spells; alignment (kept only as a stat block field) | omitted or used as guidance (§1.3) |
| MM | Stat block rules; legendary actions and resistance; lairs and regional effects; habitats, treasure themes and groups | 1 (each family as in Appendix A) |

---

## Appendix F – Decisions Anton may want to change

These were decided so the work can go ahead without stopping. Each is easy to change if Anton says so; record his answer in `STATUS.md` and here.

1. **World Variety is finished first**, because the new peoples build on it.
2. **The order of the expansions** follows §6. Within Acts II and III they can be reordered (the "Needs" column of §6 says what must come first).
3. **The 2024 rules replace the 2014 ones everywhere** – including the gentler surprise rule and the harsher exhaustion – and balance is re-measured so that a careful player still survives.
4. **Firearms** come only as rare, expensive gnomish Renaissance weapons; the modern and futuristic ones are left out.
5. **The D&D gods, Greyhawk and the multiverse's named powers** are not imported; each world keeps its own faiths. Artifact names stay.
6. **Saves may break with any update**, and no migrations are written; the release notes say when a new character or world is needed.
7. **The shelf shows only these expansions**, released ones only. The earlier big updates (pictures, grid combat, sound, the lived history, World Variety) get no icons unless Anton asks for them.
8. **Expansions cannot be switched off**: they are chapters of one game.
9. **The Knight** stays as an extra, Realmwalker-only fighter path; the **Cutthroat** becomes the book's Assassin.
10. **Raising the dead** is in the game but rare, costly and grim; the player's own death is final unless someone in the party can raise them in time.
11. **The planes** are large special regions reached through portals, not whole new worlds.
12. **Big monsters** are drawn at the same 32-pixel size as everything else and scaled up on the battlefield, unless the tile atlas can take bigger pictures.
13. **Book text never enters the game's files**; every description is written fresh in the game's voice.
14. **The Player2 AI writer is removed for now** (§0.4), and every text is written into the game; it can be restored later from the `before-ai-removal` tag.
15. **No more friends' build**: friends download the game from GitHub (`README.md` explains how); each finished part goes straight to `main`, and each finished expansion is tagged and released there, without waiting for Anton.
16. **Creature details in tooltips** are shown in full by default; a setting limits them to what the character knows.
17. **Borrowed monster pictures are adapted** to the game's palette, outline, light and scale by an automatic pass plus small touches in code; full hand-redraws can come later if Anton wants them.
18. **Letters mode is gone**; pictures are the only look, and a PC that cannot show them gets a clear message.
