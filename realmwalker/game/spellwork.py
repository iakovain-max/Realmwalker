"""What spells do outside a fight (Expansion 3 E.1): food and water, purifying what has turned, a feast, wards on the
camp, a body kept from decay, a curse loosened, a body made whole. A spell says which with its op {"op": "road",
"does": ...} (rules/spells.ROAD_USES); game/magic.cast_on_road spends its slot and materials and calls `cast` here.

Wards live on the camp (game/camp.Camp.wards: ward -> {"until", "dc", "by"}), so walking away leaves them behind:
- alarm (Alarm): whatever comes in the night wakes the camp; nobody takes the animals unseen.
- hound (Mordenkainen's Faithful Hound): the same, and the phantom dog bites the first to come (4d8 force, a
  Dexterity save against the caster's DC).
- hut (Leomund's Tiny Hut): a dome nothing can pass; the night's visitors go away, and inside it is dry and warm.
- rope (Rope Trick): a space out of the world for an hour: a short rest even with enemies hunting nearby.
- mansion (Mordenkainen's Magnificent Mansion): a door out of the world for a day: a feast, a warm dry night, and
  rest even with enemies hunting.

Companions do what they would on their own: before a long rest in the wild one who knows a ward as a ritual casts it
(`before_rest`); when the party has nothing to eat or drink one with a food or water spell ready casts it
(`conjure`).
"""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.core.textgen import escape_markup
from realmwalker.rules import spells as spellrules
from realmwalker.rules.character import Character
from realmwalker.rules.inventory import WATER_RISK, add_item, container_capacity, distinct_packs, remove_item

HOUR = 60
FEAST_EATING = 60  # minutes: the feast takes an hour to eat before its good sets in (PHB 2024)
HOUND_BITE = "4d8"


def _first(c: Character) -> str:
    return escape_markup(c.name.split()[0])


def _road(spell: dict) -> dict:
    return spellrules.op(spell, "road") or {}


# ---------------------------------------------------------------------------- wards on the camp
def wards_here(game) -> dict:
    """The wards still up at the camp the party is in: ward -> its record."""
    from realmwalker.game.camp import camp_here

    camp = camp_here(game)
    if camp is None or not camp.wards:
        return {}
    now = game.world.time
    for k in [k for k, v in camp.wards.items() if float(v.get("until", 0)) < now]:
        del camp.wards[k]
    return dict(camp.wards)


def warded(game, *kinds: str) -> str | None:
    """The first of these wards up at the camp here, or None."""
    here = wards_here(game)
    return next((k for k in kinds if k in here), None)


def sheltering(game) -> bool:
    """A Tiny Hut or a Mansion: dry and comfortable whatever the weather outside."""
    return warded(game, "hut", "mansion") is not None


def hidden(game, kind: str) -> bool:
    """May the party rest here though enemies hunt nearby? Out of the world: a Mansion (any rest), a Rope Trick (a
    short one); a lone caster melded into stone (any rest); a camp veiled by Hallucinatory Terrain or Mirage Arcane
    (any rest: hunters pass it by)."""
    if warded(game, "meld") is not None and len([c for c in game.party if c.alive]) == 1:
        return True
    if warded(game, "veil") is not None and _veil_holds(game):
        return True
    from realmwalker.game import warding

    if warding.keeps_out(game):  # (E.6: Guards and Wards' fog; a Magic Circle or hallowed ground against its kinds)
        return True
    return warded(game, "mansion") is not None or (kind == "short" and warded(game, "rope", "demiplane") is not None)


def _veil_holds(game) -> bool:
    """Hunters on a close-up map look for the veiled camp: the cleverest of them makes an Intelligence (Investigation)
    check against the caster's DC (rolled once an hour)."""
    lm = game.local
    if lm is None:
        return True
    rec = wards_here(game)["veil"]
    hunters = [cr for a in lm.actors if a.alert for cr in a.creatures if cr.hp > 0]
    if not hunters:
        return True
    best = max(int((game.tables.creatures[cr.def_id].get("abilities") or {}).get("int", 10)) for cr in hunters)
    rng = game.world.rng.child(f"veil/hunt/{game.world.time // 60}")
    return dice.d20(rng).natural + (best - 10) // 2 < int(rec.get("dc", 13))


