"""Help: every key binding and a short guide. Grows with each milestone."""

from __future__ import annotations

from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas, ScrollText

HELP_TEXT = """<title>Realmwalker</title>
A grim, open-world party role-playing game built on the rules of Dungeons & Dragons 5th Edition. Travel, trade, fight, scheme, survive, and eventually die. The world goes on without you.

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
  <loot>c</>               Character sheet: abilities, skills, features, ties, backstory
  <loot>i</>               Inventory: Enter wears/wields/removes, d drops, D drops one, ← → filters, s sorts
  <loot>e</>               Equipment: what you wear in each slot, which body parts are protected, warmth
  <loot>g</> or <loot>,</>          Pick up what is lying here (on foot, in the close view)
Carrying weight matters: worn armour and clothes count half. Above your limit you are slowed; far above it you cannot walk. Coins weigh too.
  <loot>r</>               Camp: fire, tent, eat, cook, boil water, forage, hunt, fish, rest, sleep
  <loot>h</>               Health: needs, warmth, blood, pain, wounds and their treatment, sickness
  <loot>w</>               Fill your waterskins (and drink) at a well, river or lake
  <loot>W</>               Wash (at water)

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

<title>Other screens</title>
  <loot>L</>               The full message log
  <loot>/</>               Map legend: what every symbol means
  <loot>Esc</>             Game menu: help, settings, save and leave

<title>Player2 AI</title>
The game uses the free Player2 app to write names, descriptions and dialogue. Keep Player2 running for AI text. Without it the game still works, using its own built-in text. The indicator in the bottom-right corner shows which is in use. The AI never decides what happens: dice and rules do.

<title>More to come</title>
Companions, quests and a proper obituary arrive milestone by milestone. This page lists every key as they are added.
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
