# Realmwalker — progress log

Newest session first. Each milestone lists what's new, how to try it, decisions made, and known issues.

## Status at a glance

| Milestone | State |
|---|---|
| M0 — Setup | ✅ Done (2026-09-19) |
| M1 — World and movement | ✅ Done (2026-09-19) |
| M2 — Character | ✅ Done (2026-09-19) |
| M3 — Combat | ✅ Done (2026-09-19) |
| M4 — Body and survival | ✅ Done (2026-09-19) |
| M5 — Settlements and people | ✅ Done (2026-09-19) |
| M6 — Factions and politics | ✅ Done (2026-09-19) |
| M7 — Companions and progression | ✅ Done (2026-09-19) |
| M8 — Adventure content | ✅ Done (2026-09-20) |
| M9 — Death, legacy and release | ✅ Done (2026-09-20) |
| After v1 | 🔨 Continuing |

---

## After v1 — continuing work (2026-09-20)

The nine milestones are done; this is what has been added since, in the same spirit (all of it from the design's
own v1 lists).

**More kinds of work** (design section 13). Besides bounties, lairs, beasts, letters, heirlooms, captives, debts,
disappearances and dragons, people now offer (sixteen kinds in all):
- **escort**: walk someone to another town. They travel with you and pay at the gate. Lose a fight on the road and
  they do not survive it. Some of them are running from something, and only say so on the second night.
- **assassinate**: a name, a town, and money for a quiet death. Face to face the story sometimes falls apart —
  then you can still do it, or tell them who paid and take their gratitude (and their purse) instead.
- **cure**: bring healing herbs to a town the sickness is in, and it lifts.
- **feud**: two notables who have not spoken in years. Talk each of them round, or pay them off.
- **steal**: lift a named thing from a named pocket, with the law where the law always is.
- **defend**: a village knows the raiders are coming, and roughly when. Be there on the day and they come out of
  the fields at dusk; be somewhere else and the place is sacked, sometimes burned, and the news travels.
- **smuggle**: a sealed crate that must reach another walled town without the gate wardens seeing it (they search
  travellers already; now they look for this too, and taking it is smuggling, whoever asked you to carry it).
Work of the quiet kind — killing, lifting, smuggling — brings no news and no fame, only infamy and the standing
of whoever paid.

**Companions ask for things.** A companion who becomes devoted finally asks you for one job of their own, chosen by
what they want: revenge on a real gang, a book they have wanted all their life, a cult they want ended, a pocket
worth picking, a debt nobody else will collect (press **b** on the party screen). It pays half, out of their own
purse. Seeing it through binds them to you; refusing or failing it loses them.

**Finding the work.** Every place your journal wants you is lit like lamplight on the map and the world map, and
the side panel shows how much work is in hand and when the next piece is due (click it, or press **j**).

**More on the road.** Eight new travel events: a flooded ford, a burnt farm, toll men whose arrangement may be
their own, a carter axle-deep in the ruts, a ring of standing stones, charcoal burners, a sick child at a cottage,
and a body in the reeds. Twenty in all, each with real choices.

**More things that live out there.** Gnolls, hobgoblins, bugbears, berserkers and stirges, each in bands of
their own and in country that suits them (measured with the balance harness: a gnoll pack or a hobgoblin patrol
is a real fight at level 1; berserkers are a decision, not a fight, until about level 3).

**Every level under the ground says what it is like** — cut stone and old grain in a cellar, burial niches three
deep in a crypt, scorched rock and opened armour in a lair — once, when you first come down. With Player2 running
the AI writes it instead, from the real facts of that level, and only while the built-in words are unread. Dark
places also look lived in now: fallen stone, old bones, tables and beds, pillars in the crypts and temples, water
in the low places of caves.

**Your own story.** The character sheet lists what you are known for (your last deeds, with fame and infamy), and
the chronicle's Legends tab has "Those who came before": the characters who lived and died in this world, with
their obituaries, beside the old heroes and the dragons.

**A dungeon belongs to whoever holds it.** The bottom of a bandit cellar used to hold bandits, goblins, rats and
the restless dead at once; now a place takes its character from its master, with vermin in the corners.

**The world feels lived in.** Towns have street life (a rug beaten against a wall, a loose pig and three
people chasing it, the watch going by with a lantern and a long look) that changes with the hour, with market
days, and with what the town is going through — chalk on a door in plague, children stripping bark in a famine,
new shutters after a raid. The sky says when it turns: rain starting and stopping, fog coming up out of the
ground, the first flakes, the heat settling on you. And every named region can describe itself, in the AI's words
when Player2 is running, from the real facts of the place.

**Your name goes before you.** Fame and infamy now change how a stranger takes you the first time you speak:
notables have heard more and sooner than a farmhand, fame impresses the proud and the greedy, and a bad name
frightens the kind and the nervous worst of all.

**Things the design asked for that the game did not have yet.**
- A **Spells screen** (**S**): every spell a caster knows, grouped by level, what it does, whether it can be cast
  now, the spell attack bonus and save DC, slots left today, and the size of a wizard's book. Until now you could
  only see your spells in the middle of a fight.
- **Simple crafting** at camp (**m**): torches and splints from firewood, bandages from linen, salted meat and
  smoked fish that keep, and a herbal remedy from healing herbs with a kit and a fire, each on a Survival or
  Medicine check.
- **Caravans** on the road: trade with them, walk with them for safety and a little pay, lean on the factor for a
  toll, or take what they have and meet their dozen hired swords.
- **A confirmation before drawing steel** on somebody in conversation, as the design asks for dangerous acts.
- **Landmarks on the skyline**: a ruin, a cave or an old tower coming into view is remarked on and goes on your map.