def night_visitors(game, enc) -> tuple[object, list[str]]:
    """Something comes for the camp in the night: what the wards do about it. Returns the encounter (None when it is
    turned away) and what to say."""
    ward = warded(game, "mansion", "hut", "veil", "decoy", "earthworks", "hound", "mouth", "alarm")
    if ward in ("mansion", "hut"):
        where = "the shimmering door" if ward == "mansion" else "the dome"
        return None, [f"In the night something comes to {where}, circles it, finds no way in, and goes away."]
    if ward == "veil":  # (Hallucinatory Terrain, Mirage Arcane: an Investigation check against the DC sees through)
        rec = wards_here(game)["veil"]
        rng = game.world.rng.child(f"veil/{game.world.time}")
        best = max((int((game.tables.creatures[cr.def_id].get("abilities") or {}).get("int", 10))
                    for cr in enc.creatures if cr.hp > 0), default=10)
        if dice.d20(rng).natural + (best - 10) // 2 < int(rec.get("dc", 13)):
            return None, ["In the night something passes close by the camp, and goes on: to its eyes there was "
                          "nothing here."]
        ward = warded(game, "decoy", "earthworks", "hound", "mouth", "alarm")
        notes = ["<warn>Something in the night stops, and looks through the land's false face at the camp.</>"]
        enc2, more = night_visitors_after_veil(game, enc, ward)  # (with no other ward: an awakened animal's watch)
        return enc2, notes + more
    return night_visitors_after_veil(game, enc, ward)


def night_visitors_after_veil(game, enc, ward: str | None) -> tuple[object, list[str]]:
    from realmwalker.game import warding

    enc, first = warding.night(game, enc)  # (E.6: hallowed ground, a circle, the fog, a glyph, a symbol, forbiddance)
    if enc is None:
        return None, first
    enc2, more = _after_the_lasting(game, enc, ward)
    return enc2, first + more


def _after_the_lasting(game, enc, ward: str | None) -> tuple[object, list[str]]:
    if ward == "decoy":  # (Programmed Illusion: they fall on an illusory camp; the real one is awake)
        enc.asleep, enc.warned = False, True
        enc.spotted_first = True
        return enc, ["<warn>In the dark, shapes fall on a camp a little way off, and find nothing there but "
                     "an illusion.</> You are awake, and they have not seen you yet."]
    if ward == "earthworks":  # (Move Earth: seen climbing the ditch and the bank)
        enc.asleep, enc.warned = False, True
        enc.spotted_first = True
        return enc, ["<warn>Something comes over the ditch in the dark and scrabbles up the bank:</> you are awake, "
                     "and see it before it sees you."]
    if ward == "hound":
        rec = wards_here(game)["hound"]
        notes = ["<warn>The phantom hound bays in the dark: something is coming.</>"]
        foe = next((cr for cr in enc.creatures if cr.hp > 0), None)
        if foe is not None:
            rng = game.world.rng.child(f"hound/{game.world.time}")
            dc = int(rec.get("dc", 13))
            dex = (game.tables.creatures[foe.def_id].get("abilities") or {}).get("dex", 10)
            save = dice.d20(rng).natural + (int(dex) - 10) // 2
            if save < dc:
                hurt = dice.roll(HOUND_BITE, rng).total
                foe.hp = max(1, foe.hp - hurt)
                notes.append(f"Unseen jaws close on the first of them: {hurt} force.")
        enc.asleep, enc.warned = False, True
        return enc, notes
    if ward == "alarm":
        enc.asleep, enc.warned = False, True
        return enc, ["<warn>A bell rings out of nowhere in the dark: the alarm. Something is coming.</>"]
    if ward == "mouth":  # (Magic Mouth)
        enc.asleep, enc.warned = False, True
        return enc, ["<warn>A voice cries out from a stone at the edge of the camp: something is coming.</>"]
    return _awake_watch(game, enc, [])


