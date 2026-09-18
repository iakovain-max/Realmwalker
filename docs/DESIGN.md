# REALMWALKER — Build Prompt & Design Document for Claude Code

*(Working title. Rename it anytime.)*

This document is both your instructions and the game's design. Read all of it before writing any code.

---

## 0. Who you are working with, and how to work

You are building a complete game for someone who **is not a programmer and cannot read or write code**. That shapes everything:

- **You own all technical work.** Make every technical decision, handle setup, and debug your own problems. Never ask the user to edit code or run commands they don't understand. When you need them to do something (install an app, click a button, test a feature), give short numbered steps for **Windows** and tell them exactly what they should see.
- **Explain progress in gameplay terms.** Say "you can now create a character and walk around the world map", not "implemented the entity system".
- **Set up the environment yourself.** Install Python 3.12 if it's missing (e.g. via `winget`), create a virtual environment and install dependencies. Provide two double-clickable launchers:
  - `Play.bat` starts the game.
  - `Build_For_Friends.bat` packages the game for sharing (see Section 2).
- **Use git.** Commit after every working step with a clear message, so any change can be undone. If the user says "it broke after the last change", you can find and revert it.
- **Maintain three living files:**
  - `docs/DESIGN.md`: this document, copied in verbatim at the start. It is the source of truth.
  - `CLAUDE.md`: project conventions, folder map, and how to run the game and tests.
  - `docs/PROGRESS.md`: what's done, what's next, known bugs, decisions you made, and how to test the latest features.

  Update `PROGRESS.md` at the end of every session so a fresh session can pick up where the last one stopped.
- **Build milestone by milestone** (Section 17). Before a milestone is finished, all of these must be true:
  - all tests pass;
  - the game launches;
  - the headless autoplay test has run cleanly.

  Then **stop** and give the user a short note: what's new, how to try it, and what to look for. Wait for their feedback before starting the next milestone.
- **Don't stall on ambiguity.** If something here is unclear, or would clearly work better another way, choose the option that best serves the vision in Section 1. Record the decision in `PROGRESS.md` and mention it to the user in one line.
- **The game must never crash on the player.** Catch errors at system boundaries, write them to `logs/`, show a friendly in-game message, and continue when possible.

---

## 1. Vision

This is a single-player, text-heavy, open-world **party RPG based on D&D 5th Edition**. Its look is simple ASCII/tile graphics in the tradition of **Dwarf Fortress adventure mode** and **Caves of Qud**.

The player creates a character in a large generated world and then does whatever they like:
- travel and survive;
- trade;
- fight;
- join factions and meddle in politics;
- recruit companions and take work;
- explore ruins;
- and eventually die.

**Tone:** realistic high fantasy for adults (18+). The world has taverns, elves, dwarves, dragons and magic, but it behaves plausibly:
- Wounds are dangerous and slow to heal.
- Winter kills, and so does dysentery.
- Lords scheme, and wars starve villages.
- Bandits are often desperate men.
- Magic is rare, costly and politically charged.

Violence, gore, cruelty, moral greyness, crime, religion and adult themes are all in scope. Nothing is sanitized. Life should feel precarious and consequential, but fair: danger is signalled in advance, and cautious, clever play is rewarded.

**Three pillars:**
1. **Deep, interlocking simulation.** Health, survival, weather, economy and politics interact to generate stories.
2. **Readable presentation.** Simple glyphs, strong color coding and rich text. Everything important can be inspected. Text is central: arriving somewhere, meeting someone, a change in weather and each day of travel all produce short prose passages.
3. **AI is the writer, never the referee.** The Player2 AI writes names, descriptions, personalities, dialogue and lore. The game's code decides every number and every outcome.

---

## 2. Technology and sharing

**Stack and code rules:**
- **Stack:** Python 3.12 and **python-tcod** (window, CP437 glyph grid, true color, keyboard and mouse), plus `numpy` for map arrays, `httpx` for HTTP, `pytest` for tests and **PyInstaller** for packaging.
- **Data-driven design.** All game data lives in human-readable JSON files under `data/` so balance can be tweaked without touching code. This includes races, classes, backgrounds, spells, base items, materials, creatures, diseases, foods, faction templates, name lists and fallback text. Validate the data files on startup and show clear error messages.
- **Logic separate from display.** Keep simulation logic completely separate from rendering so every system can be tested without a window.
- **One seeded random generator.** All randomness goes through a seeded RNG owned by the world, so bugs can be reproduced.

**Display and performance:**
- Target Windows at 1920×1080 or larger. Support window resizing and font size hotkeys.
- Key presses should get an instant response.
- World generation should take about a minute or less. AI flavor text can keep filling in afterwards in the background.

**Sharing with friends:** `Build_For_Friends.bat` produces a folder containing `Realmwalker.exe` and its data, zipped as `Realmwalker.zip`. Friends unzip it and double-click; they don't need Python. Include a plain `README_FRIENDS.txt` that explains three things:
1. Install **Player2** (free) and keep it running to get AI content.
2. The game still works without Player2, using built-in text.
3. Windows SmartScreen may warn about an unknown app. Click "More info → Run anyway".