**Factions make you earn each promotion** (the design's "faction rank-up tasks"). You join at the bottom
whatever your standing; standing opens the door to the next rank, and a piece of that faction's work walks you
through it — an offer from one of their people says whose eyes are on it, pays a little more, and promotes you
when it is done. If your standing runs two ranks ahead of what they have given you, they give in and promote you
anyway, so nobody is ever stuck.

**Help and energy.** The help opens with "Your first hour": seven steps from the title screen to a first piece of
finished work, and what to buy before leaving town. Settings gains **AI extras**, which keeps Player2's limited
energy for people, places and conversation if you would rather not spend it on regions, dungeons, items, the
wording of work and obituaries.

**Fixes.** "Text detail" in Settings did nothing at all until now (it governs street life, companions on the
road, the weather turning, the sounds of the night and whether the AI is asked to describe regions). The dead no
longer linger in the party or among those waiting (cleared as time passes, on rejoining,
and never written into a save); `first()` no longer calls a character named "The Wanderer" "The"; the autoplay
bot's invariants no longer complain about a companion or a band of enemies holding their dead while the battle is
still being fought. A battle's dice used to come from a stream keyed on how many messages were in the log, so
saying one more thing before a fight changed the fight; each battle now has its own numbered stream. The balance
harness was measuring one run twelve times (the body and health dice are keyed on the world clock, and every run
started at the same minute), which is now fixed and the numbers are real. The debug console gained
`quest <kind>` for trying a piece of work on the spot.

---

## M9 — Death, legacy and release (done)

**What you can do now**
- **Die properly.** Death is still permanent, but now it means something. The death screen gives you an
  obituary: what you were, how and where you died, what you killed, the work you finished, who you travelled
  with, what you did that anyone will remember, and what the powers of the land thought of you. With Player2
  running, the AI writes it in its own words; the words are kept with the world.
- **The world keeps your story.** A death is written into the world itself: famous ones go into the chronicle
  (**n**) and travel as news; unknown ones pass without remark, as they should. Everything you carried is gone —
  no body, no grave, no gear to recover, exactly as the design asks.
- **Companions outlive you.** Those still standing go home, remember who they travelled with and how it ended,
  and can be hired again by whoever comes next.
- **A new life in an old world.** **New Character** on the title screen makes a character in a world you have
  already played, starting wherever you choose. The world does not wait: three weeks to five months of politics
  run first, and you are told what changed before your first step — towns taken, new rulers, wars begun and
  ended, plague, famine, gangs, a dragon awake — along with what people are saying and who walked this land
  before you.
- **Help for everything.** The help screen (**F1**) now covers every system and every key, including the
  underground, magic items, work and the journal, dragons, books and paper, death and new lives, and where the
  game keeps your saves and its error log.
- **A build to send to friends.** `Build_For_Friends.bat` runs the tests, builds `Realmwalker.exe`, checks that
  the packaged game starts, and zips it (about 35 MB) with a readme that says what the game is and how to run it.

**How to try it**
1. Double-click `Play.bat` and **Continue**.
2. Get yourself killed (it is not hard). Read the obituary.
3. On the title screen choose **New Character**, pick the same world, and make someone new. Read what happened
   while nobody was watching, then walk into it.
4. To send the game to someone: double-click `Build_For_Friends.bat` and wait a few minutes; it leaves
   `Realmwalker.zip` in the project folder.

**What to look for:** Does the obituary feel like a proper ending? Is the world noticeably different when you
come back to it as someone new? Is anything in the help missing or wrong?

**How it was verified**
- 550 automated tests pass at the close of M9 (572 now, with the work since), including new ones for the death record, unremarkable deaths, companions going
  home, the obituary (built-in and AI), saving the dead with the world, the years between lives, and the death
  and interlude windows at every size.
- **A balance pass, measured** (`tools/balance.py`, locked in by `tests/test_balance.py`):
  - at level 1 alone, two wolves are won 48% of the time and put you on your back in half the fights; three
    bandits are won 38% of the time; a lone wolf or a single bandit is a fight, not a death sentence (80-95%);
  - a party of three at level 1 usually wins those fights but pays for them (someone down in 40%, someone dead
    in 3-8%); at level 3 the same fights are comfortable;
  - a winter night in the open without fire or shelter leaves you at 1-6 hit points and exhausted; a fire stops
    the damage; a fire and a tent leave you merely cold;
  - an untreated critical wound bleeds you to death within a day (17 runs in 20), and binding it saves you
    (0 in 20); a serious, dirty wound left alone for a week festers in about a fifth of cases and kills in
    about one in twelve, and binding and cleaning it roughly halves that.
  Nothing needed retuning: the numbers already sit where the design asks.
- The smoke test tours every screen; autoplay ran clean in both AI modes; the packaged build was made and its
  exe smoke-tested.

**Decisions (and why)**
1. **The obituary is kept in the world, not the character**, so the next character can be told who came before
   them — the only thing that carries over is the story.
2. **Reputation does not carry over.** Standing, money and gear die with the character; the world's memory of
   the deeds does not.
3. **The interlude runs the real politics engine**, not a summary generator, so what you are told about is what
   actually happened while you were away.
4. **Balance is measured, not asserted.** The harness prints the numbers so they can be tuned later with
   evidence, and the tests fail if the game drifts much softer or much deadlier.

**Known issues**
- The interlude does not age or replace ordinary townsfolk (only the great ones, who are simulated).
- A world with no living character keeps its local maps and townsfolk as they were, so a town you emptied stays
  empty for the next character.
- (Companion personal quests, escorts, smuggling, assassinations and faction rank-up trials were on this list
  and have since been built — see "After v1" at the top.)

---

## M8 — Adventure content (done)

**What you can do now**
- **Dungeons under every ruin, cave, barrow and tower.** Walk onto the steps down (`>`) in the close view and go
  under: cellars, crypts, hideouts, warrens, hidden temples, mage towers, caves and dragon lairs, one to three
  levels deep, each built from real rooms and corridors (or gnawed cave tunnels), with doors, locked doors, secret
  doors, hidden rooms, chests, coffins and traps. The master of the place waits at the bottom.
  - It is dark: light a torch or lantern (they burn down, so carry spares), or see only what is under your nose;
    dwarves and elves see a little in the dark.
  - **s** searches where you stand for traps, secret doors and hidden rooms. Walking into a locked door or a chest
    tries to open it (thieves' tools help). Opening a coffin may wake what is in it.
- **Magic items**, rare and mostly old. What you find looks like "a strange sword" until you know it: **Enter** on
  it in your pack studies it for an hour (Arcana, once a day per item), or a priest will tell you for a donation.
  Known items list exactly what they do (to hit and damage, armour class, saves, a skill, resistance, light,
  warmth, an ability, or a spell a few times a day) and carry a name and a history drawn from the world's own past
  — the AI writes those when Player2 is running. Some are cursed: they will not come off and they work against you
  until a temple lifts it.
- **Work, and a journal (j).** Ask people in towns "Is there any work?". A bounty on a real gang's captain in
  their real hideout; a lair to clear; a named beast to hunt (it is really out there, where they said); a sealed
  letter to carry to a real person in another town; an heirloom — or one of the world's lost treasures from the
  chronicle — to bring back from a real barrow; a son or daughter taken by outlaws, chained in the deepest room;
  a debt to collect; people going missing, and the cult that takes them. Wanted posters on the notice board can be
  taken down and taken on (press the number).
  - Each job has a reward and a deadline, and the place goes on your map. Finish it and go back to whoever set it.
    Fail it or give it up (**a** in the journal) and they, and their people, remember.
  - **Not everything is as you were told.** The outlaws may be starving deserters you can talk into leaving
    instead of killing (half pay, and your kinder companions approve). The debtor may have nothing but children
    and an empty house: take it anyway, or forgive it. A sealed letter may be worth reading — and once read, it
    can still be delivered (for half), taken to the lord (for more, and the sender is disgraced), or held over the
    sender's head for everything in their purse.
- **Dragons.** Every world keeps one asleep in a lair in the high country. While you play it wakes now and then to
  burn a village or take tribute in cattle and silver, and the news travels. The country around a lair shows it:
  burned trees, bones in the grass, no birds. It is a killing fight; its hoard is real gold, and taking any of it
  wakes the owner. Kill it and the tribute stops, the realms nearby remember it, and the chronicle (**n**) records
  who did it, beside the old heroes. Lords near a lair will pay for the head — but only offer it to a party that
  looks like it might live.
- **Paper is treasure.** Old maps, books of histories, books of old lore and dead strangers' letters turn up in
  chests and graves. **Enter** reads one (an hour): real places go on your map, a faction that really holds this
  land joins your list, one of the world's lost artifacts is named along with where it came to rest, or a cult's
  hidden temple is pointed out. They say the same thing every time you read them.

**How to try it**
1. Double-click `Play.bat` and **Continue** (old saves are upgraded).
2. In a town, talk to the innkeeper, the headman, a priest, a smith, a guard: **"Is there any work?"**. Take
   something on, then press **j** for the journal. Read the notice board in the square (**¶**) and press **1**.
3. Walk to the place on your map, press **>** to go into the close view, find the steps down (**>**) and go under.
   Light a torch first (**i**, Enter on it). Press **s** now and then.
4. Kill what is at the bottom, take what it was sitting on, and go back to whoever set you the work.
5. Try the other side of a job: break the seal on a letter you are carrying (**i**, Enter), and see what it says.

**What to look for:** Is the work worth doing (pay, distance, deadlines)? Is the journal clear about what is left
to do? Are the dungeons interesting to walk through, or a maze? Is a magic item exciting when you find one?

**How it was verified**
- 532 automated tests pass. New ones cover: dungeon layouts (every room reachable, stairs, secret rooms, coffins
  that do not block doorways), light and darkness, traps, searching, locks and chests; magic items (budgets,
  effects, identifying, curses, charges, treasure, the AI's names, saving); quests (offers tied to real gangs,
  sites, beasts, people and artifacts; taking work in conversation and from the board; clearing a lair; a bounty
  paid by the watch; deserters talked away; hunting a named beast; retrieving a thing from the deepest level;
  freeing a captive or finding them dead; a letter delivered, opened, or used against its sender; collecting a
  debt from someone who can pay and someone who cannot; investigating the missing; deadlines and dead givers;
  saving; the AI wording an offer through the mock server); dragons (lairs, the warning signs, waking to burn or
  take tribute, killing one for good, and a lord's reward); books, maps and letters; and the journal window at
  every size.
- The smoke test tours the new journal window; autoplay ran clean in both AI modes (12,000 turns each), now also
  taking on work, with invariant checks on the journal.

**Decisions (and why)**
1. **Quests are made from what the world already has.** No quest invents a gang, a village or a treasure: it
   points at a faction, a site, a person or an artifact that exists, so finishing one changes the world (a gang
   loses its captain, a site is cleared, a cult is found, a dragon dies) and the news spreads like any other deed.
2. **Code owns the terms; the AI only speaks.** The reward, the deadline, the target and the outcome are the
   game's; the AI may write the giver's words, and the game always shows the pay and the days itself.
3. **Hidden sides instead of moral labels.** A job can turn out to be something else when you get there; the game
   never says which choice is right, but your companions have opinions.
4. **One job at a time from each person, a new one about once a week**, kept with the town (so a town you visit
   often keeps changing) and thought of before you ask, so the AI has time to word it.
5. **The dragon is guaranteed.** A world where the last dragon was killed in the chronicle felt smaller, so world
   generation always leaves one asleep somewhere.

**Known issues**
- ~~Companions have no personal quests of their own yet~~ — built after v1: a devoted companion asks for one
  job of their own (party screen, **b**).
- A job's giver dying (plague, war, your own sword) closes the job with a note rather than passing it to their
  heir.
- Dungeon levels are built when you first go down and kept in the save, so a level you have seen does not change
  if the data files change.

---

## M7 — Companions and progression (done)

**What you can do now**
- **Level-up choices.** Levels still bring hit points and features at once, but the choices are yours now: a
  path (Champion or Knight, Thief or Cutthroat, Life or War, Evocation or Abjuration), ability increases at levels
  4 and 8 (+2 to one or +1 to two; Constitution adds hit points at every level), and a wizard's new spells and
  cantrips. The level-up screen opens by itself after a level-up; **Choose for me** makes sensible choices; you can
  also come back later (character sheet **c**, then **l**).
- **Spell scrolls.** Scrolls of every spell are sold where mages gather (cities, and towns with a circle of mages).
  A wizard can copy one into the spellbook (Enter on it in the pack): an Arcana check, 50 gold crowns and two hours
  per spell level, and the scroll is used up either way. Anyone can read a scroll aloud once in a fight from the
  spell menu (with a check if it isn't their kind of magic).
- **Companions**, up to four. Travellers looking for work wait at the inns of villages, towns and cities (a new lot
  every month or so), and sell-swords are for hire in a mercenary company's town. They are sell-swords, old
  soldiers, hedge wizards, wandering priests, zealots, cutpurses, outlaw hunters and runaway serfs. Ask
  "Would you travel with me?" and they name their price: a daily wage, some of it up front, and for cutpurses a
  share of the loot.
  - They are full characters of their class and about your level, with their own gear, needs, wounds and
    sicknesses. They level up with you, and you make their choices. In a fight you command each one. They can
    die, for good.
  - **Loyalty** moves with what you do, by their values (devout, in it for the money, kind, honourable,
    law-abiding, no friend of lords, greedy, cruel, brave, learned, cautious) and what they want (revenge on
    outlaws, knowledge, a cause, loot, pay). They say what they think. Unpaid wages sour them fast. Unhappy
    companions grumble, and mutinous ones slip away in the night with some of your coin. Devoted ones say so.
  - **Orders** on the party screen (**p**): follow, keep watch when you camp (you are woken before an attack), forage
    while the others sleep, or wait at this spot until you return. You can also talk to them, raise their pay or
    dismiss them.
  - The party shares its food and water. **G** in the pack hands something to the next member; **Tab** switches
    between members on the sheets.

**How to try it**
1. Double-click `Play.bat`, **Continue** (or a new world). Go to a town, walk into the inn, and talk to a traveller.
2. Hire them, then press **p** to see the party, and **c**/**i**/**e** for their sheet, pack and gear.
3. Fight something together; after a level-up, make your choices.
4. Do something your companion hates (or loves) and watch the log.

**What to look for:** Are companions worth their pay? Is loyalty too touchy, or not touchy enough? Are the
level-up choices clear?

**How it was verified**
- 479 automated tests pass. New ones cover: the fighter's path at level 3; ability increases (and hit points from
  Constitution); wizard spell choices; choices made for you; a scroll for every spell; copying (success, failure,
  who may); reading a scroll in a fight; scrolls for sale; travellers at the inns and their coming and going;
  hiring (and who won't come); hiring in conversation; loyalty following values and crimes; wages, unpaid days and
  desertion; loot shares; waiting and rejoining; keeping watch and foraging at camp; shared food; a companion's
  death; saving the party and those waiting; companions under your command in battle; and the level-up and party
  windows at every size.
- Autoplay: thousands of turns in both AI modes, now also hiring companions, with checks on party size, loyalty,
  waiting companions and level-up choices. No errors.

**Decisions (and why)**
1. **Companions are townsfolk turned into full characters** at hiring (their name, looks and story carry over), so
   everything that works for you (needs, wounds, levels, battle) works for them.
2. **Loyalty reactions come from tags** that the game already knows (mercy, execution, theft, prayer, loot...), so
   any new deed can be given a tag and every companion reacts to it by their values.
3. **Dismissed or deserting companions go home** as townsfolk (a deserter does not like you any more).
4. **Personal quests for devoted companions** come with the quest system (M8).

**Known issues**
- Freed prisoners and grateful townsfolk joining you come with quests (M8).
- Devotion has no effect in battle yet beyond their word; mutiny never turns to outright betrayal yet.
- Towns you visited before M7 get their travellers on your next visit.

---

## M6 — Factions and politics (done)

**What you can do now**
- **The powers of the land.** Every world now has kingdoms and the noble houses sworn to them, free cities,
  dwarven clans, highland clans and elven realms, and tribes of orcs, goblins or nomads in the wild. It also has
  churches (one per faith) and a knightly order, guilds (merchants, mages, healers, smiths), mercenary
  companies, a hidden thieves' guild, secret cults, bandit gangs and pirate crews. Each has a leader, values
  (pious, mercantile, warlike...), friends and enemies, and realms have their own laws. Every town is held by
  someone; the king lives in the keep of his capital, the lady in her hall, the high priest in the great temple.
  Press **f** for the Factions screen, and **p** on the world map to colour the land by realm. Crossing a border
  is announced.
- **Your standing** with each faction (Hated, Distrusted, Neutral, Respected, Honoured), plus fame and infamy.
  People who answer to a faction treat you by it, and prices follow it. Your background ties are now real: the
  soldier served an actual lord (and a deserter is remembered), the acolyte belongs to a real church, the noble
  has a family house, and the criminal has a real price on their head.
- **Deeds ripple.** Helping a faction pleases its friends and angers its enemies, but only once the news reaches
  them. Beating bandits angers their gang and pleases the lord of the land; the same goes for cultists and
  raiders. Take prisoners after a fight and hand them to any watch for a reward.
- **Law and crime.** Theft (steal in a market with **s**), pickpocketing, trespass (in a house at night),
  assault and murder are crimes, and so are poaching, smuggling, magic without a licence, witchcraft and
  heresy, each by the local law. A crime needs a witness: a guard arrests you on the spot; anyone else goes to
  the watch within hours unless you persuade, pay or frighten them into silence. When the watch takes you, you
  can pay, go quietly, bribe, run or fight. Sentences range from a fine or jail (your belongings are held until
  you are released) to the lash, the brand, hard labour or the rope, and you can try to escape. A disguise kit
  hides your face.
- **Joining.** Ask a guild's, church's or order's people to swear you in (they need your good opinion, and
  sometimes a skill, a trade, a faith or a fee). Ranks rise with standing and bring better prices. The right
  question may find the thieves' guild or a cult. A ruler who honours you may grant you a title.
- **History.** Each world has 250 years of history: dynasties with their usurpers, wars and conquests, plagues
  and famines, ruins with a past, dragons (some slain, some only sleeping), legendary heroes and lost
  artifacts. Press **n** for News and history: the news you have heard, the chronicle of the land, and its
  legends. With the Player2 AI running, one background request per world writes the chronicle as a monk would.
- **The world moves on.** While you play, rulers age, sicken and die, and their heirs or usurpers follow.
  Neighbours go to war, fight battles, besiege and take towns (borders really change), and make peace. Vassals
  rebel, plague and famine come and go, tribes raid, cults spread and are rooted out, gangs rise and are
  hanged. All of it becomes news that travels about 24 miles a day: you hear it at inns, from travellers, and on
  the notice board (¶) in a town square, which also has wanted posters (perhaps your own) and the lord's
  orders. War makes food and arms dear and fills the roads with refugees and deserters. A besieged town is
  hungry. Plague can follow you out of a town.

**How to try it**
1. Double-click `Play.bat`, start a **New World** (older worlds get their factions and history when loaded).
2. Press **f** to see who rules, **n** for the news and the chronicle, **m** then **p** for the realm map.
3. In a town, walk into the ¶ board in the square. At the inn, ask for news.
4. Try your luck with **s** in a market, or pick a pocket, and see what the watch does.

**What to look for:** Does the world feel like it has a past and a present? Do the factions and their quarrels
make sense? Is the law too harsh or too soft? Is the news interesting, or too much?

**How it was verified**
- 449 automated tests pass. New ones cover: every size of world has its powers; the structure of realms; the
  realm map; saving; older worlds; starting knowledge; background ties; rulers in their seats; first
  impressions; borders; witnesses and reports; unseen crimes; no law in the wild; fines; sentences (jail, lash,
  brand, rope, escape); bribes and running; fighting the watch; recognition; disguise; deeds rippling;
  gangs angered; prisoners; settling debts; silencing witnesses; joining and ranks; titles; theft; pickpockets;
  contraband; history (rulers, conquests that agree with the map); the world moving on for years; succession;
  a war with a siege; plague coming and going; prices in hard times; news travelling at the right pace; news at
  the inn; notice boards; the chronicle, built-in and by the (mock) AI; and every new window at every size.
- Autoplay: thousands of turns with AI off and with the fake AI on several seeds. It now commits crimes in front
  of the watch (arrests, sentences, escapes) and checks the factions, the law's records, wars, sieges and news.
  No errors. A separate stress run of 30 years of live politics on three worlds found no broken state.
- The window smoke test now shows the factions, the realm map and the chronicle. Its tour is now free of random
  road encounters, which could hijack it.

**Decisions (and why)**
1. **Code decides all politics**; the AI only writes the chronicle (one request per world, in the background).
2. **History is told, not replayed onto the map.** The map of today is made first; history then runs the same
   politics engine over 250 years for grudges, wars and plagues, but only tells of conquests that agree with
   today's borders. Wars still being fought at the end of history are today's wars.
3. **The live simulation runs a week at a time** and is cheap (30 years in about a second).
4. **Deeds reach factions at the speed of news**, from where they happened to each faction's seat.
5. **Crimes are judged by the realm at the top of the chain of lords**; a bounty in one kingdom means nothing in
   the next.
6. **Towns you visited before this update** keep their old maps (no notice board); new towns have one.

**Known issues**
- Quests, work for guilds, and hunting dragons and lost artifacts come with M8. Membership gives prices and ranks
  for now.
- Companions: M7. Joining sieges and battles yourself is on the ideas list for after v1.
- The built-in chronicle is plain and list-like; the AI version reads much better.

---

## M5 — Settlements and people (done)

**What you can do now**
- **Towns are full of people.** Walking into a settlement (`>`) you find its innkeepers, priests, smiths,
  shopkeepers, healers (barber-surgeons in towns), stablemasters, headman or reeve or mayor or alderman
  (a thane in dwarven holds, an elder among elves), a lord in the keep of a city, market traders at their stalls,
  the watch, and ordinary folk: farmers, weavers, carters, washerwomen, beggars, fishers, woodcutters, miners.
  Each has a name from their people, an age, a personality (two traits), a purse, a home and a place of work.
  They keep to day and night: shops shut at dusk and most folk go home; the inn, the temple and the watch stay.
  Some wander the streets. New buildings: general stores, healers' houses and stables, and market stalls in
  towns. (Dwarven holds now have buildings too; they had none before.)
- **Talking** (walk into someone): who they are, what to know about the place (they name the other notable
  people), news and rumours (dangerous roads, and places you did not know, which go on your map), other people
  in town, threats (Intimidation), bribes, and one to three skill-check options. Outcomes come from a fixed list
  (information, liking you more or less, prices, a small gift, a fight, calling the watch, running off, a new
  topic), so nobody can promise what the game cannot deliver. **First impressions** depend on your clothes,
  cleanliness, bleeding wounds, race and background; people **remember** what you did (threats, bribes, help)
  and greet you accordingly. Hostile people won't talk. Fight townsfolk and the dead stay dead; the rest hate you.
- **With the Player2 AI running**: when you set out for a town or stand at its gate, one background request
  writes its description, its inn signs and full profiles of its notable people (looks, personality, speech,
  backstory, a secret, what they want). When you talk to a notable (at most once a day each), one request writes
  their opening line and proposes options that fit the person and the moment, e.g. "[Insight] She is hiding
  something about the bell". A short "…" appears; if the AI is slow, the built-in lines take over. AI words only
  ever replace text you have not seen.
- **Markets**: every merchant has stock and coin, restocks weekly, only buys their own trade, and won't touch
  stolen goods. Prices follow the land (salt cheap on the coast, iron in the hills, furs in the cold north, grain
  on the plains), trade goods are dear where nobody makes them, cities pay more for food, holds less for steel,
  winter food is dear, and the merchant's feelings and a daily haggle move them. **Trading pays**: in a test
  world salt bought on the coast sold inland for 2.8 times as much, furs 2.3 times, iron 1.8 times.
- **Services** ("What can you do for me?"): a bed in the common room or a private room (a safe night's sleep),
  hot meals, baths, performing for coin (Performance) and dice at the inn; healers treat all your wounds at once,
  operate on internal bleeding and sell herbal cures; priests pray for healing or to lift a sickness (for a
  donation); smiths mend weapons and armour; a day's paid work at the smithy, the stable or on a farm.
- **Animals**: mules (carry 200 lb for you), ponies, draft horses and riding horses from the stable. Riding makes
  open ground and roads quicker if everyone has a mount. They need a bag of fodder a day, or grazing outside
  winter; unfed they starve after a few days. Robbers take them. They show in the side panel.

**How to try it**
1. Double-click `Play.bat`, **Continue**. Press `>` in a town. Walk into people (the `☺` symbols).
2. Talk to the innkeeper: ask for news, then "What can you do for me?" for a meal or a bed.
3. Visit the smith or shopkeeper: "Let me see your goods", buy and sell with Enter, haggle with `h`.
4. Buy a mule at a stable (towns and cities) and see your carrying limit rise (`i`).

**What to look for:** Do towns feel alive? Are conversations readable? Are prices sensible, and is trading
worth it? If Player2 is running, do the AI lines fit the people?

**How it was verified**
- 382 automated tests pass. New: every kind of settlement has its people, none in walls or on top of each
  other; people are made once; shops close and folk go home at night; first impressions; walking into someone
  starts a talk; the menu and its answers; special options; threats remembered; bribes; fighting townsfolk; people
  survive saving; the AI requests list the right facts; AI words only replace unseen text; AI options are kept to
  what that person can deliver; a conversation with the (mock) AI; a slow AI falls back and late replies are
  ignored; heading for a town asks for its words; every kind of merchant has stock and coin; cities stock more;
  trade goods are cheap where made; winter food is dear; mood and haggling move prices; buying and selling;
  merchants only buy their trade and run out of coin; restocking; trading in conversation; shops survive saving;
  inns, healers, temples, smiths, labour; animals (carrying, riding, selling, starving, saving); hostile people
  offer nothing; every new window renders at every size.
- Autoplay: 10,000 turns with AI off and 10,000 with the fake AI on several seeds, now walking into towns and
  talking, trading and using services, checking townsfolk never stand in walls or on each other and shops never
  go below zero. No errors.
- The window smoke test now talks to a townsperson, and **always runs with the AI off** (it had been using the
  real Player2 app when it was running; that is fixed so tests never spend your AI energy).

**Decisions (and why)**
1. **Code names people** (from their culture's name lists) and decides everything mechanical; the AI writes only
   words, in one rich request per town and one per conversation, to spend Player2 energy sparingly. Towns merely
   passed on a journey are not asked about; ordinary folk use built-in text only.
2. **Conversation outcomes come from a whitelist** that is narrowed per person (no prices from a priest, no gifts
   from someone with nothing, no watch where there are no guards).
3. **Prices** are driven by production near each town rather than a full simulated supply chain; that gives real
   trade routes now. Caravans, war and famine moving prices arrive with the world simulation (M6).
4. **Animals add carrying capacity to the leader** rather than having their own packs, to keep the inventory
   simple.

**Known issues**
- Law, crime, bounties and reputation with factions come with M6 (for now, attacking townsfolk is only
  remembered by them and recorded in your deeds).
- Quests and work beyond day labour: M8. Recruiting companions: M7.
- Settlements visited before this update have no general store, healer or stable (their maps were already made);
  their people appear on your next visit.

---

## M4 — Body and survival (done)

**What you can do now**
- **Weather.** Rain, drizzle, storms, snow, blizzards, fog and heat waves roll across the map as moving fronts,
  on top of each place's climate (latitude, height, season, day and night). The side panel shows the weather
  where you are; the world map shows it for the whole land (`m`, then `w`). Weather slows travel, shortens how
  far you can see (fog!), soaks you, and follows you into fights (rain spoils bowshots, fog hides the enemy).
- **Your body over time.** Hunger, thirst, tiredness and dirt grow as you go (faster when walking, in the heat,
  or when shivering). **Body heat** comes from the air, wind, rain, what you wear (warmth, wind and rain
  protection of each layer), whether you are wet, what you are doing, shelter, bedding and fire. Clear stages
  with warnings: peckish → hungry → starving; thirsty → parched → dehydrated; chilled → cold → hypothermic →
  freezing; hot → overheated → heat exhaustion → heatstroke. **5e exhaustion** (levels 1–6) builds up from the
  worst of these, with its real effects (disadvantage, half speed, half hit points...), and level 6 is death.
  A night's sleep with food and water takes one level away.
- **Food and water.** Eating and drinking happen by themselves from your pack when needed (a setting you can
  turn off; then use Enter on food or a waterskin in the inventory). Waterskins hold 4 pints and weigh what the
  water weighs. Wells in towns are safe; rivers, lakes and marshes may give you dysentery or marsh fever unless
  you boil the water. Food spoils (fresh bread in days, rations in months); spoiled or raw food may poison you.
  `w` fills your waterskins, `W` washes.
- **Health (h).** Wounds from battle now live on: bleeding wounds lose blood until bandaged (small cuts clot by
  themselves; gushing ones kill in hours), dirty open wounds may **fester** and poison the blood, **broken
  bones** heal straight only if splinted, **critical** wounds and unset bones may leave **lasting injuries**
  (a scar, a scarred face, a lost eye, lost fingers, a weak arm, a limp, bad lungs). Healing takes days
  (minor), one to three weeks (serious, critical) or about a month (bones). **Pain** and **blood loss** make
  everything harder. Treat wounds on the Health screen: bandage, clean, stitch, splint, cauterize, poultice;
  poppy milk dulls pain (and can hook you); drink helps too (and leaves a hangover). Clerics can cast Cure
  Wounds, Healing Word and Lesser Restoration outside battle.
- **Ten diseases** (all in `data/diseases.json`): dysentery, food poisoning, wound fever, lung fever, marsh fever,
  camp fever, plague, filth fever, the frothing sickness (from animal bites: always fatal once it shows, unless
  magic cures it first) and grave rot (from the dead). Each has its own way of spreading, time before it
  shows, stages, treatments, chance of death and after-effects. Rest, warmth, clean water and herbs help you
  throw them off.
- **Effects that matter in a fight:** exhaustion gives disadvantage, a broken arm can't hold a weapon (and
  two-handed weapons need both arms), head wounds can make you black out, great pain can put you in shock.
- **Camp (r).** Light a fire (easy in woods, hard in the open, impossible in a storm without a tent; you need a
  tinderbox, and firewood where there is none), pitch a tent, eat, cook raw meat and fish, boil water, forage
  (1 hour), hunt (2 hours), fish (2 hours, at water), see to wounds, rest or sleep. A fire warms, dries, cooks
  and keeps most beasts off, but people see it from afar. Something may find you while you hunt or sleep; if
  it comes while you sleep, you are caught unawares.
- **After a fight with beasts** you can butcher the carcasses for meat, hides and furs.
- **The road.** Travel takes longer in bad weather, and when you are hurt, sick, starving or exhausted.
  **Off the road in fog, storms or darkness you can lose your way** (Survival); a road or clear weather brings
  you back. **Twelve kinds of travel event** (all in `data/travel_events.json`): a pedlar (buy food, water,
  bandages...), pilgrims, a patrol, refugees, a wounded traveller, an abandoned camp, hunters (buy meat and
  hides; learn where the game is), a fresh carcass, a wayside shrine, a patch of healing herbs, hungry
  deserters, a gibbet. Choices use your skills, cost or gain things, add to your deeds, and some turn into
  fights. **Each day of travel is written up in the log**: by the Player2 AI when it is running (one small
  request per day, in the background), otherwise from built-in text.
- Everyone now starts with two bandages. New items: spirits, poppy milk, healing herbs, roast meat, fish, porridge,
  wild food, firewood.

**How to try it**
1. Double-click `Play.bat`, **Continue**. Press `h` to see your Health screen and `r` for the camp.
2. Walk out of town into the wilds and keep going for a few days: watch the weather, the side panel, and the
   log at each new day. Try the world map's weather view (`m`, `w`).
3. Get into a fight (or use the debug console: `` ` `` then `fight wolf_pack`), then look at your wounds with `h`
   and treat them. Rest in camp with `r` → `l`.
4. Try a winter night in the open without a fire (it is dangerous), then with one.

**What to look for:** Is survival interesting or just busywork? Are the warnings clear before things get
deadly? Is the Health screen understandable? Are travel events fun? Do the daily passages read well?

**How it was verified**
- 329 automated tests pass. New: weather is deterministic, varied and plausible; seasons are smooth; fronts move;
  needs grow and sleep restores; a winter night outside is dangerous and a fire or shelter prevents it; rain
  soaks and fire dries; heat waves; starvation and thirst build exhaustion and kill; long rests need food;
  eating, drinking, wells, river sickness, spoiled food; death ends the game; the new body fields and waterskin
  contents survive saving; wounds bleed, clot, fester (dirty more than clean), heal over days and bones over
  weeks; unset bones leave limps; wound fever; diseases incubate, strike or pass, can be recovered from, and
  the frothing sickness kills unless magic cures it early; treatments use supplies and skill; cautery; splints;
  poultices; healing magic outside battle; poppy and withdrawal; drink and hangovers; penalties in skills,
  saves and attacks; broken arms; exhaustion in battle; health state survives saving; fire, cooking, boiling,
  camps breaking when you move; foraging, hunting, fishing; butchering; every travel event and option can be
  played; requirements; news; events on roads; getting lost in fog and found by a road; travel days written up
  with and without the AI (mock); every new screen renders at every window size.
- Balance simulations (200 characters each): a bandaged minor cut heals in under 2 days; an untreated serious
  cut kills about 1 in 11 (by festering), 1 in 100 if cleaned and bandaged; a gushing critical wound left alone
  is usually fatal, almost never if treated; broken legs take 3–4 weeks; plague kills about 1 in 6 hardy
  fighters. A soldier sleeping at -8°C with a blanket and no fire wakes hypothermic; with a fire, fine.
- Autoplay: 10,000 turns with AI off and 10,000 with the fake AI on each of two seeds, meeting fights and travel
  events, checking body values, wounds, diseases and waterskins stay within bounds. No errors.
- The window smoke test now visits the Health screen and the weather map.

**Decisions (and why)**
1. **Weather is computed, not stored**: a smooth function of the world seed, place and time. Fronts really
   move and saves need nothing extra; the same moment always has the same weather.
2. **Eating and drinking are automatic by default** (the pack is used when you are hungry or thirsty). Survival
   stays meaningful (supplies run out, water can be bad, food spoils) without tedious micromanagement. It can be
   turned off in Settings.
3. **Exhaustion** uses the 5e track as the design asks; for checks and saves outside true rolls it counts as -5
   (the 5e passive-check equivalent of disadvantage); in battle it is real disadvantage.
4. **Hit points stay stamina**: blood loss, pain, festering and sickness are the body's real state, and they are
   what kill you slowly. Hit points only drop at the extremes (freezing, heatstroke, sepsis, the worst diseases).
5. **Travel-day passages use the AI sparingly**: one small background request per day of travel, skipped when
   energy is low (the built-in text is used instead).
6. **Animals (mules and horses)** are left for M5, where they can be bought; the travel rules are ready for them.

**Known issues**
- A camp is not saved: if you quit while camped, the fire is out when you come back.
- Getting lost is not saved either (you know where you are after loading).
- Inns, baths, healers and surgeons arrive with towns (M5); plague outbreaks in towns with the world simulation.
- Companions (who can keep watch and treat each other) arrive in M7.

---

## M3 — Combat (done)

**What you can do now**
- **The wilds are dangerous.** While you walk, travel or wait outside a town, something may find you. The
  wilder the region (the "Wilds" line in the side panel), the more likely; night is worse and roads are a
  little safer. What you meet depends on the land: wolves and boars in the woods, bandits and deserters on
  the roads, the restless dead near ruins, orcs and ogres in the hills, a troll if you are unlucky.
- **Trouble on the road** gives you a choice before any blood is spilled: **Fight**, **Ambush** them (only
  if you saw them first), **Slip away** (a Stealth roll), or **Talk your way past** (Persuasion; animals and
  fanatics won't listen). It also tells you how dangerous they look, from "You could take them" to "This
  will very likely kill you".
- **Ruins, caves, barrows and towers are inhabited.** On their close-up maps the inhabitants show as
  letters; once they notice you they turn red and come for you. Walk into them to attack (catching them
  unawares if they hadn't seen you); if they reach you first and you hadn't seen them, *you* are surprised.
- **The battle screen**: your side and theirs, each in a front and a back rank, with health bars, the order
  of battle along the top and the battle log. On your turn: Attack, Cast a spell, Use an item, Class
  ability, Dodge, Help / first aid, Shove or grapple, Change rank, Parley, Surrender, Flee. Pick a weapon or
  spell, then a target (number keys, arrows, or click). Clicking an enemy attacks it straight away.
- **5e rules**: initiative, attack rolls against armour class, advantage and disadvantage (prone, helped,
  dodging, darkness, shooting while in melee, pack tactics...), critical hits, saving throws, sneak attack,
  second wind, action surge, fighting styles, racial traits (halfling luck, half-orc endurance, dwarven
  poison resilience). With "Show dice rolls" on (Settings), every roll is shown in the log.
- **Ranks**: melee reaches only the enemy front rank unless it is empty or you have a reach weapon; from the
  back you need a bow, a thrown weapon or a spell. Archers fall back to shoot; brutes push forward.
- **Where blows land**: every hit strikes a body part, described in plain grim words ("Aldith slashes
  Jocelyn across the left hand"). Hard hits leave **wounds**: cuts that bleed each round until bandaged,
  broken bones, bites. Armour on that part makes a wound less likely. Wounds stay after the fight (healing
  them over time comes with M4).
- **Falling**: at 0 hit points you go down and start **bleeding out**: a few rounds, fewer if hit again. A
  friend can stop it (Help, a healer's kit, or Spare the Dying). Monsters simply die.
- **Morale**: badly hurt enemies, and bands that lose half their number or their leader, may break. Beasts
  run; bandits and soldiers may throw down their weapons; fanatics and the dead never do.
- **Surrender and robbery**: bandits, thugs and deserters take prisoners. If they beat you (or you
  surrender), they take your money and your best valuables and leave you alive. Wolves, the dead and
  cultists do not take prisoners.
- **Spells**: wizards and clerics cast from spell slots (cantrips are free): Fire Bolt, Magic Missile, Sleep,
  Burning Hands, Thunderwave, Shield, Mage Armor; Sacred Flame, Cure Wounds, Healing Word, Bless, Guiding
  Bolt, Command and more; higher levels up to Fireball, Spirit Guardians and Cone of Cold (35 spells). Turn
  Undead for clerics from level 2.
- **After the fight**: what the field looks like, experience (shared out; **levels go up automatically**
  with more hit points and new features), the fate of **prisoners** (let go, rob, question, kill; taking them
  for a bounty needs M6) and the **spoils** (take all, mark and take some, or leave the rest; on a close-up
  map what you leave stays on the ground).
- **Rest** (`r`): a short rest (an hour, spend hit dice to heal) or a long rest (eight hours: full hit
  points, spell slots and features back). A long rest in the wilds can be interrupted.
- **Death is permanent.** A death screen tells how, where and when, what you killed and what you did. The
  world stays; start a new character in it from the title screen. (The AI-written obituary is M9.)
- 22 kinds of creature in 23 encounter groups, all from data (`data/creatures.json`), with original
  descriptions; rules numbers follow the SRD 5.1.

**How to try it**
1. Double-click `Play.bat`, **Continue** (or make a new world). Walk out of town into country marked
   "dangerous" or worse, and wait (`.`) or travel at night. Or find a ruin or cave on the world map (`m`),
   go there and press `>`.
2. In battle, try `a` then Enter then `1`; try `c` as a wizard or cleric; try `p` against bandits.
3. Afterwards press `r` to rest.
4. (Testing shortcut: the debug console, the backquote key left of 1, has `fight bandits`, `fight list`,
   `heal`, `gold 50` and `xp 300`.)

**What to look for:** Are fights readable? Is the pace of enemy turns right (about half a second each; any
key hurries them)? Are level-1 fights too hard or too easy? Is anything in the battle screen confusing?

**How it was verified**
- 261 automated tests pass. New: battles against seven kinds of foes over many seeds always finish with sane
  numbers; every class can fight; initiative order; the same seed gives the same fight; ranks limit melee;
  going down, bleeding out and first aid; wounds from heavy hits; bandits surrendering and fleeing; fanatics
  and undead never breaking; parley and surrender rules; fleeing sometimes working; wizard slots, cantrips,
  Sleep; cleric healing and Turn Undead; Second Wind; potions; XP and level-up; short and long rests; a whole
  encounter to victory with loot and XP; defeat by bandits meaning robbery and by wolves meaning death;
  prisoner fates; slipping away and talking; encounter odds; inhabited sites surviving a save; fights played
  through the screens at every window size and against every encounter group; the death screen; broken
  creature data being reported on the data-error screen.
- Balance check (200 simulated fights each, a level-1 fighter alone): one wolf 83% won, two bandits 80%, three
  bandits about 40%, two wolves 28%. The design's target is that two wolves or three bandits are "a real
  threat" at level 1; a lone character also has evading, talking, fleeing and surrender. Groups are scaled
  down for a party of one until companions arrive (M7).
- Autoplay: 20,000 turns with AI off and 20,000 with the fake AI (plus 4,000 each on another seed), now
  starting about one fight every 150 turns and checking during battles: hit points in range, valid states,
  creatures never standing in walls, the dead never walking on. No errors.
- The window smoke test now meets bandits on the road and screenshots the encounter, the battle screen, the
  attack menu and target choice.

**Decisions (and why)**
1. **One action per turn**, no reactions, bonus actions, opportunity attacks or concentration (the design's
   v1 simplification). Fleeing is a group roll instead of movement. Ranged attacks from the front rank while
   engaged have disadvantage instead of provoking.
2. **Hit locations and wounds** use the design's list (head, torso, arms, legs); armour lowers the chance a
   hit becomes a wound rather than the damage. Severity scales with the share of hit points lost.
3. **Robbers keep you alive** (bandits, thugs, deserters); beasts, the dead and cultists kill. This makes
   defeat a setback rather than the end in many fights, as the design's "surrender" option intends.
4. **Enemy groups are scaled to party size** (a lone character meets smaller bands). Once companions exist
   (M7) full bands appear.
5. **Levels go up automatically** with sensible choices (average hit points, the class's features); choices
   such as subclass and spells can be revisited when M7 adds the full levelling screen.
6. **Knowledge checks**: at the start of a fight the party's best Nature/History/Religion roll decides whether
   you know an enemy's exact numbers; otherwise you only see "wounded", "badly hurt" and so on.

**Known issues**
- Quitting in the middle of a fight doesn't save the fight: you continue from just before it (inhabitants
  of a close-up map keep any hurts you gave them; a band met on the road is gone).
- ~~Wounds don't heal, fester or bleed outside battle yet~~: done in M4.
- ~~Only hostile encounters for now~~: travel events added in M4.
- Prisoners can't be taken to a town for bounty or ransom yet (M6).
- One character only; companions (and fighting side by side) arrive in M7.

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
- ~~Spells can't be cast yet~~: done in M3.
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