def _awake_watch(game, enc, notes: list[str]) -> tuple[object, list[str]]:
    """An awakened animal keeps watch (Awaken): the camp is never caught asleep."""
    from realmwalker.game import glamour

    a = glamour.awake_animal(game)
    if a is not None and not enc.warned:
        enc.asleep, enc.warned = False, True
        notes = notes + [f"<warn>{escape_markup(a['name'])} wakes you with a word: \"Up. Something comes.\"</>"]
    from realmwalker.game import allies

    fam = allies.watcher(game)  # (Find Familiar: a familiar keeps watch as an awakened animal does)
    if fam is not None and not enc.warned:
        enc.asleep, enc.warned = False, True
        notes = notes + [f"<warn>{escape_markup(fam['name'])} the {fam['form']} rouses you in the dark: "
                         f"something is coming.</>"]
    return enc, notes


def guards_the_animals(game) -> str:
    """Words for a ward that keeps the animals from rustlers, or ""."""
    ward = warded(game, "mansion", "hut", "veil", "hound", "mouth", "alarm")
    from realmwalker.game import glamour, warding

    if ward is None and warding.guards_the_animals(game):  # (E.6: a sanctum's fog, Guards and Wards)
        return warding.guards_the_animals(game)
    if ward is None and glamour.awake_animal(game) is not None:
        return (f"{escape_markup(glamour.awake_animal(game)['name'])} calls out in the small hours: someone was at the "
                f"animals, and runs off with nothing.")
    return {"mansion": "The animals stand safe in the Mansion's stable.",
            "veil": "Whoever came for the animals in the night could not find the camp.",
            "mouth": "A voice cries out from a stone in the small hours: someone was at the animals, and runs off.",
            "hut": "Whoever came for the animals found the dome and went away with nothing.",
            "hound": "The phantom hound bays at someone by the tethers, and whoever it was runs off with nothing.",
            "alarm": "The alarm rings in the small hours: someone was at the animals, and runs off with nothing."
            }.get(ward or "", "")


def ward_minutes(spell: dict) -> int:
    """How long a ward stands: its rounds, or its days (Mirage Arcane's ten; Magic Mouth and Programmed Illusion
    stand while you camp, which is never a month)."""
    if _road(spell).get("days"):
        return int(_road(spell)["days"]) * 24 * 60
    return int(spell.get("rounds", 4800)) // 10


def _ward(game, caster: Character, spell: dict, level: int) -> list[str]:
    from realmwalker.game.camp import make_camp

    ward = _road(spell)["ward"]
    camp = make_camp(game)
    minutes = ward_minutes(spell)
    dc = spellrules.save_dc(game.sheet(caster), game.tables)
    # (from the end of the casting: the minute it takes is still to pass)
    camp.wards[ward] = {"until": game.world.time + minutes + int(spell.get("minutes", 1)), "dc": int(dc),
                        "by": caster.name}
    first = _first(caster)
    lasts = f"{minutes // 1440} days" if minutes >= 2880 else f"{minutes // 60} hours" if minutes >= 120 else ("an hour" if minutes >= 60 else f"{minutes} minutes")
    words = {
        "alarm": f"{first} walks the edge of the camp with a bell and a silver wire: anything that comes near in the "
                 f"next {lasts} will wake you.",
        "hut": f"A dome of shimmering force springs up around the camp, opaque from outside, dry and still within. It "
               f"lasts {lasts}, if nobody leaves it.",
        "hound": f"{first} blows a silver whistle that makes no sound. Somewhere in the dark a phantom hound sits down "
                 f"to watch, for {lasts}.",
        "rope": f"{first} throws a rope into the air; it hangs there, and at its top a window opens into a space out "
                f"of the world. For {lasts} you may rest in it, whoever hunts below.",
        "mansion": f"A shimmering door stands in the air. Beyond it, a fire-warmed hall, a table laid for a hundred, "
                   f"and soft beds: yours for {lasts}.",
        "meld": f"{first} lays both hands on a great rock and steps into it, gear and all. For {lasts}, nothing of "
                f"{first} can be seen or found; the stone hums faintly with the world outside.",
        # Part E.4's
        "decoy": f"{first} sprinkles jade dust in a ring some way off. Whatever comes in the night will find a camp "
                 f"there, fire and sleepers and all, and fall on it; the real one will be awake.",
        "mouth": f"{first} touches a stone at the edge of the camp, and a mouth opens in it, then closes. It will cry "
                 f"out when anything comes near, as long as you camp here.",
        "veil": f"{first} walks the camp's edge, and the land round it changes: to any eye outside, there is "
                f"nothing here but {'more of the same land' if minutes < 2880 else 'land of another kind entirely'}, "
                f"for {lasts}.",
        # Part E.5's
        "earthworks": f"{first} kneels and presses both hands to the ground, and for ten minutes the earth round the "
                      f"camp heaves and slides: a ditch opens, a bank rises behind it. Whatever comes in the night "
                      f"will have to climb it.",
    }
    out = [words[ward]]
    if ward == "mansion":
        for c in game.party:
            if c.alive:
                c.hunger, c.thirst = 0.0, 0.0
        out.append("<good>Everyone eats and drinks their fill at the banquet.</>")
    return out


