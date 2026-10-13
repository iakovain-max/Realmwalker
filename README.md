# Realmwalker

A grim, open-world fantasy role-playing game in the spirit of Dwarf Fortress adventure mode and Caves of Qud, played
on the rules of Dungeons & Dragons. You make a character in a large generated world and do whatever you like: travel,
trade, fight, scheme, survive... and in the end die. The world goes on without you.

Drawn in pixel art: people dressed in what they really wear, towns built the way each people builds, dungeons, a map
painted on parchment, and fights on a battle mat with animation. Playable with the keyboard or the mouse alone.

**For adults (18+):** violence, cruelty and grim themes.

## What you can do

- **Travel a world with a past that was really lived**, year by year, for 100 to 1,000 years (you choose):
  dynasties, named wars and battles, beasts and the heroes who hunted them, saints and heretics, swords and crowns
  passed from hand to hand. Every ruin was a real town, every lord has real ancestors, and the troll in the cave has
  killed people you can read about in the Legends book. The world keeps moving while you play: wars, plagues,
  sieges, new rulers, beasts coming down on the farms.
- **Meet its peoples.** Every people builds, dresses and names things its own way: Norse longhalls, Qasari domes and
  courtyards, Khurgan tent camps, Volsk onion domes, Itzan pyramids, dwarven holds cut into the mountain, elven homes
  in giant trees. Townsfolk live their day while you watch.
- **Stay alive**: hunger, thirst, cold, heat, exhaustion, wounds that bleed and fester, sickness, and treatment that
  matters (bandage, clean, stitch, splint).
- **Fight on a grid**, like a battle mat, with wounds, morale, surrender and prisoners, by the 2024 rules
  (*Dice & Destiny*, version 1.1): enemies that think, reactions that ask you first, the 2025 monsters, treasure and
  magic items by the book, an icon for every state and a card for anything you point at.
- **Talk to everyone.** They have names, trades, memories and opinions of you.
- **Hire companions**, pay them, keep them loyal (or don't), and command them in a fight.
- **Take on work**: bounties, lairs to clear, beasts to hunt, letters to carry, captives to free. Not every job is
  what you were told it was.
- **Go underground**: cellars, crypts, caves and barrows, with traps, locked doors, secret rooms, chests, and
  something waiting at the bottom.
- **Kill a dragon**, if you think you can. The world will remember who did it.
- **Die.** It is permanent. The world keeps your story, and you can begin a new life in the same world.

## How to get it and play (Windows)

1. On this page, click the green **Code** button, then **Download ZIP**.
2. Unzip it anywhere (your Desktop or Documents, for example).
3. Open the folder and double-click **`Play.bat`**.

The first time, `Play.bat` sets everything up by itself: it installs Python 3.12 if your PC does not have it (with
Windows' own installer) and the game's building blocks. That takes a minute or two; after that the game starts at
once. You do not need to install anything else.

If you know Git, you can instead clone the repository (`git clone https://github.com/iakovain-max/Realmwalker.git`)
and double-click `Play.bat` in it.

Windows may say it "protected your PC" from an unknown file the first time. Click **More info**, then **Run anyway**.

### Getting the newest version

- **Downloaded as a ZIP**: download the newest ZIP the same way and unzip it over the old folder (or into a new one).
  Your saved games are not in this folder, so they are safe.
- **Cloned with Git**: double-click **`Update_And_Play.bat`**. It fetches the newest version and starts the game.
  (It needs [Git for Windows](https://git-scm.com/download/win).)

New versions sometimes cannot read worlds or characters made by older ones; the game then says so kindly and leaves
the files untouched. Start a new world.

## Keys

Press **F1** in the game for the full list. The ones you need first:

| Key | What it does |
|---|---|
| Arrow keys, number pad | Walk (7 9 1 3 are the diagonals) |
| Enter | The obvious thing here: go into a town or the land around you; take what lies here; talk to who is beside you |
| t | Talk to someone beside you (on foot); travel (on the overworld) |
| m | The world map |
| l | Look around |
| r | Make camp, rest, sleep |
| c, i, h | Character sheet, pack, health |
| j | Journal (your work and the people you know) |
| x | Leave the close view, back to the world map |
| Esc | Back, close, the menu (Settings are there) |
| Ctrl + / Ctrl − | Bigger / smaller text |
| Ctrl M | All sound off and on |
| F11 | Fullscreen |

The mouse does everything too: click the map to walk there, click a person to talk, right-click anything to see what
you can do with it, and every action is a button along the bottom with its key in the corner.

## Your own music

The game comes with music, and you can add your own. In the game's folder is a folder called `music` (the game makes
it the first time it starts), with a folder for each moment: title, travel, town, tavern, dungeon, rest, combat,
boss, victory, defeat and death. Put `.ogg`, `.mp3`, `.flac` or `.wav` files in them. In the game, Esc → Settings →
Your music shows what plays when.

## Where things are saved

Settings, saved worlds and screenshots live in `%APPDATA%\Realmwalker` (paste that into the address bar of a File
Explorer window). If something goes wrong, the file `logs\errors.log` in the game's own folder (beside `Play.bat`)
helps fix it: send that.

## Credits

Realmwalker is a free fan project, shared with friends; it is not sold. Its rules are adapted from the Dungeons &
Dragons 5th edition core books (the 2024 *Player's Handbook* and *Dungeon Master's Guide* and the 2025 *Monster
Manual*) and the System Reference Document 5.1 by Wizards of the Coast; Dungeons & Dragons and the names of its
monsters and magic items belong to Wizards of the Coast. All descriptions, places, people and stories in the game are
written for Realmwalker.

Tiles from Dungeon Crawl Stone Soup (CC0), adapted; the people, buildings, map and much else drawn in code for the
game. Sounds and music by Kenney, artisticdude, rubberduck and RandomMind (CC0). Typefaces DejaVu Sans Mono, Cinzel,
EB Garamond and Grenze Gotisch. Full details in [`docs/CREDITS.md`](docs/CREDITS.md).
