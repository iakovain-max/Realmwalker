# Adventures & Events – the design of Expansion 6

*The heart and mind of Realmwalker. Written on 2026-10-22 for Anton, and for every Claude Code session that builds
this expansion; widened on 2026-10-24 after his second note (rare quests that matter, and stories that are seen). It
rests on surveys of the game's code (version 1.5.0), on the Dungeon Master's Guide 2024 (chapters 4 and 5, renown,
marks of prestige, settlements), on Ravenloft: The Horrors Within (2026), on Curse of Strahd, and on three books about
solo play (DM Yourself, The Solo Adventurer's Toolbox, Citadel of the Raven). Nothing in this file copies a book's
prose; every word the player will read is still to be written in the game's own voice.*

The task list that builds it is `docs/expansions/06-adventures-events.md`. This file is the design: read §0–§4 once
fully, then only the section your part points to.

---

## 0. In one page (for Anton)

Right now Realmwalker is a magnificent world with nothing happening to you in it. The world is simulated in depth –
kings die, wars grind, beasts take lairs, cults grow, dragons sleep – but the player meets all of that only as a
list of jobs that pay money. You walk to a marker, you fight, you are paid, and nothing you did matters afterwards.

Expansion 6 adds the part of the game that tells stories. Six new things:

1. **Threats.** The world's dangers become real actors with plans. The barrow king who died at Marrow Ford in 812 is
   stirring; the cult in Kessa means to open its circle on midwinter night; the wolf of the Greyfells grows bolder
   each month. Each threat has a villain from the world's own history, a scheme that moves forward week by week, and
   **signs** you can see: the dead on the roads, a hamlet emptied, prices rising, a lord murdered. Ignore a threat and
   it wins – and the map changes for the worse.
2. **Adventures.** When you take a threat on, the game builds an adventure around it: a story in chapters, with a
   beginning, a middle and an end. It sends you to new places, it gives you a cast (a patron, an ally with a stake,
   a rival who wants the same prize, the villain's lieutenants, sometimes a traitor), it hides things for you to find
   (where the relic lies, what the villain fears, who is lying), and it ends in a **finale**: a big, fair, prepared
   fight against a boss you have heard about for hours. Everything you found along the way makes that fight
   winnable.
3. **Events.** Things happen to you for reasons. The villain notices you: a letter at dawn, a test in the night, an
   invitation to dinner, a bargain, an attack on the people who helped you. Allies seek you out. Rivals get there
   first. The bandit you spared comes back. Kings are crowned and you are in the city for the tournament. A
   **Storyteller** keeps the rhythm – rising tension, a crisis, relief – so that something worth telling happens every
   day or two of travel, and it is always about something.
4. **Legend.** You grow as a story, not only as numbers. Every adventure won raises your Legend: people greet you
   by the name you earned ("Barrowbreaker"), lords receive you, kings send for you, bards sing what you did, titles and
   land come to you, rivals and assassins come too. You choose an **Ambition** when you make your character (to avenge
   someone, to win back your family's seat, to be sung of for ever...), and it is woven through the adventures you
   play. When it is fulfilled you may end your tale – and your hero stays in the world as a living lord, an old
   champion at the inn, a name in the Legends book for your next character to meet.
5. **Quests that matter.** The job board goes: nobody hands out a weekly job any more. A quest is now something that
   has gone wrong in the life of someone real – a son run off to the gang, an innocent man in the stocks, a debt come
   due, a body in the reeds – met in the street and assembled from the world itself, so that no two are alike; or a
   chapter of an adventure; or a commission from a faction you serve. Quests are rare (a town has one at a time), each
   has a real decision and a way through without blood, each leaves something you can see later, and many lead into an
   adventure. Paid work stays, small and honest: contracts and bounties.
6. **You see it happen.** A stable boy runs up with a letter that opens in its writer's own hand; a crowd gathers under
   the gibbet; the villain steps out of the dark at your campfire. A town burned in a war **is** burned when you come:
   charred shells, ash in the streets, smoke over it on the world map, new graves by the temple, and in a season the
   scaffolds of its rebuilding. The dead of a fight lie where they fell, and the blood stays on the cobbles. Near the
   end of a tale you may fight through a whole town as it burns. The world map shows the world's state – sieges
   ringed with tents, hosts marching on the roads, a region under grey mist – and, once in a hero's life, a wound torn
   across the land by a god's blow, with a crusaders' camp-city at its edge.

And every ending **writes itself into the world**: a town liberated or burned, a ruler crowned, a cult destroyed, a
road safe again, a statue in a square, a song in the inns, a page in the Legends book. The next life in that world
starts in a place your last life changed.

The old loop was: *king → mercenaries → food → marker → fight → pay → repeat*. The new loop is: *you see something
happen → it is someone's trouble, and part of something larger → you choose what to care about → the story pulls you
somewhere new → the villain answers → you prepare → the finale → the world changes, and you can see it → you are
someone now, and bigger things notice you*.

---

## 1. What is wrong today (the diagnosis)

Anton's four lacks, and what the code shows behind each (from the survey of 2026-10-22):

| Lack | What the code does today |
|---|---|
| **Impact** | A finished job changes standing, a disposition and `politics["cleared"]`. A cleared bandit hideout leaves the gang's leader alive and the gang faction active (nothing calls `Politics.fall`); an investigated cult is only `know()`n. Only a missed `defend` burns a village. No quest outcome changes an owner, a ruler, a relation or a faction's strength. |
| **Direction and narrative** | Seventeen standalone templates (`quests.BUILDERS`), one target each, re-rolled weekly per notable. No quest leads to another. Rumours, books, letters and events only mark places as known; none of them creates work. Faction `goals` are strings nothing reads. |
| **Narrative progression** | Fame is a number. Ranks exist inside factions. Nothing about the world's treatment of you changes with what you have done, beyond prices and a few followers. |
| **Interesting things happening** | 25 travel events, chosen at random by road, biome, danger, time of day and season; each is a single decision (3–8 options) with no follow-up. Politics moves on random rates (`beast_comes`, `dragon_wakes`, `raid`, `cult_year`) and never responds to the player. Nobody escapes, remembers, retaliates or returns. |

Also: lords are the best people to work for, because they give the richest templates and the strongroom gifts (pay
itself follows the template's range, the distance and the party's level); hunt-beast targets come from a fixed list
of nine names, not from the world's beasts; the event screen shows one decision and ends; the journal has no
storylines; quests die with the character while the world (and its threats) lives on.

Anton's second note (2026-10-24) adds two more, and the second survey of the code (the same day) shows both:
- **Quests are a menu.** A town of eighty people holds eight to twelve open offers at once and a city fifteen or more
  (`quests.offer_for`: a roll every seven days for each giver, 0.6 for notables and 0.3 for the rest, each offer kept
  for fourteen), and the choice "Is there any work?" appears exactly on the people who have one. So no quest weighs
  anything.
- **Nothing is shown.** The politics engine burns, sacks, besieges, starves and plagues towns, but no status touches a
  close-up map, a townsperson's day or the world map (only words, within twelve squares). Nobody ever walks up to the
  player. When a fight ends its dead vanish, and nothing it did stays on the map. Nothing on the world map moves but
  the party, and nothing changes the land while you play.

The world simulation is the game's greatest strength. Expansion 6 does not replace it: it gives it a **director**,
so that the simulation's dangers reach the player as stories, and a **memory**, so that the player's deeds reach the
simulation as consequences, and **eyes**, so that both can be seen.

---

## 2. What playing will feel like: a first evening

*(An illustration of the finished expansion. Names come from a made-up world.)*

Mira, a soldier of House Varn, starts her life at dusk outside Harrowmere. The gate warden will not open: a child was
taken from the mill last night, the third this month, and the town is afraid of the dark. Inside, a crowd stands at
the mill door, where the miller's wife is shouting at the headman; she sees Mira's sword and pushes through to her.
The headman offers twenty gold for "the beast". An old woman by the inn's fire says it is no beast: on the hill above
the town stands the barrow of Aldric the Red, killed at Marrow Ford in 812 – and the Legends book agrees, Mira can
read it there and then.

**Chapter I – The Taken.** The tracks by the mill are small, bare feet, and they go up the hill, not into the woods.
The miller will not say where he goes at night. Brann, an old soldier whose son was the second child taken, asks to
come. He wants no wages. In the barrow's first level Mira finds the miller's daughter alive among the bones, and a
fresh sigil on the wall: someone is waking the dead king. That night, at her camp, a raven drops a scrap of black
wax-sealed vellum: *"Leave my children to me. – A."* The villain has noticed her.

**Chapter II – The Red King's Crown.** To lay Aldric to rest she needs his crown, taken by the knight who slew him and
buried with that knight in the old temple at Coldwell, two days east. At a crossroads a road-woman reads her cards for
a copper: *the key lies where a river forgets its name; one who has lost a son will stand with you; the last door is
under the hill, where the king sits on his own bones.* A band of glory-hunters, the Brothers Ost, want the crown too –
the baron has posted a price on the barrow. Meanwhile the dead are seen on the Marrow road; passing Fennick, she finds
its doors open, its hearths cold and its dogs howling at the hill; grain in Harrowmere costs half as much again. At
Coldwell's gate a stable boy runs up with a note in a shaking hand: the miller's wife writes that her husband was paid
in old silver, by a man who smelled of the grave. At Coldwell the necromancer who woke Aldric – one of his two
lieutenants – waits with the crown. He escapes, wounded, swearing she will hang beside him.

**Chapter III – The Night at the Ford.** On the new moon the dead march. With the militia Brann raised from the mill
hands, Mira holds the ford through three waves by the light of the carts they set burning across the road, then goes
under the hill. Aldric rises from a throne of bones with his last lieutenant and his wights. Because she carries his
crown, his will can no longer turn her blows aside (no Legendary Resistance); because she learned his true name in the
temple's chronicle, he flinches when she speaks it; because Brann is there, the wights do not fall on the wounded. It
is still the hardest fight of her life.

**Epilogue – What became of them.** When Mira rides back through Harrowmere, the mill wheel turns again, three new
graves stand by the temple, and the stones of the ford are still dark. Brann's son was found alive in the barrow's
deepest room, and Brann stays with Mira as a sworn companion. The Brothers Ost tell the story of the ford in every
tavern from Coldwell to the coast; within a month a song, *The Crown at Marrow Ford*, is sung in three towns. The
necromancer is still out there – he has a grudge now. The baron sends for "the one they call **Barrowbreaker**": her
Legend has risen, and the work the baron has is bigger than a barrow.

That is one adventure of a tier-1 hero, roughly an evening of play, perhaps two. Every piece of it already exists in
the game's world (the barrow, the dead king, the battle, the temple, the history), and every piece of it is generated.

---

## 3. The eleven laws of the story engine

Every part of this expansion obeys these. A reviewer checks new content against them.

1. **Someone always wants something.** Every event has a cause in the world: a villain's move, a faction's need, a
   companion's past, a remembered deed, a happening. Nothing that matters is purely random.
2. **The next step is always clear, and there is always a choice.** The journal always says what you could do next,
   and there are usually two or three things you could do first. Never a dead end; never only one door.
3. **Nothing you do to a story is forgotten.** Spared, freed, betrayed, cheated, saved – the world keeps a record, and
   the record comes back as events (echoes).
4. **Every ending changes the map.** Something visible changes in the world for each outcome – good or bad – and the
   news, the townsfolk and the Legends book say so.
5. **Bosses are fair.** A finale's boss is known by name long before it is met, its strength is signalled, its
   weaknesses can be learned, and preparation measurably helps. The finale is never an ambush.
6. **Failure moves the story forward.** A lost fight, a missed deadline, a wrong accusation – each costs something
   and changes the story, but never ends it. ("No, but…" instead of a dead end.)
7. **The world does not wait, but it warns.** Threats move on their own clocks, slowly, with signs before every step.
8. **Growth is told, not only counted.** Every tier of Legend changes how the world treats you, in words and in what
   is offered.
9. **The world's own history first.** Villains, places, relics and allies come from what the ages left; only what is
   missing is invented, and what is invented is then part of the world's history too.
10. **Always one more chapter.** Every chapter ends with a reveal and the next hook; every adventure's ending leaves
   a thread (a fled lieutenant, a grateful lord, a bigger shadow) that can grow into the next.
11. **Show, don't tell.** What happens is seen before it is read: people act, places keep what happened to them, the
   world map shows the world's state, and words come last and say less (§5.17).

---

## 4. The new loop, from the moment to the life

| Clock | Length | What fills it | The payoff |
|---|---|---|---|
| **The moment** | minutes | a beat or a scene: a sign on the road, a runner with a note, a crowd at the gibbet, a villain's letter, an ally's confession, a rival's camp, a clue found, a choice with a skill check | a revelation, a small reward, a choice that will matter |
| **The situation** | half an hour to an evening | someone's trouble, met in a town or on the road (§5.15–5.16): a scene, a decision, ways through, a clock | a person saved or lost, a favour or a contact, a grave or a wedding, often a thread into a threat |
| **The chapter** | an hour or so | 2–4 steps toward a chapter goal, usually in a new place, ending in a set piece (a lieutenant, a siege night, a rescue) and a reveal | chapter title card, a key for the finale, a new place, a new face, the next hook |
| **The tale** | an evening or two (a tier-1 adventure) to many evenings (tier 4) | 3–5 chapters, the villain's escalation, the finale, the epilogue | the boss fight, the world changing, Legend rising, a relic, a title, a sworn ally |
| **The life** | the whole character | an Ambition woven through 3 adventures of rising tier, Legend tiers, titles and land | being someone; the chance to end the tale well; a legacy the next character meets |

The money loop stays underneath (contracts and bounties, mercenaries, trade, food, survival) and still pays the bills;
it is no longer the point. The weekly job board is gone: a quest is now a situation, a chapter or a commission
(§5.15), and situations lead into adventures.

---

## 5. The pieces

### 5.1 Threats: the darkness in the world

A **threat** is a danger with a will behind it, living in the world whether or not the player cares. Threats are
world-side records (`world.politics["threats"]`), so they outlive characters, move during the interlude between lives,
and can be met by the next hero further along their scheme.

**Where threats come from** (law 9: the history first). At world creation, after the ages, `world/threats.seed` reads
what the history left and makes threats, most of them *dormant*:

| Source in the world (`world.politics`, factions, figures) | Threat kind | Its villain |
|---|---|---|
| `tombs` (a king or lord buried with a death worth remembering) + nearby `scars` | **the risen** | the tomb's figure, risen (barrow wight, or stronger by tier) |
| `lairs` (a living named beast; its `kills`, `fame`) | **the beast** | the beast figure (`past.beast_title`) |
| active `bandit_gang` factions (leader figure, site) | **the outlaw lord** | the gang's leader |
| active `cult` factions (`presence`, hidden site) | **the hidden circle** | its leader figure, "the Voice" (`fx.leader_of`) |
| `towers` whose master lives (`world/dungeon.tower_master`) with a dark trait, or a fallen mages' circle | **the mad mage** | the tower master |
| `tribe` factions with raid history near hamlets | **the warband** | the warchief (a figure made for it) |
| `dragons` (living dragons and their lairs; a town's `tribute`; the one the history left sleeping) | **the dragon** | the dragon figure |
| realms with `flags["crisis"]`, a regent, a claimant in the family tree, a rebel vassal | **the crown in shadow** | the usurper, regent or plotter |
| `grudges` between living figures of two houses | **the blood feud** | the harder of the two |
| unfound `artifacts` with a dark story, or held by a living villain | **the relic hunt** | whoever else wants it |
| plague history and live `plague` status | **the sickness** | its source (a hag, a necromancer, a poisoned well's culprit) |
| any of the above at tier 3–4 that the game makes into a ruler of a cursed region | **the dread lord** | a vampire count, a lich, a hag queen (later expansions add more) |

New threats are also born **while you play**: politics already makes new gangs, cult growth, beasts coming down,
dragons waking and succession crises; the `Politics` method that does each calls `threats.seed_from(politics, kind,
refs)` with the faction, figure or site it touched, which may make (or wake) a threat. And endings make sequel threats
(the fled lieutenant, the power vacuum, the defeated villain's heir).

**Tier comes from the place, not the hero** (DESIGN.md §6: enemies scale with the danger of the region, so some fights
should be avoided). A threat's tier is set from its source's site and area danger; the Storyteller *offers* threats
that fit the hero's tier first, and a threat above the hero is signalled as such (the sage's warning, the boss's card,
an Insight check). Taking one on early is possible, and deadly, as it should be.

**The record** (full shape in §8.3): kind, tier (1–4, as the DMG's tiers of play: local, regional, realm, world),
state, villain (a figure id plus what the story needs: temper, goal, dark deed, torment, anchor, first words), home
place, reach (an area on the map), the places at stake, the **scheme**, lieutenants, signs shown, the adventure that
engages it (if any), and its ending.

**Life cycle.** `dormant` (nothing happens; it only waits for a trigger) → `stirring` (signs begin; rumours; the
scheme's first stage) → `active` (the scheme advances on its clock) → `ended` (won, lost, laid to rest, fled, or
became something else). A dormant threat wakes when the Storyteller needs one of its tier near the player, when a
trigger fires (someone robs the tomb; a cult's fortunes rise; the dragon's sleep ends), or slowly by chance.

**How many.** The world keeps a budget of active threats by size (small 3–5, medium 5–8, large 8–12), spread over the
map and over tiers, with at least two tier-1 threats within a week's walk of any starting town, and at most two
stirring or active threats near the hero (within 30 tiles) that the hero has not taken on – the rest wait dormant.
The numbers are data.

**The scheme and its signs** (Dungeon World's fronts, the DMG's "threads that rot", Citadel's progress points). A
scheme is 4–6 **stages**; each stage has a duration (by tier: tier 1, 10–20 days; tier 2, 15–30; tier 3, 20–40; tier
4, 30–60), the **signs** that show it (news, rumours, town barks, encounters on the roads, a status on a settlement,
flavour on the land), and the **world effects** it applies when it begins. The last stage is the **doom**: what the
villain wins if nobody stops it. Example – *the risen*: `omens` (graves disturbed, dogs howl at the barrow) → `the dead
walk` (restless dead on the roads at night within the reach; travellers vanish) → `the emptying` (a hamlet empties;
its people walk to the barrow; refugees on the roads) → `the dead march` (doom: the nearest village is emptied and
held by the dead, the region's danger rises by two, and the king's dead hold the land until someone lays him to rest).

The scheme advances inside the weekly politics step (`Politics.advance`), so it moves with the rest of the world, also
during the interlude between lives (where it advances at most one stage). The player's deeds **hold** it (a chapter
completed sets it back a stage or freezes it for a while) and the villain's setbacks make it *lash out* (§5.4). Signs
always come before a stage's effects (law 7): a stage's first sign is shown at least a week before its effects, and the
journal shows the clock as a row of marks once the player knows the threat. Signs reach the player through
`world/news.add` with words from threats.json, at importance 2 or less (so that they do not fill the Legends history);
the effects that matter (a hamlet emptied) are remembered in the history by the effect itself.

**The world fights back too** (so that the map does not simply rot while the hero is busy elsewhere). Threats also end
without the player: the politics engine already hangs gangs and purges cults; the history's beast-hunting heroes keep
hunting while you play (a small weekly chance by the hero's fame against the beast's); a rival band may win; a scheme
burns out when its source fails (a cult with no presence left falls). **Dooms are bounded and recoverable**: a doomed
village is emptied, not erased – after a season survivors and settlers come back (a `rebuilding` status) – and a doom
raises its threat's tier at most once.

### 5.2 Adventures: from a threat to a tale

An **adventure** is the player's engagement with one threat, built from a **blueprint** (§6) when the player
**accepts** its hook. Until then a hook is only a light offer on the threat (`threat["offer"]`: who offers it, where,
since when), so a declined hook leaves nothing behind. Once accepted, the adventure is generated once, kept in the
save (`world.politics["adventures"]`), and changes as it is played. A hero carries at most three adventures at once
(plus the ambition's); further hooks wait.

**Shape.** A title; a premise; a **hook**; 3–5 **chapters**; a **finale**; an **epilogue**. Each chapter has a goal
(said in the journal in one line), 2–4 **steps**, a rule for when it is done ("all", or "any 2 of 3"), a **set piece**
(the chapter's big moment: a lieutenant, a rescue, a siege night, a confrontation) and a **reveal** (what the player
learns at its end, which opens the next chapter). Tier 1 adventures have 3 chapters and 5–8 required steps; tier 2,
3–4 chapters and 8–12; tiers 3–4, 4–5 chapters and 10–16 (optional steps come on top). A blueprint grows with its
tier: steps and whole chapters may say `tier_min`.

**The content rule** (enforced by `storybook --check`): every chapter has at least one step that is not a fight, and
at least one choice with a lasting consequence (a codeword that a later beat, step, ending or epilogue page reads).

**Steps** are the moves of the story. Each step kind is a small Python handler with data (§8.5):

| Step | The player... | Detected by |
|---|---|---|
| `go` | reaches a place (a town, a site, a field, a crossroads) | `_arrive`, `enter_local`, `descend` |
| `witness` | talks to someone who saw something (named, or any N of a town) | a conversation choice |
| `search` | searches a place: a house, a battlefield, a dungeon level, a body | a placed clue feature, dungeon search, Look |
| `read` | reads a document: a letter, a journal, a chronicle, an order | `books` reading, a placed item |
| `learn` | learns a truth (the villain's name, past, weakness) by any of several routes: a sage, a library, a temple's chronicle, Speak with Dead, divination, a captive questioned | whichever route is taken first |
| `slay` / `capture` | defeats a named foe (lieutenant, beast, rival), or takes them alive | `on_battle` by the foe's story tag |
| `fetch` | takes a thing: the relic, a key, proof | a placed chest or a carried item |
| `rescue` / `escort` / `deliver` | frees a captive / brings someone / carries something | existing quest machinery |
| `recruit` | wins an ally (their condition: a favour, a check, a gift, a promise) | a conversation, or a small inserted step |
| `rally` | gathers support: N of M notables agree, defenders hired, a faction's help | conversations, money |
| `prepare` | gets the means: silver, holy water, fire, a scroll, earthworks, a ward | inventory, crafting, services |
| `hold` | defends a place through a night of waves | a scheduled battle (the `defend` pattern) |
| `infiltrate` | gets inside unseen or disguised (a guarded hall, a masquerade) | the law's disguise and sneaking checks |
| `rite` | does something at a place: lays the dead to rest, cleanses a well, lights a beacon | an item used at the place |
| `choose` | makes a decision that splits the story | a beat with choices |
| `confront` | meets the villain or a lieutenant face to face – to talk, or to fight | a beat, maybe a battle |
| `endure` | survives a set piece: the villain's hunt, a storm, a night in the haunted house | a beat and a battle |
| `finale` | ends it | §5.8 |

Many steps simply make a quest dict through the existing machinery (`quests.py`: rescue, escort, deliver) with
`q["adventure"]` and `q["step"]` set, so the detection the game already has keeps working; the adventure listens for
that quest's end. A **step quest** has the matching template, the patron as its giver (and the patron's town), a long
deadline from the adventure (so `_check_quests` and `quests.daily` stay happy; the story, not `daily`, decides what a
dead giver means), and **no pay of its own**: adventures pay at chapter ends and the finale, mostly in things that are
not money (law: the old marker-fight-pay loop must not come back inside the new one). Step quests show in the
Adventures tab, not under Work. Things placed in dungeons for steps (a captive, a chest, a clue) are placed by the
story on the level the step names, through `story_sites` (§8.4) – not by `quests.on_arrive_dungeon`, which places
only on the deepest level.

**Leads and clues** (the three-clue rule). Every truth the player must learn to go on has **at least three ways** to be
learned (law 2; the DMG: "the party must never miss vital information because of one failed check"). The generator
places the clues: one with a witness, one in a document or a place, one through a skill or magic (a check at the
scene, a sage, divination). A failed check never loses a lead: it costs time, money, a wound or a favour instead
("No, but…").

**Freedom and convergence.** Steps in a chapter can usually be done in any order; chapters branch and come back
together (Citadel's hubs). A chapter may have an optional step that gives a key for the finale but is not needed to
go on. The player may also skip ahead: if they walk into the villain's lair in chapter I, they can fight it there –
and if they win, they win (the DMG: if a major villain appears before the end, the party must be able to beat it),
with the "early end" rules of §5.4.

**Failing forward.** A failed step is a branch, not a wall: the captive dies (the step becomes "avenge" or "bury"),
the relic is taken by the rival (a new step: take it from them), the accusation was wrong (the real culprit is warned;
the scheme advances), the defence fails (the village burns; the next chapter happens among refugees). Each blueprint
lists what a failed step becomes.

**Hidden variables** (Curse of Strahd's reading, the solo books' "settle a fact the first time it matters"). Some
truths are chosen when the adventure is made and kept hidden: where the relic is (one of 2–4 real sites), which of the
candidate allies is the true one, whether there is a traitor and who, what the villain's weakness is, where the
last stand will be. The player learns them by play, or early through **the Reading** (§5.7).

**Codewords.** Choices and discoveries set named flags on the adventure (`flags`: "spared_ost", "knows_true_name",
"burned_the_letters"), which later beats, steps, endings and the epilogue read – alternative keys, as in a gamebook.

### 5.3 The cast

Every adventure binds **roles** to real people. The generator looks in the world first and invents only to fill a gap
(law 9); anyone invented becomes a real NPC or figure of the world.

| Role | What they are for | Where the generator looks first |
|---|---|---|
| **Villain** | the will behind the threat | the threat's figure (§5.1) |
| **Lieutenants** (1–3) | the villain's hands: each guards a chapter, each has a face, a trait and a weakness | the villain's faction's members; figures with grudges against the patron; else made from the villain's kind |
| **Patron** | the one who asks you and pays | the notable with the most at stake: the lord of the threatened place, its priest, a grieving parent |
| **Allies** (1–2) | someone with a stake who joins you | kin of a victim, a hero of the history at an inn (`people.heroes_at_the_inn`), a hunter, the villain's estranged kin, a companion whose past is in it |
| **Rival** (sometimes) | someone else after the same prize | a living hero figure and a band; deserters; another adventuring party made for it |
| **Innocent** | who suffers if you fail | a child, a village, an heir, a captive |
| **Traitor** (sometimes, hidden) | someone in the cast who serves the villain | one of patron/ally/companion, with tells placed as clues |
| **Sage / seer** | who can tell the truth for a price | a temple's priest, a tower's wizard, a road-woman, a hermit at a wonder |

Rules from the books: a patron betrays at most once in a hero's life (the DMG: more and players stop trusting hooks);
trust is established before it is broken (Ravenloft: repeated good encounters first); a traitor always has at least
two tells the attentive player can catch; the villain targets the ally the reading named (Curse of Strahd: the
villain senses the danger and tries to kill them).

### 5.4 The villain who acts

The villain is the reason the story feels alive. Villains are **met early and often** (Ravenloft: "use them liberally
rather than saving them for climactic plots"; Strahd's encounters are tests, not kills), and they **answer** what the
player does.

**Attention** (0–5) is how much the villain cares about you: 0 *unaware*, 1 *has heard of you*, 2 *watching*, 3
*testing*, 4 *wrathful*, 5 *obsessed*. It rises when you hurt the scheme (a step done +1, a lieutenant slain +2, its
servants or beasts killed +1, a Reading that drew its card +1, great magic cast in its reach +1, each Legend tier
+1 at the start) and falls slowly when you leave it alone (−1 a fortnight).

**Moves.** At each beat opportunity the Storyteller may give the villain a move fitting its attention, its temper and
what it can do (a beast does not write letters; it leaves a carcass at your camp):

| Attention | Moves (examples) |
|---|---|
| 1 | a rumour that someone was asking about you; a spy follows (seen by a Perception check, flees if seen); an omen |
| 2 | a **letter** (or a sign: a dead bird on your bedroll); a **gift** with a warning; a **test** (minions attack for a few rounds, then withdraw) |
| 3 | a **visit** (the villain at your camp or in your inn room by night – talking, never at full strength, protected by an illusion, mist, guest-right or a sheer drop; staged on the map, §5.18); an **invitation** (dinner at its hall under safe conduct: no encounters on the way, nothing useful learned, a threat at the end); a **bargain** (step aside for gold, a boon, a secret; or join it); a **wedge** (an offer to a companion: help if another is sacrificed) |
| 4 | a **reprisal** (the people who helped you are hanged, burned out or vanish – told in the news); a **frame** (you are accused of a murder it did, through the law's witnesses); a **kidnap** (an ally, a companion who wandered, the innocent – a rescue step is inserted); a **strike** (a lieutenant's ambush in force) |
| 5 | a **hunt** (the villain comes in person at a place of its choosing, fights, and escapes when hurt); the villain moves the relic; it pays the rival to stop you |

A villain's **temper** weights its moves: *proud* (letters, invitations, duels), *cunning* (spies, frames, wedges,
bargains), *cruel* (reprisals, kidnaps), *grieving* (visits, gifts, pleas), *zealous* (signs, demands, sacrifices),
*bestial* (signs, tests, hunts). Its **first words** reveal its obsession (Ravenloft), and each villain keeps a small
pool of **omens** – six to eight signs that it is watching – shown more often near its lair and as its attention rises.

**A spy that steals** (Curse of Strahd): a spy that is not seen may steal a token (a lock of hair, a glove); the
villain's next move is then tailored to you (a nightmare about your dead, a letter naming your companion).

**Wrath.** A major setback (a lieutenant killed, the relic taken, the innocent saved) makes the villain lash out at
once: attention jumps, a reprisal or a strike follows, and very often an invitation – it wants to see you.

**Escapes and early ends.** Before the finale a villain met in a fight (a test, a hunt) has an **escape** fitting its
kind (mist, a scroll of teleport, a lieutenant's sacrifice, a wounded beast fleeing to its den) when its hit points
fall low – once per adventure. If the player *prevents* the escape (grappled, restrained, killed in one blow, a key
that forbids it), the villain dies. Then the **early end** rules (Ravenloft's "unexpected ends") apply: no finale, but
a short last chapter – its contingencies fire (a letter delivered on its death, standing orders to its servants, a
caged thing let loose), a lieutenant takes its place as a weaker villain, or "the cat is away" (the places it held
open up). The player is never robbed of a fairly won kill.

**Anchors and returning villains** (Ravenloft's darklords revive unless their anchor is dealt with). Undead, fiends
and the dread lords have an **anchor** – a phylactery, a heart in a temple, a crown, a true name, bones in unhallowed
ground. Killed without the anchor dealt with, they return after some weeks (a sequel threat with a grudge). This makes
the anchor the natural chapter goal and the finale's true condition.

### 5.5 Lieutenants who remember (the nemesis rule)

Lieutenants are named, have a look, a trait (cruel, vain, devout, cowardly, loyal...), a weakness and a grudge track.
They are met before the villain and **remember**: one who escapes comes back with a scar and a grudge, better armed;
one who is spared may turn (a redemption: a new ally, or a betrayal later); one who is killed makes the villain grieve
or rage (wrath). A lieutenant who survives the adventure may become the villain of a sequel. Their fates are named in
the epilogue.

### 5.6 Allies, rivals and traitors

**Allies are stories, not mercenaries.** An adventure ally has a *stake* (a lost son, a burned home, a vow), a **join
condition** that is a small quest of its own (Curse of Strahd: bury a parent, cure a madness, reconcile with a son,
be persuaded), and an **arc** of three beats: a confidence (their secret or their past), a crisis (they want revenge
now and may break off; they are captured; they doubt you), and a fate (they die well at the finale, swear to you as a
permanent companion, or go home to rebuild). They join as companions without wages, under a new bond `oath` in
companions.json (not `sworn`, which already means a realm's lent sword and is recalled by `followers.recall_check`),
and react to your deeds with their own values. If the party is full, the ally rides with the patron and fights beside
you in the set pieces and the finale (`Battle.add_ally`) without taking a place in the party. While cast in a story,
a person carries `flags["story"]`, which `people.refresh_travellers` and `quests.daily` respect (today an inn's
adventurer "moves on" after 30 days). Ordinary hired swords stay exactly as they are; they are simply no longer the
best help you can find.

**Rivals** want the same prize: a hero of the history with a band, a band of deserters, a noble's son with paid
swords. They have their own clock: if you are slow, they get there first (the relic is theirs; take it, buy it or let
it go); they may ambush you, propose a truce, beg your help when they are in over their heads, sell you out to the
villain, or be found dead in the lair – the most chilling sign of all. A rival's relationship with you (−2 to +2)
decides how they show up, and they are named in the epilogue.

**Traitors** are one of the cast (never the ally the Reading named), with a hidden reason (the villain holds their
kin; they are paid; they believe in it), at least two tells, and a moment (the finale, the vacant throne, the night
before). Catch them early and the betrayal becomes a confrontation; miss them and it becomes a twist.

### 5.7 The Reading (the Wayfarer's Deck)

A seer can read for you – a road-woman at a crossroads camp, a blind priest, a hermit at a wonder – for a coin or a
favour. The Reading is the diegetic way to learn an adventure's hidden variables early, and the most atmospheric
moment of the opening chapter.

The game has its **own** deck, the *Wayfarer's Deck* (original names, original meanings; not the tarokka): twenty
great cards (the Lantern, the Hound, the Widow, the Ford, the Crown, the Bell, the Mask, the Key, the Ash Tree, the
Bride, the Smith, the Pilgrim, the Sleeper, the Broken Shield, the Crow, the Mother, the Grave, the Wheel, the
Candle, the Wolf) and four suits of minor cards (Blades, Coins, Cups, Stones) for colour. A reading lays five places,
each answering one hidden variable:

1. **The key** – where the anchor or relic lies.
2. **The hand** – who will stand with you (the true ally).
3. **The shadow** – what the villain fears (its weakness).
4. **The door** – where the last stand will be.
5. **The turn** – what is coming next (the scheme's next sign, or a warning of the traitor).

**The truth comes first, the card second**: the generator already knows the answer, picks a card whose tags fit it
(the Ford for a river crossing or a battle at a ford; the Widow for an ally who lost someone), and writes a riddle from
the real place's own descriptors – its past from the ages, its look, its name ("where the river forgets its name";
"where the king's rider fell in the year of the long winter"). A card may come up *silent* (the seer cannot see it;
come back after the next chapter). And sometimes the villain's own card turns up: the villain learns of the reading,
speaks a sentence through the seer's mouth, and its attention rises (Ravenloft's opposed card).

Later the cards' imagery is planted in the world and pointed out when met ("a smith's sign over the door – the Smith,
as the road-woman said"), Ravenloft's "manipulating fate".

### 5.8 The finale: a fair, epic fight

The finale is the reward the whole adventure promised. Its shape is **knowledge → preparation → confrontation**
(a monster hunt in the old style): the player learns what the boss is, gathers what beats it, and chooses when to go.

**The arena.** The finale happens at the place the story named – usually the deepest level of the villain's lair, set
before the player ever enters (§8.4: bosses are bound to sites ahead of `populate`), or a set-piece field laid by
`game/arena.build` (a ford at night, a burning village with fire that spreads (§8.14), a ritual circle on a hill, a
throne hall, a bridge, a tower top). The arena has features that matter: braziers to light, a circle to break, pillars
for cover, sarcophagi that open on the second phase.

**The boss.** Until later expansions bring the Monster Manual's legendary families, a boss is made from a creature
the game already has with a **boss template** (`villains.json`): more hit points by tier, 1–3 Legendary Resistances,
2–3 legendary actions from a menu by role (move, strike, command its minions, a cantrip), a signature move, and a
**second phase** at half its hit points (a new form, a summoning, the arena changing, a line spoken). The kernel's
legendary actions and resistances (proven on test creatures in Expansion 1) are used here for real for the first
time. Its lieutenants and minions fight beside it.

**Keys.** Everything found on the way can be a key, and every key has a concrete effect in the fight, applied when
the battle starts (`story.finale.prepare`, the pattern of `warding.at_the_start`):

| Key (examples) | Effect in the finale |
|---|---|
| the anchor held (the crown, the heart, the true name spoken) | no Legendary Resistance; or the second phase never comes; or it cannot escape or return |
| its weakness learned (silver, fire, a holy word) | the matching weapons or spells deal more; the party knows to bring them |
| the ally recruited | the ally fights beside you; their special help (the wights ignore the wounded) |
| the rival befriended | the rival band arrives on round 3 |
| the militia raised / the defenders rallied | the minions are fewer; a second front is held |
| the beacon lit / the ground hallowed | the party is blessed for the fight |
| the secret way found | the party starts with surprise, or the boss without its guards |
| the lieutenant slain | that lieutenant is not in the fight |

**Fairness rules** (law 5):
1. The boss's strength comes from its threat's tier and region, not from the hero's level (DESIGN.md §6). Each tier
   has a **target level** (data; at first tier 1: 3, tier 2: 7, tier 3: 13, tier 4: 18), and the forge sets the
   finale so that for a party of that level, with **no keys**, it is above the DMG's "high" budget – very dangerous,
   maybe best avoided – and with **every key** it is a hard "high" fight a careful party wins. A hero below the target
   is told so. These two numbers are measured (§9). (A named beast or lord of the history may have grown with its
   legend, as `encounter.legend_grows` does today; that growth stops at the tier's bound.)
2. The finale is never a surprise: there is always a warning ("the door beyond is the last") and a chance to rest
   before it.
3. The party can always retreat, unless the place was said to seal (and then the clue said so). A retreat costs
   (the villain heals, the scheme advances a stage, an ally may be lost), but the tale goes on.
4. The boss telegraphs: its great attacks are announced a turn before ("draws in a breath", "the circle begins to
   glow"); the second phase is announced by a line.
5. A boss intro card is shown first: name and epithet, its first words, and **what you know** – each key found ticked,
   each unknown left as a question mark. The player sees how prepared they are.
6. Losing the finale need not be death. A cruel or proud villain takes the fallen alive (Fair Chances; the solo
   books' "defeat as content"): you wake in its cells, and the adventure gains an escape chapter.

### 5.9 Endings: what the world keeps

Every blueprint has 3–6 **endings**, chosen by what happened: *destroyed* (slain, anchor dealt with), *laid to rest*
(the rite done), *redeemed* (persuaded, with what it covets – Ravenloft's memory shrines), *bargained* (you took its
offer: a dark ending), *fled* (it escaped the finale: a sequel threat), *doom* (the scheme won), *abandoned* (you gave
up; the threat goes on), *fallen* (the hero died; the threat goes on and remembers).

Each ending is a list of **consequence operations** (the second whitelist of §8.6, checked at start-up) applied
through the systems that already move the world – never beside them: story foes are skipped by `past.on_battle`, and
the endings call the same helpers it uses (`past.beast_slain`, `figure_slain`; `politics["laid"]` for a barrow,
`scar["laid"]` for a battlefield's restless dead), so nothing is counted twice. The operations: a site cleared; a
figure killed and remembered (`history.remember`); a faction falls (`Politics.fall`); a settlement changes hands
(`Politics.set_owner`, written in the ownership ledger); a ruler crowned (the succession code); relations shift; a
status added or lifted (`siege`, `plague`, `tribute`, `beast`, a new `emptied`, `rebuilding`, `cursed` or `blessed`);
a population falls (never below a floor of survivors) or returns; a ruin rebuilt, or (from Part G) a settlement ruined
in full; the region's danger changes; a **monument** stands in a square (a statue, a shrine, a gibbet with the
villain's cage); a place is renamed ("Varn's Rest"); a law changes; a **song** is composed by a real bard figure and
sung in inns after some weeks; a relic goes to a temple or to you; you are given a title, land, a right (free board
for life, a letter of recommendation that opens doors where its writer holds sway – the DMG's marks of prestige).

**The epilogue** – *What became of them* – is a screen of 4–8 short pages, one for each thing the story touched:
the place, the patron, the allies, the rival, each lieutenant, the innocent, the realm, and (last) you, with your
new standing and Legend. It is written from the ending, the codewords and the cast's fates. It is the moment the
player sees that it mattered, and it goes into the Legends book as a named chapter of the world's history (*The
Return of Aldric the Red, 1043*).

### 5.10 Events: beats, the Storyteller, echoes and happenings

**Beats** are the small units of story (storylets, as in Fallen London and Wildermyth): a scene with a place, a text,
2–4 choices (some with skill checks or costs), and outcomes from a whitelist; a beat may schedule a follow-up beat
days later, so beats chain. Beats are data (`beats.json`, many fragments), each with **conditions** on the game's
state (where, which adventure and chapter, the villain's attention, tension, Legend, a companion's values, a codeword,
the season, a remembered deed...). The event screen grows into a **beat screen**: several pages, branching choices,
pictures (the villain's figure, the place), and a title card for chapter openings.

**The Storyteller** (the director) decides *when*. It keeps:
- **tension** (0–100): up after hard fights, villain moves and signs; down after rest in a safe town, relief beats and
  victories; slowly back toward a resting level;
- **the quiet clock**: hours of travel or town time since the last story moment (a beat, a step progressing, a reveal);
- **the rhythm**: rising tension → a crisis → relief (Ravenloft's roller coaster; the DMG's "vary the type").

At each opportunity – a stretch of travel (where `events.roll_event` is asked today), arriving in a town, making camp
for the night, entering a dungeon level, after a battle – it asks: is a beat due (a scheduled follow-up, a villain move
earned by attention, a chapter opening)? has it been quiet too long? It then picks among the eligible beats by weight
× specificity (the beat whose conditions say most about this moment wins) × fit to the tension (high tension wants
relief; low tension wants a sign or a hook) × novelty (not the same family twice running). Random travel events and
encounters keep happening, but less often when a story beat is due, and the encounter tables near an active threat
lean toward its servants (the dead on the roads of the risen king's reach).

A setting **Storyteller** (Steady, Restless, Gentle, Off) sets the target gaps: on the road a story moment every 12–20
travel hours (Steady), 6–12 (Restless), 24–36 (Gentle), or only scripted beats (Off). (The pacing measure of §9
accepts a median a little outside the target, 8–24 hours for Steady.)

**Echoes** (law 3). `reputation.deed` gains tags and a subject (the person you spared, freed, robbed, cheated, saved,
killed, the village you defended), and so do the two places where the commonest moral choices are made today without
passing through `deed`: `fight.decide_captive` (spared, robbed, questioned, executed, taken for bounty) and
`law.commit` (the crimes). They are kept as **echo seeds**. Weeks later an echo beat may bring them back: the spared
bandit warns you of an ambush, the freed captive's family sends a gift and a son who wants to ride with you, the
widow of the man you killed curses you in the market, the cheated merchant has hired knives, the village you saved
sends its young to join you, the lord whose son you shamed challenges you to a duel. Echoes need the person to be
alive and the deed to be known where you are.

**Happenings** are the world's own events with a place and a time, made from what politics already does: a
**coronation** (after a succession) with a **tournament** (bouts on the battle mat against knights for a purse and
fame), a **royal wedding** (after a marriage), a **funeral** (after a ruler's death), a **muster** (at a war's start:
the realm calls for swords), a **siege** (a besieged town: get in, get out, defend), **refugees** on the roads (after
a sack), a **quarantine** (plague), seasonal **fairs** and holy days (the existing processions). If you are there, the
town shows it (the *festival* mark's banners and lanterns, the stage's crowds, barks, special services) and its beats
happen to you (an assassin at the coronation; a knight who insults you at the tourney; a refugee who carries a
letter). Happenings are announced on notice boards and in the news, so they can be travelled to.

### 5.11 Legend: narrative progression

**Legend** is how far your story has travelled. It rests on fame (the game's existing `renown.fame`, which
adventures raise by tier: 5 / 12 / 25 / 50 for winning a tier 1 / 2 / 3 / 4 adventure) and on what you have finished:

| Tier | Needs | What changes |
|---|---|---|
| 0 **Stranger** | – | people judge you by your clothes, your people and your wounds, as today |
| 1 **Known in a town** | fame 5 | the towns you helped greet you by name; a free meal and bed there; petitioners begin to come to you |
| 2 **Named in the region** | fame 15 and a tier-1 adventure won | you choose an **epithet** from 2–3 earned by your deeds ("Barrowbreaker", "the Wolf of Kessa", "the Merciful"); lords receive you; rivals notice you; your foes have heard of you (a morale check before a fight with lesser bands) |
| 3 **Hero of the realm** | fame 35 and a tier-2 adventure won | the ruler sends for you; a **title** (a knighthood, a wardenship); bards sing of you; challengers seek duels; assassins come if you are infamous |
| 4 **Famed across the land** | fame 70 and a tier-3 adventure won | other realms court you; **land** (a small holding: a house, an income, people – Bastions & Banners later builds on it); the greatest threats take note of you at once |
| 5 **Legend** | fame 120 and a tier-4 adventure won | a statue; first among the great in the Legends book; you are remembered for generations of play |

Each tier-up is a moment: a beat (the herald, the song, the lord's summons), a fanfare, and a line in the Legends book.
**Titles** are the game's existing ones (`reputation.grant_title` / `title_problem`, law.json titles,
`renown.flags["titles"]`), now also granted by Legend and by adventures' endings; **challengers** use the existing
duels (`game/shadows.py`). So that "Legend" means one thing, the map key screen (`ui/screens/legend.py`, today titled
as a map legend) is renamed *Map key*; the Legends book keeps its name, and your Legend is your place in it.
**Infamy** has its own mirror track (a feared name: "the Butcher of Ashford"): guards grow hostile, petitioners turn
to fear, dark patrons court you, and the villains offer you bargains as an equal.

What you are offered depends on your Legend (laws 8 and 10): a ruler gives realm-tier adventures only to a hero of the
realm; a stranger gets the steward and the small jobs. This fixes "walk straight to the king": the king does not
receive strangers, and the work that matters to a village comes from the village.

### 5.12 Ambitions and the first hour

**Ambition.** A new step in character creation, after the background: *What drives you?* – or *I do not know yet*
(and the road will show you). Each ambition is a personal saga of three adventures of rising tier, rooted in the
background's ties to the world's history (`world/ages/ties.py` already gives a noble a real house, a soldier a real
lord, a criminal a contact): **Vengeance** (the one who killed your kin, now a captain, later a baron), **Homecoming**
(your house's lost seat, a ruin of the history), **Redemption** (the wrong of your past, and the people it hurt),
**Glory** (to be sung of: reach Legend 4), **the Oath** (a vow to a fallen lord: destroy what killed them), **the
Seeker** (your family's lost relic), **the Cure** (a curse in your blood, or a sick sibling), **the Crown** (a claim
through your family tree), **the Lost** (a parent or sibling taken by a tribe, a cult, a dread lord), **Fortune** (land
and a title of your own), **the Calling of the faith** (a god's charge), **Forbidden Knowledge** (a dead archmage's
secret). When the third adventure ends, you may **end your tale**: an epilogue of your life, and your hero stays in the
world as a living figure – a lord in their hall, an old champion at the inn, a hermit at a shrine – for later
characters to meet.

The hero is not a figure of the history and has no family tree, so an ambition **makes what it needs at creation and
writes it into the history** (`history.remember`, `factions.make_figure`): Vengeance makes the slayer (a living figure
placed as a gang's captain or a lord's man, with the remembered killing of your kin, kept in `renown.flags["kin"]`);
Homecoming picks a ruin whose past names a fallen house and makes you of its blood; the Crown makes your line a cadet
branch of a real house; the Lost places the taken one as a captive of a real tribe, cult or tower; the Seeker picks an
unfound artifact of the history and makes it your family's. **Ending a tale** is a flow beside death:
`death.retire(game)` *(new)* writes the life into `politics["retired"]` (as `fallen` does for the dead), makes the hero
a figure and an NPC in the chosen settlement (`people.become_figure`), releases the companions, and shows the life's
epilogue before the title screen.

**The first hour.** A new life never starts on a quiet road. The Storyteller chooses an **opening** from the
background, the ambition and the start town (the DMG's and Ravenloft's openings): arriving into a crisis (the gate
shut because of the beast; the funeral of a figure who died this morning), a summons (a letter with a seal), present
terror (you wake as a captive of the gang and must escape), a shared mystery (a dying stranger presses a ring into your
hand), a happening (the coronation tournament). The opening is a short tier-1 adventure (2–3 chapters, a small boss
with one key), built to end around level 2–3, and its epilogue hands you the thread of your ambition. The rule: a
story hook within the first conversation in town, or the first game day.

### 5.13 Death, legacy and the next hero

Death keeps its weight: everything the character carried is gone. But the story is world-side, so:
- an adventure in progress becomes **orphaned**: the threat goes on, its villain remembers ("the last one who came
  hangs in my hall"), and its scheme keeps moving through the interlude;
- the obituary tells the tale as far as it went;
- a new character in that world may choose the ambition **Take up the fallen's task** (at creation, if an orphaned
  adventure exists): they start near it, as kin, squire or friend of the dead hero, and the villain's attention starts
  at 2 ("another one comes");
- a retired hero is a figure of the world (§5.12), and may become a patron, an ally, or – if their tale ended darkly –
  a villain.

### 5.14 What changes in what the game already has

- **The job board goes** (§5.15, from Part C): no weekly offers; the templates' builders and listeners become the
  machinery of situations, contracts and steps. Until then (Parts A–B), a bounty on a threat's beast or gang is that
  threat's hook, and a hunt-beast, bounty, clear-lair or investigate job whose target belongs to a threat opens the
  threat's hook when it is done ("there is more to this").
- **Deeds stick** (fixes the survey found): a cleared gang hideout's boss is the gang's real, named leader; killing
  them goes through `Politics.die(fig, cause, led=gang)`, which already runs the succession (a gang may end, or elect
  a new leader – never an active gang "led by the dead"), and clearing the hideout as well makes the gang fall
  (`Politics.fall`, news); a cult's temple boss is its Voice, and clearing it ends the cult; hunt-beast work and beast
  bounties prefer the world's real beasts (`lairs`) over the fixed list; `news.prune` and plague exposure run every
  day, not only after the first quest; `uniques.daily` runs whether or not you have companions; `dragons.mark_slain`
  writes its history event through `history.remember`.
- **The king and the pay.** Pay already follows the work (the template's range, the distance, the party's level);
  lords are simply the givers of the richest templates and of the strongroom gifts. Now rulers and great lords receive
  you, give their own commissions, their strongroom gifts and realm-tier adventures only from Legend 2–3; before that
  a **steward** (a new people.json job in their hall) hears petitions and gives the hall's contracts. Adventures and
  situations pay in chapters, favours and things money cannot buy; contracts and bounties pay as jobs did.
- **Notice boards** show **every stirring threat within a week's walk** as a hook ("The temple at Coldwell pays for
  word of the barrow"), so that a hero who finishes a tale always has the next in sight (law 2); also the happenings,
  the bounties, and the town's contracts with their terms.
- **Rumours lead somewhere.** The dialogue outcome `reveal_hook` (today it tells a piece of news) opens the nearest
  threat's hook when there is one, and `reveal_clue` is added; a found letter can start an adventure.
- **Travel events** stay, and gain beats beside them; the Storyteller lowers their chance when a story beat is due.
- **Mercenaries** stay as they are, and comment on the story through their values (`companions.react` gains story
  tags: `villain_met`, `lieutenant_slain`, `bargain_taken`, `innocent_saved`, `ally_died`...).
- **The journal** gains an **Adventures** tab, first: each adventure's title, its chapters (done, current, to come),
  the current goals and where they are, the cast you know (pictures; the villain a shadow until met), the clues and
  keys found, the Reading if done, the scheme's clock, the codewords that matter.
  Beneath them, **Troubles**: the situations met, in the hero's own notes; the People tab gains favours and contacts.
- **The map** marks adventure places with their own marks (a chapter's places, the villain's reach shaded once known),
  and shows the world's state: smoke over burned towns, sieges, hosts on the roads, changed land (§5.21).

### 5.15 Quests reborn: the end of the job board

Anton, 2026-10-24: "the old quests were, essentially, both random and meaningless... I would like quests to be
rarer, but for them to lead into a great adventure, tell a story, and each and every quest being meaningful." Today
a town of eighty people holds eight to twelve open job offers at once, and a city fifteen or more: almost every
notable has one about three weeks in four (`quests.offer_for`: a roll every 7 days, 0.6 for notables and 0.3 for the
rest, kept for 14), and "Is there any work?" finds them. Quests are a menu, so none of them weighs anything. From
this expansion on:

1. **No more weekly offers.** Nobody rolls a job each week any more: `quests.offer_for` stops making offers from the
   seventeen templates, the "Is there any work?" choice goes, and so does `GameScreen._think_of_work` (which also
   quietly built far towns every day). The templates do not vanish: their builders and listeners (rescue, escort,
   deliver, retrieve, defend, cure, investigate...) become the machinery that situations and adventures use for their
   steps.
2. **A quest is now one of three things**, and nothing else:
   - a **situation** (§5.16): something has gone wrong in the life of someone real – a son run off to the gang, a
     wedding forced, a debt come due, a body in the reeds – and the player has seen it or heard of it;
   - a **chapter of an adventure** (§5.2), itself made of situations and set pieces;
   - a **commission** from a faction the player has joined, drawn from that faction's real goals (today's rank
     trials, rarer and specific).
3. **Paid work stays – honest, small and few.** Bounties on the board (on real gangs and real beasts; a bounty on a
   threat's outlaw lord is that adventure's door), **contracts** (guarding a merchant's caravan on a real road, a
   mercenary company's muster when war comes, a lord's levy), labour, performing, trade, loot and ransom, as today.
   Paid work is labelled as such, shows its terms and has no ceremony; a town has one contract at a time (two in a
   city), renewed every few weeks, each on a real road with a real danger on it. It is where trouble finds you (the
   caravan meets the threat's servants on the road), not a story of its own.
4. **How many.** A town shows at most one live situation at a time (two in a great city), and a new one at most every
   ten to twenty days, chosen by the Storyteller for what matters near the hero: threats, the ambition, factions,
   echoes; and no more than three are live within reach of the hero (30 tiles). At any moment a town typically has
   one situation, a threat's hook on its board and a contract (two in a city).
5. **Every quest matters** – six rules, checked by `storybook --check`: (1) it is about a person with a name and a
   stake; (2) it leaves a consequence the player can see later (someone alive, gone, married, ruined; a shop open
   again; a new grave); (3) it has a real decision (two ways through that end differently); (4) it has a way through
   without a fight; (5) it connects outward – to a threat or adventure, a faction, the history, the ambition, or a
   lasting tie (a contact, a favour owed, an enemy made); (6) it pays money only when someone really would, and money
   is seldom the best of the reward.
6. **Rewards that are not money.** A **favour** owed, called in later as a way through someone else's obstacle (the
   smith speaks for you before the reeve; the abbess gives you sanctuary; the fence opens his back door); a
   **contact**, who sends word, warns you and deals with you at night; a key for a finale; a bed in a house that is
   grateful; a secret; a companion; standing; a little fame.
7. **Experience from stories.** Situations, chapters and finales give experience for how they end (the DMG's milestone
   advice, and more for a way through without blood), so that following stories levels a hero faster than hunting
   things; fights still give theirs. A setting, *Experience*: from fights and stories (the default), or from stories
   only.
8. **Coin stays fair.** A careful player's income over thirty days of play must stay within a band of today's
   (measured by `storyplay`, §9), so that rare quests do not starve the hero.

**How the layers lead into each other** (law 10): you **see** something (a scene: §5.18) → it is someone's
**situation** → it turns out to be part of something larger (a **threat**) → an **adventure** → whose ending
**changes the world** → which makes new situations (refugees, grief, rebuilding, a seat left empty, a debt of honour).

### 5.16 Situations: stories about people, not quest types

A situation is not a type. It is a small story assembled from the world: **who** (real people with their ties and
traits), **why** (a cause in the world), **what is at stake and by when**, **what stands in the way**, **the ways
through**, **a turn it may take**, **how the player meets it**, and **what each ending leaves behind**. The game never
asks "is this a rescue quest?"; it asks "what must be true for this to be over – and for whom is that good, and for
whom bitter?".

**Where they come from** (their *root*):
- the **lives of townsfolk** (below): a debt comes due, a son runs off, a marriage is forced, a sickness, a death, a
  theft, an accusation, an old crime surfacing, a love found out, a rival's scheme;
- a **threat's signs** (a kinsman gone near the barrow; the herd taken by the beast) – the commonest door into an
  adventure;
- **politics** (the war takes a son for the levy; a siege's hunger; the plague's quarantine; a claimant's servant on
  the run; a new gang taxing the market);
- a **happening** (the wedding in danger; the tourney's champion poisoned);
- an **echo** of the hero's own deeds;
- a **faction's goal**, made real at last (factions carry goals today that nothing reads);
- **the history** (a grudge's next killing is due; an artifact's last heir; the restless dead of a scar; the last
  survivor of a town that fell);
- **the land** (a flood, a fire, a mine fallen in);
- a **companion's past**.

**The parts** (data; catalogue in §6.7–6.11):
- a **predicament** – the shape of the trouble; about forty, from "someone has gone where they should not" to "a love
  that must not be", in the spirit of Polti's thirty-six dramatic situations (1895, a public-domain list);
- **roles** bound to real people: the one in trouble, the one who asks (often not the same), the one in the way, the
  one who holds what is needed, the witness, the hidden hand;
- **stakes and a clock** in the world's own terms ("they hang him at dawn on Saturnsday");
- **goals** as states of the world, with two or three endings that are not simply win or lose ("Ivo home and alive";
  "Ivo alive, but staying with the gang"; "Ivo dead");
- one to three **obstacles** (about thirty kinds: a door, a guard, a lie, a law, a price, a distance against a
  deadline, a danger on the way, a rival, a custom, a tongue, a rank too high to reach, a missing name, a mob, a
  ward...), each with its **ways through** (talk, pay, sneak, steal, force, fight, magic, the law, a favour, a
  companion's skill, a forged paper, waiting, walking away);
- at most one **turn** (about twenty-five: the one who asks is lying; the victim is the culprit; the lost one does not
  want to be found; the letter damns its sender; the culprit is someone you once helped; two troubles are one);
- a **meeting** – how the player comes upon it, always shown (§5.17): an argument overheard in the street, a plea at
  your table, a runner with a note, a body in the river, a man in the stocks, a funeral passing, a notice nailed to a
  door, a companion who knows a face, a bell at midnight;
- **endings** that write themselves into people and places.

**Ways through are recognised, not scripted.** A situation's goals are conditions on the world ("Ivo is in his
mother's house, alive"), checked whenever something happens (after a conversation, a fight, an arrival, a day). However
the player makes them true – talking the gang's captain round, buying Ivo out, sneaking him away at night, charming
the captain with a spell, having the lord hang the gang, or killing them all – the situation knows, and its ending
reflects how (a codeword for each way). The ways the game offers on screen are only the ones it can foresee; the
player's own count too.

**Lives.** For this, townsfolk get lives. Notables, and some others, in the towns near the hero carry a small record:
their **ties** (spouse, children, parents, a lover, a rival, a creditor, a patron, an enemy – kin are names first and
become people when a story needs them), a **want**, a **fear**, **secrets** (a debt, a lover, a crime, a forbidden
faith – the cults' secret members already exist –, a false name), and **things of note** (an heirloom, a deed, a horse).
Each week a few **life events** happen by their state and the world's (the war, the plague, the feud, a threat's
signs). Most play out by themselves, and show: the widow in black at the well, the shop shut with a sign on the door,
the empty house, a new grave, a christening at the temple. A few become situations for the hero. The words townsfolk
carry today (`npc.profile` want and secret) are written from these records.

**Hand-made vignettes.** Beside the assembled situations the game carries **vignettes**: small stories written by
hand, with their own scenes and words, each needing particular things in the world (a lake over a village drowned in
the history; a temple bell; a faith's saint's day; a ruin's last survivor), so that they turn up seldom and feel made:
the drowned bell that rings at night; the miller's daughter betrothed to a ghost; the bridge-keeper's toll of riddles.
Forty come with this expansion; every later one adds more.

**Variety, measured.** In one world no two situations the hero meets share root, predicament, turn and meeting all at
once; among thirty situations met there are at least twenty different predicaments (twelve while only Part C's
first twenty exist) and twelve different meetings;
every one passes the six rules of §5.15; `storybook` prints situations as it prints adventures, with a score of how
alike a world's situations are, which a test keeps under a bound.

**Situations inside adventures.** An adventure's steps can be situations bound to it: the Risen's witness is not "talk
to the miller's wife" but *the miller's wife will not speak, because her husband takes the waker's silver* – a
predicament, an obstacle, a way through. That is where an adventure gets its variety from.

### 5.17 Show, don't tell

Anton's rule for this expansion (2026-10-24): stories must be **seen**, not read about. A story moment is first of all
something that happens in front of the player – people moving, things in the world, the place itself changed – and
only then words. The rules every blueprint, situation and beat follows:

1. **A clue is a thing.** Not "you learn that the waker went east" but tracks in the mud by the mill (a decal you can
   follow square by square), a torn scrap of cloak on a thornbush, a letter pressed into your hand, a light in a window
   at midnight, two men arguing in the street whose words you hear as you pass.
2. **People act.** They run up to you, flee, hide, kneel at a grave, carry a body, ring a bell, gather at a notice,
   bar their doors at dusk, spit at your feet. Townsfolk already live their days on the map; stories borrow them.
3. **Places show what happened.** A burned house stands burned. The dead lie where they fell until someone buries
   them – and then there are new graves in the graveyard. Blood stays on the cobbles for days. A hanged helper sways
   on the gibbet in the square when you come back. A saved village has its mill turning and its children playing.
4. **The world map shows the world's state.** Smoke rises over a burned town; tents ring a besieged one; a red wound
   glows across the land where a god struck it; hosts march along the roads; a cursed region lies under grey mist.
5. **Big moments are staged.** A chapter opens on a title card over a picture of its place; a villain's visit happens
   at your camp with the fire dimming and a figure stepping out of the dark; a boss enters with its name across the
   battle mat, a sound and a shake; a great event shakes the screen wherever you are.
6. **Words come last and say less.** Journal lines are the hero's own notes ("The tracks were small. Bare feet."),
   not objectives ("Investigate the mill"). Beats describe what is seen, heard and smelled; they never explain what
   the player has just watched.
7. **Everything still works with Animations off** (CLAUDE.md): staged scenes jump to their end state, effects stand
   still, and every change of place and map is still drawn.

### 5.18 The stage: scenes played on the map

A **scene** is a small piece of choreography played on a close-up map (a town, a camp, a dungeon level), in the town's
own time. Today nobody in the game ever walks up to the player – townsfolk only live their days, bands only hunt – so
the stage is new. A scene gives cues to actors – real townsfolk taken from their day for a while, or people who arrive
for it (a messenger at the gate, a horseman on the road, a child from an alley) – and for the place itself. Scenes are
data (`scenes.json`), and beats, situations, adventures and happenings ask for them.

**Cues** (a whitelist, like the beat ops): `pick` (cast a role from the townsfolk: nearest of a trade, a named NPC, any
child), `arrive` (someone enters at a gate or the map's edge), `walk` / `run` to a place or to you, `follow` someone,
`flee`, `say` (words over the head; story words are shown whatever the Text detail setting, unlike street barks),
`shout` (louder: heard further, and on the log), `give` (an item
changes hands, with the item drawn between the two figures for a moment), `take`, `kneel` / `fall` / `die` (the figure
lies down – §5.19, the fallen), `crowd` (N townsfolk gather round a point and murmur), `disperse`, `door` (open, close,
slam, bar), `bell` (a sound heard across the map), `light` (lamps go out; a fire flares), `fire` (start a fire at a
cell), `focus` (the camera eases to a point and back), `wait`, `hold` (the player's keys wait until this cue is done;
Space or Escape skips to the end), `talk` (open the conversation, with the portrait), `beat` (open a beat), `fight`
(start a battle with a band). A scene ends by returning its actors to their days.

Examples:
- *The runner*: `pick` a stable boy near the inn → `run` to you → `say` "Sir! Sir, wait!" → `give` a sealed letter →
  `say` "From the miller's wife. She said only you." → `run` away. Reading the letter shows it as a handwritten page
  (§8.12) and adds the clue.
- *The crowd at the gibbet*: `crowd` at the square's gibbet → `focus` on it → the body of Brann's cousin on the rope
  (the villain's reprisal) → `say` lines from the crowd → `disperse`.
- *The villain's visit*: at camp at night, `light` the fire low → `arrive` a figure at the edge of the firelight →
  `walk` to three squares from you → `talk` (the villain's words, a choice) → the figure is gone when the fire flares.
- *The alarm*: `bell` → townsfolk `run` to their homes and bar their `door`s → the street empties → the dead come
  over the wall.

**Eavesdropping, tailing and tracking** are scenes too, and the best "show, don't tell" there is: two NPCs talk where
you can hear (their words over their heads as you come near, the rest lost if you are too far); a suspect leaves the
inn at midnight and you can follow him through the streets (Stealth against his looking back, the law's sneaking
rules), to the door where he meets the waker; tracks on the ground lead off the map's edge and on into the next square
of the land.

### 5.19 Places that change

Every place a story touches changes, on its close-up map and on the world map, and keeps the change until time
mends it. A **mark** is a data-driven change of a place (`marks.json`, §6.12): what it does to the ground and the
buildings, what it scatters, what it lights, what the air does, what sounds and music play, how the people behave,
and how it ages into the next mark. The first marks:

| Mark | On the close-up map | Ages into |
|---|---|---|
| **burning** | fire on streets and buildings, spreading from cell to cell; flames and black smoke over burning roofs; embers drifting; an orange glow even by day; townsfolk fleeing or fighting the fire; the roar of fire | burned, in a day or two |
| **burned** | ash and scorched ground; charred building shells, some roofless with their rooms open to the sky; rubble and fallen beams in the streets; the fallen where they fell, then new graves; crows; few people, in mourning dress | rebuilding, after a season |
| **rebuilding** | scaffolds and new timber, carts of stone, the sound of hammers; some houses still black | rebuilt (the place as it was, with new wood, perhaps a memorial) |
| **sacked** | broken doors, goods scattered, blood on the cobbles, the fallen, the raiders' marks on walls | burned or mended |
| **besieged** | barricades in the streets, the gates shut, soldiers on the walls, the hungry at the temple; outside, the besiegers' tents and banners in a ring (a town ringed by a horde or by the dead, with no war behind it, is *beset*: the same look) | sacked, or mended |
| **plague** | doors marked with red, carts of the dead, pyres smoking outside the walls, masked healers, empty streets | mended, with many new graves |
| **famine** | empty stalls, beggars, a bread queue at the granary | mended |
| **haunted** | mist at night, cold lights, a door that will not stay shut, dogs that will not pass | laid (when the dead rest) |
| **cursed / blighted** | dead trees, grey grass, still air, birds silent, a wrongness in the light | cleansed |
| **occupied** | the conqueror's banners, their patrols, a gallows | freed |
| **festival** (coronation, wedding, fair) | banners and garlands, stalls, crowds, music, lanterns at night | – |
| **memorial** | a statue, a shrine, a cairn or a gibbet with the villain's cage, left by an ending | – (lasting) |

**The settlement statuses that exist today become marks**: politics already burns, sacks, besieges, starves and
plagues towns (`Settlement.status`: burned, sacked, siege, plague, famine, raided, tribute, beast), but today only
words say so – no status touches a close-up map, a townsperson's day or the world map. From this expansion on, a town
burned by a war **looks** burned when you arrive. That alone makes the whole politics engine visible. Marks are kept
as settlement statuses (those politics writes, plus the new ones), with the day they began, and they age by the
world's clock (`Politics.expire_status` today only ends them).

Two rules of the town's map hold for every mark: buildings are **marked, never removed** (their order is used
everywhere: who lives where, inn names, trespass, roof pictures), and every mark keeps the town walkable (the entry,
a way out, every door reached – `tests/test_towns.py`). A burned building's trade closes until it is rebuilt (its
keeper sells from a stall, or is among the dead); the town's people thin when its dead are counted, and newcomers
arrive while it rebuilds (population only ever falls today; it learns to grow back).

**The fallen, blood and graves.** When a fight ends on a close-up map, the dead are left where they fell (their real
figures, lying, darkened, with blood under them) and blood stays on the squares where the blows fell – the battle mat
already knows both, and `Field.origin` says where on the close-up map the field was cut from. The dead stay for a day
or two (the townsfolk carry them off; in the wild, crows and then bones), and the town's graveyard gains a fresh grave
for each of its own. Blood fades over days. It is the cheapest, strongest piece of "show, don't tell" in the whole
expansion: the player can walk back through the street where the fight was and see it.

### 5.20 Battles through a living town (assaults)

Near the end of some adventures (and whenever politics sacks a town while the player is in it, or a dragon burns it,
or the dead march into it), the whole town becomes the battle: an **assault**. It is played on the town's close-up
map in its own time:

- **Attackers** come in as bands from the gates, the walls or a portal in the square (the threat's servants: the dead,
  raiders, orc warbands, a beast, a dragon – and demons once the next expansion, Tieflings & Warlocks, brings the
  fiends; until then a summoner's portal lets out imps and quasits), and hunt; **defenders** (the watch, the militia
  if the player rallied it, allies) hold points.
- **Fire** spreads from where the attackers set it (a cellular spread over what can burn: thatch and timber fast, stone
  slowly), the mark *burning* growing street by street; smoke hides, embers drift.
- **The townsfolk** run for their refuges (the temple, the keep, the gates), and those caught by attackers fall – in
  the street, where you will find them.
- **Objectives** stand on the map: the children in the orphanage (lead them to the gate), the alarm bell (ring it: the
  militia comes), the temple doors (hold them), the summoner on the square (kill him: the portal closes), the well
  (put out the fire round it).
- **Fights** happen where the player meets a band, as now (the field cut from the town), with the fire on the field as
  burning squares that spread each round, smoke as cover, a burning roof that may fall in; other bands close by join
  the fight a round or two later, from the edge of the field (today a fight holds one band only). Running from a
  fight in an assault takes the party a few streets away, not out of the town.
- **The clock**: the longer it takes, the more burns and the more die. There is no single way to win: save the
  children or hold the temple or kill the summoner first; you will not do everything.
- **Afterwards** the town is *burned* where it burned and untouched where you held; the dead are counted and named in
  the epilogue ("Seventeen died in Weavers' Row. The children of the orphanage lived."), the population falls by
  them, refugees go to the next town, a memorial may come later, and the survivors remember who stood with them.

### 5.21 The world map changes

Two kinds of change, drawn two ways:

**Changes to the land itself** – rare, great, lasting: a crevasse torn across thirty squares of country where a god
struck the earth; a forest dead and grey for leagues round a cursed tower; a dragon's scorched country; a valley
drowned when a dam of the old kings broke; a new lake in a crater where a star fell. They change the overworld's
arrays (biome, relief, elevation, roads) through a **ledger of land changes** (`world.politics["land"]`: each record
says what, where, with which seed, so that the base world plus the ledger gives today's land – checked by autoplay, as
the ownership ledger is), and the painted map is **repainted**: today the painter keeps copies of the world made when
it was built and the pictures are kept on the GPU by keys without a version, so a change shows only after a reload;
the expansion adds a land version that rebuilds the painter and its chunks (the overview stands in while the thread
paints, nearest first) and goes into the pictures' keys. Close-up maps already made in the changed country take the
change too (the crack runs through them as chasm; the dead forest's trees become dead trees).

**Signs on the map** – frequent, coming and going, drawn each frame over the painted map (no repaint): smoke rising
from a burned or sacked town; a ring of tents and banners round a besieged one; a black flag over a plague town; the
shadow of a dragon circling over a town that pays it tribute; lanterns and banners over a city at its coronation; a
column of refugees on a road; a **host** marching (an army, a horde, the dead, a crusade: a column of figures behind
its banner, with a little dust, moving day by day along the roads – wars are abstract today, so the war engine gains
the positions of its hosts); a threat's reach washed grey, red or under mist once the player knows it; the slow red
pulse of the rift.

The great wound itself is a **wonder made while you play**: the world already keeps its wonders as named things
with their squares, and each wonder kind shapes the close-up maps of its squares; the rift is a new kind, with the
crack running through every close-up map it crosses, and travel across it only at the places the story leaves (a
fallen bridge, a ledge, later a crusaders' bridge). Roads it cuts are cut.

**New places** appear: sites (a cult's camp, a monster's nest, a crashed star) and settlements (a crusaders' camp-city
at the rift's edge, a refugee camp outside a besieged city, a fort a realm builds on a new border), founded with a
name, an owner (always a realm, as autoplay demands; the crusading order is its patron), a people and a road to the
nearest road, with a town map laid out as a camp of canvas tents, palisade and banners, and on the world map a camp
drawn larger than any town mark, growing with it; they can grow into towns if the story lets them live. Today nothing
creates a settlement or a site while you play (new gangs take empty old sites), so founding is new: settlements and
sites are kept in lists whose order is their id, so a new one is only ever added at the end.

### 5.22 Cataclysms: when the world itself breaks

The greatest threats begin with a **great event** that the whole world sees: wherever the player is, the screen
shakes, the sky goes wrong, a sound like the world breaking; the news comes over the following days from every
direction; the world map shows the wound. Cataclysms are rare (at most one in a hero's life, at Legend 3 or more, or
from the history's darkest prophecies; a new world may also begin in a time of cataclysm, a world option, so that a
hero's tale starts on the road to the camp-city), and each is a tier 3–4 threat with its own blueprint (§6.13): the
wound in the world (a god's blow, a rift and the hordes that pour from it), the fallen star (a crater, a glowing
shard, a cult that worships it), the drowned land, the night that does not end (a region in darkness), the dead god's
plague.

Cataclysms bring everything together: a land change, hosts pouring out across the map, a region spreading week by
week, refugees on every road, new places founded by the realms that answer (the camp-city), assaults on the camp, a
descent, and an ending that leaves the land changed for ever – a scar that becomes a pilgrimage, or a country lost.

---

## 6. The catalogue

### 6.1 Blueprints

Each blueprint is a data entry (`adventures.json`, §8.2) with its chapters, step slots, cast, hidden variables, twists,
keys, beats and endings; the words are written in the game's voice with enough variants. The horror genres of
Ravenloft's chapter 4 (body, cosmic, dark fantasy, folk, ghost, gothic, disaster, occult detective, psychological,
slasher) are used as **flavours** that colour a blueprint's beats, omens and twists, not as blueprints of their own.

| # | Blueprint | Tiers | From (§5.1) | In a sentence | Part |
|---|---|---|---|---|---|
| 1 | **The Beast of {place}** | 1–3 | the beast | hunt a named killer: its victims, its history, its weakness, its den | A |
| 2 | **The Risen** | 1–3 | the risen | a dead king of the history stirs; learn why, find what binds him, lay him down | D |
| 3 | **The Outlaw Lord** | 1–2 | the outlaw lord | a gang's leader bleeds a valley; win the valley, break the gang, face the man | D |
| 4 | **The Hidden Circle** | 2–3 | the hidden circle | disappearances; three suspects among the town's great; stop the rite on its night | K |
| 5 | **Fire on the Valley** | 1–3 | the warband | a warband will come; raise the defence, scout, strike first or hold the night | K |
| 6 | **A Crown in Shadow** | 2–4 | the crown in shadow | a succession poisoned; choose a side, expose the plot, crown someone | K |
| 7 | **The Shadow of the Dragon** | 3–4 | the dragon | tribute and fire; the history's dragonslayer weapon, allies, the lair | K |
| 8 | **The Hunt for {relic}** | 2–4 | the relic hunt | a race against rivals and a collector through three ruins for a thing of the history | K |
| 9 | **The {colour} Death** | 2–3 | the sickness | a plague with a source; ingredients, a healer ally, the quarter to burn or save | K |
| 10 | **The Mage of {tower}** | 2–4 | the mad mage | lights in the tower, things escaped, an apprentice's warning, the last experiment | K |
| 11 | **The Grief of {house}** | 1–2 | a haunted house or inn (from a murder in the history) | a ghost with three words; who killed it, and the murderer still alive and honoured | K |
| 12 | **Blood Between Houses** | 1–3 | the blood feud | two houses at each other's throats; a wedding, a duel, peace or ruin | K |
| 13 | **The Master of {domain}** | 3–4 | the dread lord | a cursed region with its rules and closed borders; invitations, three treasures, the castle | K |
| 14 | **Under the Banner** | 2–4 | a war of the politics engine | the muster, a battle, a siege, a mission behind the lines | K |
| 15 | **A Companion's Tale** | any | a devoted companion's past (a grudge, a home, a vow) | the companion's own adventure, with them as the ally | K |
| 16 | **The opening** | 1 | the first hour (§5.12) | a short tale that starts a life | D |
| 17 | **Ambition sagas** | 1–4 | the ambition (§5.12) | three adventures woven from the hero's own past | J |
| 18 | **The Wound in the World** | 3–4 | a cataclysm (§5.22) | a god's blow tears the land open and hordes pour out; a crusaders' camp-city vows to close it | K |

### 6.2 The three blueprints of Parts A and D, in full

Each has a **first form** (what its part ships, with the step kinds that part builds) and a **full form** (what
the later parts add: villains' moves, rivals, traitors, bargains, the Reading, songs and ruin).

**1. The Beast of {place}** (genre: folk or dark fantasy). *Sources*: a living beast in `lairs`, with victims in its
`kills`. *Villain*: the beast (a bestial temper: signs, tests, hunts; no letters). *Cast*: patron (headman, a farmer
who lost his herd, a lord), ally (a hunter, the kin of a victim), rival (a glory-hunter, 40%), innocent (a hamlet).
*Hidden*: its weakness (by creature kind: fire, silver, a bait it cannot resist, its den's other mouth), its den's
place among 2 candidates (when the lair is not known).
- *I. The Killings*: `go` to the latest kill; `search` the carcass or the body (tracks, size); `witness` the survivor.
  Reveal: what it is, and its name from the history ("the Grey Widow, who took the Lannet boys in 1031").
- *II. The Hunt's Price*: `learn` its weakness (a hunter's lore, an old book, Nature check at a kill, divination);
  `prepare` (buy or make the means); `choose` the way – bait it or track it. Set piece: it comes to the bait, or it
  turns on the trackers; wounded, it flees to its den (its escape).
- *III. The Den*: `go` and the `finale` at the lair (the dungeon's last room, or a wild arena). Phase two: cornered,
  it goes mad (more attacks, no flight).
- *Twists* (one at most, by chance): it is a cursed person (lycanthropy: kill or cure – a moral choice); someone feeds
  it (a lord using it to clear his land of tenants); it guards young (spare them?).
- *Keys*: the weakness; the bait; the den's other mouth (surprise); the hunter ally.
- *Endings*: slain (the region's danger falls, the lair is cleared, the figure dies in the history, a trophy, fame);
  cured / spared (a strange ally later); fled (it returns in a season, a sequel); doom (the hamlet is emptied; the
  danger rises).
- *First form (Part A)*: steps go, search, witness, learn, prepare, choose, slay, finale; the set piece's flight is
  the beast's ordinary morale (beasts flee when badly hurt); the beast's signs and its moves of Part A (an omen; a
  carcass left at your camp as its "letter"; a test by night); keys weakness, bait, ally; endings slain and doom; the
  `choose` (bait or track) sets a codeword the den chapter and the epilogue read; an epithet is offered at the
  epilogue. *Full form*: rivals (Part F), the twists and the cure (Part K), escape and return (Part E).

**2. The Risen** (genre: ghost or gothic). *Sources*: a tomb in `tombs` whose figure died in a remembered way, with a
`scar` near it, or a barrow with a wight. *Villain*: the tomb's figure, risen (proud or grieving), with an **anchor**
(his crown, his sword, his true name, his bones moved from hallowed ground). *Lieutenants*: the waker (a necromancer, a
cultist, a grave-robbing noble) and one risen champion of his old guard. *Cast*: patron (a priest, the headman), ally
(someone who lost kin to the dead), rival (glory-hunters after the barrow's gold, 50%), innocent (the taken, a
village). *Hidden*: where the anchor lies (2–3 candidate sites from his history: where he died, where his slayer is
buried, the temple that keeps the chronicle), the waker's identity (sometimes the patron: the once-only betrayal).
- *I. The Dead Do Not Rest*: `witness` (the taken, the watchers), `search` (the battlefield, the disturbed graves),
  `rescue` (the taken, on an upper level of the barrow – the forge needs a barrow at least two levels deep for this
  blueprint, so that the rescue never happens in the boss's room; else the taken are held at the waker's camp).
  Reveal: who he was (from the Legends: his deeds, his death) and
  that someone woke him.
- *II. What Binds Him*: `learn` his past and his anchor (the temple's chronicle, a sage, Speak with Dead, the
  Legends book itself); `fetch` the anchor from its site; `slay` or `capture` the waker; `recruit` the ally. The
  villain's moves begin (a letter in an old hand; the dead at the camp's edge).
- *III. The Night of the Dead*: `hold` the place he means to take on a set night, said in the journal (the calendar's
  new moon if `data/calendar.json` has the moon, else "in N days, at night"): waves of the dead, the militia if
  rallied; the `finale` in his barrow: the throne room, his champion, his wights; phase two: the barrow wakes
  (sarcophagi open). With the anchor, a `rite` can lay him to rest instead of a fight to the end.
- *Keys*: the anchor; his true name; the ally; the militia; the barrow's other entrance; the ground hallowed.
- *Endings*: laid to rest (the barrow's `politics["laid"]` and the battlefield's `scar["laid"]`; the region's night
  encounters fall; the barrow's gold may be taken with a curse or left); destroyed with the anchor broken (he is gone
  for good); destroyed without the anchor (he returns in weeks, wrathful: a sequel); bargained (he offers to spare the
  town for a living heir of his slayer – a dark ending); doom (the nearest village is emptied and held by his dead;
  the region's danger +2; in time he may rise a tier, once).
- *First form (Part D)*: steps witness, search, rescue, learn, fetch, defeat (slay or capture), recruit, rally (the
  militia), hold, rite, finale; minimal attention and his letter or the dead at the camp's edge; endings laid to rest,
  destroyed (both kinds), doom. *Full form*: the waker as traitor and the bargain (Parts E–F), rivals (Part F), the
  dread lord rising (Part K).

**3. The Outlaw Lord** (genre: dark fantasy). *Sources*: an active `bandit_gang` with a leader figure and a hideout.
*Villain*: the leader (cunning or cruel; or, through the `deserters` hidden side, desperate). *Lieutenants*: a
right hand and the gang's inside man in the town (the traitor's slot). *Cast*: patron (the lord whose roads are
bled, or the merchants' guild), ally (a robbed carter, a deserter who wants out), rival (the lord's own captain, who
wants the glory). *Hidden*: the inside man, the hideout's back way, whether the gang is starving deserters.
- *I. The Bleeding Road*: `escort` a caravan as bait or `witness` the robbed; `slay` a raiding party; `capture` one
  alive (questioned: a lead).
- *II. The Man in Town*: `learn` who sells the gang the caravans' days (three suspects; clues; a wrong accusation
  warns the gang and costs standing); `confront` the inside man; `choose`: deal with the leader (a parley; the
  deserters' truth) or break him.
- *III. The Hideout*: the `finale` at the hideout (the named leader and his right hand), or a parley that ends it
  without blood (the gang disbands, its men pardoned through the lord – a law outcome).
- *Endings*: broken (the leader dies, the gang faction falls, the road's danger falls, the lord's gratitude: a right
  or a title at Legend 2); pardoned (the gang becomes the lord's men or scatters; a later echo); fled (the leader
  becomes a sequel's villain); doom (the gang grows: a second hideout, the town pays tribute).
- *First form (Part D)*: steps escort, witness, defeat, capture (`fight.decide_captive` "questioned" gives the lead),
  learn (three suspects – the inside man is a step's target here, not the hidden traitor role), confront, choose
  (parley or break), finale; endings broken, pardoned (through the lord's law), doom (`tribute` status). *Full form*:
  the lord's captain as rival (Part F), the leader's escape and return (Part E), a title from the lord (Part J).

### 6.3 The rest of the blueprints, in outline

*(Part K writes them in full, with the same parts as above. Every outline names the twist and keys that make it
itself.)*

- **4. The Hidden Circle** (occult detective, cosmic). I. *The Missing* (witnesses, a searched house, a symbol); II.
  *The Circle* (three suspects among the notables – the true one bound at generation; an infiltration of a meeting
  in disguise; the circle strikes back with a frame through the law); III. *The Rite* (a race to the night: break the
  circle's points, fight the high priest and what came through). Twist: the patron is the circle's head; or the
  "summoned thing" is what keeps something worse asleep (a necessary evil). Keys: the rite's words, the points broken,
  the true name. Endings: the cult falls (faction), the notable disgraced or dead, the town's temple purged; doom: the
  thing walks, the town becomes a dread lord's seat.
- **5. Fire on the Valley** (the Seven Samurai). I. *Smoke* (a burned hamlet, scouts, the warband's size); II.
  *Preparations* (`rally` defenders, hire swords, fortify by labour, `prepare` fire and stakes; optional: steal their
  horses, kill their shaman, parley); III. *The Night of Fire* (a `hold` in waves, then the warchief's duel). Endings:
  the village saved (a home for the hero: free board, a house later), the tribe's relation changes; doom: burned.
- **6. A Crown in Shadow** (intrigue). I. *The Summons* (Legend 2+: a lord sends for you; a poisoned cup); II.
  *Allegiances* (choose a side among claimants; win houses; expose the poisoner by documents, spies, a confession);
  III. *The Crowning* (a coup by night in the castle, a duel of champions, or a battle the politics engine resolves with
  the party's fight as its turning point). Endings change who rules (`set_owner`, succession), titles from the winner,
  the losing side's lasting enmity.
- **7. The Shadow of the Dragon** (epic). I. *Tribute* (a town burned or taxed; the lord seeks a champion); II. *The
  Means* (the history's dragonslayer weapon or its pieces, the dragon's name, a hold's oath, the lair's road); III.
  *The Lair* (the lair's regional effects on the way; the fight in phases: the air, the hoard). Twist: the dragon's
  bargain (a share of the hoard to betray the realm); the dragon holds back something worse. Endings: the dragon slain
  (tribute lifted, the hoard, fame of legend); bargained; doom (a second town burns; the realm pays for ever).
- **8. The Hunt for {relic}** (a race). I. *The Lead* (a book, a dying scholar; the Reading tells where its pieces
  are); II. *The Three Keys* (three ruins in any order; the rival band and a collector – a lich, a mage, a noble – race
  you; whoever is slow finds the other's dead); III. *The Vault* (its guardian, the rival's last move; keep it, return
  it, destroy it – each with its consequence). Uses `politics["artifacts"]` and their provenance.
- **9. The {colour} Death** (disaster). I. *Outbreak* (the sick, the quarantine, a healer ally); II. *The Cure*
  (ingredients from dangerous places, the source's direction); III. *The Source* (a cursed well and its culprit, a
  hag, a necromancer's experiment). The clock is the town's people dying (its population falls each week; visible).
  Choice: burn the sick quarter to save the rest.
- **10. The Mage of {tower}** (body or cosmic horror). Lights and abductions; an apprentice's warning; the experiment
  (a made thing loose); the tower ascended floor by floor (Expansion 5's lived-in towers); the mage's last work. Twist:
  the mage is holding something worse back.
- **11. The Grief of {house}** (ghost story). A haunting with rules (it can say only three words; it returns a day
  after it is destroyed – Ravenloft's haunting that will not stay dead); the truth of its murder in the history; the
  murderer still alive and honoured; laid to rest by justice (the law), by a rite, or destroyed in its wrath.
- **12. Blood Between Houses** (gothic). From `grudges`: two houses, a planned wedding, a duel, a murder; broker peace
  (a marriage; the ledger of wrongs settled), or choose a side and see the other ruined.
- **13. The Master of {domain}** (gothic; the crown jewel; tier 3–4; built in Part K, and widened by Crypts & Curses
  and the planar expansion). A dread lord rules a region under rules of its own (no sun at noon; the dead rise after
  seven days; the borders close – the mists turn travellers back – once it has noticed you); its first contact is an
  **invitation** with a seal; three treasures and the true ally are drawn by the Reading; its tests, gifts and
  bargains run all through; its castle is the last chapter, the room of the last stand drawn by the cards, its anchor
  hidden elsewhere. Endings: destroyed (the region's rules end; the borders open; the people's fates); the hero
  takes its place (the darkest ending: you become a dread lord of the world for your next character to face);
  escaped (you get out; it remains).
- **14. Under the Banner** (war). The realm's muster at a war's start; a battle (the politics engine's battle, with the
  party's fight as its key skirmish); a siege (get in or hold); a mission behind the lines (a bridge, a commander, a
  hostage). Endings move the war's score and maybe the peace.
- **15. A Companion's Tale.** For a companion who is devoted (loyalty high) and carries a grudge, a lost home or a
  vow: a tier-fitting adventure with the companion as the ally, their stake as the premise, and their fate in the
  epilogue. Replaces the half-pay "personal quest" templates.

### 6.4 Beat families (`beats.json` fragments)

| Family | Examples |
|---|---|
| **Signs** (per threat kind and stage) | dogs that will not go near the barrow; a cart of the dead's belongings at the market; a well that tastes of iron; a child singing a rhyme about the wolf; the hamlet's door marks |
| **Villain moves** (§5.4) | the rumour, the spy, the letter, the gift, the test, the visit, the invitation and the dinner, the bargain, the wedge, the reprisal, the frame, the kidnap, the strike, the hunt, the gloat, the wrath |
| **Allies** | the plea, the join condition, the confidence, the doubt, the crisis, the sacrifice, the farewell |
| **Rivals** | the meeting, the race, the theft, the ambush, the truce, the plea for help, the sale to the villain, found dead |
| **Patrons** | the briefing, the payment, the hidden motive revealed, the patron in danger, the reward |
| **Reveals and chapter openings** | the title card and its line; the reveal scene of each blueprint's chapter |
| **Relief** | a grateful village's feast; a song at the inn; a quiet night with a companion's story; a bath and a clean bed; a child's gift |
| **Echoes** (§5.10) | the spared, the freed, the saved, the cheated, the robbed, the bereaved, the shamed, the inspired |
| **Happenings** (§5.10) | coronation, tourney bouts, wedding feast, funeral, muster, siege, refugees, quarantine, fair, holy day |
| **Legend** | the herald, the bard who wants your story, the petitioner, the challenger, the assassin, the summons, the title, the land |
| **Ambition** | the letter from home, the old enemy's name heard, the dream of the lost, the house's ruin seen at last |
| **Reading** | the seer's camp, the cards, the silent card, the villain speaking through the seer |
| **Dark gifts** (Ravenloft) | an offer at a cursed place or from a villain: a real power with a visible mark and a price that falls on a natural 1; the giver may call the debt in later |

### 6.5 Legend tiers, epithets and titles

`legend.json`: the tiers of §5.11 with their numbers; **epithets** by deed tag (beast slain: "Wolfbane", "-bane" forms
from the creature; the dead laid: "Barrowbreaker", "the Gravewarden"; a village held: "the Shield of {place}"; mercy:
"the Merciful"; cruelty: "the Butcher of {place}"; a king made: "Kingmaker"...), at least six forms per tag, offered
2–3 at a time; **titles** through the game's existing titles (`reputation.grant_title`, law.json), named by realm
culture (knight, warden, thane, castellan...) with what they give (people.json greetings, prices, the law's treatment,
an audience); **lands** (a holding in a village: a house, an income by the village's size, its people's needs – a hook
for Bastions & Banners later).

### 6.6 Ambitions

`ambitions.json`: the twelve of §5.12, each with: which backgrounds suit it (any may choose), what it binds at creation
(a figure, a ruin, a relic, a claim, a curse – from `ties.py` and the history), its three stages (a blueprint and a
tier for each), its beats (letters from home, the name heard, the dream), and its fulfilment (the retirement epilogue
and what the hero becomes in the world).

### 6.7 Predicaments (`situations.json`, the shapes of trouble)

The first forty, each written as data with its roles, preconditions, goals and endings. The endings shown are the
kinds each has besides "it went well" – every predicament has at least one bitter or mixed ending.

| # | Predicament | The trouble | Endings |
|---|---|---|---|
| 1 | Gone where they should not | someone has gone to the gang, the barrow, the enemy town, the cult | home and whole · alive, but staying · dead |
| 2 | A promise that cannot be kept | a dowry, a debt, a delivery, a vow to a lord | kept with help · broken with honour · broken in shame |
| 3 | Two who want one thing | land, an office, an heir's hand, a relic | one wins · shared · both lose it |
| 4 | A truth someone wants buried | a crime, a parentage, a debt | buried · told · used (blackmail) |
| 5 | A truth that must be proven | a will, a claim, an innocence | proven · believed without proof · lost |
| 6 | An innocent accused | the watch has the wrong man | freed · freed but shamed · hanged |
| 7 | A guilty one protected | the lord's son did it | judged · paid off · avenged outside the law |
| 8 | A wrong that waits for revenge | someone wants a killing done | done · stopped · turned into a price paid |
| 9 | Blood owed | a feud's next death is due | prevented · done · peace by marriage or payment |
| 10 | A sickness with a cause | a person, a herd, a crop, a well | cured · the cause stopped, the sick lost · it spreads |
| 11 | A curse on a house | crops fail, children sicken, a dead hand on the door | lifted · moved onto another · lived with |
| 12 | Something precious in the wrong hands | the heirloom pawned, stolen, seized | returned · bought back dear · lost, and a copy made |
| 13 | The lost | a living one to find, or a dead one to bring home and bury | found · found dead and buried · never found |
| 14 | A love that must not be | across houses, faiths, peoples; a forced marriage | together · parted · fled together, outlawed |
| 15 | A child in danger | taken, sick, hunted, sold | saved · saved at a price · lost |
| 16 | The stranger is not who he says | a false name, a spy, a runaway noble | unmasked · protected · let go |
| 17 | A fugitive at the door | a deserter, a runaway serf, a hunted healer | away free · handed over · caught |
| 18 | A ruler's need | an envoy, a champion, a spy, a hostage to exchange | served · served badly · refused, and remembered |
| 19 | A rite that must be done | a burial, a harvest rite, a pilgrimage, an oath-taking | done · done wrong · not done, and the omen |
| 20 | The dead do not rest | a ghost with a task | laid · bound · angered |
| 21 | Bread or the rope | the hungry steal; the law is the law | pardoned · punished · fed and hidden |
| 22 | A temptation | a bribe, a forbidden book, a dark gift | refused · taken, and marked · taken and turned against its giver |
| 23 | An oath that binds the wrong way | sworn to a cruel lord, a dead cause | kept · broken, outlawed · released |
| 24 | A betrayal found out | a partner cheats, a spouse strays, a brother sells secrets | punished · forgiven · hidden |
| 25 | Someone changed | madness, a possession, a fever of the mind | healed · lost · mercy |
| 26 | A trial | a judge, a witness or the accused; a mob's justice | just · unjust · overturned |
| 27 | A ransom | a hostage held for coin or a deed | paid · rescued · lost |
| 28 | Fire, flood, fall | a burning house, a flooded mine, a fallen bridge – now | all saved · some saved · none |
| 29 | An enemy who is not evil | a captive foe, a beast with a reason, a deserter of the other side | spared · killed · made an ally |
| 30 | Masters at odds | two smiths, two healers, two bards: a contest or a sabotage | won fair · won foul · both ruined |
| 31 | The collector at the door | a debt called in by hard men | paid · fought off, and they come back · the house lost |
| 32 | The will | an inheritance; a testament hidden or forged | the rightful heir · the strong heir · the temple takes it |
| 33 | A load that did not come | a caravan, a ship, a messenger late on a bad road | found · found plundered · never found (a threat's sign) |
| 34 | A place no one will enter | a haunted mill, a cursed wood, a sealed cellar | cleansed · fled from · sealed for good |
| 35 | The wolf at the fold | a predator takes the herd (not a threat's great beast) | killed · driven off · a bargain with the hunter |
| 36 | A message that must, or must not, arrive | a letter, a warning, a confession | arrives · lost · arrives changed |
| 37 | A strange arrival | a refugee with a strange gift, a foreign merchant, a child from nowhere | welcomed · driven out · claimed by those who follow |
| 38 | A feast in danger | a wedding, a festival, a funeral feast | saved · spoiled · a massacre, or not |
| 39 | The last of a line | the last keeper of a secret, a craft, a family's name | passed on · lost · stolen |
| 40 | Your own wrong | someone the hero wronged seeks redress (an echo) | amends · refused · a feud of your own |

### 6.8 Obstacles and their ways through

| Obstacle | Ways through (each a check, a cost or an action the game knows) |
|---|---|
| a locked or barred door | the key (stolen, borrowed, found), picking it, forcing it, Knock, another way in (a window, the roof, the cellar), the keeper's favour |
| a guard | talk, a bribe, a distraction (a companion, an illusion), sneaking, overpowering, a disguise, papers, a favour, the law |
| one who will not talk (fear) | reassurance (Insight then Persuasion), protection, removing what they fear, a charm or Detect Thoughts, a favour |
| one who will not talk (loyalty, pride, price) | pay, threats, proof that the other is false, a companion they trust, shaming them in front of others |
| a lie | catching it (Insight), a second witness, a document, Zone of Truth or Truth Serum, someone who knows (an echo) |
| a law | a petition to the lord, a pardon (standing, a favour), breaking it (a crime with witnesses), a loophole (a sage, a priest), a title |
| a price | paying, haggling, working it off, stealing it, a favour traded, a substitute (a forged paper, a false heirloom) |
| a distance against a deadline | hard travel, a horse or a coach, travel by magic, a messenger, giving up something else |
| a danger on the way (wolves, robbers, a threat's servants, a storm, a flooded ford) | fighting, going round (another road, by night, unseen), a guide, waiting it out, magic |
| a rival after the same thing | racing, a deal, sabotage, an alliance, exposing them |
| a custom or taboo | respecting it (finding kin to go in), a priest's leave, breaking it and bearing the scorn, a disguise |
| a tongue you do not speak | a companion, a hired speaker, Comprehend Languages, Tongues, signs (a check) |
| a rank too high | a letter of recommendation, a favour, Legend, dressing as a noble, the steward's palm, the day of the hunt or the feast |
| a missing name or place | a sage, a library, the Legends book, witnesses, divination, the Reading |
| a mob | calming it (Persuasion, a priest), facing it (Intimidation), hiding the one it wants, giving it someone else, the watch |
| a sick or dying person | a healer, magic, herbs (Medicine), a cure from far away |
| a ward or a curse | Dispel Magic, Remove Curse, the rite, its maker's death, a priest |
| a beast | hunting, snares, bait, fire, Animal Handling, Speak with Animals |
| a riddle | the player's own reading of the clues, an Intelligence check, a sage, force |
| a demand for a champion | the duel (`game/shadows.py`), a champion found (a companion), refusal and shame |
| an official on the take | paying more, a document that damns him, going over his head, blackmail |
| an impostor | unmasking (Insight, a test, an old acquaintance), playing along |
| one who does not want rescue | persuasion, carrying them off (a crime), letting them go (an ending of its own) |
| a family's honour | helping in secret, winning over the elder, letting it fail |
| a place shut (a gate at night, a crowd, a quarantine) | waiting, a bribe, sneaking, a pass |
| too few hands (a fire to fight, a wall to raise, a harvest) | rallying (hiring, persuading), labouring yourself, magic |
| a bargain that must be honoured (a hag's, a fey's) | honouring it, cheating it cleverly, breaking it and paying |
| a watcher who will tell (a spy in the house) | finding and turning them, feeding them false words, silencing them |
| an unseen enemy | detection, a trap, a test |

### 6.9 Turns

The one who asks is lying · the victim is the culprit · the lost one does not want to be found · the letter damns its
sender · the culprit is someone you once helped · two troubles in the town are one · the beast protects something ·
the dead one is alive · the price was a lie · a third party arrives for it · the help you need is your enemy's · the
clock was shorter · the one who asked dies before the end · the innocent is guilty of something else · the thief only
took back what was theirs · a threat's hand is behind it (a thread into an adventure) · the gift is cursed · the
witness is the hidden hand · the right thing breaks a law you are sworn to · the family turns on the helper · the cure
is worse than the sickness · the hero is the one blamed · someone you love is on the other side · the prize is false
and the real one elsewhere · it was a test.

### 6.10 Meetings (how a situation is met – always shown)

A quarrel overheard in the street · a plea at your table at the inn · a runner with a note · a body in the river or
on the road · a man in the stocks, a whipping in the square · a funeral passing · a notice nailed to a door · a
companion who knows a face · a bell at midnight · a children's rhyme · a crowd round a shut shop · a fight in an alley
you can step into · a stranger following you · smoke, or a broken cart, seen from the road · a dream · a priest's
sermon · the crier's cry · a horse with an empty saddle · a woman weeping at the well · a house with the lord's seal
on its door · the watch searching every cart · an empty stall where the old woman always sat · a gift left at your
door · a face at a window that should be empty.

### 6.11 Vignettes (hand-made, rare)

The first forty are written with this expansion; ten of them, to set the tone:
- **The drowned bell** (a lake over a village drowned in the history): on still nights a bell rings under the water;
  the last of the drowned village's line wants it raised; raising it wakes what drowned them.
- **The bride of the dead** (a miller's daughter; the grave of a young man of the history): she has promised to marry
  a ghost, and the wedding is on the new moon.
- **The bridge-keeper's toll** (an old bridge; a hermit): riddles drawn from the bridge's own past.
- **The last smith of the old way** (a smith who is a figure; a blade of the history): he would forge again the blade
  his forebear made, if you bring him the star-iron.
- **The tithe-barn fire** (a village in famine): the barn burns at night with the grain in it; who set it, and why?
- **The saint's bones** (a temple and its saint of the history): the relics are stolen on the eve of the saint's day.
- **The hanging tree** (a scar with a gallows tree): at midnight the hanged speak, and each wants one thing.
- **The orphan's map** (an orphanage; one of the fallen heroes of this world): a child carries a map drawn by a hero
  who died here – perhaps one of the player's own past lives.
- **The masked feast** (a noble house with a grudge): at the masked feast someone will kill the heir, and everyone
  wears the same mask.
- **The silent village** (a hamlet with plague in its history): nobody speaks after dusk; one child does.

### 6.12 Marks

The marks of §5.19 are data (`marks.json`): what each does to the ground, the buildings, the things lying about, the
light, the air, the sounds and music, the people's days and words, and what it ages into. Later expansions add their
own (a dragon's scorched country, the Underdark's fungus spreading up a well, a fey ring's overgrowth).

### 6.13 The Wound in the World (a cataclysm; tier 3–4; Part K)

The showcase of everything this expansion can do. It can be met early: a new world may begin in a time of
cataclysm (§5.22), and the debug console's `showcase rift` stages it in any game.
- **The great event.** A god of the world's faiths – or a demon prince, or a titan the history buried – strikes the
  earth. Wherever the player is, the screen shakes and the sky goes red for a day; the news comes in from every road;
  the world map shows a rift torn across twenty to forty squares of country (a land change and a new wonder). Hosts
  pour out of it across the map (the dead and the things of the deep earth: zombies, ghouls, wights, trolls, giant
  spiders; fiends join them once Tieflings & Warlocks brings them); a region of corruption spreads from it week by
  week (washed red on the map; blighted country at its heart); refugees fill the roads; prices rise.
- **The answer.** A knightly order (or a realm, or a faith) vows to close it and founds a **camp-city** at its edge: a
  palisade, canvas tents in rows, a chapel tent, forges, horse lines, banners in the order's colours – a new
  settlement on the map, drawn there larger than any town, which grows as the adventure goes on (more tents, then
  timber halls), or falls.
- *I. The Road to the Wound*: refugee columns and their situations; burned villages on the way; the first sight of the
  rift from a ridge (a title card); the camp's gate.
- *II. The Camp*: the marshal (the patron); the camp's own troubles (a preacher who calls the wound a judgement;
  deserters; stolen stores; a spy of the thing below); a night holding the line (an assault on the camp); winning the
  order's champions and a hated mercenary captain (allies); a rival (a mad prophet's flagellants who mean to go down
  first).
- *III. The Means*: what can close it (the Reading draws it: a relic of the history, the god-slayer's spear; a rite;
  the true name of what struck), sought in the places the world remembers, while the corruption spreads and a town
  falls elsewhere (an assault: the player chooses where to be).
- *IV. The Descent*: a dungeon of many levels down into the rift (a `rift` site with its own dungeon style: raw rock,
  red light, walls of bone), the thing's
  lieutenants who remember, and the camp's last stand above while you are below (heard in the news and from an ally's
  runner when you come up).
- *V. The Heart*: the finale with the thing that struck, or its herald; in its second phase the rift's walls close in.
- *Endings*: **closed** (the rift stays as a scar for ever, its glow gone; the camp-city becomes a town with a name from
  the story; the order gains a seat; pilgrims come; the hero's statue stands at the edge); **sealed at a cost** (an ally
  given to the rite; a mark on the hero); **failed** (the corruption takes the region: blighted country, emptied towns,
  the hosts spreading – the next hero inherits a broken land); **the bargain** (the thing offers the hero its power).
- *Other cataclysms*, built on the same pieces: the fallen star (a crater lake, a shard that whispers, a cult), the
  drowned land (a dam of the old kings breaks), the night that does not end (a region where the sun does not rise),
  the dead god's plague.

---

## 7. One adventure, and two situations, as the storybook prints them

`tools/storybook.py` (§9) prints a generated adventure as a synopsis, so that Anton and the reviewers can read what the
game would tell without playing it. A Part D adventure must read like this (names from a test world):

```
THE RED KING WAKES                          (the_risen, tier 1, threat T7, adventure A3, world seed 4412)
Premise   Aldric the Red (d. 812 at Marrow Ford, killed by Ser Hodd of Coldwell) stirs in his barrow above
          Harrowmere (barrow depth 3). Woken by Wessel the grave-robber (lieutenant 1, cunning).
Hook      opening: the gate of Harrowmere is shut; a child taken from the mill (innocent: Lissa, the miller's girl)
Patron    Mother Agna, priest of Harrowmere (honest)
Ally      Brann Tull, old soldier, son taken (join: none; arc: confides / wants to go alone / dies or swears)
Rival     the Brothers Ost (3, glory-hunters, relation 0; clock: reach the barrow's gold in 18 days)   [Part F on]
Hidden    anchor = his crown, at Coldwell temple crypt (candidates: Coldwell crypt, Marrow Ford cairn)
          weakness = his true name "Aldric Varrowsson" (in the Coldwell chronicle); last stand = the barrow's deepest
          room; traitor = none
Scheme    omens (now) -> the dead walk (in 9 days) -> the emptying (Fennick) -> DOOM the dead march (Harrowmere)
I   The Taken        witness Lissa's mother; search the mill path; rescue Lissa (barrow level 1)  -> reveal: Aldric
II  What Binds Him   learn his past (Agna's chronicle | the Legends | speak with dead at the ford);
                     fetch the crown (Coldwell crypt, level 2); defeat Wessel (Coldwell, level 1); [recruit Brann]
                     choose: tell Harrowmere the truth about Ser Hodd's line, or keep it (codeword)
III The Ford         rally the mill hands; hold Marrow Ford on the night of the new moon (3 waves);
                     FINALE barrow level 3 (Aldric + champion Ser Odo the Faithless + 4 wights;
                     phase 2 at half: sarcophagi open)
Keys      crown -> no Legendary Resistance, rite allowed | true name -> frightened 1 round | Brann -> fights beside
          | militia -> the ford's third wave halved | ford held -> the barrow's wights halved
          | side door (from the Coldwell chronicle) -> surprise
Endings   laid to rest | destroyed, anchor broken | destroyed (returns in 4-8 weeks) | bargained [Part E on] | doom
Target    tier 1 = level 3; 14-22 days; boss with all keys: high; with none: deadly+
```

Situations print the same way (§5.16). One from inside that adventure, and one of a town's own:

```
THE MILLER'S SILVER                       (situation Q12, Harrowmere; inside adventure A3, chapter I)
Predicament  a truth someone wants buried (#4)        Turn  none
Roles       holder  Edda Marl, the miller's wife (fearful, loyal)
            in the way  Tobin Marl, the miller (paid by Wessel in old silver; ashamed)
            hidden hand  Wessel the grave-robber (lieutenant 1)
Stakes      Edda will tell what she saw at the mill only if Tobin is safe, from the watch and from Wessel
Meeting     a quarrel overheard at the mill door at dusk (scene overhear_quarrel)
Obstacle    one who will not talk (fear): reassure her (Insight 12, then Persuasion 13) | protect Tobin (the reeve's
            favour, or his debt paid: 40 gp) | Detect Thoughts | wait: she sends a runner with a note to Coldwell
Goal        knows(you, waker_place)   -> the step's lead:home and clue:waker
Endings     told, Tobin spared (Edda a contact; Tobin gives his silver to the temple)
            told, Tobin hanged (the watch heard of the silver; the gibbet in the square; Edda's hatred)
            never told (the lead comes by the other two routes; the mill stands shut)
XP          medium for party level 2; x1.25 without a fight

IVO AND THE GREY BROTHERS                 (situation Q41, Kessa; root: a life – Marda Venn's son has run off)
Predicament  gone where they should not (#1)          Turn  the lost one does not want to be found
Roles       in trouble  Ivo Venn, 16, apprentice cooper        asker  Marda Venn, widow, cooper, his mother
            in the way  Sef Harrow, captain of the Grey Brothers (bandit gang F12; hideout the Old Toll, 9 tiles)
            witness  Pell the ferryman (saw Ivo cross on Saturnsday)
Stakes      the Grey Brothers ride against the salt caravan in 6 days, and Ivo rides with them
Meeting     a woman weeping at the well (scene weep_at_well); or, at the Old Toll first, a boy on watch
Obstacles   a guard at the Old Toll | one who does not want rescue (Ivo) | the gang
Ways        talk Ivo round (Persuasion 15, or his dead father's letter, which Marda keeps) | buy him out (Sef: 60 gp)
            | take him away by night | the lord's men (a petition to the reeve) | fight the gang
Endings     home and whole (Marda: a favour, "a cask and a bed"; Ivo back at his barrels; the gang sore at you)
            alive, but staying (Ivo a Grey Brother: met again on the road, an echo)
            dead (in the caravan fight; a new grave by the temple; Marda in black at the well)
Connects    the Grey Brothers are the gang of the Outlaw Lord threat T3; the caravan raid is its second stage
```

---

## 8. Architecture

Everything here follows `CLAUDE.md`: logic never imports UI; one seeded RNG (`rng.child`); data-driven with schemas;
never make the player wait; never crash; every word written into the game. Names in `this style` that exist today
were checked in the surveys of 2026-10-22 and 2026-10-24; names marked *(new)* are to be made.

### 8.1 Modules

```
realmwalker/world/threats.py        (new) threat records; seed(world, tables, rng) after the ages; seed_from(politics,
                                     kind, refs); advance(politics, days) from Politics.advance (schemes, signs through
                                     world/news.add, stage effects and doom; the world's own endings of threats);
                                     reach and overlay queries. World layer: no GameState, so it also runs in the
                                     interlude.
realmwalker/game/story/             (new) the story engine, player side
  __init__.py                       the one door: every hook the rest of the game calls (§8.4)
  forge.py                          blueprint + threat + hero -> adventure record (casting, places, hidden variables,
                                     chapters, clues, scaling, naming)
  selectors.py                      the named selectors blueprints use for places and people (checked at start-up)
  cast.py                           roles; finding or making people; allies' arcs; rivals' clocks; traitors' tells
  steps.py                          the step kinds (a registry by id, §8.5)
  villain.py                        attention, moves, tempers, spies, escapes, anchors, early ends, wrath
  reading.py                        the Wayfarer's Deck: cards for truths, riddles, silent cards, the villain's card
  finale.py                         boss templates, arenas, keys -> battle effects, phases, the intro card's data
  endings.py                        choosing the ending; consequence ops; the epilogue's pages; sequel threats
  beats.py                          the beat language: conditions, outcome ops, follow-ups, PendingBeat
  director.py                       the Storyteller: tension, the quiet clock, opportunities, choosing beats, offers,
                                     encounter overlays near threats
  echoes.py                         echo seeds from deeds; echo beats' conditions
  happenings.py                     happenings from politics events; town state; the tourney
  legend.py                         tiers, epithets, titles, land, greetings, songs; the infamy track
  ambitions.py                      ambitions at creation; their sagas; ending a tale; taking up the fallen's task
  words.py                          titles, journal lines, riddles, epilogue pages (textgen with nested tables)
  check.py                          start-up check of all story data against the registries (like engine/check)
  situations.py                     situations: roots, predicaments, roles, obstacles, turns, meetings, endings and
                                     clocks; situations inside adventures (§8.10)
  goals.py                          the goal predicates; goals.notify and the ways through (§8.10)
  lives.py                          lives (ties, wants, fears, secrets, things) and life events (§8.10)
  favours.py                        favours and contacts (§8.10)
  work.py                           contracts, bounties and commissions; the end of the weekly offers (§8.10)
  stage.py                          scenes and their cues (§8.11)
  assault.py                        assaults (§8.15)
realmwalker/game/placemarks.py      (new) marks stamped on close-up maps (§8.13)
realmwalker/game/remains.py         (new) the fallen, decals and graves; written back from battles (§8.14)
realmwalker/game/fire.py            (new) fire on close-up maps and in battle (§8.14)
realmwalker/world/marks.py          (new) marks on settlements: add, lift, age (§8.13); world layer
realmwalker/world/reshape.py        (new) the ledger of land changes (§8.16); world layer
realmwalker/world/hosts.py          (new) hosts on the map (§8.16); world layer
realmwalker/world/founding.py       (new) settlements and sites founded while you play (§8.16); world layer
realmwalker/ui/screens/beat.py      (new) the beat screen: pages, choices, checks, pictures, chapter title cards
realmwalker/ui/screens/epilogue.py  (new) "What became of them"
realmwalker/ui/screens/finale.py    (new) the boss intro card before the finale's battle
realmwalker/ui/screens/journal.py   + the Adventures tab (first tab)
realmwalker/ui/screens/creation.py  + the Ambition step
realmwalker/ui/screens/sheets.py    + the Legend page
realmwalker/ui/screens/titlecard.py (new) chapter title cards (§8.12)
realmwalker/ui/screens/letter.py    (new) letters and notes as pages (§8.12)
realmwalker/ui/gfx/vignette.py      (new) the vignette composer (§8.12)
realmwalker/ui/gfx/atmosfx.py       (new) embers, ash, smoke haze and mist over a close-up map (§8.14)
realmwalker/ui/gfx/mapsigns.py      (new) signs, hosts, washes and the rift's pulse on the world map (§8.16)
tools/storybook.py, tools/storyplay.py, tools/showcase.py   (new) §9
```

### 8.2 Data: the pack `data/packs/06_adventures_events/`

| File | What it holds |
|---|---|
| `pack.json` | the expansion's record (§4.1 of EXPANSIONS.md) |
| `threats.json` *(new kind)* | threat kinds: sources, tiers, the active budget by world size, schemes (stages with days by tier, signs, effects), dooms, villain roles, tempers and anchors, encounter overlays by stage |
| `adventures.json` *(new kind)* | blueprints (§6), step texts, chapter titles, hooks, epilogue pages, nested word tables |
| `villains.json` *(new kind)* | tempers and their move weights, moves (attention, needs, beat), boss templates by tier and role, escapes by kind, anchors, omens, first words |
| `beats.json` *(new kind; fragments `beats.signs.json`, `beats.villain.json`, `beats.cast.json`, `beats.relief.json`, `beats.echoes.json`, `beats.happenings.json`, `beats.legend.json`)* | the beats |
| `reading.json` *(new kind)* | the Wayfarer's Deck: cards, their tags and riddles; the five places |
| `legend.json` *(new kind)* | tiers, epithets, titles, lands, greetings by tier |
| `ambitions.json` *(new kind)* | the ambitions |
| `happenings.json` *(new kind)* | happening kinds: what makes them, how long, the town state, their beats, the tourney's bouts |
| `situations.json` *(new kind; fragments `situations.predicaments.json`, `situations.obstacles.json`, `situations.turns.json`, `situations.meetings.json`, `situations.roots.json`, `situations.vignettes.json`)* | predicaments (roles, needs, goals, endings), obstacles and their ways through, turns, meetings (each naming its scene), roots (the predicaments each can make), the hand-made vignettes, and their words |
| `lives.json` *(new kind)* | ties by job, age and household; wants, fears, secrets and things of note; life events with their conditions, effects and story chance |
| `scenes.json` *(new kind)* | scenes as lists of cues; the specs of vignette pictures |
| `marks.json` *(new kind)* | marks: their dressing (cells, looks, scatter, lights, people, sounds, music, atmosphere), map signs, words, stages and aging; the burnt forms of terrains |
| `assaults.json` *(new kind)* | assault kinds: bands and waves by threat kind and tier, objectives, clocks, fire seeds, the tally's words |
| `work.json` *(new kind)* | contract kinds (from trade, war and faith) with their terms and renewal; commissions by faction goal |
| fragments of existing files | `dialogue.json` (story topics, `reveal_clue`/`open_hook` lines), `people.json` (the seer, the steward, militia, greetings by Legend, criers' lines for marks), `companions.json` (story tags in likes and hates), `music.json` (moods `story/omen`, `story/finale`, `story/epilogue`, `story/ruin`, `story/assault`), `sounds.json` (`chapter`, `reveal`, `sign`, `legend_up`, `villain`, `bell`, `fire`, `crowd`, `quake`, `horn`), `sprites.json` (map marks and signs, card faces, beat pictures, the new terrains and decals, mourning dress, the held letter), `quests.json` (texts for step quests and contracts), `local_terrain.json` (fire, embers, scorched ground, charred floors and walls, fallen beams, broken doors, barricades, gallows, pyres, scaffolds, fresh graves, ritual circles, cages, rift edges), `biomes.json` (rift, rift ledge, blighted, scorched land, drowned, crater), `wonders.json` (the rift), `sites.json` (the `rift` site and its `rift_depths` dungeon style), `towns.json` (the encampment style), `economy.json` (contract pay), `travel_events.json` (a `picture` for each event) |

Each new kind is registered in `schemas.DATA_FILES` (and `PACK_ONLY`), gets a `Tables` attribute
(`tables.threats`, `tables.adventures`, `tables.villains`, `tables.beats`, `tables.reading`, `tables.legend`,
`tables.ambitions`, `tables.happenings`, `tables.situations`, `tables.lives`, `tables.scenes`, `tables.marks`,
`tables.assaults`, `tables.work`), cross-references in `registry.check_cross_references` (creature ids, groups,
sites' styles, beat ids, step kinds, selectors, ops, condition keys), and its text floors in
`tests/test_text_variety.py`.

A blueprint, abridged:

```json
"the_risen": {
  "tiers": [1, 3], "from": ["risen"], "flavours": ["ghost", "gothic"],
  "needs": {"home_depth_min": 2},
  "title": ["The {villain_short} Wakes", "Ashes over {town}", "The Crown of {villain_short}"],
  "places": {
    "home": "threat.home",
    "town": "settlement_near(home, 0, 6)",
    "lore": "settlement_with(temple, 12, 40) | settlement_great(10, 60)",
    "anchor": "hidden(2, site_of_figure(villain.slayer), scar_of(villain), site_style(crypt|temple, 6, 30))",
    "ford": "scar_of(villain) | road_tile_near(town, 2, 8)"
  },
  "cast": {
    "patron": {"pick": ["priest_of(town)", "headman_of(town)", "lord_of(town)"]},
    "allies": {"count": [1, 1], "pick": ["kin_of_victim(town)", "hero_at_inn(town)", "veteran_of(town)"]},
    "rival": {"chance": 0.5, "pick": ["hero_band(tier)", "glory_hunters(tier)"], "from_part": "F"},
    "lieutenants": [{"as": "waker", "pick": ["necromancer", "cultist", "grave_robber"]},
                    {"as": "champion", "pick": ["risen_guard"]}],
    "innocent": {"pick": ["child_of(town)", "settlement(town)"]},
    "traitor": {"chance": 0.2, "from": ["patron"], "as": "waker", "from_part": "F"}
  },
  "hidden": {"anchor": "places.anchor", "weakness": "villain.true_name", "last_stand": "home.deepest"},
  "chapters": [
    {"id": "taken", "need": "all", "title": ["The Taken", "The Dead Do Not Rest"],
     "steps": [
       {"kind": "witness", "who": "innocent.kin", "gives": ["lead:home"]},
       {"kind": "search", "at": "town.outskirts", "optional": true, "gives": ["clue:waker"]},
       {"kind": "rescue", "who": "innocent", "at": "home.level(1)", "fails_to": "bury"}],
     "set_piece": "rescue", "reveal": "reveal_villain"},
    {"id": "binds", "need": 2, "title": ["What Binds Him"],
     "steps": [
       {"kind": "learn", "about": "villain", "routes": ["sage(lore)", "library(lore)", "legends", "speak_dead(ford)",
                                                      "divine"], "gives": ["key:true_name", "key:side_door", "clue:anchor"]},
       {"kind": "fetch", "what": "anchor", "at": "anchor", "gives": ["key:anchor"]},
       {"kind": "defeat", "who": "lieutenant.waker", "alive_ok": true, "gives": ["clock:-1", "clue:anchor"]},
       {"kind": "recruit", "who": "ally.0", "optional": true, "gives": ["key:ally"]},
       {"kind": "choose", "beat": "risen_truth_of_hodd", "gives": ["flag:told_the_truth|flag:kept_the_secret"]}],
     "reveal": "villain_wrath"},
    {"id": "ford", "need": "all", "title": ["The Night at the Ford"],
     "steps": [
       {"kind": "rally", "at": "town", "need": 3, "optional": true, "gives": ["key:militia"]},
       {"kind": "hold", "at": "ford", "when": "new_moon|days(10)", "waves": 3, "gives": ["key:ford_held"],
        "fails_to": "doom_stage"},
       {"kind": "finale", "at": "home.deepest"}]}
  ],
  "finale": {"boss": "villain", "with": ["lieutenant.champion", "minions(wights)"], "phase": "barrow_wakes",
             "keys": {"anchor": ["no_legendary_resistance", "rite_allowed"], "true_name": ["frightened(1)"],
                      "ally": ["ally_fights"], "ford_held": ["minions(-50)"], "side_door": ["surprise"]}},
  "endings": [
    {"id": "laid_to_rest", "if": ["rite_done"],
     "ops": [["lay_barrow", "home"], ["lay_scar", "villain"], ["figure_rests", "villain"], ["danger", "home", -1],
             ["fame", 5], ["history", "laid_to_rest", 4], ["song", 20]]},
    {"id": "destroyed", "if": ["boss_dead", "key:anchor"],
     "ops": [["figure_rests", "villain"], ["danger", "home", -1], ["fame", 5], ["history", "risen_destroyed", 4]]},
    {"id": "returns", "if": ["boss_dead"], "ops": [["sequel", "returns", 28, 56], ["fame", 3]]},
    {"id": "bargained", "if": ["flag:bargain_taken"], "ops": [["status", "town", "cursed"], ["infamy", 4]],
     "from_part": "E"},
    {"id": "doom", "if": ["scheme_done"], "ops": [["emptied", "town"], ["danger", "home", 2], ["threat_grows", 1]]},
    {"id": "abandoned", "ops": [["threat_free", "villain"]]}
  ]
}
```

A beat, abridged:

```json
"villain_letter_proud": {
  "family": "villain", "where": ["camp", "inn"], "time": "dawn",
  "when": {"attention": [2, 3], "villain.speaks": true, "villain.temper": ["proud", "cunning"], "cooldown": 6},
  "weight": 3,
  "text": ["{letter_found}", "{letter_seal}", "{letter_body}"],
  "choices": [
    {"label": ["Burn it."], "ops": [["flag", "burned_letter"], ["companions", "defiance"]]},
    {"label": ["Keep it. It is in his own hand."], "ops": [["item", "villain_letter"], ["clue", "handwriting"]]},
    {"label": ["Answer it."], "requires": {"item": "paper"}, "check": {"skill": "deception", "dc": 14},
     "success": [["attention", -1], ["clue", "villain_place"]], "failure": [["attention", 1]]}]
}
```

### 8.3 Records in the save

All story records are **JSON-native** (string keys, lists not tuples, no sets), because the save writes them as JSON
and autoplay's `_check_save_round_trip` compares the written form – it cannot see an int key that came back as a
string. A story test compares the loaded records with the ones in memory and asserts JSON-native types.
World-side records need no save code; the new Renown field does (`Renown.to_dict` / its loader).

```
world.politics["threats"]    {"T7": {"id", "kind", "tier", "state", "source": {kind, site|faction|figure, event},
                               "villain": {"figure", "creature", "temper", "goal", "deed", "torment", "anchor",
                               "words"}, "home": {"site"|"settlement"}, "reach": {"x", "y", "r"}, "stakes": [...],
                               "scheme": {"stages": [...], "stage", "since", "next", "held_until"},
                               "lieutenants": [{"figure", "role", "trait", "fate", "grudge", "scars"}],
                               "signs": [ids shown], "offer": {"by", "where", "since"}|null,
                               "adventure": "A3"|null, "born", "ended", "outcome"}}
world.politics["adventures"] {"A3": {"id", "threat", "blueprint", "tier", "title", "state" (active/won/lost/
                               abandoned/orphaned), "hero": {"name", "life"}, "began", "chapter",
                               "cast": {...role: {"npc"|"figure"|"band", "state", "arc", "relation"}},
                               "places": {...name: {"site"|"settlement"|"tile", "level"}},
                               "hidden": {...}, "reading": {...}|null, "chapters": [{"id", "state",
                               "steps": [{"id", "kind", "state", "quest", "target", "optional", "gives"}]}],
                               "clues": {...truth: count}, "keys": [...], "flags": [...], "attention",
                               "moves": [{"day", "move"}], "journal": [...], "ending", "epilogue": [...]}}
                             "life" is death.py's id for a life (the world's id and the character's name) plus
                             renown.flags["start_day"], so two heroes of the same name are told apart.
world.politics["story_sites"] {"12,40/1": [{"adv": "A3", "what": "captive", "role": "innocent"}],
                               "12,40/3": [{"adv": "A3", "what": "band", "roles": ["villain", "champion", "minions"]}]}
                               – keyed by the dungeon key of the level (`world/dungeon`'s "x,y/level"), read when
                               that level is populated
world.politics["story_people"] {"S12": [{"adv": "A3", "role": "ally", "made": {...}}]} – people the forge made, placed
                               when their town is next populated or its travellers refreshed (so forging never builds
                               a town map)
world.politics["happenings"] [{"id", "kind", "settlement", "start", "end", "data"}]
world.politics["director"]   {"hero", "n" (opportunity counter), "tension", "quiet_since", "last_beats": [...],
                               "cooldowns": {...}, "scheduled": [{"day", "beat", "data"}], "pending": {...}|null}
Renown.legend (new field)    {"tier", "epithet", "offered": [...], "lands": [...], "songs": [...],
                               "ambition": {"kind", "binds", "stage", "adventures": [...], "done"},
                               "echoes": [{"day", "tag", "who", "where", "weight", "used"}]}   (titles stay where
                               they are today: renown.flags["titles"])
quest dicts (existing)       + "adventure": "A3", "step": "binds.2" for step quests
creatures and local actors   + "story": {"adv", "role"} on story foes (saved with the actor)
world.politics["situations"] {"Q41": {...}}   (§8.10)
world.politics["contracts"]  {"12": [{"id", "kind", "giver", "terms", "until", "quest"}]}   (by settlement id)
world.politics["assaults"]   {"12": {...}}   (by settlement id; §8.15)
world.politics["land"]       [{"id", "kind", "day", "seed", "shape", "cells"}]; and "land_version" (§8.16)
world.politics["hosts"]      [{"id", "kind", "faction", "group", "strength", "x", "y", "path", "goal", "speed",
                               "since", "state"}]; and "hosts_tick"
world.politics["styles"]     {"57": "encampment"}   (a founded settlement's town style)
world.settlements, sites, wonders   + entries appended while you play (founding; the rift)
politics["director"]         + "scene" (the scene being played), "sky" (a great event's tint)
Settlement.status            + the new marks, each a dict with "since" (§8.13)
NPC.flags                    + "life", "errand", "opener", "flee_to", "closed_until", "visitor"
Town.flags                   + "gathering"; "offers" and "offer_day" no longer written
LocalMap.meta                + "marks" (stamped marks and the cells they changed), "bodies", "decals", "graves",
                               "fire" ({"x,y": [stage, ticks]}), "dark", "land_version"
LocalActor                   + "goal" (saved in to_dict)
Renown.legend                + "favours", "contacts"
```

**Saves**: every part that changes what a save holds bumps `FORMAT_VERSION` (19 with Part A, then once more for each
later part that adds a saved field) and says "a new world is needed" in its notes, as CLAUDE.md requires. Readers
still use `.get(..., default)` for optional keys. The pending beat is kept in the director record, so quitting in the
middle of a beat brings it back on load; a new life clears it (`story.begin`).

### 8.4 Hooks into the game

| Where (today's code) | Call *(new)* | Why |
|---|---|---|
| world creation, in `world/generator.py` right after the ages have made today's records (`world/ages/present.records`) | `threats.seed(world, tables, rng.child("threats"))` | dormant threats from the history |
| `Politics.advance` (after `pressures`) | `threats.advance(self, days)` | schemes move weekly; signs through `world/news.add` (importance ≤2); stage effects through `set_owner`, statuses, `fall`, `die` |
| the `Politics` methods that make gangs (`new_gang`), grow or purge cults (`cult_year`), bring beasts (`beast_comes`), wake dragons (`dragon_wakes`) and start crises (`succeed`) | `threats.seed_from(self, kind, refs)` | new threats while you play (some of these make no history event, so they pass their references directly) |
| `GameState.pass_time`, the day-change block | `story.daily(game)` (with its own catch-up stamp, the `politics["last_tick"]` pattern) | rivals' clocks, allies' arcs, the director's quiet clock, scheduled beats, the step deadlines the story owns |
| same block | move `news.prune` and plague exposure out of `if self.quests:`; run `uniques.daily` without companions | survey quirks |
| `GameState._move_overworld`, before `events.roll_event` | `story.on_travel(game, minutes)` | the Storyteller's travel opportunity; a due beat replaces the random event |
| `encounters.roll_encounter` | `story.overlay(game, x, y)` | a threat's servants on its roads; the chance changes near it |
| `GameState._arrive` (after `quests.on_arrive`) | `story.on_arrive(game)` | `go` steps, the ford's `hold`, rivals met, happenings seen |
| `GameState.enter_local` (after `settlement_troubles`) | `story.on_enter_town(game, settlement)` | town beats, patrons, allies at the inn, happenings' town state |
| `fight.rest` (camp) and the inn's night (`services._night`) | `story.on_night(game, where)` | night visits, dreams, spies, letters at dawn |
| `game/dungeon.populate`, **after** `quests.boss_for` and with precedence over the whole chain (`BOSSES[style]`, `past.boss_for`, the tower master, the deserters) | `story.boss_for(game, lm)` reading `politics["story_sites"]` for this level's key; it returns the full band (boss, lieutenants, minions) as creatures, placed as its own `LocalActor` in the last open room; story boss actors never hunt | named story bosses set before a level is first filled |
| `dungeon.descend` (after `quests.on_arrive_dungeon`) | `story.on_descend(game, lm)` | the level's story features (captive, chest, clue) placed by the story; `go`; the finale's warning and safe room |
| `dungeon.open_chest`, `dungeon.bump`, `dungeon.search` (the Search action) and `search_library` | `story.on_chest`, `story.on_feature`, `story.on_search` | `fetch`, `rescue`, `search`, `learn` |
| `GameState._move_local` (walking into an actor) and `_creatures_act` (an actor reaching you), **before** `fight.start_battle` | when the actor is a story finale band: set `game.finale` (pending; in `busy`) and stop | the boss intro card can still say "Not yet" |
| `fight.start_battle` | `story.finale.prepare(battle, game)` (the `warding.at_the_start` pattern) | keys applied; the boss's phases armed |
| `fight.finish_battle`, after `past.on_battle` and **outside** its `if game.quests:` | `story.on_battle(game, result, actor)` | `slay` by story tag (`result.dead`, `result.captives`, `fled`), escapes, lieutenants' memory, wrath, endings |
| `past.on_battle` | skip creatures with a `story` tag | the story's endings do the history, once |
| the defeat branch of `fight.finish_battle`, before `game.over` is set | `story.on_defeat(game, result)` | defeat as content (taken alive) |
| `fight.decide_captive` | `story.on_fate(game, creature, fate)` | `capture`, "a captive questioned" as a `learn` route, echo seeds |
| `law.commit` | an echo seed for the crime | echoes |
| `quests.reward`, `quests.fail` | `story.on_quest_end(game, q, ok)` | step quests report back |
| `books` reading | `story.on_read(game, item)` | `read` steps |
| the Legends book screen, when a page is opened | `story.on_legends_page(game, kind, ident)` (a screen calling logic) | the `legends` route of `learn` |
| `divining.questions` and Speak with Dead (`game/speech.py`) | adventure truths as answers | magic is a `learn` route |
| `dialogue.role_choices` and `Conversation.choose` | `story.talk_choices(conv)`; a `STORY_CHOICES` dispatch set | witnesses, sages, allies' conditions, accusations, patrons, envoys |
| `reputation.deed` | new keywords `tags=` and `subject=`, recorded by `echoes.seed` | echoes, epithets |
| `companions.react` | new story tags | companions care about the story |
| `people.refresh_travellers`, `quests.daily` | respect `flags["story"]`; place `story_people` | cast people are not moved on or failed |
| `death.die` | `story.on_death(game)` (from Part A: orphan the hero's adventures, clear the pending beat) | orphaned adventures; the villain remembers |
| `interlude.pass_the_years` | nothing new (it runs politics, so threats move; at most one stage each) | |
| creation; the first step of a life | the Ambition step (Part J); `story.begin(game)` (from Part A: resets the director, offers the opening) | the opening |
| `GameScreen._open_event_screen` (after the level-up branch, before `read_board`) | `game.beat` → `BeatScreen`; `game.finale` → `FinaleScreen`; `game.epilogue` → `EpilogueScreen` | pending story screens (`GameState.busy` includes them) |
| `quests.map_marks` / `world_view.draw` | `story.map_marks(game)` | adventure marks; the villain's reach |
| journal `TABS` | `("Adventures", "Work", "People")`; the Work tab leaves out step quests | |
| `notices.notices` | every stirring threat within a week's walk as a hook; happenings | |
| `tools/autoplay.py` | `_check_adventures`, `_check_threats` and the bot's story moves | §9 |

**Hooks of Parts B–K** (the stage, situations, marks, fire, assaults and the world map):

| Where (today's code) | Call *(new)* | Why | Part |
|---|---|---|---|
| `townlife.goal`, first (before the brawl) | errands, gatherings, `flee_to` | the stage; assaults | B, H |
| `townlife.tick` (first) and `townlife.settle` | `stage.tick`, `fire.tick`, `assault.tick`; their `settle`s for long jumps | once per town tick, whether the clock or the player's steps drive it (`town_tick` already runs `_people_act`) | B, H |
| `townlife.tick`, after moving | runners take two steps; an errand's arrival (the item, the opener, `game.talk_to`) | the stage | B |
| `Conversation.greet` | pop `npc.flags["opener"]` and say it first | a scene's words | B |
| `GameScreen.time_flows`, `GameState.move`, the game screen's keys | `game.held`: the town clock runs while a scene holds (even when "Time in towns" waits), moves wait, Space or Escape skips; `busy` is untouched, since `town_tick` stops while busy | scenes play while you watch | B |
| `GameScreen.update`, where `verbosity` is copied | copy `animations` and `experience` onto `game` | logic never reads the settings | B, C |
| `GameState.enter_local`, right after `get_local_map` | `placemarks.stamp`; `local.patch_land` | places that change, before bands and people are placed | B, G |
| `people.prepare_town`, between the map and its people | `placemarks.stamp` | the same for towns made ahead of a visit | B |
| `GameState.enter_local`, after `settlement_troubles` | `story.on_enter_town`: stage a meeting; forge a due situation | situations | C |
| `Politics.sieges`, `take`, `beast_comes`, `dragon_wakes`, `plague`, `famine`, `raid`; `quests.raid_missed` | write statuses through `marks.add` | one door in | B |
| `Politics.expire_status` | `marks.age(self)` | marks age instead of vanishing | B |
| `Politics.regrow` | settlements regrow toward their peak | rebuilding | G |
| townlife's walk grid, `encounters.move_actors`, `GameState._move_local` | the fire mask blocks burning cells | fire | B |
| `LocalView.art_for` and `LocalArt` | `LocalArt.patch(cells)` | burn-outs without rebuilding a map's art | B |
| `fight.start_battle`, after `arena.build`, before `battle.start` | `fire.on_battle_start(battle, game)` | burning fields | B |
| `Battle`, the start of each round | `round_hooks` *(new)*: fire spreads, walls fall, reinforcements enter | fire; assaults | B, H |
| `Battle._check_end` | bands still due keep the fight open | reinforcements | H |
| `combat`, where slashing or piercing damage lands | `Battle.blood` squares | the blood stays | B |
| `fight.finish_battle`, after `_settle_townsfolk` | `remains.after_field` through `Field.origin`; the party stands where its leader stood | the dead stay | B |
| `finish_battle`'s "fled" branch | in an assault: a few streets away, not `leave_local` | assaults | H |
| `encounters.move_actors` | an actor's `goal`; townsfolk block bands | assaults | H |
| `economy.shop_spec`, `services` | no trade in a burnt shell or from a shut shop | burned towns | B |
| `describe.settlement_line`, `settlement_troubles`, `people.town_moment`, `Town.description` | the marks' words (beast and tribute too) | words follow sight | B |
| `quests.offer_for`, `offers_in`, `quests.talk_choices`, `GameScreen._think_of_work` | no weekly offers; no "Is there any work?"; contracts, commissions and situations' own choices; and what leans on the offers today (the bot, rank trials, fence work, the hint and help lines, tests: §8.10) | quests reborn | C |
| the seventeen builders in `quests.py` | split into a picker and `make(game, giver, target, rng)` | situations and contracts give the target | C |
| `quests.board_bounties` | real beasts and threats' servants too; a threat's bounty opens its hook | | A, C |
| `people.populate_town`; where `npc.profile` is written | `lives.ensure`; a story person takes the place of the generated one of their job; the profile written from the life | lives | C |
| a conversation's end, `finish_battle`, `fight.decide_captive`, `law.commit`, items changing hands, entering and leaving towns and buildings, `story.daily` | `goals.notify(game, kind, ...)` | situations recognise the ways through | C |
| `fight.finish_battle`'s experience; the Settings screen | `game.experience`; `xp_story` | experience from stories | C |
| `story.on_death` | live situations drop their quest dicts and go back to `latent` | quests die with the hero; stories do not | C |
| `story.daily` | `lives.week`, `work.renew`, situations' clocks; `hosts.advance` | | C, G |
| `Politics.advance` | `hosts.advance` (by its own stamp) | hosts move in the interlude too | G |
| `WorldPainter` and `ChunkCache` (`ui/gfx/paint.py`); the chunk and overview `Image` keys | `refresh(cells)`: only the chunks touched are queued again, on the thread; a version per chunk in its key | repainting what changed | G |
| `WorldView.draw`, after the settlements | `mapsigns.draw` | signs; hosts, washes, the camp | B, G |
| `GameState._biome_remap`, `_cost_cache`, `_remaps` | reset by `game.land_changed()` | travel and maps follow the land | G |
| `world/wonders.SHAPERS`; `world/dungeon.style_for` | `"rift"`; the `rift` site's `rift_depths` style | the rift and its depths | G, K |
| `plan.style_for`, `worldview.town_mark` (each gaining a `world` argument) | `politics["styles"]` first | founded camps | G |
| `encounters.roll_encounter` | hosts near the party | hosts | G |
| `news.faction_place` | a host's place | | G |
| `daylight_tint`, LocalView's `_light`; the `GameScreen` frame | the sky's tint; `game.shake` | great events | K |
| `tools/autoplay.py` | `_check_situations`, `_check_marks`, `_check_assaults`, `_check_land`, `_check_hosts`, `_check_founded`; nobody on a burning cell | invariants (§8.9) | B–K |

**The populate-once rule.** A dungeon level is built and populated once. So an adventure binds what it needs to the
exact level when it is forged (`story_sites`, keyed by the level's dungeon key), and uses only levels not yet
populated – or appends its actors to a populated level as a `LocalActor` (as `populate` does) and places its features
on arrival.

**Named foes.** A story creature carries `story = {"adv", "role"}` *(new field on spawned creatures, saved with the
actor)* besides `name` and `named=True`; `story.on_battle` reads `result.dead`, `result.captives` and the fled for
those, so nothing depends on matching names.

### 8.5 The generator and the steps

**Forging an adventure** (`forge.make(game, threat, blueprint, hook)`, seeded `rng.child(f"adventure/{aid}")` – keyed
by the new adventure's id, so a second adventure on the same threat does not replay the first):
1. Check that the blueprint fits the threat, its tier and its place, including its `needs` (a barrow deep enough);
   every selector must resolve, else try the next blueprint.
2. **Places** first, by selectors, with distance bands, at least one place the player has never seen, and no two
   chapters in the same place unless the blueprint says so.
3. **Cast** each role by its `pick` list, in order (picks may name places: `priest_of(town)`), from the world first
   (`cast.find`); else make the person (a figure through `factions.make_figure`, an NPC recorded in `story_people` and
   placed when the town is next populated – forging never builds a town map).
4. **Hidden variables**: choose among the candidates and store them.
5. **Chapters and steps** from the blueprint's slots (`tier_min` for the bigger tiers); each step's `bind` turns its
   spec into a target; clues are placed so that every truth has three routes; codewords listed. The content rule
   (§5.2) is checked here too.
6. **Scale**: the tier's target level; budgets for the set pieces and the boss (the DMG budget, the boss template),
   checked against the two fairness bounds.
7. **Bind sites**: write `story_sites` for every level that holds a story foe or thing.
8. **Words**: the title, the hook, the chapter titles, the journal lines (kept once written).
9. Store the record; mark the threat engaged; clear its offer.
Forging takes under 50 ms on a medium world and never blocks a screen.

**The selector language** (a small grammar, parsed once at start-up by `story/check.py`):
- a **selector** is `name(arg, ...)`; arguments are place names already bound in this blueprint (`town`, `home`),
  role paths (`villain.slayer`, `lieutenant.waker`), numbers (distance bands in tiles: `lo, hi`), and `|`-joined style
  words;
- `a | b` tries `a`, then `b`;
- `hidden(n, a, b, c)` binds a hidden variable: it resolves up to `n` candidates from the alternatives and picks one
  as the truth;
- a place path may name part of a place: `home.level(1)`, `home.deepest`, `town.outskirts` (a tile on the town's edge),
  `town.inn`.

| Selector (Parts A and F) | Resolves to |
|---|---|
| `threat.home` | the threat's home: a site (lair, barrow, hideout) or a settlement |
| `settlement_near(ref, lo, hi)` | the nearest settlement whose distance from `ref` is within the band |
| `settlement_with(temple, lo, hi)` | a settlement whose kind has a temple (data/towns.json) within the band |
| `settlement_great(lo, hi)` | a great city within the band |
| `site_style(style|style, lo, hi)` | a site of one of those dungeon styles within the band |
| `site_of_figure(path)` | where a figure lies (`buried`), lived (`home` "X5") or died (`died_at`), if a site |
| `scar_of(path)` | the haunted battlefield of the figure's death (`politics["scars"]`) |
| `road_tile_near(ref, lo, hi)` | a road tile within the band (for a field set piece: a ford, a bridge) |
| `lair_of(path)` | the lair site of a beast figure (`politics["lairs"]`) |
| `hideout_of(faction)` | a gang's site |
| people: `priest_of`, `headman_of`, `lord_of`, `kin_of_victim`, `hero_at_inn`, `veteran_of`, `child_of`, `notable_of`, `fence_of` | the notable of that job in the settlement; a figure of the history with a fitting tie; else made |

**A step kind** is a small class registered by id (`@step("fetch")`), with: `bind(forge, spec) -> target`,
`setup(game, adv, step)` (makes its quest dict, records its feature or band in `story_sites`, adds its dialogue
topic), `journal(game, adv, step)`, `marks(game, adv, step)`, the listeners it answers (`on_battle`, `on_fate`,
`on_arrive`, `on_talk`, `on_search`, `on_read`, `on_item`, `on_day`), `done` / `failed` (with `fails_to`), and
`repair(game, adv, step)`: when its target vanished (a town emptied by politics, a person dead), it rebinds or turns
into its failure branch, so no adventure is ever stuck (law 6).

**Which part builds which step kinds**: Part A – go, search, witness, read, learn, prepare, choose, slay, finale;
Part D – rescue, fetch, defeat (slay or capture), capture, recruit, rally, hold, rite, escort, confront; Part E –
endure; Part F – deliver, infiltrate; later blueprints add their own when they need them. `hold` is a set of waves:
successive battles at the place (a settlement, or a road tile laid out by `game/arena.build`), each started from the
last one's aftermath with no rest between, on a set night said in the journal.

### 8.6 The beat language and the consequence language

**Beat conditions** (a whitelist; `story/check.py` reports unknown keys at start-up): `where` (road, wild, town, inn,
camp, dungeon, a settlement kind), `time`, `season`, `adventure` (blueprint, chapter, step state), `attention`,
`tension`, `legend`, `infamy`, `villain.*` (temper, speaks, kind), `cast.*` (role bound, alive, joined, relation),
`party.*` (size, a companion with a value, money, an item), `flag` (a codeword), `echo` (a seed of a tag, its age),
`happening`, `threat_near` (kind, stage, distance), `standing` (a faction), `cooldown`, `once`, `chance`.

**Beat ops** (a whitelist): everything `events.apply_outcome` does today (`text`, `items`, `money`, `loot`,
`fatigue`, `effect`, `deed`, `news`, `xp`, `hurt`, `time`, `fight`, `ambush`) plus `clue`, `key`, `flag`, `step_done`,
`step_add` (insert a step: a rescue, a revenge), `attention`, `clock` (move the scheme), `tension`, `ally_joins`,
`ally_leaves`, `betray`, `kidnap`, `frame` (`law.commit` with false witnesses), `reprisal` (a helper NPC dies or
vanishes, news), `invite` (safe conduct: no encounters on the way), `visit` (the villain's scene), `named_fight` (a
story foe's encounter), `item` (a letter, a gift, a token), `standing`, `disposition`, `remember` (history), `fame`,
`infamy`, `status` (a settlement's), `schedule` (a follow-up beat in N days), `epithet_offer`, `title`, `companions`
(a react tag). An op with a number is clamped by data limits (no beat gives more than its tier allows). **Each part
adds the conditions and ops its own content uses** (Part A the first set, listed in its tasks); "the beat language in
full" in Part I only completes the list.

**Consequence ops** (the endings' whitelist, applied by `story/endings.py` through the world's own systems):
`clear_site`, `figure_dies` (through `Politics.die` for figures with a post, so successions run), `figure_rests` (a
risen figure laid down), `beast_slain` (through `past.beast_slain`), `faction_falls` (`Politics.fall`), `set_owner`,
`succession`, `relation`, `law`, `status` (add or lift), `emptied` (a settlement's people fall to a floor of
survivors; `emptied` status), `rebuild`, `ruin` (Part G: a settlement ruined in full), `danger` (a region's),
`lay_barrow` (`politics["laid"]`), `lay_scar` (`scar["laid"]`), `monument`, `rename`, `song` (a work by a bard figure
after N days), `relic` (where an artifact goes), `title` (`reputation.grant_title`), `land`, `right`, `standing`,
`fame`, `infamy`, `history` (`history.remember` with a kind and importance), `news`, `sequel` (a new threat: returns,
heir, lieutenant), `threat_grows` (once), `threat_free` (the threat goes on without an adventure), `ally_fate`.

**Endings** are an ordered list: each has an `id`, an `if` (a list of ending conditions, all of which must hold) and
`ops`; the first that matches wins, and the last has no `if` (the default). Ending conditions: `boss_dead`,
`boss_fled`, `rite_done`, `key:<k>`, `no_key:<k>`, `flag:<f>`, `step_done:<id>`, `scheme_done`, `hero_dead`,
`abandoned`, and for situations `way:<kind>` (how a goal was reached). An entry may say `from_part` (it is skipped
until that part is built).

**Checks**: a beat's skill check goes through `Conversation.check` when a person is speaking (attitude, Glibness,
Portent and the rest apply) and through `camp.check` otherwise (Portent and the Battle Master's `check_die` already
hook it).

**Finale keys** (one list for data and code): `no_legendary_resistance`, `legendary_resistance(-n)`,
`vulnerable(type)`, `frightened(rounds)`, `ally_fights`, `rival_arrives(round)`, `minions(-percent)`, `surprise`,
`party_buff(buff)`, `no_escape`, `no_phase_two`, `rite_allowed`, `lieutenant_absent(role)`.

**Ops and conditions of Parts B–K.** Beats, situations and endings also take `scene` (play a scene, §8.11), `letter`
(give a letter and show its page), `mark` (add, lift or move a mark on a place, §8.13), `body` and `grave`, the people
ops of §8.10 (`npc_fate`, `tie`, `favour`, `contact`, `xp_story`, `shop`, `move`), `assault` (schedule one, §8.15),
`host` (raise a host), `reshape` (a land change through the ledger; `land` already names land granted to the hero),
`found` (a settlement or a site, §8.16), and `sky` and `shake` (great events, §8.12); `status` becomes another name
for `mark`, so there is one way to touch a place. Beat conditions gain `mark` (a place's), `situation` (a predicament,
a role bound, a state), `life` (a tie, a want, a secret) and `scene` (one played).

### 8.7 Screens, pictures and sounds

- **Beat screen** (`ui/screens/beat.py`): a parchment panel like the event screen, with a picture (the villain's
  doll, the place's scene, a card face), several pages, numbered choices with their checks and costs, the result,
  Continue. Chapter openings show a **title card** ("Chapter II – What Binds Him") with a sound (`chapter`) and the
  music mood `story/omen` behind it. `autoplay_keys` picks choices.
- **Boss intro card** (`ui/screens/finale.py`): the boss's figure large, its name and epithet, its first words, the
  "What you know" list (keys ticked, unknowns as question marks), "Fight" / "Not yet". Music `boss`.
- **Epilogue** (`ui/screens/epilogue.py`): one page per fate, a picture for each (the place's scene, the person's
  doll), "Continue"; the last page is you and your new Legend, with the `legend_up` fanfare if it rose.
- **Journal**: the Adventures tab (§5.14); the chapter list with ticks; the cast as small dolls (the villain a dark
  silhouette until met); the scheme clock as marks; clues and keys.
- **Map**: marks for adventure places (`sprites.json` map marks: a story mark, a sign mark), the villain's reach as a
  faint wash once known.
- **Sheets**: a Legend page (tier, epithet, titles, lands, songs sung of you, the ambition's stages).
- **Pictures** to draw (`tools/tile_art.py`): map marks, the Wayfarer's Deck's twenty card faces (small, painted in
  the game's style), title-card frames, a few beat backdrops (a camp at night, a hall at dinner, a crossroads).
- **Sounds and music**: `chapter`, `reveal`, `sign`, `villain`, `legend_up` (tools/build_sounds.py, CC0 packs); moods
  `story/omen`, `story/finale`, `story/epilogue` in data/music.json (the player's own music folders work for them too).
- **Parts B–K** add the pictures of §8.12 (the vignette composer, the title card as its own screen, letters as pages,
  epilogue vignettes, boss entrances) and the art of §8.17.

### 8.8 Words

All text is written into the game (CLAUDE.md). The story needs more words than any expansion so far, and words are
where it will live or die:
- **Nested tables.** Unlike quest text today (`textgen.fill(..., tables={})`), story text uses textgen's nested
  tables (`{letter_seal}` -> "sealed with black wax, pressed with {sigil}"), so that a family of beats reads
  differently every time.
- **Real names everywhere.** Every text slot that can be a real person, place, battle, year or relic is one:
  `figure.full_name()`, `past.beast_title`, `site_past`, a battle's name from the history, a work's title.
- **Variety floors** in `tests/test_text_variety.py` for every family: each beat ≥3 intros; each blueprint ≥3 titles,
  ≥3 hooks, every chapter ≥2 titles and ≥3 reveal lines; each villain temper ≥6 first-word lines and ≥8 omens; each
  epilogue page kind ≥4; each card ≥3 riddles for each of its meanings; epithets ≥6 per tag.
- **The voice**: grounded, concrete, period-appropriate, no modern slang, no stock phrases (DESIGN.md §3.7), and
  never the books' prose (EXPANSIONS.md §1.5). Only the extra flavour lines of signs and omens are behind Text
  detail; the sign itself (its news, the journal's clock, the encounter it brings) always shows (law 7).
- Written once and kept: an adventure's title, hook, journal lines and epilogue are written when first needed and
  stored in its record.
- **Situations** are where words multiply: each predicament ≥3 lines for every meeting kind it can use and ≥3 for
  each of its endings; each obstacle ≥3 ways of being described; each mark ≥4 arrival lines and ≥6 barks; each scene's
  lines ≥3 variants. Journal lines are the hero's own notes (§5.17), never objectives.

### 8.9 Determinism, performance, safety

- Streams: `rng.child("threats")`, `rng.child(f"adventure/{aid}")`, `rng.child(f"beat/{n}")` (with `n` the director's
  saved opportunity counter), `rng.child(f"villain/{aid}/{day}")`, `rng.child(f"reading/{aid}")`. Same seed and same
  choices, same story.
- Budgets: seeding threats adds under a second to world creation on a large world; `threats.advance` under 5 ms a
  week; the director under 5 ms an opportunity (beats indexed by family and `where`); forging under 50 ms; nothing
  scans per frame.
- **Never stuck**: every live step has a target that exists and can be reached, or a `repair`; autoplay checks it.
  **Never unwinnable**: the forge checks the boss with every key against the "high" bound at the tier's target level.
  **Never spammy**: at most one villain move every two days, one story beat per opportunity, and the Storyteller's
  cooldowns per family.
- **Autoplay's invariants and the story**: a doom never takes a settlement's population to 0 (a floor of survivors);
  an emptied or doomed settlement keeps a realm as its holder (a dread lord's seat, later, is a status, not an owner
  change, until Part G designs it); a risen villain's figure is dead by nature, so the invariant is "no villain of an
  ended threat still acts"; step quests carry a template, a deadline and a town, as `_check_quests` demands.
- Streams of Parts B–K. `RNG.child` depends only on its path, so every stream names what makes it unique:
  `rng.child(f"situation/{qid}")`, `rng.child(f"life/{npc}/{week}")`, `rng.child(f"scene/{n}")` (the director's
  counter), `rng.child(f"marks/{sid}/{mark}/{since}")` (a stamp restored and stamped again is the same; a second fire
  years later is not), `rng.child(f"fire/{key}/{tick}")`, `rng.child(f"assault/{sid}/{since}")`,
  `rng.child(f"land/{id}")`, `rng.child(f"host/{id}/{day}")`, `rng.child(f"found/{sid}")`.
- More invariants for autoplay: a stamp never breaks `check_works`; no townsperson and actor on one square; every
  assault has its settlement, and a live assault is on the current map or resolving; the land ledger replays; every
  founded settlement has a realm holder and people; every live situation's town exists and its people exist or have a
  repair; no errand on a dead person.

### 8.10 Situations, lives, favours and paid work (Part C)

**The situation record** is world-side, like an adventure, so an unfinished one outlives the hero who met it:

```
world.politics["situations"] {"Q41": {"id", "town": 12, "root": {"kind": "life"|"threat"|"politics"|"happening"|
                               "echo"|"faction"|"history"|"land"|"companion"|"adventure", ...refs},
                               "predicament": "gone_where_they_should_not",
                               "roles": {...role: {"npc"|"figure"|"band"|"faction"|"place"}},
                               "stakes": {...}, "clock": {"due": day, "what": "the_raid"},
                               "goals": [{"id", "test": [...], "ending"}], "obstacles": [{"kind", "at", "ways": [...],
                               "state"}], "turn": {"kind", "state"}|null, "meeting": {"kind", "scene", "state"},
                               "state", "ways": [{"goal", "way", "day"}], "adventure": "A3"|null, "threat": "T7"|null,
                               "ending": null, "made": day, "words": {...}}}
```

Its states: `latent` (made; its meeting waits for the hero to be near) → `met` (seen: it is in the journal) → `taken`
(the player acted on it) → `done` / `failed`, or `lapsed` (the clock ran out without the player, and **the world's
own outcome happened**: the boy rode with the gang and died in the raid, and his grave is by the temple – law 7).

**Forging** (`situations.make(game, town, root=None)`, seeded `rng.child(f"situation/{qid}")`, under 20 ms):
1. **A root.** The Storyteller asks for a situation when a town within reach of the hero (30 tiles, the reach of life
   events) has none live, its gap (10–20 days, data) has passed and fewer than three are live within reach.
   Situations are forged only in towns that already have their people – visited, or prepared by a story – so
   forging never builds a town map; a town entered for the first time is a natural moment (`story.on_enter_town`).
   Candidate roots are gathered from that town: its lives' events marked as story
   seeds, the threats whose reach covers it (their current signs), its marks and the realm's wars, a happening, an
   echo seed, the goals of factions present, the history (a grudge's next death, an artifact's heir, a scar's dead),
   the land, a companion's past. Each root kind lists the predicaments it can make (`situations.roots.json`).
2. **A predicament** that fits the root and can be cast here (its `needs`: a watch for "an innocent accused", a
   temple for "a rite that must be done"), weighted down by what this hero has already met (§9, the variety score).
3. **Roles bound to real people**: the root's people first; then the adventure selectors (§8.5) that fit (`notable_of`,
   `kin_of`, `rival_of`, `creditor_of`...); a kin who is only a name in a life becomes an NPC now (`people.make_npc` and
   `people.add`). A role in a town not yet peopled is bound to a figure or a faction, or recorded in `story_people`;
   when that town is populated, the story person takes the place of the generated person of the same job (never two
   millers).
4. **One to three obstacles** from the predicament's list, placed where the roles are, each with its ways through.
5. **At most one turn** (by chance, data); some need things (the culprit you once helped needs an echo seed).
6. **The meeting**: a meeting kind that fits the town and the predicament, played as a scene (§8.11) the next time
   the hero is in the town – or on the road, for a body in the river or smoke seen from a hill.
7. **Stakes and a clock** in the world's terms (a day of the calendar, a caravan's departure, the next stage of a
   threat).
8. **Endings**: two to four, each a list of consequence ops (§8.6, with the people ops below), at least one bitter or
   mixed.
9. **Words**, written once and kept (the meeting's lines, the journal's notes, each ending's line).

**Goals: the predicate language** (`game/story/goals.py`; a whitelist checked at start-up by `story/check.py`, like
the beat conditions): `alive(r)`, `dead(r)`, `at(r, place)` (a building, a town, a site), `with_party(r)`, `free(r)`
(not a captive, not held by the law), `holds(r, thing)` (an item kind, or a story item by id), `gone(r)` (moved away,
fled the town), `married(r, s)`, `owes(r, s)`, `knows(r, truth)`, `law_state(r, state)` (accused, pardoned, hanged),
`standing(faction, op, n)`, `status(place, mark)`, `cleared(place)`, `faction_active(f)`, `flag(f)`, `day(op, n)`;
combined with `all`, `any` and `not`. Roles and places are the forge's paths (`home_of(asker)`).

**When the hero dies**, live situations lose their quest dicts (quests die with the character) and go back to
`latent`, keeping their clocks: the next hero may meet them, or find them lapsed.

**Listening.** Whenever something happens that could change a predicate, the live situations within reach are tested
again: when a conversation ends, after `finish_battle`, `fight.decide_captive` and `law.commit`, when an item changes
hands (giving, trade, theft, loot), when the party enters or leaves a town or a building, and in `story.daily`.
`goals.notify(game, kind, **refs)` is the one call; each situation keeps the event kinds its predicates read
(`listens`, worked out at forging), so a test runs only when it can matter (under 0.2 ms each, with at most three
live within reach).

**Ways through are recognised, not scripted.** The event that made a goal true is recorded with its **way**: `talk`
(a conversation's outcome), `pay`, `sneak` (the law's sneaking rules, unseen), `steal`, `force` (a lock forced, a door
broken), `fight` (a battle won), `magic` (a spell's outcome: a charm, Knock, Suggestion, Detect Thoughts), `law` (a
petition, a pardon), `favour` (one spent), `companion` (a companion's skill), `wait`. Endings may test the ways used
(`way:<kind>`, an ending condition), so the same goal reached by talk or by blood ends differently in the world and
in its line. An obstacle is mostly something the game already has – a lock, a guard of the watch, a price, a person's
attitude in `Conversation`, a deadline – and data names where it stands, what makes it pass (a predicate or an event:
`door_open`, `attitude >= friendly`, `paid(40gp)`) and the choices it adds to the right person through
`story.talk_choices`. The offered ways are only the ones the game foresees; any other way that makes the predicate
true counts the same.

**Turns** are data: when one fires (on meeting, on taking, at the first goal reached, at half the clock), what
changes (a role rebinds, a goal is added or struck, an obstacle appears, a codeword is set, a scene plays), and the
tell placed beforehand so the attentive player can see it coming (an Insight check, a second witness, a letter).

**Situations inside adventures.** A step may name a predicament (`"situation": "truth_buried"`); the forge then binds
the situation's roles to the adventure's cast and its goal to the step (the step is done when the situation is), and
the situation's meeting is the step's scene. That is where adventures get their variety (§5.16). Step kinds and
situations share the goal predicates: Part D's `rescue`, `fetch` and `recruit` are written on top of them.

**People ops** (for situations' endings, and for beats and adventures alike): `npc_fate` (alive, gone, married,
ruined, jailed, dead – through the people code, never by flags alone), `tie` (make or break a tie in a life), `grave`
(a fresh grave in the town's graveyard, §8.14), `mark` (§8.13), `favour`, `contact`, `xp_story`, `shop` (open or shut
a trade: `npc.flags["closed_until"]`), `move` (someone moves to another town).

**Lives** (`game/story/lives.py`, `lives.json`). A life is kept on the person (`npc.flags["life"]`, saved with the NPC,
JSON-native): `{"ties": [{"kind": "son", "name": "Ivo", "npc": 813|null, "state": "alive"}], "want", "fear", "secrets":
[{"kind": "debt", "to": ..., "known": false}], "things": [{"kind": "heirloom", "item": ...}], "events": [{"day",
"kind"}]}`. Lives are made lazily: `lives.ensure(game, town)` runs from `people.populate_town` (and on entering a
populated town that lacks them) for the notables and up to twelve others, from data (ties by job, age and household;
wants and fears by job and traits; secrets by traits, wealth and the cults' hidden members; things by wealth). The
words townsfolk carry today (`npc.profile`'s want and secret) are written from the life, so there is one source.
**Life events** run weekly for towns within 30 tiles of the hero (`lives.week`, from `story.daily`; at most three a
town): a debt due, a sickness (more in plague), a son taken by the levy in war, a death of age, a marriage, a birth,
a theft, a quarrel, a love found out. Each has conditions on the life and the world, effects that play out by
themselves and show (mourning dress: a `mourning` outfit; a shop shut with a sign; a new grave; a christening crowd
at the temple through the stage), and a chance to become a situation's root.

**Favours and contacts** (`game/story/favours.py`; kept in `Renown.legend["favours"]` and `["contacts"]`). A favour is
`{"from": npc, "weight": 1-3, "kind": "word"|"shelter"|"door"|"goods"|"sword", "day", "used": false}` and is spent as
a way through any obstacle that lists `favour` and lies within the giver's reach (their town, their faction, their
trade). A contact is `{"npc", "kind": "informant"|"fence"|"smuggler"|"healer"|"scholar", "since"}`: they send word
(a runner when you come to their town, a letter carried by the news), deal at night, and warn you when the law has
your description. Both are listed in the journal's People tab.

**Story experience.** The `xp_story` op gives experience by the encounter budgets the game already uses for the
party's level: a situation's ending a "medium" budget (×1.25 for a way through without a fight), a chapter a "high"
one, a finale its fight's experience and a bonus. A setting **Experience** ("both", the default, or "stories"; in the
Settings screen, copied onto `game.experience` every frame as `verbosity` is – logic never reads `config.py`) can make
fights give none (the DMG's milestone style): the XP line of `fight.finish_battle` reads `game.experience`.

**Paid work** (`game/story/work.py`, `work.json`):
- **The weekly offers stop.** `quests.offer_for` no longer rolls offers; `offers_in` and `GameScreen._think_of_work`
  go (and with them the daily `prepare_town` of far towns, a survey quirk); `quests.talk_choices` no longer adds "Is
  there any work?". Someone with a contract, a commission or a role in a situation has their own choice instead
  ("About the caravan to Kessa", "Your son"). `Town.flags["offers"]` and `["offer_day"]` are no longer written. What
  leans on the offers today moves with them: the bot takes work only through `offer_for` (`tools/autoplay.py`); rank
  trials (`quests.mark_trial`) and fence work (`shadows.guild_work`) ride on offers and become commissions; the
  first-day hint and the help and journal lines that say "ask 'Is there any work?'" (`state.py`, `help.py`,
  `journal.py`) are rewritten; and the tests that look for work (`test_first_hour.py`, `test_app_ui.py`,
  `test_followers.py`) look for situations and contracts instead.
- **The builders are split.** Each of the seventeen builders picks its own target today (`_rescue` a random gang
  within 22 tiles and an invented captive; `_escort` a random traveller and destination; `_defend` refuses cities).
  Each becomes two halves: a picker (today's choice, kept for anything that still wants a random target) and
  `make(game, giver, target, rng)`, which builds the quest dict for a target it is given. Situations, contracts and
  steps call `make`; the listeners stay as they are.
- **Contracts** (`politics["contracts"]`, keyed by settlement id: `[{"id", "kind", "giver", "terms": {"pay", "days",
  "route"}, "danger", "until", "quest"}]`), one a town (two in a city or a great city), renewed every 14–28 days by
  `work.renew` from what the town really has: its trade and roads (guard a merchant's goods to the next market town,
  carry goods), its faiths (escort pilgrims to a shrine), a village's known raiders (`defend`). Each names a real
  danger on its way, chosen from what is within reach (a threat's servants, a gang's ambush, the wolves of a lair), so
  that a contract too touches the world and can turn into a situation (rules 2 and 5 of §5.15). They build through
  `make` for `escort`, `deliver` and `defend`, show their terms, and pay by `base_quest`'s formula, so incomes stay
  where they were. The muster and the levy wait for Under the Banner (Part K).
- **Bounties** stay on the board (`board_bounties`: today one per gang within 30 tiles; now also beasts with lairs and
  threats' servants), paid by the watch; a bounty on a threat's villain or lieutenant is that adventure's hook.
- **Commissions** come from the factions the player has joined, made from each faction's `goals` (strings today, data
  keys from Part C: `expand`, `revenge`, `purge`, `wealth`, each with commission kinds), and the rank trials stay.

### 8.11 The stage (Part B)

**Scenes** (`game/story/stage.py`, data `scenes.json`) are records, one at a time, kept in
`politics["director"]["scene"]` = `{"id", "kind", "map": key, "cast": {role: npc id | actor id | "you"}, "i" (the cue
being played), "t0", "hold", "state"}`. A scene is asked for by a situation's meeting, a beat (`scene` op), an
adventure's step, a happening or the director's `on_enter_town`; it starts only on the map the player is on, when
nothing is busy, with a cooldown per town.

**Driving.** On a town map the stage advances inside townlife's own loop: `townlife.tick` calls `stage.tick` first,
so a scene moves once per town tick whether the town clock or the player's steps drive it (`town_tick` already runs
`_people_act`, so nothing may be called from both), and `townlife.settle` – a jump of more than forty ticks – calls
`stage.settle`, which plays the scene to its end. While a scene holds, the player's keys wait (`game.held` *(new,
not saved)*: `GameState.move` refuses, and the game screen reads only Space and Escape, which call `stage.skip`), but
`busy` is left alone – `town_tick` does nothing while busy – so the town clock keeps running, and `time_flows` is true
while a scene holds even when "Time in towns" waits. The whole town moves while a scene plays; a scene only borrows its
actors. Elsewhere (a wild map, a dungeon level) a scene advances on the player's steps and waits, and at a camp on
the road the camp screen plays the same cues in its picture (the figure steps into the firelight). A cue that cannot
finish (a runner blocked for 40 ticks) skips ahead: a scene never stalls.

**How cues become movement** (the survey's smallest additions, made general):
- `walk` / `run` / `follow` / `flee` set `npc.flags["errand"] = {"to": [x, y] | "you" | npc id, "pace": 1 | 2, "scene",
  "until"}`; `townlife.goal` reads the errand first, before the brawl (for "you", a free square beside the player);
  `townlife.tick` moves a runner two path steps a tick, keeping the swap, side-step and no-overlap rules and
  `PATHS_PER_TICK`.
- `say` / `shout` write through `townlife.speak(game, lm, npc, words, ticks)` *(new)*, which ignores the Text detail
  setting (story words are not flavour) and is drawn like barks; `shout` also goes to the log.
- `give` / `take` move the item (`npc.inventory` and `add_existing`) and set a transient `game.stage_fx` entry (not
  saved) that LocalView draws: the item's sprite between the two figures for half a second.
- `kneel` lowers the figure by a quarter of its height; `fall` and `die` make a body record (§8.14) – `die` also
  kills the person through the people code (`alive=False`, `quests.on_npc_death`).
- `crowd` sets `Town.flags["gathering"] = {"spot": [x, y], "ids": [...], "radius", "until", "murmur"}` (saved);
  `townlife.goal` sends its people to free squares in rings round the spot, and their barks come from the murmur
  table; `disperse` clears it.
- `arrive` makes a person at a gate or the map's edge (`people.make_npc`, `people.add`, `flags["visitor"]`, and
  `flags["placed"]`, or `townlife.place_new` would move them straight beside you), who walks away and is removed when
  the scene ends unless the scene keeps them.
- `door` opens, closes, slams or bars a door (`dungeon.set_terrain`); `bell` plays the `bell` sound with a log line;
  `light` puts lamps out for the scene (`lm.meta["dark"]` cells) or makes a fire flare; `fire` starts a fire (§8.14).
- `focus` eases LocalView's camera to a square and back (`game.camera = {"to", "until"}`, at most three seconds; not
  with Animations off).
- `talk` sets `npc.flags["opener"]` and `game.talk_to`; `Conversation.greet` pops the opener and says it before the
  greeting, and opens the situation's topic. `beat` opens a beat; `fight` starts a battle; `wait` and `hold` pace it.
- When a scene ends, errands and gatherings are cleared and its people go back to their days.

**Eavesdropping, tailing and tracks.** `overhear` places two people at a spot with lines that are said only while the
party is within six squares and sees them; hearing the key line makes `knows` true. `follow` gives the suspect an
errand with a `look_back` DC: every few steps, while the party is within eight squares, a Perception check against
the party's Stealth (the law's sneaking rules); seen, the scene branches (he runs, or turns to face you); lost (out of
sight and fourteen squares away), the cue fails and the obstacle stays. Tracks are decals (§8.14) leading to the map's
edge; following them onto the world map lights the next square (`story.map_marks`).

**Animations off**: `game.animations` is copied from the settings every frame (as `verbosity` is), and with "off"
every movement cue completes at once (the runner is beside you, the crowd stands at the gibbet).
**Saving mid-scene**: the scene record is saved, and on load the scene skips to its end, so it never repeats or
breaks. The townlife speed test (a tick for 250 people under 30 ms) must still pass with a scene of twenty actors.

### 8.12 Pictures for stories (Part B)

- **The vignette composer** (`ui/gfx/vignette.py` *(new)*): `compose(canvas, rect, spec, now)` paints a small scene from
  a spec – a backdrop by kind (street, square, inn room, hall, camp at night, road, ford, barrow mouth, ruin,
  battlefield, burned street, rift's edge, crusaders' camp, a sickroom), the time of day and the weather (the sky
  gradient of `scenes.camp`), props (tile sprites: a gibbet, a pyre, banners, tents, a cart, a grave), figures (dolls
  from the real people's parts: the villain, the patron, the runner, the dead), light (fires, with their glow) and an
  atmosphere (§8.14). Specs are data (a `picture` key on beats, situations' meetings, title cards and epilogue pages,
  and on `travel_events.json`'s events) filled from the story. Backdrops are `Image`s keyed by kind, size and seed and
  cached (the `titleart.landscape` method); figures, fires and mist are drawn each frame, so they move.
- **The beat screen** (§8.7) and the **event screen** gain a picture panel above the text (the
  `DialogueScreen._portrait` pattern).
- **The title card** (`ui/screens/titlecard.py` *(new)*): a vignette of the chapter's first place, panning slowly with
  Animations on, the chapter's number and name in the "title" face and its line beneath, the `chapter` sound; any key
  goes on – it never holds the player longer than they wish.
- **Letters** (`ui/screens/letter.py` *(new)*): a letter, note or order as a page – parchment (code-drawn, cached), the
  writer's hand (two or three OFL handwriting faces in `assets/fonts` and `typefaces.py`, chosen by writer: a villain's
  hand is not a miller's wife's), a wax seal in the writer's house or faction colours, and the line that matters
  underlined once it has been read. Letters are items (`item/sealed_letter` and `item/found_letter` exist) with a
  `letter:<id>` tag naming the text (items have tags, not free data: the pattern of the `quest:<id>` tag), so the page
  opens again from the inventory. A `fig/held/letter` layer lets a
  runner be drawn holding it.
- **Epilogue pages** are vignettes of the places as they now are (burned, rebuilt, a statue in the square).
- **Boss entrances** (battlefx): at a finale's start the boss's name and epithet cross the mat in the "title" face for
  two seconds, with a shake and the `villain` sound; phase two the same, with its line.
- **Great events** (Part K): `game.shake` (a transient: a few frames of offset, read by `GameScreen`) and the sky's
  tint (`politics["director"]["sky"] = {"tint", "until"}`, read by `daylight_tint` on the world map and by LocalView's
  base light in `_light`).

### 8.13 Marks on places (Part B; aging and ruin in full in Part G)

- **`world/marks.py`** *(new, world layer; not to be confused with `rules/engine/marks.py`, the marks spells leave on
  creatures)*: `add(world, s, mark, day, **data)`, `lift(world, s, mark)`, `age(politics)` and `marks_of(s)`, over the
  table in `marks.json`. Marks live in `Settlement.status`: the keys politics writes today keep their values (`sacked`
  and `burned` a day number; `siege`, `plague`, `famine`, `raided` and `beast` dicts; `tribute` a name), and
  `marks.since(s, key)` reads either form; the new marks (`burning`, `rebuilding`, `emptied`, `beset`, `haunted`,
  `cursed`, `occupied`, `festival`, `memorial`, `assault`) are dicts with at least `since`. `siege` stays a war's own
  (autoplay requires an active war behind every siege); a town ringed by a horde or by the dead, with no war, is
  `beset` – the same look, a different cause. Every place that writes a status today (`Politics.sieges`, `take`,
  `beast_comes`, `dragon_wakes`, `plague`, `famine`, `raid`, and `quests.raid_missed`) writes it through `marks.add`,
  so there is one door in.
- **Aging.** `Politics.expire_status` calls `marks.age`, so marks pass into their next stage instead of vanishing:
  burned → rebuilding (after 90–150 days) → gone, sometimes leaving a memorial; sacked → mended or burned; plague →
  mended, with its graves. Durations are data; today's ends of `sacked` (120 days) and `burned` (365) stay as the ends
  of the last stage. **Regrowth**: `Politics.regrow` (which today regrows only military strength) brings a rebuilding
  settlement's people back toward the peak kept in its mark, 1–3% a month, and newcomers are added to its Town at the
  next visit (`people.make_npc`, `people.add`, with lives).
- **Stamping the close-up map** (`game/placemarks.py` *(new)*): `stamp(game, lm, s)` runs in `enter_local` right after
  `get_local_map` (before any band or person is placed: `enter_local` peoples the town before `settlement_troubles`),
  in `people.prepare_town` between making the map and peopling it, and when a mark changes while you are there (then
  people and bands on changed cells step off first). So an unvisited town looks burned the first time you see it. It
  compares `lm.meta["marks"]` – what was stamped, and the cells each mark changed with their old ids (the Passwall
  pattern: `[[x, y, old_id], ...]`) – with the settlement's marks, and applies, re-stamps or restores. A mark's
  dressing (`marks.json`) says which buildings it touches (a share, by kind, nearest a point: the burned quarter round
  where the fire began), what their cells become (wooden floors → `charred_floor`, some walls → `ruin_wall` or
  `rubble`, furniture → ash, doors → `door_broken`), their look (roofless shells: `look["roof"] = "none"`, which
  already draws no roof; charred walls: a `charred` entry in `roofs.WALLS` and in houses' palettes), what it scatters
  (rubble, fallen beams, ash, blood, barricades, banners), what it lights, what it does to the people (mourning, a
  shut trade, a bread queue as a gathering, the conqueror's patrols), and its sounds and music mood.
- **What a stamp keeps true**: buildings are marked, never removed or reordered (their indices are used by homes, inn
  names, trespass, followers and roof seeds); the rules of `tests/test_towns.py` `check_works` hold (the entry, a way
  out, every door reached; the stamp never touches the entry, the road to the edge or a door's approach); after a stamp
  `lm._building_grid` is reset, `townlife.forget()` is called, and posts and homes that fell inside unwalkable cells
  move to the nearest free square. Restoring a mark puts every recorded cell back exactly.
- **Services and words.** A trade whose building is a burnt shell is shut (its keeper sells from a stall, or is among
  the dead): `economy.shop_spec` and `services` check the building's look and `npc.flags["closed_until"]`.
  `describe.settlement_line`, `settlement_troubles`, `people.town_moment` and `Town.description` speak of every mark
  (also beast, which has no words on arrival today, and tribute, which the describe line leaves out).

### 8.14 The fallen, blood, decals and fire (Part B)

- **Decals** (`lm.meta["decals"]`: `{"x,y": [kind, day, variant]}`): blood, old blood, scorch, tracks (with their
  direction), ash, a chalk sign; drawn by LocalView in a new layer after `over` and before objects, fading by age
  (blood 3–6 days, tracks a day or until rain, scorch until its mark changes); at most 400 a map, the oldest first to
  go. Pictures: the unused DCSS blood (`misc/blood/blood_red*`, `dungeon/floor/cobble_blood_*`, `wall_blood_*`) through
  `build_tiles.py`'s `pick_many`; tracks and scorch drawn in `tools/tile_art.py`.
- **The fallen** (`lm.meta["bodies"]`: `[{"x", "y", "who": {"npc": id} | {"creature": def id} | {"char": name},
  "angle", "day", "side"}]` – who they were, not their picture: logic keeps no doll parts, and LocalView composes the
  figure from who it was): drawn in LocalView's people pass with the battle mat's method (`dolls.draw` with `angle`,
  darkened, with a blood pool), hidden under roofs like townsfolk; at most 60 a map. In a settlement the town carries
  its dead off after a day (a scene, if you are there), each of its own gets a **fresh grave** in the graveyard (a
  `grave_fresh` cell near the temple or the town's edge, listed in `lm.meta["graves"]` and counted by epilogues), and
  many foes go to a pyre outside the walls. In the wild: crows for two days, then `bones` on the square.
- **Written back from battles.** In `fight.finish_battle`, after `_settle_townsfolk`, `remains.after_field(game, battle,
  result)` maps the field to the close-up map through `Field.origin` (only for fields cut from `game.local` by
  `arena._local`; a laid-out wild field writes nothing): a body record for every fighter dead on the field; blood
  where blows drew it (`Battle.blood` *(new)*: the squares where slashing or piercing damage landed, filled where
  `combat` resolves damage) and under the dead; scorch where fire zones burned; fire that still burns (below). The
  party is then put where its leader stood when the fight ended (a walkable square of the same map), so the dead lie
  round you.
- **Fire on close-up maps** (`game/fire.py` *(new)*). **Live fire is an overlay, not terrain**: `lm.meta["fire"]` =
  `{"x,y": [stage, ticks]}` (JSON-native, so the save can write it), drawn by LocalView as flames over the cell (the
  `fx/fire` frames and a warm light). Burning cells are blocked through one mask that townlife's walk grid (changed cell
  by cell, and a path crossing a newly burning cell is dropped and found again – never `forget()` on every spread),
  `move_actors` and the player's moves all respect; a cell is lit only when nobody stands on it (townsfolk and bands
  on it step off first, and the party's squares wait). Terrain is written only when cells burn out, in batches (at
  most every ten ticks), and `LocalArt` gains `patch(cells)`, so a burn-out re-picks a few cells instead of rebuilding
  the whole map's art (today any change of the terrain's bytes rebuilds it); a burnt form that would block a square
  (a fallen beam, a charred wall) waits until the square is empty. New terrains (`local_terrain.json` and
  `sprites.json`): `embers` (walkable, a faint light), `scorched`, `charred_floor`, `charred_wall`, `fallen_beam`,
  `door_broken`, `barricade`, `gallows`, `pyre`, `scaffold`, `grave_fresh`, `ritual_circle`, `cage`, `rift_edge`
  (Parts G and K). **Spread**: `townlife.tick` calls `fire.tick` (under 1 ms: it visits only burning cells and their
  neighbours) – a burning cell burns for a number of ticks by what it was (thatch fast, timber slower, furniture),
  then becomes its burnt form (`marks.json` `burnt_forms`); each tick it may light a flammable neighbour (by
  material, and by the wind of `game.weather`); rain slows it; stone, water and wells stop it; a building whose cells
  have burned past a share becomes a burnt shell (its look roofless and charred). `townlife.settle` and leaving the
  map call `fire.settle(lm, seconds)`, which moves the fire on at once for the time that passed. Fire spreads only on
  town maps; fire written back to a wild map or a dungeon level burns out at once into scorched ground.
- **Drawing fire.** `_roofs` draws `fx/fire` frames along a burning building's roof, two to four smoke columns
  (`roofs.smoke_puff`, darker, larger and faster than a chimney's) and an orange glow; `_light` adds fire light by day
  too when a map has fire or a burning mark (today point lights are skipped while it is light); `animate` is applied to
  the ground and over layers as well as objects (the gap the survey found: falls and hot springs will animate too).
- **Atmospheres** (`ui/gfx/atmosfx.py` *(new)*, on weatherfx's method of tiled textures shifted by time, clipped to the
  map): embers, falling ash, smoke haze (a dark fog), mist, a red sky; one at a time, chosen by the map's marks and the
  story; still with Animations on "calm", none with "off".
- **Fire in battle.** `fire.on_battle_start(battle, game)`, called in `fight.start_battle` after `arena.build` and before
  `battle.start` (the `warding.at_the_start` pattern), lays ownerless fire zones (`Zone(kind="fire", owner=None,
  rounds=-1, ...)` – they never count down) on the field's burning cells and fog-like smoke zones beside them;
  `Battle.round_hooks` *(new: callables run at the start of each round)* then spreads fire to flammable neighbours,
  burns cells out (the zone goes; the cell becomes scorched), and brings a burning wooden wall down after a few rounds
  (`Field.set_terrain` to rubble, telegraphed the round before – "the beams groan"; whoever stands there takes damage
  and falls prone). Only on a field that `fire.on_battle_start` marked as burning does the field's flammable mask gain
  the materials of houses (wooden floors, walls and doors, tables, beds, barrels, crates, carts, stalls); every other
  fight is as today, where `Battle._ignite` already sets grass and straw burning for a round when fire damage lands –
  `grid.FLAMMABLE` itself is not widened, or every Fireball in an inn would start a blaze. The spread uses `_ignite`'s
  numbers (1d6 fire, Dexterity DC 10). At the end the field's fire is written back to the map.

### 8.15 Assaults (Part H)

- **The record**: `politics["assaults"]` keyed by settlement id = `{"id", "kind" ("raid", "sack", "the_dead",
  "summoned", "dragon"), "threat", "adv", "since", "clock", "waves": [{"at", "bands": [{"group", "count", "entry":
  "gate"|"wall"|"portal"|[x, y], "goal"}]}], "fire": {"seeds", "since"}, "objectives": [{"id", "kind", "at", "who",
  "state"}], "tally": {"dead": [...], "saved": [...], "burned": [building indices], "slain": n}, "state"}`, from
  `assaults.json` (bands and waves by threat kind and tier, objectives, clocks, fire seeds, the tally's words). The
  attackers are creatures the game has: the dead, raiders, orc and goblin warbands, gnolls, a dragon, and for a
  summoner's portal the imps and quasits of the cult circles' groups. Demons in bands come with the fiends of
  Tieflings & Warlocks, the next expansion, whose data only adds groups to `assaults.json`.
- **Driving**: `townlife.tick` calls `assault.tick(game, lm)` while the player is in the town (so it moves once a town
  tick, on the clock or on the player's steps), and `townlife.settle` calls `assault.settle(game, lm, seconds)`, which
  resolves the minutes that passed in the abstract (waiting, a long talk, a fight's minutes). Waves enter at their
  minute as `LocalActor`s (new ids are the largest id + 1: ids can repeat today); a new actor field `goal` (a square,
  "folk" – the nearest townsperson – or "you"; saved in `to_dict`) gives `move_actors` a target when the band is not
  hunting the player. Townsfolk now block bands, except a band whose goal is folk.
- **Townsfolk**: `npc.flags["flee_to"]` (the nearest refuge away from the attackers: the temple, the keep, a gate), read
  by `townlife.goal` before everything but errands; inside a refuge they are safe (counted as saved), out of a gate
  they are refugees (`followers.ruined_near` already sends refugees to nearby inns). A band that reaches someone kills
  them **away from a battle** (`assault.kill`: `alive=False`, a body record and blood, `quests.on_npc_death`, the
  tally). Guards and soldiers go to the objectives' points as errands; militia raised by the player are made for the
  assault (job `militia`); defenders next to a band fight it in the abstract each tick (a chance to kill one of it or
  to fall).
- **Fights**: a band meeting the party fights as now, on a field cut from the town, with fire laid (§8.14); bands
  within ten squares of the field join from the field's nearest edge at round two to four (`Battle.add_foes(creatures,
  edge, round)` *(new)*: full foes, counted for experience and for victory – `add_ally`'s bonds do not suit them; and
  while bands are still due, `Battle._check_end` does not call the fight won: if the last foe on the field falls
  first, the due bands come in at the start of the next round);
  defenders on the field fight beside you (`Battle.add_ally` with a new bond `defender`, which earns nothing). Fleeing
  a fight in an assault puts the party twelve to twenty squares away from the bands (`finish_battle`'s "fled" branch,
  with `game.assault` set, does not `leave_local`).
- **Objectives** are things on the map: children in a house to lead out (they follow the party: the `follow` cue to
  "you"), the bell to ring (the `bell_post` cell: the militia comes), doors to hold (defenders and the party near it for
  N minutes), a summoner to slay (a named band with a `story` tag: the portal closes), a fire to put out round the well
  (water carried in a bucket, or a spell). There is no single way to win; the clock decides how much burns.
- **The clock**: phases (the first wave, the fire, the second wave, the leader) over 60–120 town minutes; it ends when
  the clock runs out, the attackers' leader falls (they break and flee) or every objective is decided.
- **Away**: an assault on a town the player is not in resolves in the abstract (`assault.resolve`, through the world
  layer's `hosts.strike`, so it works in the interlude too: a burned share and the dead by the defenders' strength
  against the attackers', the marks, the news); the player can arrive while it is happening (a scene at the gate).
- **Afterwards** (`assault.end`): the burned buildings carry the `burned` mark (only those buildings: the dressing of a
  partial mark), the population and the town's people fall by the named dead, refugees go to the next towns,
  `Town.description` is rewritten, and the epilogue's lines are written from the tally, naming the places they fell
  near ("by the tannery", "on the temple steps").

### 8.16 The world map (Part B for marks' signs; Part G for the rest)

- **Land changes** (`world/reshape.py` *(new, world layer)*): the ledger `politics["land"]` = `[{"id", "kind" ("rift",
  "blight", "scorch", "drown", "crater", "dead_forest"), "day", "seed", "shape", "cells": [[x, y, field, old, new],
  ...]}]` and `politics["land_version"]`. `reshape.apply(world, record)` works the cells out from the shape (seeded,
  avoiding settlements as `wonders.avoid` does, and the party's square and the square of the map it is on) and writes
  the arrays (`biome`, `relief`, `elevation`, `road`, `danger`, and `river` for a drowning), recording old and new
  values; autoplay's `_check_land` undoes and redoes the ledger on a copy and compares, as the ownership ledger is
  replayed. New biome ids are appended to `world.biome_ids` and defined in a `biomes.json` fragment: `rift`
  (impassable: travel already reads biome passability in `step_minutes` and `travel_costs`), `rift_ledge` (a crossing:
  passable, slow), `blighted`, `scorched_land`, `drowned`, `crater`; the roads a rift cuts are cut. A crusaders'
  bridge, later, is a road cell over the rift.
- **What must follow a change** (`game.land_changed()` *(new)*, called after every apply): `GameState._biome_remap` is
  rebuilt and `_cost_cache` cleared; `_remaps` (keyed by map key, checked only by length) drops the keys of maps
  replaced or patched; `world.rebuild_index()` if wonders or places changed; the current travel route is planned again
  if it crosses changed squares.
- **Repainting only what changed.** Today the painter is made once per world object (`WorldView.ready`), from copies
  of the world's arrays, and the chunk and overview `Image` keys carry no version, so a change would show only after a
  reload. `WorldPainter.refresh(world, cells)` *(new)* re-derives its copies for the changed cells (and re-traces
  roads only when roads changed); `ChunkCache` queues again only the chunks those cells touch and restarts its thread
  (today the thread ends once everything is painted, and `look_at` will not start it again); each chunk's key carries
  that chunk's version (`("chunk", id(world), gx, gy, v)`) and the overview's the land version, and the old pictures
  stand in until the new ones are painted on the thread (the GPU lets the old go after 900 frames unused). A blight
  spreading by a few squares a week repaints a few chunks, never the map, and never on the main thread. The painter
  learns the new land: a rift's stroke (a dark gorge with glowing edges, drawn along its cells like `_draw_rivers`
  draws a gorge), dead trees and grey tint for blight, black-brown ash for scorched land, water for the drowned, a
  crater's rim.
- **Built close-up maps** take the change on entry (`local.patch_land(world, lm)`, in `enter_local` beside
  `add_entrance`, when `lm.meta["land_version"]` is older): the crack as `chasm` cells with red light across the map,
  keeping a way over where the ledger left a crossing; trees to `dead_tree` in blight; grass to ash where scorched.
  Actors, items and townsfolk on changed squares move to the nearest free square; then `townlife.forget()`.
- **The rift as a wonder made while you play**: `world.wonders.append(Wonder(id=len(world.wonders), kind="rift", ...,
  cells=..., flags={"made": day, "story": adventure id}))` and `world.rebuild_index()` (only ever appended; a rift stays
  within the 80 cells a wonder may cover); `wonders.SHAPERS["rift"]` shapes its squares' close-up maps (the crack, raw
  rock, red light, walls of bone in the deep), and `wonders.json` gains the kind (its words, its Look, the hermits and
  seers it draws). Its depths are a site appended at its edge (founding's site path) of a new kind `rift`, for which
  `world/dungeon.style_for` picks a new dungeon style `rift_depths` (`sites.json`).
- **Signs on the map** (`ui/gfx/mapsigns.py` *(new)*, called in `WorldView.draw` after the settlements and before the
  names; under 2 ms a frame; nothing is painted into chunks): for explored or known settlements with a mark that shows
  from afar – smoke rising (burning, burned, sacked; darker and lit from below at night while burning), a ring of
  tents and banners in the besieger's colours (siege; for `beset`, the horde's own), a black flag (plague), a dragon's
  shadow circling slowly (tribute), lanterns and banners (festival), a gibbet or a statue beside the mark (memorial);
  refugee columns along the roads from a sacked town for some days; hosts (below); a threat's reach washed grey, red
  or under mist once the player knows it, through the existing `overlays` hook (a soft whole-world picture keyed by
  the threat and its version); the rift's slow red pulse, with ash and smoke drifting from it (with Animations on);
  and a founded camp as a composite larger than any town mark, growing with its stages (a palisade ring, rows of
  tents, forge smoke, banners).
- **Hosts** (`world/hosts.py` *(new, world layer)*; `politics["hosts"]` = `[{"id", "kind" ("army", "horde", "the_dead",
  "crusade", "warband"), "faction", "group" (an encounter group), "strength", "x", "y", "path", "goal", "speed",
  "since", "state"}]` and `politics["hosts_tick"]`): raised by the war code (a besieger's army marches to the town it
  will besiege, so a siege is seen coming), by threats' stages (the dead march; hordes out of the rift) and by
  crusades. `hosts.advance(world, days)` moves them by the days since `hosts_tick`, called daily from `story.daily` and
  weekly from `Politics.advance` (whichever comes first; the interlude moves them too), along roads by a path kept per
  host. Arriving, an army acts through the war code (`sieges`, `take`) and a tribe's warband through `raid`, as today;
  hordes, the dead and crusades have no war or tribe behind them, so they act through `hosts.strike(world, tables,
  host, s)` *(new, world layer)*: marks (`beset`, `burned`, `emptied`), losses with the floor of survivors, refugees
  and news – the interlude can run it, and `assault.resolve` uses it. Near the party (within three
  squares) `encounters.roll_encounter` raises the chance and uses the host's group (as scars do); walking onto a host
  offers a beat (its camp: parley, join, slip past – or its vanguard); `news.faction_place` gains a branch for a faction
  with a host in the field. Drawn by `mapsigns`: a short column of figures (three to seven, by its strength, dolls of
  its own creatures) behind its banner, with a little dust, gliding day by day.
- **Founding** (`world/founding.py` *(new)*), by the survey's checklist: (1) `Settlement(id=len(world.settlements),
  owner=-1, area=world.area[x, y], population > 0)` appended – never deleted or reordered – then
  `world.rebuild_index()`; (2) `Politics.set_owner(s, fid)` with a realm (a knightly order's liege realm holds its
  camp: autoplay requires a realm holder), so the ownership ledger records it; (3) `factions.touch(world)`; (4)
  `world.culture[x, y]`, appending to `culture_ids` if the people is new; (5) a road to the nearest road (`path2d` as
  `generator._roads` lays them), then `_cost_cache` reset and `land_version` bumped, since the road must be painted;
  (6) the square's wilderness map, if one was built, is dropped (`world.local_maps.pop(key)` and its `_remaps` entry;
  if the party stands there, the founding waits until it leaves); (7) the town style from `politics["styles"]` (by
  settlement id): `plan.style_for(tables, settlement)` and `worldview.town_mark(tables, s, default)` see no world
  today, so both gain a `world` argument (their callers have one) and read the override before the culture; (8) a name
  from `naming.Namer(tables.place_names, rng, forge=names.forge(world, tables))` with its `used` set filled from the
  world's names, unless the story gives one ("the Camp of the Vow"); (9) news (`news.add`) and history
  (`history.remember`); (10) autoplay's invariants (population above 0; events naming valid places). Sites are founded
  the same way.
- **The encampment** layout (`world/towns/layouts.py`, built on the method of the `camp` layout the Khurgan felt tents
  use): rows of canvas tents (buildings with a new `tent` look, a
  peaked canvas tent drawn in `ui/gfx/houses.py`), a palisade, a chapel tent (the temple), forges, horse lines, banners
  and standards, fire pits; it grows with its mark's stages (a camp → a fortified camp, where timber halls replace
  tents by a change of look → a town), each stage a re-stamp; on the world map `map/town_encampment_small|big` through
  `town_mark`.

### 8.17 Art to make

| What | How |
|---|---|
| blood splats, bloodied cobbles, blood down walls | DCSS, unused today (`misc/blood/blood_red*`, `dungeon/floor/cobble_blood_*`, `wall_blood_*`), picked in `build_tiles.py` |
| bone-strewn floors, cages, bone and flesh walls (the rift's deep) | DCSS (`green_bones_*`, `cage_*`, `dungeon/wall/undead_*`, `wall_flesh`) |
| smoke clouds, dust, gloom; a burning tree | DCSS (`cloud_*`, `cloud_forest_fire`); `fx/smoke` and `fx/dark` (in the sheets, unused) |
| a portal on the square | DCSS `dungeon/gateways` |
| statues for memorials | DCSS's unused statues (`statue_angel`, `statue_sword`, ...) |
| fire on the ground (3 frames), embers, scorched ground, charred floors and walls, fallen beams, a broken door, barricades, a gallows, a pyre, scaffolds, a fresh grave, a ritual circle, a rift's edge, tracks, crows | drawn in `tools/tile_art.py`, `nature_art.py`, `town_art.py` |
| the canvas tent form; charred wall and roof palettes | code in `ui/gfx/houses.py` and `roofs.py` |
| map marks and signs: the encampment and the growing camp's composite, the tents' ring, a black flag, a dragon's shadow, banners, a host's column and dust, the rift's stroke and its drifting ash, dead trees and ash on the map | `tools/map_art.py`, `ui/gfx/stamps.py`, `ui/gfx/paint.py`, `ui/gfx/mapsigns.py` |
| atmospheres (embers, ash, haze, mist, red sky) | textures in `ui/gfx/atmosfx.py` |
| vignette backdrops (fourteen kinds), parchment, wax seals | code (`ui/gfx/vignette.py`, the `titleart` method) |
| a handwriting face or two | OFL fonts in `assets/fonts` |
| a held letter | a `fig/held/letter` layer in `tools/figure_gear.py` (rest and left_rest grips) |
| mourning dress | a `mourning` outfit in `sprites.json` figures |

**Figures keep their one pose.** The fallen are turned (as on the battle mat), a kneeling figure is lowered, the burned
are darkened (the `dolls.frost` method with a charred palette), ghosts are pale and half-seen. No new poses or facing
in this expansion (§11). `tests/test_graphics_ui.py`'s picture test covers every new terrain, decal and outfit.

### 8.18 Budgets for the eye

- A frame on a burning great city at the closest zoom: at most 8 ms for the map's layers, with at most 64 animated
  fire cells drawn (beyond them, still flames), 40 smoke columns and one atmosphere layer; measured by a frame-timing
  test (`tests/test_frame_time.py`: a headless recording on a stamped great city, with a generous bound for slow
  machines).
- World map signs at most 2 ms a frame; washes are cached pictures, made again only when a reach or the land version
  changes.
- A repaint never blocks and never repaints more than the chunks a change touched: the old pictures stand in while
  the new ones come on the painter's thread.
- Fire never rebuilds a map's whole art: burn-outs are written in batches at most every ten ticks and patched cell by
  cell (`LocalArt.patch`).
- Fire spread under 1 ms a tick on a great city; stamping a great city's marks under 50 ms, once on entry; an
  assault's tick under 5 ms with six bands and three hundred townsfolk (the townlife 30 ms test still holds).
- A scene never holds the player longer than its own length, and Space or Escape always skips it.

---

## 9. Proof: tests, tools and measures of fun

- `tools/storybook.py --seed N --size medium --count 20 [--blueprint the_risen] [--check]`: makes (or loads a cached)
  world and prints synopses like §7; `--check` fails on any unbound role, unreachable place, missing word, truth with
  fewer than three routes, or chapter breaking the content rule (§5.2). Anton can read what the game would tell;
  reviewers read a sample before every merge.
- `tools/storyplay.py --seed N --blueprint X --runs 20 [--keys all|none|half]`: plays adventures through with a
  scripted careful party (real travel and time, the battle Auto for fights, sensible choices) and reports: finished or
  not; days; levels gained; fights; beats seen; the gaps between story moments; the finale's win rate.
- **The fairness measure** (`tests/test_story_balance.py`, slow, through storyplay): with every key, a careful party of
  the tier's target level wins the finale at least 80% of the time; with no keys, at most 45%, and the retreat works.
- **The pacing measure** (storyplay with the Storyteller on Steady; autoplay teleports, so it cannot measure this):
  the median travel time between story moments is 8–24 hours; no live adventure goes 30 days without a **possible
  step** (a live step whose target exists and is reachable, or has a repair); at most one villain move in any two days.
- **The first hour** (`tests/test_first_hour.py`, which exists today, extended): a new life is **offered** a hook (an
  offer record shown in a beat, a conversation or on a board) within its first game day.
- **The forge** (`tests/test_forge.py`, slow): forge seeds (not world seeds) on the cached test worlds – many forges
  per world, each blueprint – every role bound, every place reachable, every truth with three routes.
- **Determinism**: the same world seed and the same choices forge the same adventure (record equality).
- **Round trip and types**: every story record survives save and load exactly, and every value is JSON-native.
- **Consequences**: every ending of every blueprint applied on a test world leaves a consistent world (owners replay
  from the ledger; figures' deaths recorded; factions that fall are inactive; no settlement at 0 people; news exists).
- **Text**: the variety floors (§8.8; per family below); a test that every `{slot}` in story data is filled in a run
  of `storybook --check`.
- **Floors per family** (minimums for a part to count as done): signs – 3 beats for each stage of each threat kind;
  villain moves – 2 beats for each move and each temper that uses it; chapter openings and reveals – 3 lines each;
  relief – 12 beats; echoes – 2 beats for each echo tag; happenings – 3 beats each; Legend – 2 beats for each tier-up;
  ally arcs – 2 beats for each arc beat; the Reading – 20 cards with 3 riddles for each of their meanings.
- **Autoplay**: `_check_threats`, `_check_adventures` (known blueprint, valid state, unique id, its threat exists,
  every live step valid, cast references exist, story sites exist) and the bot takes hooks, follows steps, answers
  beats, fights finales.
- **Every quest matters** (`storybook --check`, from Part C): every situation forged on the test worlds passes the six
  rules of §5.15 (a person with a name and a stake; a consequence that can be seen later; two endings that differ; a
  way through without a fight; a thread outward; money only from someone who would pay).
- **The variety measure** (`tests/test_situations.py`, slow, through storyplay): among the first thirty situations a
  scripted hero meets in one world, no two share root, predicament, turn and meeting; there are at least twelve
  different predicaments (twenty once the catalogue is complete, Part K) and twelve different meetings; and the
  **likeness score** stays under 0.25 – two situations' likeness is the share of these parts they have in common
  (root kind, predicament, turn, meeting, the kinds of their obstacles, the jobs of the one in trouble and of the one
  who asks), and the score is its mean over every pair met.
- **The rarity measure**: a town never shows more than one live situation (two in a great city); a town's next one
  comes at least ten days after its last ended or lapsed; at most three are live within reach of the hero (30
  tiles); and a hero who stays within reach of peopled towns is offered a new one at least every twenty days.
- **The income measure**: storyplay's careful player earns, over thirty days, between 0.7 and 1.3 times what the same
  player earned on the build before Part C changed anything (measured once by C.1 and kept in
  `tests/data/income_ref.json`).
- **Pictures** (headless, recorded over the real tile sheets): every mark stamped on a test town of each people (every
  picture name resolves; `check_works` holds; restoring gives the original terrain), every scene played to its end on
  a test town, every world change applied (land records, signs, hosts, a founded encampment), and every new screen
  (the title card, a letter, a beat with its picture, the epilogue's vignettes).
- **`tools/showcase.py`** (on `town_tour.py`'s method): makes a world and saves screenshots of each mark on a town of
  each people, the key moments of each scene, an assault at three moments, the world map before and after a rift with
  its signs and hosts, the title card, a letter and the epilogue – the contact sheet Anton looks at, and the fresh
  reviewer checks before a part is done. The debug console gains `showcase`, `mark <mark>`, `scene <id>`, `assault`
  and `rift`, to stage them in a running game.
- **Frame timing** (`tests/test_frame_time.py`): the budgets of §8.18.
- **The smoke tour** also shows a burned town, a title card and a letter.

---

## 10. Fit with the expansion programme

- **Numbering.** Adventures & Events becomes Expansion 6 (version 1.6.0). Tieflings & Warlocks and everything after it
  move down one (7–27); the last, Planes & Portals, is still version 2.0.0. The codex's `dlc` and `upgrade_in` numbers
  of 6–26 become 7–27 (`tools/codex/`, one script; the codex README's "1–26" too), and the DMG's renown (96), marks of
  prestige (84–85) and settlement calamities (98) move to Expansion 6 (adapted: Legend, titles and rights, threat
  seeds) – EXPANSIONS.md's Bastions & Banners and Bards & Brigands sections drop them. The "Needs" column moves with
  the numbers, and Callings & Crossroads also needs 6. The §4.1 `pack.json` example and the §5.5 STATUS template are
  updated; `CLAUDE.md` and `STATUS.md` references to expansion numbers are renumbered; the dated entries of
  `PROGRESS.md` and the old design notes stay as they were written, with one line at the top of PROGRESS.md saying the
  programme was renumbered on this date.
- **A question every expansion answers** (in its design note, and in EXPANSIONS.md §5.2's definition of done – not
  as a gate on each codex entry, which would demand a story of every spell): *What stories does it tell?* From now
  on every expansion adds to the story engine: villains, blueprints, beats, happenings, ambitions. That is what turns
  each new people, class and monster family from more stuff into more tales:

| Later expansion | What it brings to the stories |
|---|---|
| Tieflings & Warlocks | the warlock's patron as a living figure with its own beats; the infernal contract blueprint; fiends as villains and lieutenants; demon bands for assaults and the rift's hordes; dark gifts in full |
| Dragonborn & Sorcerers | kobold warbands for the dragon; wild magic events |
| Orcs & Barbarians | the warband and the horde in full; mobs |
| Aasimar & Paladins | oaths as ambitions; the fallen champion as a villain; blessings as rewards |
| Elves & Rangers | the fey bargain blueprint; the favoured enemy hunt; goblin warrens |
| Druids & Beasts | the blight blueprint; the great beasts of the wild |
| Bards & Brigands | the heist blueprint; chases; settlement life and its happenings; the bard who sings of you |
| Monks & Elementals | the elemental cult; environmental set pieces |
| Callings & Crossroads | higher-level starts with an ambition already begun |
| Dragons & Hoards | the dragon blueprint with true dragons, their lairs and regional effects |
| Goliaths & Giants | the giants' war |
| Gnomes & Golems | the mad inventor; constructs as lieutenants |
| Crypts & Curses | the dread lord in full (vampires, liches, lycanthropes), curses, fear and stress |
| Drow & the Underdark | the descent; the drow house's schemes |
| Mind Flayers & Psionics | cosmic horror in full; the elder brain as a dread lord |
| Traps & Terrors | the tomb gauntlet; mythic monsters as finales |
| Ships & Sea Monsters | sea adventures; the pirate lord |
| Potions & Scrolls, Rings & Relics | relic hunts for every artifact |
| Bastions & Banners | your land attacked; sieges you command; marks of prestige for a stronghold |
| Planes & Portals | escaping a domain; planar adventures; the patrons' homes |

- **And what it shows.** From now on every expansion also brings what its stories look like: its marks, scenes, map
  signs and vignette backdrops (Dragons & Hoards a dragon's scorched country; Drow & the Underdark fungus creeping up a
  town's well; Elves & Rangers a fey ring's overgrowth; Ships & Sea Monsters ships burning in a harbour; Bastions &
  Banners your own walls besieged).
- **What stays out of Expansion 6** (to keep it from swelling): no new classes, peoples or monster families; no
  owning and running property beyond the small holding (Bastions & Banners); no ships; true legendary monsters come
  with their expansions (until then, boss templates), so assaults' demons and the rift's fiends come with Tieflings &
  Warlocks (until then the attackers are the dead, raiders, orcs, goblins, gnolls, a dragon, and the imps and
  quasits a summoner calls up); no new poses or facing for figures.

---

## 11. Risks, and decisions Anton may want to change

| Risk | What we do |
|---|---|
| **Words** are the biggest cost, and thin words would make it feel generated | helpers in batches for word families (two or three at once, each with a precise brief and finished examples), the floors, `storybook` read before every merge, and a fresh reviewer who reads twenty synopses as a player would |
| **Structure without feel**: an early part that is only "travel, fight, travel, fight" in chapters | Part A already carries the villain's minimal attention and one reaction per chapter, a choice with a lasting codeword in every chapter (the content rule), failure branches, and an epithet offered at the epilogue |
| **A doom spiral**: threats rotting the map while the hero is busy, and every new hero inheriting ruins | the world fights back (§5.1), dooms are bounded and recoverable, a cap on untaken threats near the hero, one stage at most per interlude |
| **Too much happening** (notifications instead of story) | the Storyteller setting, cooldowns, one villain move per two days, the pacing measure |
| **Railroading** in a sandbox | every hook can be ignored; threats wait (dormant) or move slowly with warnings; the Gentle setting |
| **Unfair or trivial finales** | the fairness measure; boss templates tuned by `storyplay`; the "careful player" deaths measured before and after |
| **Stuck adventures** after the world moves on | `repair` on every step; autoplay's invariant |
| **Size**: the largest expansion yet | eleven parts, each a session or two, each playable on `main`; Part A is one adventure end to end, and Parts B and C change how playing feels before the catalogue grows |
| **Saves** | each part that changes the save bumps the format and says that a new world is needed |
| **Rare quests feel empty** | situations in every town within reach (one live at a time), contracts and bounties for coin, the Storyteller's quiet clock; the rarity, pacing and income measures |
| **Situations that read as generated** | real people with lives, meetings always shown, turns with tells, hand-made vignettes, the variety measure, and a fresh reviewer who reads thirty situations as a player would |
| **Art volume** | DCSS pictures first, the rest code-drawn in batches with contact sheets, one pose for figures, `showcase` sheets reviewed every part |
| **Performance**: fire, smoke and many figures | the budgets of §8.18 and the frame-timing test; caps on animated cells and smoke; atmospheres as tiled textures |
| **Breaking towns** with stamps, fire and assaults | buildings marked, never removed; `check_works` after every stamp; restoring by recorded cells; autoplay's checks |
| **Breaking the world map's invariants** | the land ledger replayed by autoplay; founding by the checklist; the world's lists only ever appended to |

Decisions taken here that Anton may change (they go to Appendix F of EXPANSIONS.md):
1. The names: *Legend*, *Ambition*, *the Storyteller*, *the Wayfarer's Deck*, *threats*, *beats* (and the map key
   screen renamed *Map key*, so that "Legend" means one thing).
2. At most three adventures at once (plus the ambition's); hooks beyond that wait.
3. A villain's visit cannot be fought at full strength (it is a projection, a guest under guest-right, or it leaves);
   its tests and hunts can be, and it escapes once.
4. The darkest endings are in: a bargain with the villain, and at tier 4 taking the dread lord's place.
5. A hero whose ambition is fulfilled may end their tale and stay in the world as a figure.
6. Rulers give their own work from Legend 2–3, and a steward gives the small jobs before that.
7. Adventure allies join without wages and can die for good.
8. A threat's tier comes from its region, as every enemy's does (DESIGN.md §6), so an early villain can be too strong
   for you – and you are told.
9. The weekly job board is retired: a quest is a situation, a chapter or a commission; paid work is contracts and
   bounties.
10. Experience comes from stories as well as fights, with a setting for stories only.
11. Figures keep one pose: the fallen are turned and a kneeling figure is lowered; no new animation of bodies.
12. The dead stay where they fell for a day or two, with their blood, and the party stands where its fight ended.
13. At most one cataclysm in a hero's life, from Legend 3 – or from the start, if a new world is made in a time of
    cataclysm (a world option).
14. One contract a town (two in a city), each touching the world; muster and levy contracts wait for Under the Banner.