# ---------------------------------------------------------------------------- food and water
def _skins(game) -> list:
    return [it for m in distinct_packs(game.party) for it in m.inventory if container_capacity(game.tables.items, it)]


def _pour(game, pints: float) -> float:
    """Fill the party's skins with clean water, up to `pints`; returns what went in."""
    left = pints
    for it in sorted(_skins(game), key=lambda it: -WATER_RISK.get(it.fill_kind, 0)):
        if left <= 0:
            break
        cap = container_capacity(game.tables.items, it)
        if it.fill > 0 and WATER_RISK.get(it.fill_kind, 2) > 0:
            continue  # (foul water stays foul: clean water poured into it would be spoiled too)
        room = cap - it.fill
        if room <= 0:
            continue
        put = min(room, left)
        it.fill = round(it.fill + put, 2)
        it.fill_kind = "clean"
        left -= put
    return pints - left


def _drink_all(game, pints: float) -> float:
    """Everyone thirsty drinks from the conjured water before it goes into the skins; returns what they drank."""
    from realmwalker.rules import body

    drunk = 0.0
    for c in game.party:
        if c.alive and c.thirst >= 10 and drunk < pints:
            want = min(pints - drunk, max(1.0, round(c.thirst / body.PINT_POINTS)))
            body.drink(c, want)
            drunk += want
    return drunk


def _water(game, caster: Character, spell: dict, level: int) -> list[str]:
    r = _road(spell)
    pints = float(r.get("pints", 80)) + float(r.get("per_up", 0)) * max(0, level - int(spell["level"]))
    drunk = _drink_all(game, pints)
    put = _pour(game, pints - drunk)
    gallons = round(pints / 8)
    out = [f"{_first(caster)} speaks a word over the skins, and clean water wells up out of nothing ({gallons} "
           f"gallons)."]
    if drunk:
        out.append("Everyone who was thirsty drinks.")
    out.append(f"<dim>{put:g} pints go into the waterskins; the rest soaks away.</>" if put else
               "<dim>The skins were full already; the rest soaks away.</>")
    return out


def _feed(game, caster: Character, spell: dict, level: int) -> list[str]:
    r = _road(spell)
    out = []
    if r.get("rations"):
        add_item(caster, game.tables.items, r.get("item", "conjured_food"), int(r["rations"]), made_at=game.world.time,
                 tags=[f"made:{int(game.world.time)}"])  # (its own stack: it spoils a day after this casting)
        out.append(f"{_first(caster)} spreads a cloth, and on it lies bread, cheese and dried fruit enough for "
                   f"{int(r['rations'])} days of eating. <dim>Bland, nourishing, and it spoils in a day.</>")
    if r.get("pints"):
        drunk = _drink_all(game, float(r["pints"]))
        put = _pour(game, float(r["pints"]) - drunk)
        out.append(f"Beside it, clean water fills every skin" + (" and every thirsty mouth" if drunk else "")
                   + f". <dim>({put:g} pints into the skins.)</>")
    return out


