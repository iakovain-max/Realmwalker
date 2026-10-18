"""The wizard's wondrous things of the DMG 2024 outside a fight (Expansion 5 Part E): the Ring of Spell Storing (its
spells when found; a spell cast into it), the Robe of Useful Items (its patches, torn off), the Ruby of the War Mage
(set on a weapon and taken off), the Pearl of Power (a spell slot back), and what a crystal ball adds to Scrying.

- `on_make(game, item, rng)`: a ring's spells and a robe's patches, as the thing is made.
- `use_name(game, item)` / `use(game, char, item)`: the pack's verb for each, and what Enter does.
- `rings(game)`, `store_problem(game, caster, sid, level)`, `store(game, caster, sid, level)`: casting into a ring.
- `patches(item)`, `tear(game, char, item, patch)`; `ruby_weapons(char)`, `set_ruby`, `take_off_ruby`.
- `pearl_level(char, tables)`, `use_pearl(game, char, pearl)`; `scry_extras(game, caster, fig, rng)`.
"""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.core.rng import RNG
from realmwalker.core.textgen import escape_markup as esc
from realmwalker.rules import magic as magicrules
from realmwalker.rules import spells as spellrules

RING_MOST = 5  # levels a Ring of Spell Storing keeps
PATCH_WORDS = {  # what each patch becomes, as the robe's card and the pack say it
    "bullseye_lantern": "a bullseye lantern, filled and lit", "dagger": "a dagger", "mirror": "a steel mirror",
    "pole": "a ten-foot pole", "rope": "a coil of rope", "sack": "a sack", "gold_100": "a bag of 100 gold pieces",
    "silver_coffer": "a silver coffer worth 500 gold pieces", "gems_10": "ten gems worth 100 gold pieces each",
    "ladder": "a wooden ladder, 24 feet long", "riding_horse": "a riding horse with a riding saddle",
    "potions_4": "four potions of healing", "scroll_1_3": "a spell scroll of the first to third level",
    "mastiffs_2": "two mastiffs", "portable_ram": "a portable ram"}
CANNOT = ("iron_door", "pit", "window", "rowboat")  # (rolled again: nothing in the world to show them by)


def _store_prop(item) -> dict | None:
    return next((p for p in magicrules.props(item) if p.get("kind") == "store"), None)


def _patch_prop(item) -> dict | None:
    return next((p for p in magicrules.props(item) if p.get("kind") == "patches"), None)


def _ruby_prop(item) -> dict | None:
    return next((p for p in magicrules.props(item) if p.get("kind") == "war_ruby"), None)


def _pearl_prop(item) -> dict | None:
    return next((p for p in magicrules.props(item) if p.get("kind") == "trait" and p.get("trait") == "pearl_of_power"),
                None)


def _title(game, item) -> str:
    return esc(item.magic.get("title") or game.tables.items.name(item, False))


def _first(char) -> str:
    return esc(char.name.split()[0])