Store saves in a consistent location (e.g. `%APPDATA%\Realmwalker\`).

---

## 3. Player2 AI integration

Player2 is a free desktop app that gives games access to an AI language model; players just install it and run it.

**Before writing any integration code, read the current official documentation and treat it as the source of truth over this document, since the API evolves:**
- the local API docs at `http://localhost:4315/docs` (available while the Player2 app is running);
- `https://player2.game/docs`.

**What we believe (verify against the docs):**
- **Local API.** While the app runs, it exposes a local API at `http://localhost:4315`. Chat uses an OpenAI-style `POST /v1/chat/completions` with system and user messages, and the reply is in `choices[0].message.content`. Call the HTTP API directly with `httpx` through a small wrapper module of our own.
- **Health ping.** The game should call the health endpoint (`/v1/health`) about every 60 seconds while running.
- **Client ID.** Some auth flows require a game client ID. You get one from the Player2 developer dashboard (`https://player2.game/profile/developer`) by creating a free draft game. If the current docs require it for our use, walk the user through getting it step by step and store it in `config.json`.
- **Web API.** There is also a web API at `https://api.player2.game/v1`. When the app is running, a key for it can be obtained from the local app. Choose the simplest path that works for the user and for friends who have Player2 installed.
- **Daily energy budget.** Free usage has a daily energy budget. When it runs out, requests fail, possibly with generic server errors and no clear message. If the docs expose a remaining-balance endpoint, show the AI's remaining energy discreetly in the UI.

**Design rules for all AI use:**
1. **Fully playable without AI.** Everything the AI generates has a code or template fallback: name lists per culture, description templates, dialogue lines and item-name patterns. Show a small status indicator ("AI online" / "AI offline — using built-in text") and retry the connection periodically.
2. **The AI writes words; code owns numbers.** Code first creates the skeleton of every entity: stats, level, faction, prices, rarity and effects. The AI then dresses it with a name, description, personality, speech and history. When the AI proposes mechanics (item properties, dialogue skill checks), it may only pick from whitelisted effect types, and code clamps every value to a budget based on rarity, level and context.
3. **Structured output.** Prompts demand strict JSON matching a documented schema. Parse defensively (strip code fences, extract the first JSON object) and validate every field. If parsing fails, retry once with a correction message, then fall back. Also detect refusals and off-topic replies and fall back on those.
4. **Never make the player wait if you can avoid it.** Run AI requests on a background worker with a priority queue, and pre-generate ahead of the player:
   - When the party heads toward a settlement, generate its notable NPCs and descriptions.
   - Keep a small buffer of ready-made unique items and rumors.
   - If something is needed immediately and isn't ready, use the fallback at once. Upgrade it to AI text later only if the player hasn't seen it yet.
   - In conversations, show a brief "…" indicator with a timeout that falls back to template text.
5. **Generate once, keep forever.** Store every piece of AI text in the save. Nothing the player has seen is ever regenerated.
6. **Consistency.** Maintain a compact "world bible": setting summary, calendar, major factions and rulers, religions and recent major events. Include only the relevant slices in each prompt, such as the NPC's settlement, faction, relationships and nearby news. Keep prompts short and set sensible `max_tokens`.
7. **Content and house style.** The system prompt states that this is mature, grim, realistic fantasy for adults. It also sets the house style:
   - grounded, concrete and sensory;
   - period-appropriate language with no modern slang;
   - no purple prose and no stock AI phrases.

   Player2's model may still soften or refuse some content. Handle that gracefully with the fallback.
8. **Easy to tune.** Keep all prompt templates as text files in `ai/prompts/`. Log AI requests and responses to a debug log that can be switched on and off.
9. **Spend the budget wisely.** Prefer fewer, richer calls over many small ones. For example, one call returns an NPC's whole profile, and one call returns a dialogue beat together with its special options and their outcome lines.

**What the AI generates:**
- **Non-basic items.** Unique, magical, named and notable items (heirlooms, relics, masterwork gear, artifacts). The AI writes the name, appearance and history, tied to real world lore, and proposes properties within the rarity budget. Basic items (a common longsword, bread, a wool cloak) come from data files.
- **NPCs.** Name, appearance, personality, values, speech style, a short backstory, a secret and what they want. Notable NPCs (rulers, guildmasters, companions) get more depth.
- **Dialogue.** NPC lines and extra dialogue options (Section 12).
- **Flavor text.** This covers:
  - descriptions of regions, settlements, buildings and dungeons;
  - weather moments and daily travel narration;
  - battle aftermaths;
  - rumors and news;
  - in-world books, letters and notices;
  - the world history chronicle;
  - the character's obituary.
- **Quest flavor.** The hook, the giver's pitch, journal entries and resolution text. The quest's structure is always decided by code.

---

## 4. Presentation and UI

- **Main view:**
  - the map (overworld or local) on the left;
  - a side panel on the right with the party's condition at a glance (HP, worst wound, needs warnings, body temperature, encumbrance) plus date, time, season and weather;
  - a scrollable, color-coded message log along the bottom (danger in red, loot in yellow, and so on).
- **Glyphs.** Use a CP437 tileset. Terrain, creatures, items and features get consistent glyphs and colors, with a legend available.
- **Screens.** Each has a hotkey and can also be clicked:
  - **Character:** abilities, skills, class features, level, XP, background.
  - **Health:** a body diagram showing each part's wounds, plus bleeding, blood loss, pain, infections, diseases, body temperature, exhaustion and intoxication.
  - **Needs:** hunger, thirst, fatigue, warmth and hygiene, each with its stage and trend.
  - **Equipment:** a paper doll by slot and clothing layer, with armor coverage and warmth totals.
  - **Inventory:** weight, value, condition and spoilage, with sorting and filtering.
  - **Spells.**
  - **Party:** each companion's summary, loyalty, mood and current orders.
  - **Journal:** quests, notes, discovered lore and known people.
  - **Factions:** the player's reputation, titles, and the relations between factions that the player knows about.
  - **World Map.**
  - **Help:** includes all keybindings.
- **Look / Examine.** Examining anything gives a text description (AI or template) plus its mechanical information.
- **Dice display.** A setting shows every roll in the log, e.g. `Persuasion: 14 + 3 = 17 vs DC 15 — success.`
- **Controls.** Keyboard-driven with mouse support: hover tooltips and click to select. Ask for yes/no confirmation before dangerous actions such as attacking a guard or drinking an unidentified potion.
- **Main menu:** New World, New Character (in an existing world), Continue, Settings, Quit. Settings cover font size, dice display, AI on/off, text verbosity and autosave frequency.

---

## 5. Character creation and progression

- **Ability scores:** 5e point buy (27 points, scores 8–15 before racial bonuses).
- **Races (v1): Human, Elf, Dwarf, Halfling, Half-Orc.**
  - Use simplified 5e traits that matter in play. For example, darkvision matters in dark places, and dwarven resilience applies to poisons and some diseases.
  - Races also have cultural standing: different factions and regions treat them differently.
- **Classes (v1): Fighter, Rogue, Cleric, Wizard**, levels 1–10. Offer one or two subclass options each, at the appropriate level. Implement the core features in simplified form:
  - **Fighter:** fighting style, Second Wind, Action Surge, Extra Attack.
  - **Rogue:** Expertise, Sneak Attack, Cunning Action, Uncanny Dodge, Evasion.
  - **Cleric:** a domain (e.g. Life, War), Channel Divinity.
  - **Wizard:** a school (e.g. Evocation, Abjuration), Arcane Recovery.
- **Backgrounds (~8): Soldier, Acolyte, Criminal, Folk Hero, Noble, Sage, Outlander, Guild Artisan.** Each grants skills, tools, starting gear and money. Importantly, each also grants **starting social ties**, for example:
  - A Noble belongs to a real noble house.
  - A Criminal has a contact and a small bounty somewhere.
  - A Soldier served a specific lord.
- **Identity.** Name, age, sex and appearance notes, plus an optional AI-written backstory built from the player's choices.
- **Starting location.** The player picks from a few locations suited to their background.
- **Skills and XP.** Use the 18 skills, proficiency bonus and saving throws from 5e. XP comes from combat, quests, discovery (new regions, ruins, lore) and notable deeds.
- **Leveling.** Gain HP, features and spells, with Ability Score Improvements at levels 4 and 8. No feats in v1.

---

## 6. Combat (separate battle screen)

When hostilities begin, switch to a dedicated battle screen. That can happen by attacking or being attacked on the local map, or through an ambush during travel. Positioning is borrowed from **Darkest Dungeon-style rank combat**, with 5e dice underneath.

- **Ranks.** Each side has a **Front** and a **Back** rank.
  - Melee attacks can only target the enemy Front rank, unless it's empty or the attacker has reach or a special ability.
  - Ranged attacks and spells can target anyone. A ranged attack made from the Front rank while engaged in melee has disadvantage.
  - Changing rank costs the character's action.
- **Initiative.** d20 + Dex modifier. Show the turn order as a bar.
- **Turn menu.** The player directly controls every party member in combat. On each party member's turn, choose one of:
  - **Attack** (pick weapon and target)
  - **Cast Spell**
  - **Use Item**
  - **Class Ability**
  - **Dodge** (attackers have disadvantage)
  - **Help** (an ally gets advantage)
  - **Shove / Grapple**
  - **Change Rank**
  - **Parley** (a Persuasion or Intimidation check to end the fight, negotiate terms or demand surrender)
  - **Surrender**
  - **Flee** (a party-wide retreat check)
- **What's dropped from 5e.** One action per turn, with no reactions, bonus actions, opportunity attacks or concentration, except for simplified versions a class feature specifically needs (e.g. Cunning Action lets a Rogue change rank and still attack).
- **Attacks.** d20 + modifiers vs AC. A natural 20 is a critical: double damage dice and a guaranteed wound. Advantage and disadvantage work as in 5e.
- **Damage.** Damage reduces HP and can cause **Wounds** to specific body parts (Section 7). The armor covering the body part that was hit matters.
- **Conditions (v1).** Prone, Grappled, Frightened, Poisoned, Stunned, Blinded, Bleeding, Unconscious and Exhaustion, plus penalties from injuries.
- **Morale.** Enemies (and hired companions) can break, flee, surrender or beg:
  - Beasts flee when badly hurt.
  - Bandits surrender.
  - Fanatics fight to the death.

  Surrendered enemies can be spared, robbed, captured for bounty or ransom, interrogated or executed. Each choice has reputation and companion-approval consequences.
- **Environment.** Time of day, weather and terrain modify fights:
  - darkness gives disadvantage to anyone without darkvision;
  - rain penalizes bows;
  - ambushes give a surprise round.
- **After combat:**
  - an aftermath passage (template text, or AI text for significant fights);
  - looting, including armor that may be damaged;
  - wounds must be tended;
  - dead companions stay dead.
- **Combat text.** Make it vivid and specific, built mostly from templates using weapon, body part, material and severity. Example: *"The bandit's axe bites into Mira's left thigh. Blood soaks her trousers."* Don't spend AI calls on individual swings.
- **Balance.** Enemies scale with the danger of the region, not the player's level, so some fights should be avoided. Signal danger through descriptions, numbers and knowledge checks (Nature, History, Insight).

---

## 7. Health — a core system

Health is modeled realistically but stays readable.

- **Hit Points** stay as in 5e but represent stamina, luck, minor knocks and fighting fitness, not flesh. They recover with rest. Real injuries are **Wounds**.
- **Body parts.** Head, torso, left arm, right arm, left leg and right leg, with sub-locations (hands, eyes, feet) for specific injuries.
  - A hit that lands has a chance to cause a wound.
  - The chance depends on damage relative to max HP, critical hits and weapon type.
  - The lower a character's HP, the more likely hits become wounds.
- **Wound types and severity.** Types are cut, puncture, blunt, fracture, burn, frostbite and bite (bites carry disease risk). Severities are minor, serious and critical. Effects are specific, for example:
  - A broken arm means that hand can't be used, so no two-handed weapons.
  - A leg wound slows travel, penalizes Dex and makes fleeing harder.
  - A head wound means concussion: disadvantage on Int and Wis, and a risk of blacking out.
  - A critical torso wound can cause internal bleeding.
- **Bleeding and blood loss.** Each wound has a bleed rate, and blood loss builds up through weakness, fainting and death.
  - Bleeding is stopped by bandaging (a Medicine check), cauterizing (painful, and adds a burn) or healing magic.
  - Lost blood regenerates slowly with food and water.
- **Pain.** Builds up from wounds. It causes penalties and can cause shock or unconsciousness. It is eased by rest, alcohol, poppy-based medicine (with addiction risk) or magic.
- **Infection.**
  - Risk depends on how the wound was cleaned (boiled water or alcohol, clean bandages), the environment (swamps, sewers, bites) and hygiene.
  - An untreated infection progresses to fever, then possibly sepsis and death.
  - Treatment includes cleaning, herbal poultices, surgeons and divine magic.
- **Healing time.** Minor wounds take days, serious wounds take weeks, and fractures take a month or more. Fractures must be splinted to heal straight.
- **Permanent injuries.** Badly treated wounds can leave lasting effects: scars, a limp, lost fingers, a lost eye or a weakened limb. Amputation is a possible surgery to save a life.
- **Treatment sources:**
  - the character's own Medicine skill with supplies (bandages, splints, needle and thread, herbs, alcohol);
  - companions with Medicine;
  - town barber-surgeons, herbalists and temples.
- **Magic healing** is powerful but scarce. Cure Wounds restores HP and improves one wound by one severity step, and stronger magic does more. Healing potions are rare and expensive.
- **Dying.** 5e death saves are replaced by a **bleeding-out clock** that companions can interrupt with first aid. Death is permanent (Section 15).
- **Diseases** (data-driven, about 10–12 in v1). Examples:
  - dysentery (bad water or food);
  - wound fever (infection);
  - lung fever (cold, wet and exhaustion);
  - marsh fever (swamps, insects, recurring);
  - camp fever (crowding, lice, filth);
  - plague (cities, rats, highly contagious);
  - frothing sickness (animal bites, fatal once symptoms show);
  - food poisoning;
  - one or two monstrous diseases, such as grave rot from undead.

  Each disease defines:
  - how it spreads;
  - incubation time;
  - stages with symptoms and penalties;
  - how contagious it is to the party and to NPCs;
  - treatments and recovery chance;
  - possible lasting effects or immunity.

  Settlements can suffer outbreaks, linked to the world simulation.
- **Other states:**
  - intoxication (tavern drinking, with hangovers);
  - poison;
  - addiction;
  - **Exhaustion levels 1–6** from 5e, used as the single fatigue penalty track.

---

## 8. Needs, survival, weather and travel

These systems are meant to be a major part of the game.

- **Needs.** Hunger, Thirst, Sleep, Body Temperature and Hygiene.
  - Each has clear stages (e.g. Peckish → Hungry → Starving) with escalating penalties.
  - At the extremes, needs damage health and can kill, slowly and with warnings.
  - Companions have the same needs and eat from party supplies.
- **Food and water.**
  - Food has nutrition, weight, a spoilage timer and a preservation state (fresh, salted, dried or smoked).
  - Raw meat and bad water carry disease risk; cooking and boiling reduce it.
  - River and lake water is risky unless boiled; wells and inns are safe.
  - Useful gear includes waterskins, cooking pots and rations.
- **Living off the land.** Foraging, hunting, fishing and butchering use Survival and Nature checks, and depend on biome and season. Simple cooking happens at campfires.
- **Body temperature.** It is driven by:
  - air temperature and wind;
  - how wet the character is;
  - clothing insulation;
  - activity level;
  - shelter and fire.
- **Clothing layers.** Underclothes, main clothes, outer layer or cloak, headwear, gloves and footwear.
  - Each layer has warmth, wind and water resistance and weight.
  - Clothing also sends a social signal: rags and fine clothes change how NPCs react.
  - Wet clothing loses insulation and dries by a fire.
- **Temperature effects.** Hypothermia and heatstroke come in stages. Frostbite appears as wounds on the hands, feet and face.
- **Climate and weather.**
  - Climate comes from latitude, elevation and distance from the sea.
  - There are four seasons and a calendar with named months.
  - Weather fronts move across the overworld: rain, storms, snow, fog, heat waves and blizzards.
  - Weather affects travel speed, visibility, combat, foraging, disease risk and descriptive text.
- **Overworld travel.**
  - Each step costs time. How much depends on terrain, roads, weather, encumbrance, injuries and animals.
  - Show the estimated travel time to a chosen destination.
  - Off-road in poor visibility, the party can get lost (Survival check).
  - Each travel day gets a short narrated passage.
- **Travel events.** The party can meet merchants, pilgrims, patrols, refugees, deserters, beasts, bandits or monsters.
  - Many encounters are not hostile: the party can talk, trade, avoid or ambush.
  - Encounter tables depend on the region, which faction controls it, whether there's a war, the season and the time of day.
- **Animals (simple in v1).** Mules carry loads and horses add speed. They need fodder and water, and can be injured, stolen or killed.
- **Rest and camping.**
  - A **short rest** takes 1 hour.
  - A **long rest** takes 8 hours and needs food, water and reasonable safety.
  - A campfire gives warmth, cooking and drying but can be seen from afar; a cold camp stays hidden.
  - Assign companions to watches; there are night encounter checks.
  - Inns sell beds, meals, baths (hygiene) and rumors.
- **Encumbrance.** Based on weight, with 5e-style thresholds and realistic penalties.

---

## 9. World generation and exploration

**New World** lets the player choose a seed, a world size (Small / Medium / Large) and a few sliders (danger, magic rarity). Generation runs in this order:
1. Terrain: elevation, rivers flowing downhill to the sea, lakes.
2. Climate and biomes: plains, forests, hills, mountains, marshes, tundra and coast, plus optional desert.
3. Peoples and polities, settlements, roads, dungeons and lairs.
4. A simulated history of about 200–300 years (Section 10).
5. Flavor text, queued to the AI with fallback text used immediately.

- **Overworld.** Each tile is a region with biome, elevation, owning faction, danger level and features. Entering a tile opens its **local map**. A local map is generated from the seed on the first visit and then persisted; if space is a concern, store only the changes.
- **Local map types:**
  - wilderness and farms;
  - villages, towns and cities, with walls, gates, market, tavern or inn, temple, smithy, guild halls, keep, homes and slums;
  - castles, monasteries, mines and camps;
  - ruins and dungeons.
- **Dungeons.** Caves, crypts, barrows, ruined forts, mines, towers, sewers, cult temples and dragon lairs.
  - They can have several levels.
  - Inhabitants make ecological sense: a bandit hideout has a lookout, bedrolls and stolen goods; a crypt has undead and burial goods.
  - They contain traps, locked doors and secret passages (found with Perception or Investigation).
  - Light management matters: torches burn out, and darkvision is valuable.
- **Local map actions:** move, look, talk, pick up, open/close, lock/unlock (thieves' tools), search, sneak (Stealth vs NPC perception), pickpocket, climb/swim (Athletics), rest, wait, use item, attack.
- **Day and night.**
  - NPCs follow simple schedules (work, tavern, home).
  - Shops open and close, and town gates close at night.
  - Danger rises after dark.
- **Dragons.** Rare, ancient, individually generated beings.
  - Each has a name, a lair, territory, a hoard and political weight: some are worshipped, some extort tribute.
  - A level 10 party should be terrified of them. In v1 they don't need to be beatable, only real.

---

## 10. Factions, politics, history and reputation — a core system

**Faction types:**
- kingdoms, and the noble houses and vassal lords within them;
- free cities and town councils;
- guilds: merchants, thieves, mages, mercenaries, healers, smiths;
- religious orders and temples;
- cults;
- clans (dwarven holds, highland clans);
- tribes (orcs, goblins, nomads, wild elves);
- elven realms;
- bandit gangs and pirate crews (coastal only; no sailing in v1).

**Each faction has:**
- a name and type;
- a leader (a notable NPC) and notable members;
- territory and holdings;
- wealth, military strength and population;
- **values**, as tags such as pious, mercantile, xenophobic, honor-bound, expansionist or secretive;
- **laws**, for polities: whether magic, weapons and religions are legal, serfdom and slavery, and punishments;
- goals;
- a **relation score with every other faction** (-100 to +100), with states such as allied, friendly, neutral, rival, at war and vassal-of.

**History generation (at world creation):** simulate about 200–300 years with the same politics engine to produce:
- dynasties and past rulers;
- wars, founded and fallen settlements, and plagues;
- the origins of cults;
- dragon attacks;
- legendary figures and lost artifacts.

The AI writes a readable chronicle, plus in-world books and legends drawn from it. Current grudges and alliances should come out of this history.

**Politics simulation (off-screen, abstract, ticking daily or weekly in game time):**
- **Rulers and succession.** Rulers age, sicken and die. Succession follows each faction's rules and can go smoothly or cause a succession crisis or civil war. There are also assassinations, marriage alliances, betrayals, rebellions and vassals switching sides.
- **Wars.** Wars are declared for reasons: border disputes, succession claims, religion, raids or trade.
  - Armies are abstract strength numbers moving along roads, and battles are resolved abstractly.
  - Settlements can be besieged, raided, captured, burned or depopulated.
  - War raises prices; creates refugees, deserters and patrols; and changes who controls territory.
- **Other pressures.** Famine, plague, blockades and trade treaties feed into the economy. Cults grow in secret, tribes raid, and guilds fight over markets.
- **News.** Every significant event becomes a **rumor or piece of news** that travels along roads from where it happened at a realistic pace. The player hears it in taverns, from travelers and on notice boards (AI-flavored).

**Reputation:**
- **Standing.** The player has a reputation with each faction (-100 to +100) with named standings (e.g. Hated, Distrusted, Neutral, Respected, Honored), plus overall fame and infamy.
- **Actions ripple through the web of relationships.** Helping faction A raises standing with A and its friends and lowers it with A's enemies. The size of the change depends on how strongly they feel about A and on **whether they find out**.
- **Knowledge matters.**
  - Deeds spread as rumors from where they happened.
  - Unwitnessed crimes may never be traced to the player.
  - Witnesses can be bribed, intimidated or silenced.
  - Simple disguises and false names are possible.
- **Membership and rank.**
  - The player can join guilds, orders, cults and mercenary companies.
  - Rising in rank unlocks quests, discounts, training, safehouses and titles.
  - Nobles can grant minor titles (title only in v1).
- **First impressions.** Race, background, clothing, visible wounds or filth, and known allegiances all affect how NPCs first react.
- **Law and crime.**
  - Crimes: theft, trespass, assault, murder, poaching, smuggling, forbidden magic and heresy.
  - Guards respond, and bounties apply per jurisdiction.
  - Punishments follow local law: fines, jail (time passes and gear is confiscated), forced labor, flogging, branding or execution.
  - Bribery and escape are possible.

---

## 11. Economy, trade and items

**Money and markets:**
- **Currency.** Copper, silver and gold at 5e rates, with 5e prices as the base.
- **Local markets.** Each settlement has its own stock and prices, driven by:
  - what it produces (a mining town has cheap metal; farmland has cheap grain);
  - its size and the season;
  - war, famine and events;
  - its trade routes.

  Prices should differ enough between towns that **trading is a real way to make a living**.
- **Caravans.** Caravans move goods between towns (abstractly) and can be escorted or robbed.
- **Merchants.**
  - They have limited coin and stock, and restock over time.
  - They have their own dispositions, and faction membership can earn discounts.
  - The player can haggle using Persuasion, Deception or Intimidation.
  - **Fences** buy stolen goods, available to thieves' guild members.
- **Other income:** mercenary contracts, bounties, day labor, performing in taverns (Performance), a simple dice gambling game, selling loot and ransoms.

**Items:**
- **Base items** come from data files: 5e weapons, armor, adventuring gear, tools, clothing, food and trade goods.
  - Each has weight, value, **material**, **quality** (crude → common → fine → masterwork) and **condition** (it wears with use and can be repaired at a smithy or with tools).
  - Armor protects specific body parts.
  - A weapon's damage type (slashing, piercing or bludgeoning) shapes which wounds it causes.
- **Unique and magic items** are dressed by the AI.
  - They are rare, with rarity tiers from uncommon to very rare in v1; legendary items exist only as world artifacts.
  - Their properties come from a whitelist: bonus to hit or damage, resistances, light, warmth, skill advantage, spell charges and so on.
  - Code clamps their stats to the budget for their rarity. Some are cursed.
  - Some need identifying through an Arcana check, a sage or the Identify spell.
  - Their histories reference real world lore, such as a real past king or a real battle.
- **Books, letters, notices and maps** can be read in the world (AI text). Some contain lore, quest hooks or recipes.
- **Simple crafting (v1):** cooking, bandages, splints, herbal remedies (herbalism kit), torches, repairs, skinning and butchering, and drying or salting food. There is no full smithing yet.

---

## 12. NPCs, companions and dialogue

**NPC generation.**
- **Code decides the mechanics:** race, sex, age, occupation, faction, social class, wealth, stats and level, family and relationships, and personality and value tags.
- **The AI writes the rest:**
  - the name, with culture-appropriate fallback name lists;
  - appearance and a personality summary;
  - speech style and a short backstory;
  - a secret and what they currently want.
- **Memory.** NPCs remember key interactions with the player as a short list of facts plus a disposition score, which is fed into their dialogue prompts.

**Dialogue: menu-based and AI-augmented.**
- **Base menu (from code).** It reflects the NPC's role and relationship:
  - Greet;
  - Ask about... (the area, rumors, themselves, a person, a faction, a place);
  - Trade;
  - Work / Quests;
  - Recruit;
  - role-specific services: rent a room, buy a meal, healing, training;
  - Threaten, Bribe, Goodbye.
- **NPC lines (from the AI).** The AI writes the NPC's lines in character, grounded in the context it's given:
  - who they are and what they know;
  - current events near them;
  - their disposition;
  - the player's reputation, appearance and condition.
- **AI-proposed options.** In each conversation the AI may also propose **1–3 extra options specific to the situation**, each tied to a 5e skill check. For example: `[Insight] He's lying about the mill.` or `[Intimidation] Remind him what happened to the last tax collector.`
  - **The AI supplies:**
    - the option text;
    - the skill;
    - a difficulty word (easy / medium / hard / very hard), which code converts to a DC and adjusts for disposition;
    - a success outcome and a failure outcome, **chosen from a whitelist**, each with its own short line of reaction.
  - **Whitelisted outcomes:**
    - reveal information or a rumor;
    - reveal a quest hook;
    - change disposition;
    - change faction reputation (small);
    - change prices (capped);
    - give a minor item from the NPC's own inventory;
    - the NPC agrees or refuses;
    - start a fight;
    - call the guards;
    - the NPC flees;
    - unlock a new topic.
  - **Code resolves it.** Code rolls, applies the effect and shows the matching AI-written line.
- **NPCs never invent mechanics.** Each prompt lists exactly what the NPC is able to offer, so they can't promise rewards the game won't create.

**Companions.**
- **Recruiting.** Companions come from taverns, guilds, freed prisoners, grateful NPCs and so on, up to **4**. Each has race, class and level, a personality, values and wants (pay, a share of loot, revenge, a cause).
- **Loyalty and approval.** Companions react to the player's choices according to their values:
  - A devout companion hates grave robbing.
  - A mercenary cares about pay.
  - A former serf despises cruelty to peasants.

  Low loyalty leads to complaints, disobedience and desertion (sometimes taking a share of the goods), and rarely betrayal. High loyalty brings personal quests (AI-flavored), courage in battle and personal dialogue.
- **Upkeep and risk.** Companions get wages or loot shares and daily upkeep. They have needs, wounds and diseases exactly like the player, and **they can die permanently**.
- **Control.**
  - **Outside combat,** companions follow automatically and take simple orders: wait here, follow, keep watch, forage, guard camp. They comment in character.
  - **In combat,** the player controls each companion directly.
- **Leveling.** Companions level up alongside the party, and the player chooses their level-up options.

---

## 13. Quests (sandbox; no main story in v1)

- **Quests are made by code from templates and tied to real world entities.** The bandit leader in a bounty actually exists in a specific camp, and the stolen heirloom is actually in that crypt.
- **Templates (v1):**
  - bounty; clear a lair or infestation; hunt a beast;
  - escort a caravan or a person; deliver goods or a sealed letter;
  - retrieve an item from a dungeon; rescue a captive;
  - investigate disappearances (often a cult);
  - collect a debt; defend a village from raids; find a cure for an outbreak;
  - smuggle, spy, steal documents, sabotage, assassinate;
  - settle a feud;
  - faction rank-up tasks.
- **Sources:** NPCs, notice boards, faction leaders, overheard rumors, found letters and travel events.
- **Hidden sides.** Quest givers have motives, and quests can hide things. For example, the "bandits" may be starving deserters, or the letter may incriminate the person who sent it.
- **Resolution and consequences.**
  - Quests can be resolved in several ways: fight, talk, sneak, pay, or betray the giver.
  - They can have deadlines and can fail.
  - Every outcome has consequences for factions and reputation.
- **Who does what.** The AI writes the hook, the giver's pitch, journal entries and resolution text. Code owns objectives, locations, rewards and consequences.

---

## 14. Magic

- **Magic is real, rare and political.**
  - Some kingdoms license mages; others burn them.
  - Temples control divine magic.
  - Casting in public may be a crime or cause panic, depending on local law.
- **Spells.** Use 5e spell slots with a curated v1 list: about 20 wizard spells and 15 cleric spells, from cantrips to 5th level. Adapt them to rank combat and to the health system; healing interacts with wounds as described in Section 7.
- **Learning spells.** Spellbooks and scrolls exist. Wizards can copy new spells from them, which takes an Arcana check, gold and time.

---

## 15. Death, saves and legacy

- **Roguelike permadeath.** Each living character has one save, written automatically on key events, periodically and on quit. There is no manual reload. Debug builds may load backups, for testing only.
- **The world persists independently of the character.** When the character dies:
  1. Show an **obituary screen**, written by the AI: cause of death, age, deeds, notable kills, and what the factions thought of them.
  2. **Everything the dead character carried is gone.** There is no corpse or grave to find and no gear to recover.
  3. Their deeds remain in the world: in faction states, history, rumors and NPC memories ("the late so-and-so"). The dead character's reputation does not carry over to the next character.
  4. Surviving companions return to the world as normal NPCs and can be recruited again.
- **New characters.** A new character can be created in any existing world, starting wherever they choose. Before they start, the world simulation fast-forwards a few weeks or months and shows a summary of what changed.
- **Multiple worlds.** Several worlds can exist side by side.
- **Save format.** Saves are versioned and compressed. Plan migrations so that game updates don't break existing saves when possible.

---

## 16. Testing and quality

- **Unit tests** with `pytest` for every system:
  - dice;
  - combat resolution;
  - wound, bleeding and infection progression;
  - needs and temperature;
  - economy;
  - reputation ripple;
  - save/load round-trip;
  - AI JSON parsing and fallback.
- **Headless autoplay bot.** It creates a character and plays thousands of turns with random but sensible actions across travel, combat, trade and dialogue. Run it once with AI off and once with a mocked AI. It checks invariants: no crashes, no negative stock, no invalid numbers, and saves that load back identically. Run it at every milestone.
- **Mock Player2 server** so AI code paths can be tested without the real app.
- **Debug console** on a hidden hotkey, disabled in friend builds. It can:
  - reveal the map and teleport;
  - spawn items, NPCs or creatures;
  - set time, weather or season;
  - heal, give gold or set reputation;
  - fast-forward the world simulation;
  - toggle AI.
- **Balance targets:**
  - At level 1, two wolves or three bandits are a real threat.
  - A winter night without shelter or fire is dangerous.
  - An untreated serious wound is genuinely risky.
  - A careful player can still survive and prosper.

---

## 17. Milestones

Build in this order. Each milestone ends with a playable build and a stop for user feedback.

- **M0 — Setup.**
  - Set up the environment, folder structure, `Play.bat`, `CLAUDE.md`, the docs and git.
  - Build a **Player2 test screen** that shows connection status and the health ping, runs one sample AI generation, and demonstrates the fallback when the app is closed.
  - Walk the user through installing and starting Player2, and getting a client ID if one is needed.
- **M1 — World and movement.**
  - World generation: terrain, rivers, biomes, climate, settlement and road placement.
  - The overworld and local maps, movement and look.
  - Time, calendar, day and night.
  - The message log, main menu, and save/load.
- **M2 — Character.**
  - Character creation: point buy, races, classes, backgrounds, skills.
  - The Character, Equipment and Inventory screens.
  - The base item data and encumbrance.
- **M3 — Combat.**
  - The battle screen, ranks, initiative and action menu.
  - Basic creatures and bandits, and conditions.
  - Morale and surrender, loot and XP.
- **M4 — Body and survival.**
  - Wounds, bleeding, pain, infection, treatment and healing over time; diseases.
  - Needs, food, water and spoilage.
  - Clothing layers and temperature; weather systems.
  - Rest and camping, travel costs and travel events.
- **M5 — Settlements and people.**
  - Town and village layouts, and NPC generation (AI with fallback).
  - Dialogue menus with AI-proposed skill-check options.
  - Shops, markets and dynamic prices; inns, taverns and healers.
- **M6 — Factions and politics.**
  - Faction generation, relations and the reputation ripple.
  - Law and crime.
  - History generation and the off-screen politics simulation.
  - Rumors and news spreading along roads.
- **M7 — Companions and progression.**
  - Recruiting, loyalty and approval, wages.
  - Direct control in combat, orders outside it.
  - Leveling from 1 to 10, class features and spells.
- **M8 — Adventure content.**
  - The quest generator and dungeons.
  - Unique and magic items (AI).
  - Books and letters, notice boards, and dragons with their lairs.
- **M9 — Death, legacy and release.**
  - Death, obituary, and new characters in existing worlds.
  - Full help screens and a balance pass.
  - `Build_For_Friends.bat` and `README_FRIENDS.txt`.

**Ideas parking lot:** after v1, don't build these now, but note them in `PROGRESS.md`:
- more races and classes;
- sailing;
- owning property;
- joining sieges and battles personally;
- full crafting and smithing;
- NPC voices via Player2 text-to-speech;
- romance and relationships;
- a player-led warband;
- a main story with a growing world threat.

---

## 18. What to do right now

1. Copy this entire document into `docs/DESIGN.md`, then create `CLAUDE.md` and `docs/PROGRESS.md`.
2. Read the Player2 documentation (Section 3). If the Player2 app isn't installed or running yet, tell the user exactly how to install it and start it.
3. In plain language, give the user a short overview of your plan for M0 and M1. Then begin **M0** right away.