def _goodberry(game, caster: Character, spell: dict, level: int) -> list[str]:
    n = int(_road(spell).get("berries", 10))
    add_item(caster, game.tables.items, "goodberry", n, made_at=game.world.time,
             tags=[f"made:{int(game.world.time)}"])  # (its own stack: gone a day after this casting)
    return [f"{n} berries swell in {_first(caster)}'s hand, warm with magic. <dim>Each one feeds a body for a day "
            f"and heals a hit point; they are gone in a day.</>"]


def spoiled_things(game) -> tuple[list, list]:
    """Food that has turned and water that is foul, in the party's packs."""
    from realmwalker.game.survival import spoiled

    food = [it for m in distinct_packs(game.party) for it in m.inventory
            if game.tables.items.get(it.def_id).get("food") and spoiled(game, it)
            and not game.tables.items.get(it.def_id)["food"].get("vanishes")]
    water = [it for it in _skins(game) if it.fill > 0 and WATER_RISK.get(it.fill_kind, 2) > 0]
    return food, water


def _purify(game, caster: Character, spell: dict, level: int) -> list[str]:
    food, water = spoiled_things(game)
    for it in food:
        it.made_at = game.world.time  # (rid of poison and rot: as good as the day it was made)
    for it in water:
        it.fill_kind = "clean"
    bits = []
    if food:
        bits.append(f"{len(food)} lot{'s' if len(food) != 1 else ''} of turned food")
    if water:
        bits.append(f"{len(water)} skin{'s' if len(water) != 1 else ''} of foul water")
    return [f"{_first(caster)} passes a hand over {' and '.join(bits)}: the rot and the poison go out of it."]


def _feast(game, caster: Character, spell: dict, level: int) -> list[str]:
    t = game.tables
    sid = next(k for k, v in t.spells.defs.items() if v is spell)
    rng = game.world.rng.child(f"feast/{game.world.time}")
    guests = [c for c in game.party if c.alive][: int(_road(spell).get("count", 12))]
    out = [f"{_first(caster)} lays out a feast on a gem-studded bowl that melts away as the last dish is served. "
           f"Everyone eats for an hour."]
    for c in guests:
        c.hunger, c.thirst = 0.0, 0.0
        c.effects.pop("poisoned", None)
        gained = spellrules.raise_max(c, sid, spellrules.max_up_amount(spell, level, rng))
        spellrules.keep(c, t, sid, level)
        out.append(f"<good>{_first(c)}</> feels strong and unafraid" + (f": +{gained} hit points" if gained else "")
                   + " for a day.")
    out.append("<dim>For a day: no poison takes hold and it harms less, and nothing frightens them.</>")
    return out


# ---------------------------------------------------------------------------- the body
def cursed_on(c: Character) -> list:
    """Cursed things holding this character (worn or bound), not yet loosened."""
    from realmwalker.rules import magic
    from realmwalker.rules.inventory import cursed

    worn = [c.item(uid) for uid in c.equipped.values()]
    out = [it for it in worn + list(magic.attuned_items(c)) if it is not None and cursed(it)]
    return list({id(it): it for it in out}.values())


def _uncurse(game, caster: Character, spell: dict, level: int, target: Character) -> list[str]:
    from realmwalker.game import servants

    out = []
    if servants.lift_rot(target):  # (a mummy's rot: Expansion 3 F.4)
        out.append(f"{_first(caster)} lays a hand on {_first(target)}, and the grey rot in the flesh dries up and "
                   f"flakes away. <good>The curse is lifted; the strength it ate comes back.</>")
    things = cursed_on(target)
    if not things:
        return out
    names = []
    for it in things:
        it.magic["loosed"] = True
        it.magic["curse_known"] = True
        target.attuned = [u for u in target.attuned if u != it.uid]
        names.append(escape_markup(game.tables.items.name(it, False)))
    return out + [f"{_first(caster)} lays a hand on {_first(target)}: the grip of the {', the '.join(names)} loosens. "
                  f"<dim>The curse is still in it, but it can be taken off and thrown away now; put on again, it "
                  f"takes hold again.</>"]


