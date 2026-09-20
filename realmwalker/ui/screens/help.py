"""Help: every key binding and a short guide. Grows with each milestone."""

from __future__ import annotations

from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas, ScrollText

HELP_TEXT = """<title>Realmwalker</title>
A grim, open-world party role-playing game built on the rules of Dungeons & Dragons 5th Edition. Travel, trade, fight, scheme, survive, and eventually die. The world goes on without you.

<title>Your first hour</title>
1. <loot>New World</>, then make a character (press <loot>Enter</> through anything you don't care about).
2. You start in a town. Press <loot>></> to walk its streets, and walk into people (<loot>☺</>) to talk to them.
3. Ask everyone <loot>"Is there any work?"</>. Take something small — a lair to clear, a letter to carry — and press <loot>j</> to see it in your journal. The place is lit on your map.
4. Buy a <loot>torch</> or two, <loot>rations</>, a <loot>waterskin</> and <loot>bandages</> before you leave (talk to a shopkeeper and choose <loot>"Let me see your general goods."</>).
5. Walk there (<loot>m</> for the map, <loot>t</> to travel). Camp at night (<loot>r</>): a fire and a tent keep you alive.
6. Fight only what you must; at level 1, two wolves or three bandits can kill you. Run, talk, or ambush if you can.
7. Go back to whoever set you the work and say it is done. Then do it again, with better boots.
Everything else — hunger, wounds, factions, dungeons, dragons, death — is below, and the game explains itself as it goes.

<title>Keys that work everywhere</title>
  <loot>F1</>              This help
  <loot>Esc</>             Back / close
  <loot>Ctrl +</> / <loot>Ctrl -</>   Bigger / smaller text
  <loot>Ctrl 0</>          Default text size
  <loot>F11</>             Fullscreen on/off (also Alt+Enter)
  <loot>F12</>             Save a screenshot (in %APPDATA%\\Realmwalker\\screenshots)
  <loot>Mouse</>           Hover for tooltips, click to choose, wheel to scroll

<title>Menus</title>
  <loot>↑ ↓</>             Choose
  <loot>Enter</>           Select
  <loot>Letter keys</>     The highlighted letter next to each option
  <loot>← →</>             Change a setting

<title>Getting started</title>
Choose <loot>New World</> on the title screen, pick a size and seed, and the land is made in a few seconds. Then create your character in eight short steps; every step starts with a sensible choice, so you can press <loot>Enter</> through anything you don't care about. The game saves itself as you go; <loot>Continue</> picks up where you left off. <loot>New Character</> makes a character in a world you already have (one living character per world).

<title>Character creation</title>
  <loot>↑ ↓</>             Choose; the details show on the right
  <loot>← →</>             Change a value (culture, ability score, fighting style, equipment kit, age...)
  <loot>Space</>           Tick or untick a skill
  <loot>Enter</>           Accept and go to the next step
  <loot>Tab</> / <loot>Shift+Tab</>  Next / previous step (or click a step)
  <loot>W</>               Ask the AI to write your backstory (uses a little Player2 energy)
  <loot>R</>               New random name and looks

<title>Walking and looking</title>
  <loot>Arrow keys</>      Walk north, south, east, west
  <loot>Number pad</>      Walk in all eight directions (7 9 1 3 are diagonals)
  <loot>Home PgUp</>       Walk north-west / north-east
  <loot>End PgDn</>        Walk south-west / south-east
  <loot>.</> or <loot>5</>          Wait (an hour on the overworld, a minute on foot)
  <loot>></>               Enter the land around you: see it up close (towns, forests, rivers)
  <loot><</>               Leave the close view and return to the overworld (or walk off its edge)
  <loot>l</>               Look around: move a cursor to examine anything. Enter travels there.
  <loot>Mouse</>           Hover over the map to examine; click next to you to step; click further to travel
  <loot>Right-click</>     Look at a spot

<title>Journeys</title>
  <loot>m</>               World map (<loot>z</> zooms out to the whole world, <loot>w</> weather, <loot>p</> realms)
  <loot>t</>               Travel: pick a destination on the world map and see how long it takes
Roads are much faster than open country. Forests, hills and marshes are slow; mountains very slow. Rivers without a bridge must be waded. Any key stops a journey.

<title>Your character</title>
  <loot>c</>               Character sheet: abilities, skills, features, ties, backstory (<loot>l</> level-up choices, <loot>Tab</> next member)
  <loot>p</>               The party: companions, their loyalty, pay and orders
  <loot>S</>               Spells: what each caster knows, what it does, and how many slots are left today
  <loot>i</>               Inventory: Enter wears/wields/removes/uses, d drops, D drops one, ← → filters, s sorts, G gives to the next member, Tab next member
  <loot>e</>               Equipment: what you wear in each slot, which body parts are protected, warmth
  <loot>g</> or <loot>,</>          Pick up what is lying here (on foot, in the close view)
Carrying weight matters: worn armour and clothes count half. Above your limit you are slowed; far above it you cannot walk. Coins weigh too.
  <loot>r</>               Camp: fire, tent, eat, cook, boil water, forage, hunt, fish, rest, sleep
  <loot>h</>               Health: needs, warmth, blood, pain, wounds and their treatment, sickness
  <loot>w</>               Fill your waterskins (and drink) at a well, river or lake
  <loot>W</>               Wash (at water)

<title>Levels and spells</title>
Experience comes from fights, deeds and discovery. On a new level you gain hit points and features at once; the choices wait for you on the level-up screen, which opens by itself (or later: c, then l): a path at level 2 or 3 (Champion or Knight, Thief or Cutthroat, a wizard's school), ability increases at levels 4 and 8 (+2 to one or +1 to two), and a wizard's new spells and cantrips. "Choose for me" makes sensible choices.
Spell scrolls are sold where mages gather. A wizard can copy one into the spellbook (Enter on it in the pack: an Arcana check, 50 gold crowns and two hours a spell level; the scroll is used up either way). Anyone can read a scroll aloud once in a fight, from the spell menu (a check if it is not their kind of magic).

<title>Companions</title>
Travellers looking for work wait at the inns (and sell-swords in a mercenary company's town). Talk to them: "Would you travel with me?" shows their price: a daily wage, some of it up front, and for some a share of the loot. Up to four can travel with you. They are whole people, with needs, wounds, sicknesses and a class and level of their own, and they can die. In a fight you command each of them.
Each has values: a devout priest hates desecration and heresy, a sell-sword wants pay and victories, a kind soul hates cruelty, an honourable one hates theft and murder, and so on. What you do raises or lowers their loyalty, and they say so. Unpaid wages sour them fast. An unhappy companion grumbles; a mutinous one slips away in the night with some of your coin; a devoted one will follow you anywhere.
On the party screen (p): Talk, give Orders (follow, keep watch when you camp so you are not caught asleep, forage while the others sleep, or wait at this spot until you come back), Raise their pay, or Dismiss them. The party shares its food and water.
A companion who becomes devoted to you will finally ask you for something of their own: revenge on the gang that ruined them, a book they have wanted all their life, a cult they want ended, a debt nobody else will collect. Press <loot>b</> on the party screen to hear it, take it on, or turn them down (they will remember which). Seeing it through binds them to you for good.

<title>Staying alive</title>
Your body matters as much as your sword. The side panel shows anything that is wrong.
  <loot>Hunger, thirst, tiredness</> grow as time passes (faster when walking, in heat, or shivering). Food spoils; a day's rations feeds you for a day. By default you eat and drink from your pack when needed (Settings). Wells in towns are safe; rivers, lakes and marshes can make you sick unless you boil the water at a campfire (you need a pot).
  <loot>Cold and heat:</> what you wear, wind, rain, shelter, fire and what you are doing all count. Wet clothes lose their warmth. A winter night in the open without a fire can kill; so can a heat wave in armour. Check the Warmth bar on the Health screen.
  <loot>Exhaustion</> (5e, levels 1 to 6) builds up from starving, thirst, no sleep, freezing or heat. A night's sleep with food and water removes one level. Level 6 is death.
  <loot>Wounds</> heal over days (minor), weeks (serious, critical) or a month (broken bones). Bleeding wounds lose blood until bandaged; dirty wounds can fester and poison the blood. On the Health screen: <loot>b</> bandage, <loot>c</> clean, <loot>s</> stitch, <loot>p</> splint, <loot>f</> cauterize, <loot>o</> poultice, <loot>k</> poppy milk, <loot>m</> healing magic.
  <loot>Sickness</> comes from bad water or food, bites, cold and wet, marsh country and filth. It takes hold after some hours or days; rest, warmth, clean water and herbs help you recover. Some diseases kill.
  <loot>The road:</> travel is slower in storms, snow and heat, and when hurt or tired. Off the road in fog, storms or darkness you can lose your way. You will meet people as well as trouble: pedlars, pilgrims, patrols, refugees and more. Each day of travel is written up in the log.

<title>Towns and people</title>
Press <loot>></> on a settlement to walk its streets. People show as <loot>☺</>: walk into someone to talk. By day shops and stalls are open; at night most folk go home and only the inn, the temple and the watch are about. Everyone has a name, a trade, a personality and a memory: first impressions depend on your clothes, cleanliness, wounds, race and background, and they remember threats, bribes and kindness.
  <loot>1-9</>             Choose what to say (the numbers shown)
  <loot>t o g</>           Threaten · offer money · goodbye (Esc also leaves)
What you have done reaches them before you do: a name for great deeds warms people to you (and impresses the proud and the greedy more than it should), while a name for cruelty frightens them, the kind ones worst of all.
Ask who they are, about the place, for news (dangerous roads, places you did not know, which then appear on your map) and about the other people in town. Some choices are skill checks, shown like <loot>[Insight]</>; when the Player2 AI is running, notable people speak in their own words and suggest checks that fit the moment.
<title>Trade</title>
Shopkeepers, smiths, healers, market traders, innkeepers and stablemasters trade. In the market window, <loot>Enter</> buys or sells one, <loot>Tab</> switches between their goods and yours, <loot>h</> haggles (once a day). Prices depend on the place: goods are cheap where they are made (salt on the coast, iron in the hills, furs in the cold north, grain on the plains) and dear where nobody makes them, so carrying trade goods between towns pays. Merchants have only so much coin, restock every week, and won't buy stolen goods.
<title>Services</title>
Ask "What can you do for me?": beds for the night (a real sleep, safe from the wilds), hot meals, baths, performing and dice at the inn; healers who treat every wound at once, operate on internal bleeding and sell herbal cures; priests who pray for healing and cures (for a donation); smiths who mend battered weapons and armour; a day's paid work; and at the stable, mules, ponies and horses. A mule carries 200 lb for you; horses make open ground and roads quicker if everyone rides. Animals need a bag of fodder a day, or grazing outside winter, or they starve.

<title>Factions</title>
  <loot>f</>               Factions: the realms, lords, churches, guilds, tribes and outlaws you know of
The land is divided among kingdoms and the noble houses sworn to them, free cities, dwarven clans, highland clans and elven realms; tribes hold the wild country. Churches, knightly orders, guilds, mercenary companies, and secret thieves and cults work within and across them. Each has a leader, values, friends and enemies, and realms have their own laws. You have a standing with each (<danger>Hated</>, <warn>Distrusted</>, Neutral, <good>Respected</>, <good>Honoured</>): people who answer to a faction treat you by it, and a price on your head makes the watch unfriendly. Your background may have given you friends, a family, or a bounty. Rulers live in their seats: the king in the keep, the lady in her hall.
What you do spreads as news, about 24 miles a day along the roads. Helping a faction pleases its friends and angers its enemies once they hear of it. Beating bandits angers their gang and pleases the lord of the land. Your fame and infamy go before you.
Join a guild, church, order or company by asking one of its people (you need their good opinion, and sometimes a skill, a trade, a faith or a fee). Members rise in rank as their standing grows and get better prices. The thieves' guild and the cults hide among ordinary folk: the right question may find them. A ruler who honours you may grant you a title.

<title>News, history and a world that moves on</title>
  <loot>n</>               News and history: what you have heard, the chronicle of the land, dragons, lost treasures and legends
The world has centuries of history behind it: dynasties, wars, plagues, dragons and heroes. And it does not stand still while you play. Rulers grow old and die, and their heirs (or whoever seizes the seat) follow. Neighbours who hate each other go to war, fight battles, besiege and take towns, and make peace. Vassals rebel. Plague and famine come and go, tribes raid the borders, cults spread in secret, outlaw gangs rise and are hanged.
Everything that happens becomes news, travelling about 24 miles a day along the roads: you hear it in inns, from travellers and on the <loot>¶</> notice board in a town's square (walk into it to read it). A besieged town is dear and hungry; war brings soldiers, refugees and deserters to the roads; plague can follow you home.

<title>Law and crime</title>
Each realm has its own laws: magic may need a licence or be forbidden, some goods are contraband, some lords keep the game for themselves, and punishments run from lenient to cruel. Theft, pickpocketing, trespass (in someone's house at night), assault, murder, poaching, smuggling, unlicensed magic, witchcraft and heresy are crimes.
A crime needs a witness. A guard who sees it arrests you on the spot; anyone else goes to the watch within a few hours, unless you persuade, pay or frighten them into silence (talk to them). Unwitnessed crimes are never traced. A reported crime puts a price on your head in that realm; where you are wanted, the watch may recognise you.
When the watch takes you: <loot>P</>ay what you owe (petty crimes only), go <loot>Q</>uietly and take the sentence (a fine, jail, the lash, the brand, hard labour or the rope, by the local law), <loot>B</>ribe the guard, <loot>R</>un, or <loot>F</>ight. In jail your belongings are held until you are released. You may try to escape. Settle your debts with a guard, the headman or the lord.
  <loot>s</>               In a market: try to steal the chosen item (Sleight of Hand)
Walled towns search travellers at the gate now and then: what the law forbids there, and anything you are carrying that is meant to stay out of sight, is taken (and that is smuggling, whoever asked you to carry it).
A disguise kit (general stores) lets you become a stranger for half a day: crimes are blamed on the stranger, and the watch may not know your face. Take prisoners after a fight and hand them to any town's watch for a reward.

<title>Danger</title>
The wilds are not empty. The more dangerous the region (shown in the side panel), the more likely something finds you, and night is worse; roads are a little safer. When trouble comes on the road you can <loot>F</>ight, <loot>A</>mbush (if you saw them first), <loot>S</>lip away (Stealth), or <loot>T</>alk your way past. Ruins, caves, barrows and towers have inhabitants; in the close view they show as letters, with a red background once they have noticed you. Walk into them to attack.

<title>Battle</title>
Each side stands in two ranks. Melee blows reach only the enemy's front rank (unless it is empty, or you have a reach weapon); from the back rank you need a bow, a thrown weapon or a spell. Everyone acts in order of initiative. On your turn:
  <loot>a</>               Attack (pick a weapon, then a target: number keys, arrows, or click)
  <loot>c</>               Cast a spell (cantrips are free; others use a spell slot)
  <loot>u</>               Use an item: potions, bandages, healer's kit
  <loot>b</>               Class ability: Second Wind, Action Surge, Turn Undead...
  <loot>d</>               Dodge: attacks against you have disadvantage until your turn
  <loot>h</>               Help an ally (advantage), or first aid for someone bleeding out
  <loot>s</>               Shove (knock down, push back) or grapple
  <loot>r</>               Change rank (front / back)
  <loot>p</>               Parley: talk them down, threaten, or calm animals
  <loot>y</>               Surrender (only to those who take prisoners)
  <loot>f</>               Flee (everyone standing must get away)
  <loot>Click an enemy</>  Attack it with the first weapon that reaches
  <loot>PgUp PgDn</>       Scroll the battle log
Blows land on a part of the body and may leave wounds: cuts bleed until bandaged, broken bones stay broken. At 0 hit points you fall and start bleeding out; a friend can stop it (Help, a healer's kit, or a healing spell). Enemies lose heart: beasts run, bandits and soldiers may surrender, fanatics and the dead never do. Afterwards you decide the fate of prisoners and take what you want from the fallen. Death is permanent.

<title>Underground</title>
Ruins, caves, barrows, towers and the lairs of gangs and cults have something below them. In the close view, the steps down show as <loot>></>: walk onto them. Deeper levels are worse, and the master of the place waits at the bottom.
It is dark down there. Light a torch or a lantern from your pack (they burn out; carry spares) or you see only what is under your nose; dwarves and elves see a little in the dark. Doors may be locked (walk into them: thieves' tools help, or force them), chests and coffins are opened the same way, and opening a coffin may wake what lies in it.
  <loot>s</>               Search where you stand: traps, secret doors, hidden rooms (Perception)
  <loot><</> <loot>></>             Stairs up and down
Traps are hidden until you spot them: darts, pits, falling stone, gas, and worse. Search before you walk into a room you don't like the look of. A dragon's hoard is guarded by the dragon.

<title>Magic items</title>
Magic is rare, and most of it is old. What you find looks like "a strange sword" until you know it: <loot>Enter</> on it in your pack studies it for an hour (Arcana, once a day for each thing), or a priest will tell you what it is for a donation. Known items list what they do and carry the name and history the world remembers.
Some things are cursed: they cannot be taken off, and they work against you. A temple can lift a curse. Wands and rings with charges refill after a long rest.

<title>Dragons</title>
Every land has its dragon, and everyone knows its name. Most were killed by heroes long ago; one or two are only sleeping, each in a lair in the high country. A sleeping dragon still comes down now and then to burn a village or take cattle and silver as tribute, and the news travels. The country around a lair tells you: burned trees, bones in the grass, no birds singing.
It is a very hard fight and it will kill an unready party. Its hoard is real gold, heaped up and slept on, and taking any of it wakes the owner. Kill one and the world hears of it: your name goes into the chronicle (n) beside the old heroes, the tribute stops, and lords pay well for the head. Some of them will pay in advance, if you ask for work.

<title>Paper</title>
Few can read, so books, maps and letters are treasure. In your pack, <loot>Enter</> reads one (an hour). A map puts real places on your map; a book of histories tells you who held this country and adds a faction to your list; old lore names where one of the world's lost treasures came to rest; a dead stranger's letter points at somewhere worth going. Everything they say is true of this world, and they say the same thing every time you read them.

<title>Work and the journal</title>
  <loot>j</>               The journal: work in hand, what is left to do, and how it ended
Ask people in a town "Is there any work?". Anyone of standing (and now and then an ordinary soul) may have something: a bounty on a real gang's captain, a lair to clear, a named beast to hunt, a sealed letter to carry, an heirloom or a lost treasure of the old days to bring back, a son or daughter taken by outlaws, a debt to collect, people going missing, someone to walk safely to another town, herbs for a sickness, a feud to settle, a pocket to pick, a village that knows the raiders are coming and wants a sword in the street on the day, a crate that must reach another town without the gate wardens seeing it — and, if you look like you might live through it, a dragon. Wanted posters on the <loot>¶</> notice board can be taken down and taken on (press the number shown).
Each job has a reward and a number of days. The journal marks where to go; the place is put on your map, and the tile is lit on the map and the world map (m) until the job is done. When it is done, go back to whoever set it and say so. Failing it, or giving it up (<loot>a</> in the journal), sours the giver and their people.
Not everything is as it was told to you. Outlaws may turn out to be starving deserters you could talk into leaving instead of killing; the debtor may have nothing but children and an empty house; a sealed letter may be worth reading, and once read it can be delivered anyway, taken to the lord, or held over the sender's head; the man you were paid to kill may be nobody's enemy, and telling him who paid is worth something too. Your companions notice what you choose.

<title>When you die</title>
Death is permanent. There is no reload: the game saves as you go, and that save is the only one. When you die you get an obituary — what you were, how you died, what you killed, what you did that anyone will remember, and what the powers of the land thought of you — and everything you carried is gone. There is no body and no grave to loot.
What is left is the world. Your deeds stay in its history and its news; famous deaths are remembered in the chronicle. Companions who outlived you go home and can be hired by whoever comes next.
From the title screen, <loot>New Character</> begins a new life in a world you have already played. Weeks or months pass first — rulers die, wars begin and end, towns change hands, plague comes and goes — and you are told what changed before you take your first step into it.

<title>How much the game says</title>
Settings has <loot>Text detail</>: <loot>Brief</> keeps only what matters (fights, needs, news, what you find), <loot>Normal</> adds the world's voice — street life in towns, companions talking on the road, the weather turning, what you hear in the night — and <loot>Rich</> gives you more of it.

<title>Other screens</title>
  <loot>L</>               The full message log
  <loot>/</>               Map legend: what every symbol means
  <loot>Esc</>             Game menu: help, settings, save and leave

<title>Player2 AI</title>
The game uses the free Player2 app to write names, descriptions and dialogue. Keep Player2 running for AI text. Without it the game still works, using its own built-in text. The indicator in the bottom-right corner shows which is in use. The AI never decides what happens: dice and rules do.
Player2 gives a limited amount of free energy a day, so the game spends it carefully: people, places and conversation first. In Settings, <loot>AI extras</> turns off the rest (regions, dungeons, magic items, the wording of work, obituaries) if you would rather keep the energy for the people.

<title>If something goes wrong</title>
The game tries never to crash: if something breaks it says so, writes the details to <loot>%APPDATA%\\Realmwalker\\logs\\errors.log</> and carries on. That file is the thing to send if you report a problem. Your saves, settings and screenshots live in the same folder.
"""


class HelpScreen(Screen):
    title = "Help"

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
