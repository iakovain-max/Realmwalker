"""Help: every key binding and a short guide. Grows with each milestone."""

from __future__ import annotations

from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas, ScrollText

HELP_TEXT = """<title>Realmwalker</>
A grim, open-world party role-playing game built on the rules of Dungeons & Dragons 5th Edition. Travel, trade, fight, scheme, survive, and eventually die. The world goes on without you.

<title>Your first hour</>
1. <loot>New World</>, then make a character (press <loot>Enter</> through anything you don't care about).
2. You start in a town. Press <loot>Enter</> (or click <loot>Enter</> on the bar at the bottom) to walk its streets. To talk to someone, stand beside them and press <loot>t</> or <loot>Enter</> (or click them); walking into people only squeezes past.
3. Ask everyone <loot>"Is there any work?"</>. Take something small — a lair to clear, a letter to carry — and press <loot>j</> to see it in your journal. The place is lit on your map.
4. Buy a <loot>torch</> or two, <loot>rations</>, a <loot>waterskin</> and <loot>bandages</> before you leave (talk to a shopkeeper and choose <loot>"Let me see your general goods."</>).
5. Walk there (<loot>m</> for the map, <loot>t</> to travel). Camp at night (<loot>r</>): a fire and a tent (or a rough shelter, if you have no tent) keep you alive, and sleep lasts until morning.
6. Fight only what you must; at level 1, two wolves or three bandits can kill you. Run, talk, ambush, pay robbers off or throw beasts your food.
7. Go back to whoever set you the work and say it is done. Then do it again, with better boots.
Everything else — hunger, wounds, factions, dungeons, dragons, death — is below, and the game explains itself as it goes.

<title>Keys that work everywhere</>
  <loot>F1</>              This help
  <loot>Esc</>             Back / close
  <loot>Ctrl +</> / <loot>Ctrl -</>   Bigger / smaller text
  <loot>Ctrl 0</>          Default text size
  <loot>F11</>             Fullscreen on/off (also Alt+Enter)
  <loot>F12</>             Save a screenshot (in %APPDATA%\\Realmwalker\\screenshots)
  <loot>Ctrl M</>          All sound off/on (the volumes, and your own music, are in Settings)
  <loot>Mouse</>           Hover for tooltips, click to choose, wheel to scroll; right-click for what you can do

<title>Playing with the mouse</>
Everything the keys do can be done with the mouse alone.
  <loot>The bar along the bottom</>  Every action, with its key in the corner: enter, leave, look, search, creep, wait, map, travel, camp, water, wash, character, pack, health, spells, party, journal, news, realms, log, menu. What makes sense right here (enter a town, take what lies here, talk to who is beside you) is lit at the front.
  <loot>Click the map</>    Next to you: step there. Further: travel there (on the overworld) or walk there (on foot); click a person to walk up and talk.
  <loot>Right-click the map</>  A menu of what you can do there: walk or travel there, talk, pick up, search, camp, look.
  <loot>Click a portrait</>  Their character sheet; right-click for their pack, health and spells. Click the words under it for the Health screen.
  <loot>Mouse wheel</>     Over the map: closer or further. Over a list: scroll.
  <loot>In the pack</>     Click a thing to choose it, double-click to use or wear it, right-click for everything you can do with it; click a slot beside the figure to choose what goes there.
  <loot>In a fight</>      Click a square to walk there (the blue squares are this turn's reach; the path and its cost show as you point), click an enemy to walk up and attack it; pointing at an enemy shows your odds and the squares it can strike; the action buttons have pictures.

<title>Pictures and animation</>
The maps are drawn with pictures: the overworld painted like a map (towns, forests, hills, mountains, rivers and roads; fog over country you have not seen), towns, the wild and dungeons with tiles, and everyone as a figure dressed as they are. In <loot>Settings</> you can make things move less or not at all (<loot>Animations</>), and set how big the maps are drawn. <loot>+</> and <loot>-</> (or the mouse wheel) zoom the map while you play.

<title>Menus</>
  <loot>↑ ↓</>             Choose
  <loot>Enter</>           Select
  <loot>Letter keys</>     The highlighted letter next to each option
  <loot>← →</>             Change a setting

<title>Getting started</>
Choose <loot>New World</> on the title screen, pick a size and seed, and the land is made in a few seconds. Then create your character in eight short steps; every step starts with a sensible choice, so you can press <loot>Enter</> through anything you don't care about. The game saves itself as you go; <loot>Continue</> picks up where you left off. <loot>New Character</> makes a character in a world you already have (one living character per world).

<title>Character creation</>
  <loot>↑ ↓</>             Choose; the details show on the right
  <loot>← →</>             Change a value (culture, ability score, fighting style, equipment kit, age...)
  <loot>Space</>           Tick or untick a skill
  <loot>Enter</>           Accept and go to the next step
  <loot>Tab</> / <loot>Shift+Tab</>  Next / previous step (or click a step)
  <loot>W</>               Write a backstory (press again for another)
  <loot>R</>               New random name and looks

<title>Walking and looking</>
  <loot>Arrow keys</>      Walk north, south, east, west
  <loot>Number pad</>      Walk in all eight directions (7 9 1 3 are diagonals)
  <loot>Home PgUp</>       Walk north-west / north-east
  <loot>End PgDn</>        Walk south-west / south-east
  <loot>.</> or <loot>5</>          Wait (an hour on the overworld, a minute on foot)
  <loot>Enter</>           Do the obvious thing here: go into the land around you (towns, forests, rivers); on foot, take what lies here or talk to who is beside you (<loot>></> also enters)
  <loot>x</>               Leave the close view and return to the overworld (or walk off its edge; <loot><</> also works)
  <loot>+</> <loot>-</>             Zoom the map in and out (also the mouse wheel)
  <loot>l</>               Look around: move a cursor to examine anything. Enter travels there (on foot: walks there). On foot, <loot>Tab</> jumps between the places you have seen: the inn, the shop, the smithy, the healer, the temple, the people worth knowing, the stairs underground.
  <loot>Mouse</>           Hover over the map to examine; click next to you to step; click further to travel (on foot: to walk there, or up to whoever you clicked, to talk). Any key stops you.
  <loot>Right-click</>     What you can do there: walk, travel, talk, pick up, search, look

<title>Journeys</>
  <loot>m</>               World map (<loot>z</> zooms out to the whole world, <loot>w</> weather, <loot>p</> realms)
  <loot>t</>               Travel: pick a destination on the world map and see how long it takes
Roads are much faster than open country. Forests, hills and marshes are slow; mountains very slow. Rivers without a bridge must be waded. Any key stops a journey.
Before you set out, the plan says how many nights the journey means in the open, whether your food and water will last, and whether the nights are cold enough to kill. On the way you stop by yourself when night comes on, when a storm breaks, and when something is wrong: someone weary, hungry, parched, cold, bleeding or sick, or the water gone. The stop says where the nearest roof or water is, if you know of one close by. Make camp (<loot>r</>), or press <loot>t</> and Enter to go on: the map opens on where you were going. The cold, thirst or a bleeding wound will wake you from sleep before they kill you.

<title>Your character</>
  <loot>c</>               Character sheet: abilities, skills, features, ties, backstory (<loot>l</> level-up choices, <loot>Tab</> next member)
  <loot>p</>               The party: companions, their loyalty, pay and orders; <loot>f</> there sets the battle order
  <loot>a</>               Spells: what each caster knows, what it does, how many slots are left today; Enter casts one outside a fight
  <loot>i</>               Pack: everything you carry, grouped by kind, beside a figure of who wears what. Enter wears/wields/removes/uses, u takes off, d drops (all, or one with the button), g gives to the next member, ← → kinds of thing, s sorts, Tab next member. Click a slot beside the figure to choose what goes there.
  <loot>e</>               Equipment: what you wear in each slot, which body parts are protected, warmth
  <loot>g</> or <loot>,</>          Pick up what is lying here (on foot, in the close view)
Carrying weight matters: worn armour counts half, and the clothes you are dressed in not at all. Above your limit you are slowed; far above it you cannot walk. Coins weigh too. A backpack worn on the back (the Pack slot) lets you carry 15 lb more, a sack 5.
<title>What things are for</>
Every thing in the pack says on its card what it does. Enter uses it where that makes sense: a whetstone sharpens every blade (+1 damage until the next fight), tools mend worn gear (smith's tools metal, carpenter's tools wood, leatherworker's tools leather and cloth, a needle and thread clothes), snares or a hunting trap are set for the night, an instrument, cards or dice pass the evening with your companions (their loyalty rises), a prayer book is prayed from (once a day: it steadies you, gives a priest back a spent prayer, and with incense steadies everyone), ink and quill write a spell out as a scroll (Spells screen, w).
Weapons, armour, shields and helmets wear a little with every blow they give or take; below "battered" a weapon hits 1 worse and armour gives 1 less AC. A smith mends anything for a fee; your own tools mend what they are made for (fully if you were trained with them).
Some things work by being carried or worn: a holy symbol worn or held, a crystal focus held, or a component pouch carried gives a caster +1 to spell attacks and spell DCs; a signet ring, a holy symbol, a guild's letter, a scroll of pedigree or an old insignia make the people they speak to think better of you; a trophy at the neck makes you more frightening; a ring or pendant makes you look better off. A crowbar forces locks with advantage and less noise; a shovel digs a shelter in half the time; soap washes everything off and cleans wounds; cook's utensils make the food go further; a string of bells round the camp means nobody is caught asleep; navigator's tools keep your bearings in fog and dark; a spyglass sees further by day and spots trouble sooner; rope, manacles and a grappling hook bind prisoners, haul people out of ravines and get you over walls. Flasks of oil, holy water and alchemist's fire are thrown in a fight (Item).
  <loot>r</>               Camp: fire, tent or rough shelter, eat, cook, boil water, forage, hunt, fish, make and mend, snares (p), an evening with music or cards (v), rest, sleep
Without a tent, <loot>t</> at camp builds a rough shelter (an hour, and a Survival check): out of the wind and most of the rain, and a fire will burn in its lee even in a storm. Begun after dark, a sleep lasts until first light. At camp, <loot>m</> sharpens blades and mends gear, and makes what a traveller can make: torches and splints out of firewood, bandages out of linen, salted meat (with salt) and dried fish (over the fire) that keep, and — with a herbalism kit, a fire and three lots of healing herbs — a remedy worth carrying. A Survival or Medicine check decides how much you get out of it.
  <loot>h</>               Health: needs, warmth, blood, pain, wounds and their treatment, sickness
  <loot>w</>               Fill your waterskins (and drink) at a well, river or lake, or from the rain (snow, melted at a fire)
  <loot>b</>               Wash (at water)

<title>Levels and spells</>
Experience comes from fights, deeds and discovery. On a new level you gain hit points and features at once; the choices wait for you on the level-up screen, which opens by itself (or later: c, then l): a path at level 2 or 3 (Champion or Knight, Thief or Cutthroat, a wizard's school), ability increases at levels 4 and 8 (+2 to one or +1 to two), and a wizard's new spells and cantrips. "Choose for me" makes sensible choices.
Spell scrolls are sold where mages gather. A wizard can copy one into the spellbook (Enter on it in the pack: an Arcana check, 50 gold crowns and two hours a spell level; the scroll is used up either way). Anyone can read a scroll aloud once in a fight, from the spell menu (a check if it is not their kind of magic). A caster with ink and quill and a sheet of parchment can write one of their own spells out as a scroll (Spells screen, w): two hours a spell level, costly inks, and one of the day's spell slots goes into the page.
Some spells are worth casting before the fight: Mage Armour lasts eight hours, Stoneskin and Death Ward an hour, Shield of Faith ten minutes. Cast them from the Spells screen (S, pick it, Enter; left and right choose who it is for). They stay on through any fight in that time, the sheet shows them, and the log says when one fades. Healing spells can be cast from there too, or from the health screen (h) to choose the wound. A wizard who knows Identify can cast it there to learn what a strange thing in the packs is (ten minutes and a slot).

<title>Companions</>
Travellers looking for work wait at the inns (and sell-swords in a mercenary company's town). Talk to them: "Would you travel with me?" shows their price: a daily wage, some of it up front, and for some a share of the loot. Someone you free from a dungeon's chains, once you have seen them home and told whoever sent you, waits at the inn too: they ask only for their keep, and start out loyal. Up to four can travel with you. They are whole people, with needs, wounds, sicknesses and a class and level of their own, and they can die. In a fight you command each of them.
Each has values: a devout priest hates desecration and heresy, a sell-sword wants pay and victories, a kind soul hates cruelty, an honourable one hates theft and murder, and so on. What you do raises or lowers their loyalty, and they say so. Unpaid wages sour them fast. An unhappy companion grumbles; a mutinous one slips away in the night with some of your coin; a devoted one will follow you anywhere.
On the party screen (p): Talk, give Orders (follow, keep watch when you camp so you are not caught asleep, forage while the others sleep, or wait at this spot until you come back), Raise their pay, or Dismiss them. The party shares one pack: the inventory (i) is everyone's, whoever needs the arrows, the bandages or the bread finds them there, and the weight is carried by all of you together (everyone's strength, and the animals). What each one wears and wields stays theirs: choose who with Tab, or give a sword to the next one with G and they take it up. Someone told to wait, or sent away, takes only what they have on; the dead leave everything to the rest.
A companion who becomes devoted to you will finally ask you for something of their own: revenge on the gang that ruined them, a book they have wanted all their life, a cult they want ended, a debt nobody else will collect. Press <loot>b</> on the party screen to hear it, take it on, or turn them down (they will remember which). Seeing it through binds them to you for good.
Not everyone comes for a wage. A realm that honours you (standing 50 or more) will lend you one of its own if you ask its ruler, and call them home if it stops thinking well of you. Tell a farm lad, a serving girl or a drunk at the inn about the paying work you have taken, and they may come for a fifth of every reward (tell them it will make them rich, and they will remember that when the money comes). A hard word (Persuasion) can talk someone restless into leaving home. The homeless of burned and sacked places wait at the inns nearby, and once your name is known, people who have heard of you may be waiting too. None of these take a wage, and no companion carries a purse: what you pay anyone is theirs, and only your own money is ever spent.
And seven people are like no one else. They are the same in every world, only found in different places: listen for talk of an old knight who keeps watch over a barrow, a dwarf drinking near a dragon's lair, a thief the rope would not take, a nun with a bell where the sickness is, an orc scrubbing a temple floor, an elf who has written everything down, and a halfling smuggler. Each wants something different of you before they will come (a barrow cleared, a drinking match and an oath, a way out of the cells, a day among the sick, a journey to a village, something she does not know, a crate past a gate), and each brings a gift of their own. They take no wage. If they die, they are gone from that world for good.

<title>Staying alive</>
Your body matters as much as your sword. The side panel shows anything that is wrong.
  <loot>Hunger, thirst, tiredness</> grow as time passes (faster when walking, in heat, or shivering). Food spoils; a day's rations feeds you for a day. By default you eat and drink from your pack when needed (Settings), and fill your skins at a town's well as you pass, and from streams and the rain when they run dry. Wells in towns are safe; rivers, lakes and marshes can make you sick unless you boil the water at a campfire (you need a pot).
  <loot>Cold and heat:</> what you wear, wind, rain, shelter, fire and what you are doing all count. Wet clothes lose their warmth. A winter night in the open without a fire can kill; so can a heat wave in armour. Check the Warmth bar on the Health screen.
  <loot>Exhaustion</> (5e, levels 1 to 6) builds up from starving, thirst, no sleep, freezing or heat. A night's sleep with food and water removes one level. At level 5 you can only stagger, slowly; level 6 is death.
  <loot>Wounds</> heal over days (minor), weeks (serious, critical) or a month (broken bones). Bleeding wounds lose blood until bandaged; dirty wounds can fester and poison the blood. On the Health screen: <loot>b</> bandage, <loot>c</> clean, <loot>s</> stitch, <loot>p</> splint, <loot>f</> cauterize, <loot>o</> poultice, <loot>k</> poppy milk, <loot>m</> healing magic. When a limb cannot be saved (festering towards the blood, or smashed beyond mending), <loot>a</> amputates it: a blade, and fire or a torch for the stump. It saves a life and leaves a lost arm or leg for good. Each need on that screen also says where it is heading: "peckish in about 5 hours", "warming", "drying".
  <loot>Sickness</> comes from bad water or food, bites, cold and wet, marsh country and filth. It takes hold after some hours or days; rest, warmth, clean water and herbs help you recover. Some diseases kill.
  <loot>The road:</> travel is slower in storms, snow and heat, and when hurt or tired. Off the road in fog, storms or darkness you can lose your way. You will meet people as well as trouble: pedlars, pilgrims, patrols, refugees and more. Each day of travel is written up in the log.

<title>Towns and people</>
Press <loot>Enter</> on a settlement to walk its streets. People show as <loot>☺</>: stand beside someone and press <loot>t</> or <loot>Enter</> to talk (a list, if several are near), or click them; walking into people squeezes past them (a warden at a gate will not budge). In a town time runs by itself (Settings, Time in towns): everyone keeps the day of their trade, walking to work, to the inn of an evening and home to bed, and the watch goes its rounds. By day shops and stalls are open; at night most folk are asleep at home and only the inn, the temple and the watch are about. Everyone has a name, a trade, a personality and a memory: first impressions depend on your clothes, cleanliness, wounds, race and background, and they remember threats, bribes and kindness.
  <loot>1-9</>             Choose what to say (the numbers shown)
  <loot>t o g</>           Threaten · offer money · goodbye (Esc also leaves)
What you have done reaches them before you do: a name for great deeds warms people to you (and impresses the proud and the greedy more than it should), while a name for cruelty frightens them, the kind ones worst of all.
Ask who they are, about the place, for news (dangerous roads, places you did not know, which then appear on your map) and about the other people in town. Some choices are skill checks, shown like <loot>[Insight]</>.
<title>Trade</>
Shopkeepers, smiths, healers, market traders, innkeepers and stablemasters trade. In the market window, <loot>Enter</> buys or sells one, <loot>Tab</> switches between their goods and yours, <loot>h</> haggles (once a day). Prices depend on the place: goods are cheap where they are made (salt on the coast, iron in the hills, furs in the cold north, grain on the plains) and dear where nobody makes them, so carrying trade goods between towns pays. Merchants have only so much coin, restock every week, and won't buy stolen goods.
<title>Services</>
Ask "What can you do for me?": beds for the night (a real sleep, safe from the wilds), hot meals, baths, performing and dice at the inn; healers who treat every wound at once, operate on internal bleeding and sell herbal cures; priests who pray for healing and cures (for a donation); smiths who mend battered weapons and armour; a day's paid work; and at the stable, mules, ponies and horses. A mule carries 200 lb for you. Each of you rides one of the animals, the fastest first; the party goes as fast as its slowest member, so it rides at a horse's pace only when everyone has a mount (one horse among three of you is ridden at a walk). A riding horse covers about half as much ground again as a walker on roads and open country, less in woods, and nothing in marsh or mountains, where you lead it; a pony or a draft horse less. Riding tires you less than walking, a lame leg does not slow a rider, and the travel plan counts the riding. The side panel says who rides what. Animals need a bag of fodder a day, or grazing outside winter, or they starve. Out in the wild at night somebody may come for them: set a companion to keep watch (the party screen, p, then o).

<title>Factions</>
  <loot>f</>               Factions: the realms, lords, churches, guilds, tribes and outlaws you know of
The land is divided among kingdoms and the noble houses sworn to them, free cities, dwarven clans, highland clans and elven realms; tribes hold the wild country. Churches, knightly orders, guilds, mercenary companies, and secret thieves and cults work within and across them. Each has a leader, values, friends and enemies, and realms have their own laws. You have a standing with each (<danger>Hated</>, <warn>Distrusted</>, Neutral, <good>Respected</>, <good>Honoured</>): people who answer to a faction treat you by it, and a price on your head makes the watch unfriendly. Your background may have given you friends, a family, or a bounty. Rulers live in their seats: the king in the keep, the lady in her hall.
What you do spreads as news, about 24 miles a day along the roads. Helping a faction pleases its friends and angers its enemies once they hear of it. Beating bandits angers their gang and pleases the lord of the land. Your fame and infamy go before you.
Join a guild, church, order or company by asking one of its people (you need their good opinion, and sometimes a skill, a trade, a faith or a fee). You start at the bottom whatever they think of you. Standing opens the door to the next rank, but they promote you when you have done a piece of their work: take a job from one of their people and the offer says whose eyes are on it. (If your standing runs far ahead of your rank, they give in and promote you anyway.) Rank brings better prices, and from the second rank, lessons: one of their people will teach you one of their skills for each rank you rise (a long day and a fee; merchants teach Persuasion and Insight, healers Medicine and Nature, thieves Stealth, Sleight of Hand and Deception, and so on). A fence of the thieves' guild can hide a member who is wanted: three days in the guild's safehouse, and the price on your head in that realm is halved (once a week). The thieves' guild and the cults hide among ordinary folk: the right question may find them. A ruler who honours you may grant you a title.

<title>News, history and a world that moves on</>
  <loot>n</>               News and history: what you have heard, the chronicle of the land, dragons, lost treasures and legends
The world has centuries of history behind it: dynasties, wars, plagues, dragons and heroes. And it does not stand still while you play. Rulers grow old and die, and their heirs (or whoever seizes the seat) follow. Neighbours who hate each other go to war, fight battles, besiege and take towns, and make peace. Vassals rebel. Plague and famine come and go, tribes raid the borders, cults spread in secret, outlaw gangs rise and are hanged.
Everything that happens becomes news, travelling about 24 miles a day along the roads: you hear it in inns, from travellers and on the <loot>¶</> notice board in a town's square (walk into it to read it). A besieged town is dear and hungry; war brings soldiers, refugees and deserters to the roads; plague can follow you home.

<title>Law and crime</>
Each realm has its own laws: magic may need a licence or be forbidden, some goods are contraband, some lords keep the game for themselves, and punishments run from lenient to cruel. Theft, pickpocketing, trespass (in someone's house at night), assault, murder, poaching, smuggling, unlicensed magic, witchcraft and heresy are crimes.
A crime needs a witness. A guard who sees it arrests you on the spot; anyone else goes to the watch within a few hours, unless you persuade, pay or frighten them into silence (talk to them). Unwitnessed crimes are never traced. A reported crime puts a price on your head in that realm; where you are wanted, the watch may recognise you.
When the watch takes you: <loot>P</>ay what you owe (petty crimes only), go <loot>Q</>uietly and take the sentence (a fine, jail, the lash, the brand, hard labour or the rope, by the local law), <loot>B</>ribe the guard, <loot>R</>un, or <loot>F</>ight. In jail your belongings are held until you are released. You may try to escape. Settle your debts with a guard, the headman or the lord.
  <loot>s</>               In a market: try to steal the chosen item (Sleight of Hand)
Walled towns and cities shut their gates from nightfall until dawn: at the gate after dark, pay the warden at the postern, talk your way in, climb the wall, or sleep under it until morning. Walled towns search travellers at the gate now and then: what the law forbids there, and anything you are carrying that is meant to stay out of sight, is taken (and that is smuggling, whoever asked you to carry it).
A disguise kit (general stores) lets you become a stranger for half a day: crimes are blamed on the stranger, and the watch may not know your face. Take prisoners after a fight and hand them to any town's watch for a reward. If you are sworn to the thieves' guild, their people will instead sell your prisoners back to their own kind, quietly, for three times what the watch pays: no news of it travels, but the law loses respect for you if it is ever put together, and honest companions will not stand for it.

<title>Danger</>
The wilds are not empty. The more dangerous the region (shown in the side panel), the more likely something finds you, and night is worse; roads are a little safer. When trouble comes on the road you can <loot>F</>ight, <loot>A</>mbush (if you saw them first), <loot>S</>lip away (Stealth, much easier if you saw them first), or <loot>T</>alk your way past. Robbers will take half your purse instead of a fight (<loot>P</>), and hungry beasts will take food thrown to them (<loot>B</>). Beaten by robbers, you are robbed and left; beaten by beasts, you may wake hours later, mauled, with half the food gone. Ruins, caves, barrows and towers have inhabitants; in the close view a mark over their heads shows once they have noticed you. Walk into them to attack.

<title>Battle</>
Fights are fought on a grid of five-foot squares, as on a D&D battle mat, cut from the place you are in: the walls and doors of the dungeon, the street and the houses, the inn's tables, the trees and stones of the wood. Your party starts in its battle order (party screen, <loot>p</>, then <loot>f</>: a block of five by five, the front row towards the enemy); the enemy starts where it was, or as the moment says: across the field, all around you if they caught you unawares, bunched up if you caught them. Everyone acts in order of initiative. On your turn you may move up to your speed (30 feet is six squares; brush, mud, water and rubble cost double), split around one action and perhaps a bonus action:
  <loot>Click a square</>   Walk there (or the arrow keys, a square at a time)
  <loot>Click an enemy</>  Walk up to it and strike with the best weapon that reaches
  <loot>a</>               Attack: a weapon, then a target (number keys, Tab and Enter, or click). Extra Attack gives more than one, with walking between them
  <loot>c</>               Cast a spell: at someone in range and in sight, or at a square (move the mouse or the arrows: the squares it will fill light up, friends too)
  <loot>u</>               Use an item: potions, bandages, a healer's kit (on yourself or someone beside you)
  <loot>b</>               Abilities: Second Wind, Action Surge, Cunning Action, an off-hand strike, Turn Undead, a spiritual weapon's blow...
  <loot>r</> <loot>w</> <loot>d</> <loot>n</>         Dash (double move), Disengage (step away without free blows), Dodge, Hide
  <loot>h</>               Help a friend beside the same enemy (advantage), or first aid for a fallen friend beside you
  <loot>s</>               Shove (knock down, push five feet) or grab someone beside you
  <loot>p</> <loot>y</>             Parley; Surrender (only to those who take prisoners)
  <loot>f</>               Flee: from a square at the edge of the field, get away. When nobody is left standing on it, the fight is over
  <loot>z</>               Let the game play this turn for this character
  <loot>e</> or Space      End the turn
  <loot>+ -</> wheel       Zoom the field;  <loot>PgUp PgDn</> scroll the battle log
Leaving an enemy's reach gives it a free blow (an opportunity attack) unless you Disengage; the path shows a red mark where it would happen. Two of you on opposite sides of an enemy (straight across it, or corner to corner) flank it: both have advantage on blows against it, and so does the enemy when it flanks you. Point at an enemy and gold diamonds mark where to stand to flank it. Walls and trees block sight; low walls, fences, tables, boulders and other people give cover (+2 or +5 to AC). Shooting at long range, or with an enemy beside you, is at disadvantage; so is striking what you cannot see (darkness, unless you have darkvision or a light). Fire, webs and spirits stay on the ground where they were laid. Area spells catch friend and foe alike. A caster holding a spell (Bless, Web, Hold Person, Spirit Guardians) loses it if hurt and failing a Constitution save.
Blows land on a part of the body and may leave wounds: cuts bleed until bandaged, broken bones stay broken. At 0 hit points you fall and make death saving throws each turn (three failures and you are dead, three successes and you are stable); a friend can stop it (Help, a healer's kit, or a healing spell), and a blow that would take you a whole life's worth below nothing kills outright. Enemies lose heart: beasts run for the edge, bandits and soldiers may surrender, fanatics and the dead never do. Afterwards you decide the fate of prisoners and take what you want from the fallen. Death is permanent.

<title>Underground</>
Ruins, caves, barrows, towers and the lairs of gangs and cults have something below them. In the close view, the steps down show as <loot>></>: walk onto them. Deeper levels are worse, and the master of the place waits at the bottom.
It is dark down there. Light a torch or a lantern from your pack (they burn out; carry spares) or you see only what is under your nose; dwarves and elves see a little in the dark. Doors may be locked (walk into them: thieves' tools help, or force them), chests and coffins are opened the same way, and opening a coffin may wake what lies in it.
  <loot>s</>               Search where you stand: traps, secret doors, hidden rooms (Perception)
  <loot>z</>               Creep: slower, and only those whose Perception beats your Stealth see you. The dark helps, standing close does not, and armour that clanks makes it harder. Fall on a band that has not seen you and you have the first blows. Creeping past the watch works on crimes too. z again to stop.
  <loot><</> <loot>></>             Stairs up and down
Traps are hidden until you spot them: darts, pits, falling stone, gas, and worse. Search before you walk into a room you don't like the look of. A dragon's hoard is guarded by the dragon.

<title>Magic items</>
Magic is rare, and most of it is old. What you find looks like "a strange sword" until you know it: <loot>k</> in your pack handles it through an hour's rest and tells you what it does (never whether it is cursed), or a priest will tell you for a donation, or a wizard's Identify. Known items list what they do and carry the name and history the world remembers.
Things of real power must be bound to someone before they work: <loot>a</> in your pack spends an hour attuning the one whose pack page it is (and an hour to end it). Nobody can be bound to more than three things. A plain +1 sword needs no bond.
Some things are cursed: once worn or bound they will not let go, and they work against you. A temple can lift a curse. Wands and staves with charges get some of them back at dawn, not with rest.
An artifact is one of a kind: great powers and a flaw or two, rolled for this world, and it cannot be broken except in one way the world remembers. Some old things are awake: they have a mind, a purpose and a voice, they like and hate what you do, and when you go against them they make demands. Refuse, and they withhold their power, or take hold of their bearer for a few hours.

<title>Treasure and the road</>
Creatures carry what their kind carries: a bandit a few gold pieces, a wolf nothing. A band that keeps a hoard keeps it at home: the deepest chest of a lair is its master's hoard, in the form its kind likes (gems, coin and silver bars, trade goods, or old art). Cities where mages keep a house sell a minor magic thing or two.
  <loot>v</>               Travel pace: Fast covers ground in three quarters of the time but notices less and loses its way more easily; Slow takes half as long again but notices more, keeps its bearings and slips away quietly. Mountains and marsh are slow going and allow no Fast pace; a good road allows one step faster.
Not every band on the road wants a fight. Some are only wary: you can let them be and go on. Talking your way past is harder with a hostile band and easier with a friendly one; the same goes for anyone in a town, by their mood.

<title>Dragons</>
Every land has its dragon, and everyone knows its name. Most were killed by heroes long ago; one or two are only sleeping, each in a lair in the high country. A sleeping dragon still comes down now and then to burn a village or take cattle and silver as tribute, and the news travels. The country around a lair tells you: burned trees, bones in the grass, no birds singing.
It is a very hard fight and it will kill an unready party. Its hoard is real gold, heaped up and slept on, and taking any of it wakes the owner. Kill one and the world hears of it: your name goes into the chronicle (n) beside the old heroes, the tribute stops, and lords pay well for the head. Some of them will pay in advance, if you ask for work.

<title>Paper</>
Few can read, so books, maps and letters are treasure. In your pack, <loot>Enter</> reads one (an hour). A map puts real places on your map; a book of histories tells you who held this country and adds a faction to your list; old lore names where one of the world's lost treasures came to rest; a dead stranger's letter points at somewhere worth going. Everything they say is true of this world, and they say the same thing every time you read them.

<title>Work and the journal</>
  <loot>j</>               The journal: work in hand, what is left to do and how it ended, and (Tab) everyone you have met
Ask people in a town "Is there any work?". Anyone of standing (and now and then an ordinary soul) may have something: a bounty on a real gang's captain, a lair to clear, a named beast to hunt, a sealed letter to carry, an heirloom or a lost treasure of the old days to bring back, a son or daughter taken by outlaws, a debt to collect, people going missing, someone to walk safely to another town, herbs for a sickness, a feud to settle, a pocket to pick, a village that knows the raiders are coming and wants a sword in the street on the day, a crate that must reach another town without the gate wardens seeing it — and, if you look like you might live through it, a dragon. Wanted posters on the <loot>¶</> notice board can be taken down and taken on (press the number shown).
Each job has a reward and a number of days. The journal marks where to go; the place is put on your map, and the tile is lit on the map and the world map (m) until the job is done. When it is done, go back to whoever set it and say so. Failing it, or giving it up (<loot>a</> in the journal), sours the giver and their people.
Not everything is as it was told to you. Outlaws may turn out to be starving deserters you could talk into leaving instead of killing; the debtor may have nothing but children and an empty house; a sealed letter may be worth reading, and once read it can be delivered anyway, taken to the lord, or held over the sender's head; the man you were paid to kill may be nobody's enemy, and telling him who paid is worth something too. Your companions notice what you choose.

<title>When you die</>
Death is permanent. There is no reload: the game saves as you go, and that save is the only one. When you die you get an obituary — what you were, how you died, what you killed, what you did that anyone will remember, and what the powers of the land thought of you — and everything you carried is gone. There is no body and no grave to loot.
What is left is the world. Your deeds stay in its history and its news; famous deaths are remembered in the chronicle. Companions who outlived you go home and can be hired by whoever comes next.
From the title screen, <loot>New Character</> begins a new life in a world you have already played. Weeks or months pass first — rulers die, wars begin and end, towns change hands, plague comes and goes — and you are told what changed before you take your first step into it.

<title>How much the game says</>
Settings has <loot>Text detail</>: <loot>Brief</> keeps only what matters (fights, needs, news, what you find), <loot>Normal</> adds the world's voice — street life in towns, companions talking on the road, the weather turning, what you hear in the night — and <loot>Rich</> gives you more of it.

<title>Other screens</>
  <loot>o</>               The full message log (or click the messages)
  <loot>k</>               Map legend: what every symbol means
  <loot>Esc</>             Game menu: help, settings, save and leave

<title>If something goes wrong</>
The game tries never to crash: if something breaks it says so, writes the details to <loot>logs\\errors.log</> in the game's own folder (beside Play.bat) and carries on. That file is the thing to send if you report a problem. Your saves, settings and screenshots live in <loot>%APPDATA%\\Realmwalker</>.
"""


class HelpScreen(Screen):
    title = "Help"
    sound_open = "ui_page"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.view = ScrollText(HELP_TEXT)

    def render(self, canvas: Canvas) -> None:
        w, h = canvas.width, canvas.height
        width = min(96, w - 2)
        x0 = (w - width) // 2
        canvas.frame(x0, 0, width, h - 1, "Help", double=True)
        self.view.render(canvas, x0 + 2, 2, width - 4, h - 5)
        canvas.button(x0 + 2, h - 3, "Back", self.close, hotkey="Esc")
        canvas.text(x0 + 12, h - 3, "↑↓ PgUp PgDn scroll", (80, 76, 70))

    def handle_key(self, ev: KeyEvent) -> bool:
        if ev.key in ("escape", "f1", "?"):
            self.close()
            return True
        return self.view.handle_key(ev)

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent("down"), KeyEvent("pagedown"), KeyEvent("up"), KeyEvent("escape")]