def _regenerate(game, caster: Character, spell: dict, level: int, target: Character) -> list[str]:
    lost = [i for i in target.injuries if i.startswith("lost_")]
    target.injuries = [i for i in target.injuries if not i.startswith("lost_")]
    target.wounds = []
    target.hp = target.max_hp
    target.blood = max(target.blood, 80.0)
    out = [f"{_first(caster)} touches {_first(target)}, and for an hour the flesh knits itself whole."]
    if lost:
        out.append(f"<good>What was cut away grows back within minutes.</>")
    out.append(f"<good>{_first(target)} is whole again.</>")
    return out


def _repose(game, caster: Character, spell: dict, level: int, target: Character) -> list[str]:
    from realmwalker.game import revival

    body = revival.body_of(game, target)
    days = int(_road(spell).get("days", 10))
    return [f"{_first(caster)} lays a copper coin on each of {_first(target)}'s eyes and a pinch of salt on the "
            f"tongue.", revival.repose(game, body, max(1, days))]


# ---------------------------------------------------------------------------- a flame that never goes out
def _flame(game, caster: Character, spell: dict, level: int) -> list[str]:
    """Continual Flame: a torch from the packs (or a stick, if there is none) burns for ever without heat."""
    from realmwalker.rules.inventory import add_item, remove_item

    torch = next(((m, it) for m in [caster] + [c for c in game.party if c is not caster]
                  for it in m.inventory if it.def_id == "torch"), None)
    if torch is not None:
        remove_item(torch[0], torch[1].uid, 1)
    add_item(caster, game.tables.items, "everburning_torch", 1)
    what = "a torch" if torch is not None else "a stick of wood"
    return [f"{_first(caster)} touches {what} and a flame springs from it: it gives no heat and burns no fuel. "
            f"<good>An everburning torch</>, for as long as nobody dispels it."]


# ---------------------------------------------------------------------------- the door
DOES = {"ward": _ward, "water": _water, "feed": _feed, "goodberry": _goodberry, "purify": _purify, "feast": _feast,
        "flame": _flame}
ON_SOMEONE = {"uncurse": _uncurse, "regenerate": _regenerate, "repose": _repose}


# Part E.3's: finding and seeing, asking the powers (game/divining.py), talking (game/speech.py)
DIVINING = ("sense", "locate", "scout", "summons", "ask")
SPEECH = ("speak", "send", "read")
# Part E.4's: minds and the law, illusions, the small arts (game/glamour.py)
GLAMOUR = ("mind", "illusion", "art")
# Part E.5's: locks and stone, weather and land (game/stonework.py)
STONEWORK = ("lock", "mend", "hand", "make", "stone", "chest", "weather", "plants", "wave")
# Part E.6's: lasting protections and the caster's keeping (game/warding.py)
WARDING = ("protect", "hallow", "demiplane", "cauldron")
# Part E.7's: great magic, and Wish's other uses outside a fight (game/greatmagic.py)
GREAT = ("contingency", "jar", "clone", "imprison", "wish")
# Part F.1's: a familiar and a steed (game/allies.py)
ALLIES = ("familiar", "steed")
# Part F.4's: the raised dead (game/servants.py)
SERVANTS = ("raise",)


def _does(spell: dict) -> str | None:
    return _road(spell).get("does") or spell.get("road_too")


def subjects(game, caster: Character, sid: str) -> list:
    """What a spell of Part E.3 can be aimed at here (a thing to seek, a question, a companion far away...)."""
    does = _does(game.tables.spells[sid])
    if does in DIVINING:
        from realmwalker.game import divining

        return divining.subjects(game, caster, sid)
    if does in SPEECH:
        from realmwalker.game import speech

        return speech.subjects(game, caster, sid)
    if does in GLAMOUR:
        from realmwalker.game import glamour

        return glamour.subjects(game, caster, sid)
    if does in STONEWORK:
        from realmwalker.game import stonework

        return stonework.subjects(game, caster, sid)
    if does in WARDING:
        from realmwalker.game import warding

        return warding.subjects(game, caster, sid)
    if does in GREAT:
        from realmwalker.game import greatmagic

        return greatmagic.subjects(game, caster, sid)
    if does in ALLIES:
        from realmwalker.game import allies

        return allies.subjects(game, caster, sid)
    if does in SERVANTS:
        from realmwalker.game import servants

        return servants.subjects(game, caster, sid)
    return []