# ---------------------------------------------------------------------------- made
def on_make(game, item, rng: RNG) -> None:
    """A Ring of Spell Storing is found with 1d6 - 1 levels of spells in it (the DM's choice: here spells of the
    wizard's and the cleric's lists the world's casters would keep, at the numbers of a caster of that level); a Robe
    of Useful Items has two of each of its six patches and 4d4 more from the table."""
    store = _store_prop(item)
    if store is not None:
        n = max(0, dice.roll(str(store.pop("fill", "1d6-1")), rng).total)
        while n > 0:
            sid = _ring_spell(game, min(n, RING_MOST), rng)
            if sid is None:
                break
            level = int(game.tables.spells[sid]["level"])
            dc, attack = _numbers(game, level)  # (a caster of that level: the Enspelled things' numbers)
            _keep(game, item, sid, level, int(dc), int(attack), min(5, 2 + level // 2), "")
            n -= level
    patch = _patch_prop(item)
    if patch is not None:
        spec = _patch_table(game)
        left = [p for p in spec["always"] for _ in range(2)]
        for _ in range(max(0, dice.roll(str(patch.pop("extra", "4d4")), rng).total)):
            for _try in range(20):
                roll = rng.randint(1, 100)
                what = next((r[2] for r in spec["table"] if r[0] <= roll <= r[1]), None)
                if what and what not in CANNOT:
                    left.append(what)
                    break
        patch["left"] = left


def _patch_table(game) -> dict:
    from realmwalker.game import treasure

    return treasure.spec(game).get("patches") or {"always": [], "table": []}


def _numbers(game, level: int) -> list[int]:
    from realmwalker.game import treasure

    return treasure.spec(game).get("enspell", {}).get(str(level), [13, 5])


def _ring_spell(game, top: int, rng: RNG) -> str | None:
    t = game.tables
    pool = sorted(sid for sid, sp in t.spells.defs.items()
                  if 1 <= int(sp.get("level", 0)) <= top and set(sp.get("classes", ())) & {"wizard", "cleric"}
                  and not set(sp.get("classes", ())) & {"item", "creature", "again"} and not sp.get("again_of")
                  and not sp.get("stress") and not spellrules.out_of_battle(sp))
    return rng.choice(pool) if pool else None


def _keep(game, ring, sid: str, level: int, dc: int, attack: int, mod: int, by: str) -> dict:
    sp = game.tables.spells[sid]
    words = f"{sp['name']} (level {level}), kept in the ring" + (f" by {by}" if by else "") + \
        f": save DC {dc}, attack +{attack}. Cast once, then gone."
    prop = {"kind": "charges", "spell": sid, "level": level, "dc": dc, "attack": attack, "mod": mod, "value": 1,
            "left": 1, "stored": True, "no_regain": True, "worn": True, "text": words}
    ring.magic["props"].append(prop)
    return prop


# ---------------------------------------------------------------------------- the ring
def rings(game) -> list[tuple[object, object]]:
    """(wearer, ring) for every Ring of Spell Storing the party has on a finger, with room or not."""
    out = []
    for c in game.party:
        on = set(c.equipped.values())
        for it in c.inventory:
            if it.uid in on and _store_prop(it) is not None:
                out.append((c, it))
    return out


def room(item) -> int:
    store = _store_prop(item)
    return int(store.get("most", RING_MOST)) - magicrules.stored_levels(item) if store else 0


def store_problem(game, caster, sid: str, level: int | None) -> str | None:
    """Why `caster` cannot cast this spell into a party ring now (None: they can)."""
    t = game.tables
    sp = t.spells.get(sid) if hasattr(t.spells, "get") else t.spells[sid]
    if sp is None or not 1 <= int(sp["level"]) <= 5:
        return "only a spell of the first to fifth level goes into the ring"
    if game.battle is not None:
        return "not in the middle of a fight"
    found = rings(game)
    if not found:
        return "nobody in the party wears a Ring of Spell Storing"
    ok, why = spellrules.can_cast(caster, t, sid)
    if not ok:
        return why
    level = level or spellrules.lowest_free_slot(caster, t, int(sp["level"]))
    if level is None or level not in spellrules.slot_choices(caster, t, sid):
        return "no spell slot left for it"
    if level > 5:
        return "the ring takes nothing above the fifth level"
    if not any(room(r) >= level for _w, r in found):
        return f"no ring has room for {level} more levels"
    return None


def store(game, caster, sid: str, level: int | None = None) -> list[str]:
    """Cast a spell into the ring (the slot spent, its numbers kept): it has no other effect."""
    t = game.tables
    why = store_problem(game, caster, sid, level)
    sp = t.spells[sid]
    if why:
        return [f"{sp['name']}: {why}."]
    level = level or spellrules.lowest_free_slot(caster, t, int(sp["level"]))
    wearer, ring = next((w, r) for w, r in rings(game) if room(r) >= level)
    spellrules.spend_slot(caster, level)
    sheet = game.sheet(caster)
    mod = sheet.mod(spellrules.casting_ability(caster, t))
    _keep(game, ring, sid, level, spellrules.save_dc(sheet, t), spellrules.attack_bonus(sheet, t), mod,
          caster.name.split()[0])
    used = spellrules.spend_material(caster, t, sid)
    game.dirty = True
    whose = "" if wearer is caster else f" on {_first(wearer)}'s finger"
    return [f"{_first(caster)} casts <magic>{esc(sp['name'])}</> into the ring{whose}: it glows, and holds it "
            f"({magicrules.stored_levels(ring)} of {RING_MOST} levels kept)." + (f" The {used} is gone into it."
                                                                                  if used else "")]


# ---------------------------------------------------------------------------- the robe's patches
def patches(item) -> list[str]:
    patch = _patch_prop(item)
    return list(patch.get("left", ())) if patch else []


def tear(game, char, item, what: str) -> list[str]:
    """Tear a patch off the worn robe: it becomes the thing it shows (the Magic action; a moment outside a fight)."""
    from realmwalker.rules.inventory import add_item

    patch = _patch_prop(item)
    if patch is None or what not in patch.get("left", ()):
        return ["There is no such patch on it."]
    if item.uid not in set(char.equipped.values()):
        return ["Only the one wearing the robe can tear a patch off."]
    t = game.tables
    patch["left"].remove(what)
    who = _first(char)
    out = [f"{who} tears a patch from the robe, and it is {PATCH_WORDS.get(what, 'something else')}."]
    stamp = game.world.time
    if what == "gold_100":
        char.money += 100 * 100
    elif what == "gems_10":
        add_item(char, t.items, "gem_100", 10, made_at=stamp)
    elif what == "silver_coffer":
        add_item(char, t.items, "art_750", 1, made_at=stamp, name="silver coffer")
    elif what == "potions_4":
        add_item(char, t.items, "potion_healing", 4, made_at=stamp)
    elif what == "scroll_1_3":
        rng = game.world.rng.child(f"patch/{item.uid}/{stamp}")
        pool = sorted(d for d, sd in t.items.defs.items() if (sd.get("use") or {}).get("scroll")
                      and 1 <= int(t.spells[sd["use"]["scroll"]]["level"]) <= 3)
        if pool:
            add_item(char, t.items, rng.choice(pool), 1, made_at=stamp)
    elif what in ("riding_horse", "mastiffs_2"):
        kind, n = ("riding_horse", 1) if what == "riding_horse" else ("mastiff", 2)
        names = ["Patch", "Button"] if n == 2 else ["Stitch"]
        for name in names:
            game.leader.animals.append({"kind": kind, "name": name, "unfed": 0, "bought": stamp})
        if what == "riding_horse":
            add_item(char, t.items, "riding_saddle", 1, made_at=stamp)
    elif what in t.items:
        add_item(char, t.items, what, 1, made_at=stamp)
    if not patch["left"]:
        char.attuned = [u for u in char.attuned if u != item.uid]
        item.magic = {}
        out.append("That was the last patch: it is an ordinary robe now.")
    else:
        out.append(f"<dim>{len(patch['left'])} patches left.</>")
    game.dirty = True
    return out


# ---------------------------------------------------------------------------- the ruby
def ruby_weapons(game, char) -> list:
    """The simple and martial weapons the ruby could be set on: those in the character's hands, then the rest."""
    t = game.tables.items
    on = [char.equipped.get("main_hand"), char.equipped.get("off_hand")]
    out = [it for it in char.inventory if t.category(it) == "weapon" and t.get(it.def_id).get("group") in
           ("simple", "martial", None) and not str(it.def_id).startswith(("arrow", "bolt"))]
    return sorted(out, key=lambda it: (it.uid not in on, t.name(it, False)))


def set_ruby(game, char, ruby, weapon) -> list[str]:
    """Pressed against the weapon for ten minutes, the ruby holds fast: that weapon is a focus for its bearer."""
    if not magicrules.is_attuned(char, ruby):
        return [f"{_first(char)} must be attuned to the ruby first (a short rest with it)."]
    ruby.magic["set_on"] = weapon.uid
    game.pass_time(10, "rest")
    game.dirty = True
    return [f"{_first(char)} presses the ruby to the {esc(game.tables.items.name(weapon, False))} for ten minutes; "
            "its runes take hold, and the weapon is a spellcasting focus now."]


def take_off_ruby(game, char, ruby) -> list[str]:
    ruby.magic.pop("set_on", None)
    game.dirty = True
    return [f"{_first(char)} works the ruby free (the Magic action)."]


def ruby_on(game, ruby) -> str:
    uid = ruby.magic.get("set_on")
    for c in game.party:
        it = c.item(uid) if uid is not None else None
        if it is not None:
            return esc(game.tables.items.name(it, False))
    return ""


# ---------------------------------------------------------------------------- the pearl
def pearl_level(char, tables) -> int | None:
    """The spent slot a Pearl of Power would give back now: the highest spent one of level 3 or lower."""
    if not spellrules.is_caster(char, tables):
        return None
    total = spellrules.slots_total(char, tables)
    left = spellrules.slots_left(char, tables)
    spent = [i + 1 for i in range(min(3, len(total))) if total[i] and left[i] < total[i]]
    return max(spent) if spent else None


def pearl_problem(char, tables, pearl) -> str | None:
    prop = _pearl_prop(pearl)
    if prop is None:
        return "it is only a pearl"
    if not magicrules.working(char, pearl):
        return "it answers only one attuned to it"
    if prop.get("today"):
        return "used since the last dawn"
    if pearl_level(char, tables) is None:
        return "no spent spell slot of the third level or lower"
    return None


def use_pearl(game, char, pearl) -> list[str]:
    why = pearl_problem(char, game.tables, pearl)
    if why:
        return [f"The pearl: {why}."]
    level = pearl_level(char, game.tables)
    spellrules.unspend_slot(char, level)
    _pearl_prop(pearl)["today"] = 1
    game.dirty = True
    return [f"{_first(char)} holds the pearl and breathes on it: <magic>a level {level} spell slot</> comes back."]


def pearl_holder(game, pearl):
    """Who of the party the pearl answers (attuned to it), or None."""
    return next((c for c in game.party if magicrules.is_attuned(c, pearl)), None)


# ---------------------------------------------------------------------------- the pack
def use_name(game, item) -> str | None:
    if not item.magic:
        return None
    if _patch_prop(item) is not None and patches(item)             and any(item.uid in set(c.equipped.values()) for c in game.party):  # (worn: else Enter puts it on)
        return "Tear off a patch"
    if _ruby_prop(item) is not None:
        return "Take the ruby off its weapon" if item.magic.get("set_on") is not None else "Set it on a weapon"
    if _pearl_prop(item) is not None:
        return "Take back a spell slot"
    return None


CHOOSE = ("Tear off a patch", "Set it on a weapon")  # (the pack asks which first: `choices`, then `choose`)
VERBS = ("Take back a spell slot", "Take the ruby off its weapon") + CHOOSE


def use(game, char, item) -> list[str]:
    """Enter in the pack: the pearl's slot, the ruby taken off (setting it and tearing patches ask first: the screen
    opens a list with `choices`)."""
    name = use_name(game, item)
    if name == "Take back a spell slot":
        who = pearl_holder(game, item) or char
        return use_pearl(game, who, item)
    if name == "Take the ruby off its weapon":
        return take_off_ruby(game, char, item)
    return []


def choices(game, char, item) -> list[tuple[str, object]]:
    """(words, what) to choose from before `choose`: a patch to tear off, or a weapon to set the ruby on."""
    name = use_name(game, item)
    if name == "Tear off a patch":
        seen: dict[str, int] = {}
        for p in patches(item):
            seen[p] = seen.get(p, 0) + 1
        return [(PATCH_WORDS.get(p, p) + (f" (x{n})" if n > 1 else ""), p) for p, n in seen.items()]
    if name == "Set it on a weapon":
        return [(game.tables.items.name(w, False), w.uid) for w in ruby_weapons(game, char)]
    return []


def choose(game, char, item, what) -> list[str]:
    name = use_name(game, item)
    if name == "Tear off a patch":
        wearer = next((c for c in game.party if item.uid in set(c.equipped.values())), char)
        return tear(game, wearer, item, what)
    if name == "Set it on a weapon":
        weapon = char.item(int(what))
        holder = next((c for c in game.party if magicrules.is_attuned(c, item)), char)
        return set_ruby(game, holder, item, weapon) if weapon is not None else []
    return []


# ---------------------------------------------------------------------------- crystal balls
def scry_extras(game, caster, fig, rng: RNG) -> list[str]:
    """What a crystal ball adds to a Scrying that found its subject: thoughts (Mind Reading, Telepathy), a Suggestion
    once a day (Telepathy), and truesight round the sensor (True Seeing)."""
    balls = [it for it in caster.inventory if it.magic and magicrules.working(caster, it)
             and any(p.get("kind") == "flag" and str(p.get("flag")).startswith("scry_") for p in magicrules.props(it))]
    if not balls:
        return []
    out = []
    name = esc(fig.name)
    has = lambda flag: any(magicrules.item_flag(it, flag) for it in balls)  # noqa: E731
    if has("scry_thoughts"):
        out.append(f"<magic>Through the ball you hear {name}'s thoughts:</> " + _thoughts(game, fig, rng))
    prop = next((p for it in balls for p in magicrules.props(it) if p.get("kind") == "flag"
                 and p.get("flag") == "scry_suggest" and not p.get("today")), None)
    if prop is not None and fig.npc >= 0 and fig.npc in game.world.npcs and fig.kind == "person":
        prop["today"] = 1
        save = rng.randint(1, 20) + 1
        if save < 17:
            npc = game.world.npcs[fig.npc]
            npc.flags["charmed_until"] = max(float(npc.flags.get("charmed_until", 0)), game.world.time + 8 * 60)
            out.append(f"<good>You whisper a suggestion through the sensor; {name} takes it for their own thought, and "
                       "will think well of you for eight hours, should you meet.</>")
        else:
            out.append(f"<warn>You whisper a suggestion through the sensor; {name} shakes it off.</>")
    if has("scry_true"):
        what = {"dragon": "a dragon, and no shape it wears can hide it", "beast": "the beast it is",
                "god": "something no mortal shape can hold"}.get(fig.kind, f"{esc(fig.race)}, "
                                                                          f"{fig.job or fig.title or 'no one of note'}")
        out.append(f"<magic>The ball's truesight shows {name} as they are:</> {what}. Nothing invisible stands near "
                   "them unseen.")
    return out


def _thoughts(game, fig, rng: RNG) -> str:
    w = game.world
    faction = w.factions.get(fig.faction) if fig.faction >= 0 and hasattr(w.factions, "get") else None
    lines = []
    if faction is not None:
        lines.append(f"the affairs of {esc(faction.name)}")
    if fig.kills:
        lines.append("old blood they have shed, and do not regret")
    if fig.traits:
        lines.append(f"what a {esc(rng.choice(fig.traits))} mind turns over")
    if fig.spouse >= 0:
        lines.append("someone they love, and fear for")
    lines.append(rng.choice(["the next meal", "money owed", "a slight not forgotten", "sleep, and how little of it "
                                                                                       "there is"]))
    return rng.choice(lines[:-1] or lines) + ", and " + lines[-1] + "."