def problem(game, caster: Character, sid: str, target) -> str | None:
    """Why this spell would do nothing here and now (None when it would)."""
    spell = game.tables.spells[sid]
    does = _does(spell)
    if does in DIVINING:
        from realmwalker.game import divining

        return divining.problem(game, caster, sid, target)
    if does in SPEECH:
        from realmwalker.game import speech

        return speech.problem(game, caster, sid, target)
    if does in GLAMOUR:
        from realmwalker.game import glamour

        return glamour.problem(game, caster, sid, target)
    if does in STONEWORK:
        from realmwalker.game import stonework

        return stonework.problem(game, caster, sid, target)
    if does in WARDING:
        from realmwalker.game import warding

        return warding.problem(game, caster, sid, target)
    if does in GREAT:
        from realmwalker.game import greatmagic

        return greatmagic.problem(game, caster, sid, target)
    if does in ALLIES:
        from realmwalker.game import allies

        return allies.problem(game, caster, sid, target)
    if does in SERVANTS:
        from realmwalker.game import servants

        return servants.problem(game, caster, sid, target)
    if does == "ward":
        ward = _road(spell)["ward"]
        rec = wards_here(game).get(ward)
        if rec is not None and float(rec["until"]) - game.world.time > ward_minutes(spell) // 2:
            return f"it is still working here ({max(1, round((float(rec['until']) - game.world.time) / 60))}h left)"
        if game.local is not None and game.local.kind == "settlement" and ward not in ("mansion", "meld"):
            return "not in the middle of a town"
        if ward == "meld" and len([c for c in game.party if c.alive]) > 1:
            return "only the caster fits in the stone: it hides one alone"
        if ward == "earthworks" and (game.local is not None and game.local.under_rock(game.player.lx, game.player.ly)
                                     or game.world.settlement_at(game.player.x, game.player.y) is not None):
            return "only in the open country, on earth that can be moved"
    if does == "water" and not _skins(game) and not any(c.alive and c.thirst >= 10 for c in game.party):
        return "there is nothing to put the water in, and nobody is thirsty"
    if does == "travel":
        from realmwalker.game import waymagic

        return waymagic.problem(game, caster, sid, target)
    if does == "purify" and spoiled_things(game) == ([], []):
        return "nothing you carry has turned or gone foul"
    if does == "uncurse" and (target is None or not cursed_on(target) and not target.effects.get("kept:mummy_rot")):
        return "no curse holds them"
    if does == "regenerate" and (target is None or (target.hp >= target.max_hp and not target.wounds
                                                    and not any(i.startswith("lost_") for i in target.injuries))):
        return "they are whole already"
    if does == "repose":
        from realmwalker.game import revival

        return revival.problem(game, sid, revival.body_of(game, target) if target is not None else None)
    return None


def cast(game, caster: Character, sid: str, target: Character | None, level: int) -> list[str]:
    """Do what the spell does (its slot and materials already spent). Passes no time: the caller passes the
    spell's casting time (`minutes`)."""
    spell = game.tables.spells[sid]
    does = _does(spell)
    if does in DIVINING or does in SPEECH or does in GLAMOUR or does in STONEWORK or does in WARDING or does in GREAT \
            or does in ALLIES or does in SERVANTS:
        from realmwalker.game import allies, divining, glamour, greatmagic, servants, speech, stonework, warding

        out = (divining if does in DIVINING else speech if does in SPEECH else glamour if does in GLAMOUR
               else stonework if does in STONEWORK else warding if does in WARDING
               else allies if does in ALLIES else servants if does in SERVANTS
               else greatmagic).cast(game, caster, sid, target, level)
        game.cue("spell")
        game.dirty = True
        return out
    if does in ON_SOMEONE:
        out = ON_SOMEONE[does](game, caster, spell, level, target or caster)
    elif does == "travel":
        from realmwalker.game import waymagic

        out = waymagic.travel(game, caster, sid, target, level)
    else:
        out = DOES[does](game, caster, spell, level)
    game.cue("heal" if does in ("regenerate", "feast") else "spell")
    game.dirty = True
    return out


def minutes(spell: dict) -> int:
    """How long the casting takes outside a fight (a feast is eaten for an hour more)."""
    m = int(spell.get("road_minutes") or spell.get("minutes", 1))  # (Plant Growth: an action in a fight, 8 hours here)
    return m + (FEAST_EATING if _road(spell).get("does") == "feast" else 0)


# ---------------------------------------------------------------------------- companions on their own
def _companion_casters(game) -> list[Character]:
    return [c for c in game.party[1:] if c.alive and c.hp > 0 and c.spells]


def before_rest(game) -> list[str]:
    """Before a long rest in the wild: a companion who knows a ward as a ritual casts it, the hut before the alarm
    (no slot: ten minutes more)."""
    from realmwalker.game import magic

    if game.local is not None or warded(game, "mansion", "hut") is not None:
        return []
    t = game.tables
    out: list[str] = []
    for sid in sorted((s for s, sp in t.spells.defs.items() if isinstance(sp, dict) and sp.get("ritual")
                       and _road(sp).get("does") == "ward"),
                      key=lambda s: -int(t.spells[s]["level"])):
        if warded(game, _road(t.spells[sid])["ward"]) is not None:
            continue
        c = _ritual_caster(game, sid)
        if c is not None:
            out = magic.cast_on_road(game, c, sid)
            break
    # (E.6: Forbiddance, a ritual too, burns what comes in the night; white fire)
    for sid in (s for s, sp in t.spells.defs.items() if isinstance(sp, dict) and sp.get("ritual")
                and _road(sp).get("how") == "forbiddance"):
        if warded(game, "forbiddance") is not None:
            continue
        from realmwalker.game import warding

        radiant = next((s for s in warding.subjects(game, game.leader, sid) if s.ref == "radiant"), None)
        c = _ritual_caster(game, sid, radiant)
        if c is not None:
            out += magic.cast_on_road(game, c, sid, radiant)
    return out


def _ritual_caster(game, sid: str, target=None) -> Character | None:
    """The first companion who can cast this spell as a ritual here and now (nothing in the way)."""
    from realmwalker.game import magic
    from realmwalker.rules import feats

    t = game.tables
    for c in _companion_casters(game):
        if sid in spellrules.known_spells(c, t) or sid in spellrules.ritual_spells(c, t) + feats.ritual_spells(c, t):
            if magic.road_problem(game, c, sid, target) is None:
                return c
    return None


def conjure(game, need: str) -> list[str]:
    """Nothing to eat ("food") or drink ("water"): a companion with a spell for it ready casts it (a slot spent).
    Called from inside the passing of time, so it passes none itself."""
    t = game.tables
    wanted = ("goodberry", "feed") if need == "food" else ("water", "feed")
    for c in _companion_casters(game):
        for sid in spellrules.known_spells(c, t):
            spell = t.spells[sid]
            does = _road(spell).get("does")
            if does not in wanted or (does == "feed" and need == "water" and not _road(spell).get("pints")):
                continue
            ok, _why = spellrules.can_cast(c, t, sid)
            level = int(spell["level"])
            slot = spellrules.lowest_free_slot(c, t, level) if level else None
            if not ok or (level and slot is None):
                continue
            if slot:
                spellrules.spend_slot(c, slot)
            spellrules.spend_material(c, t, sid)
            return [f"<magic>{_first(c)} casts {spell['name']}.</>"] + cast(game, c, sid, None, slot or level)
    return []


def tick(game) -> None:
    """As time passes: berries that are only magic are gone when it ends; a Geas or a charm runs out
    (game/glamour.py)."""
    from realmwalker.game import glamour, greatmagic, stonework, warding

    glamour.tick(game)
    stonework.tick(game)
    warding.tick(game)
    greatmagic.tick(game)
    items = game.tables.items
    for m in distinct_packs(game.party):
        for it in list(m.inventory):
            food = items.get(it.def_id).get("food") or {}
            if food.get("vanishes") and game.world.time - it.made_at > float(food.get("spoil_days", 1)) * 24 * 60:
                remove_item(m, it.uid)
