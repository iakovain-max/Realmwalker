"""Spellcasting for pay (PHB 2024 p. 232, Expansion 3 G.2).

A temple's priest casts from the cleric's list, a mage (a townsperson of the towns where a mages' circle keeps a house,
and of every city) from the wizard's. Each reaches a highest spell level: the book's availability by place
(data/economy.json services "spellcasting" `reach`), and within it their own, settled once by who they are (`own`; a
figure of the world reaches the place's limit). The price is the book's table by spell level, moved by their mood as
every fee is, plus the value of a costly component. What they cast is what would do something for the party now,
outside a fight, each with its target; it is cast through the party's own road casting (`magic.cast_on_road` with
`hired=True`: no slot, no material, no strain, and no law broken by the party), the caster being the townsperson made
a character of their class and level (kept for the session, never saved).

Where magic is forbidden a mage casts for you only where nobody else sees, and dearer (`secret_markup`); a priest's
prayers are the temple's business, as before.
"""

from __future__ import annotations

from realmwalker.core.textgen import escape_markup
from realmwalker.rules import spells as spellrules
from realmwalker.rules.items import money_text

TRADITION = {"priest": "cleric", "mage": "wizard"}
BACKGROUND = {"cleric": "acolyte", "wizard": "sage"}
# What a spell cast for pay may do (rules/spells.road_use): the rest needs its caster to stay with you (a familiar, a
# summons, a shape, a ward on a camp, travel, the great magic) or is no use in a town.
FOR_HIRE = ("heal", "cure", "revive", "identify", "lasting", "uncurse", "regenerate", "repose", "purify", "feed",
            "water", "feast", "ask", "locate", "send", "mend")
ORDINAL = {0: "cantrip", 1: "1st", 2: "2nd", 3: "3rd"}

_CASTERS: dict = {}  # (world, npc id, level) -> Character: the townsperson as a caster (not saved)
_OFFERS: dict = {}  # the last list of offers, while nothing has changed


def spec(game) -> dict:
    return game.tables.economy["services"]["spellcasting"]


def tradition(npc) -> str | None:
    return TRADITION.get(npc.job)


def _kind(game, npc) -> str:
    s = game.world.settlements[npc.settlement]
    return "city" if getattr(s, "great", False) else s.kind


def reach(game, npc) -> int:
    """The highest spell level this townsperson casts for pay (-1: none)."""
    if tradition(npc) is None:
        return -1
    kind = _kind(game, npc)
    cap = int(spec(game)["reach"].get(kind, 2))
    if "figure" in npc.flags or npc.stats in ("archpriest", "archmage"):  # (a temple's high priest, an archmage)
        return cap
    lo, hi = spec(game)["own"].get(kind, [1, 2])
    return min(cap, game.world.rng.child(f"spellhire/{npc.id}").randint(int(lo), int(hi)))


def caster_level(top: int) -> int:
    """The class level at which a caster has slots of that spell level (the full casters' table)."""
    return max(1, min(17, 2 * top - 1))


def caster(game, npc):
    """The townsperson as a character of their class who can cast up to their reach."""
    top = max(0, reach(game, npc))
    level = caster_level(top)
    key = (id(game.world), npc.id, npc.name, level, game.moment.total_days)  # (fresh each day: their slots, an
    # addled mind and the day's omens come back with a night's rest)
    char = _CASTERS.get(key)
    if char is None:
        from realmwalker.game import companions

        cls = tradition(npc)
        char = companions.build(game, npc, cls, BACKGROUND[cls], level, game.world.rng.child(f"spellhire/c/{npc.id}"))
        if len(_CASTERS) > 64:
            _CASTERS.clear()
        _CASTERS[key] = char
    return char


def component_value(tables, sid: str) -> int:
    """The value of a spell's costly component (the cheapest thing that serves), in copper; 0 if none."""
    m = tables.spells[sid].get("material") or {}
    values = [int(tables.items.get(i)["value"]) for i in m.get("items", ()) if i in tables.items]
    total = min(values) if values else 0
    for also in m.get("also", ()):
        if also in tables.items:
            total += int(tables.items.get(also)["value"])
    return total


def secret(game, npc) -> bool:
    """A mage where magic is forbidden: casting is witchcraft, done in secret."""
    from realmwalker.game.magic import magic_forbidden

    return npc.job == "mage" and magic_forbidden(game, game.world.settlements[npc.settlement])


def price(game, npc, sid: str) -> int:
    from realmwalker.game.services import fee

    t = game.tables
    level = int(t.spells[sid]["level"])
    base = int(spec(game)["price"][level]) + component_value(t, sid)
    if secret(game, npc):
        base = int(base * float(spec(game)["secret_markup"]))
    return fee(game, npc, base)


def refusal(game, npc) -> str:
    """Why they will cast nothing just now ("" when they would)."""
    if tradition(npc) is None or reach(game, npc) < 0:
        return "they cast no spells"
    if secret(game, npc):
        from realmwalker.game import law

        if law.witnesses_here(game, exclude=[npc]):
            return "not with other eyes about: magic is forbidden here"
    return ""


def could_raise(game, minutes_dead: float) -> bool:
    """Could a priest somewhere still bring back someone this long dead, for pay: a spell of return that reaches a
    day or more (there is time to carry the body to them), of a level the priests of this world's places reach."""
    from realmwalker.game import revival

    kinds = {s.kind for s in game.world.settlements} | {"city" for s in game.world.settlements
                                                         if getattr(s, "great", False)}
    best = max((int(spec(game)["reach"].get(k, 0)) for k in kinds), default=-1)
    t = game.tables
    for sid in revival.revive_spells(t):
        spell = t.spells[sid]
        window = revival.reach(spell)
        if "cleric" in spell.get("classes", ()) and int(spell["level"]) <= best and window >= revival.DAY \
                and window >= minutes_dead:
            return True
    return False


# ---------------------------------------------------------------------------- what they can do for you
def _for_hire(game, npc, sid: str, top: int) -> str | None:
    """The spell's use if this townsperson would cast it for pay, else None."""
    t = game.tables
    spell = t.spells[sid]
    if tradition(npc) not in spell.get("classes", ()) or int(spell["level"]) > top:
        return None
    use = spellrules.road_use(t, sid)
    if use not in FOR_HIRE:
        return None
    if use == "lasting":
        if spell["target"] not in ("ally", "all_allies"):
            return None  # (a spell on its caster alone does you no good)
        if int(spell.get("rounds", 0)) / spellrules.ROUNDS_PER_HOUR < float(spec(game)["min_hours"]):
            return None  # (over before you are out of the door)
    if use == "identify" and "blessing" in game.tables.people["occupations"].get(npc.job, {}).get("services", ()):
        return None  # (a priest names a strange thing as a blessing, for a donation: services "identify")
    return use


def _first(c) -> str:
    return escape_markup(c.name.split()[0])


def targets(game, c, sid: str, use: str) -> list[tuple[str, object]]:
    """(label, target) for each thing the spell could be cast on now; "" for the party as a whole."""
    from realmwalker.game import revival, spellwork
    from realmwalker.game.magic import strange_things
    from realmwalker.rules.inventory import distinct_packs

    t = game.tables
    spell = t.spells[sid]
    living = [m for m in game.party if m.alive]
    if spell["target"] == "dead_ally":
        return [(f"for {_first(b['char'])}", b["char"]) for b in revival.bodies(game, sid)]
    if use in ("heal", "cure"):
        if use == "heal" and spellrules.heals_many(spell):
            return [("for the party", game.leader)]
        return [(f"for {_first(m)}", m) for m in living]
    if use == "lasting":
        if spell["target"] == "all_allies":
            return [("for the party", game.leader)]
        return [(f"for {_first(m)}", m) for m in living]
    if use == "identify":
        seen = set()
        out = []
        for m in distinct_packs(game.party):
            for it in m.inventory:
                if it.magic and not it.magic.get("identified") and it.uid not in seen:
                    seen.add(it.uid)
                    out.append((f"the {escape_markup(t.items.name(it, False))}", it))
        return out if strange_things(game, game.leader) else []
    if use in ("uncurse", "regenerate"):
        return [(f"for {_first(m)}", m) for m in living]
    if use in ("purify", "feed", "water", "feast"):
        return [("", None)]
    return [(escape_markup(s.name), s) for s in spellwork.subjects(game, c, sid)]


def offers(game, npc) -> list[tuple[str, str, int, str, object]]:
    """(arg, label, price, spell id, target) for everything they would cast for you now, cheapest level first."""
    from realmwalker.game import magic

    party = tuple((id(m), m.hp, len(m.inventory), len(m.wounds), len(m.diseases), m.alive) for m in game.party)
    key = (id(game), npc.id, game.world.time, sum(m.money for m in game.party), party,
           len(getattr(game, "fallen", []) or []), npc.mood(), npc.flags.get("price_mod", 0.0))
    if _OFFERS.get("key") == key:
        return _OFFERS["offers"]
    out = []
    top = reach(game, npc)
    if top >= 0 and game.battle is None:
        t = game.tables
        c = caster(game, npc)
        pool = t.spells.for_class(tradition(npc), top)
        for sid in sorted(pool, key=lambda s: (int(t.spells[s]["level"]), t.spells[s]["name"])):
            use = _for_hire(game, npc, sid, top)
            if use is None:
                continue
            spell = t.spells[sid]
            cost = price(game, npc, sid)
            level = int(spell["level"])
            for n, (label, target) in enumerate(targets(game, c, sid, use)):
                if magic.road_problem(game, c, sid, target, hired=True) is not None:
                    continue
                words = f"{spell['name']} ({ORDINAL.get(level, f'{level}th')})" + (f", {label}" if label else "")
                out.append((f"{sid}|{n}", words, cost, sid, target))
    _OFFERS["key"] = key
    _OFFERS["offers"] = out
    return out


def options(game, npc) -> list[tuple[str, str, int]]:
    """The services menu's second choice: (arg, label, price)."""
    if refusal(game, npc):
        return []
    return [(arg, label, cost) for arg, label, cost, _, _ in offers(game, npc)]


def why_none(game, npc) -> str:
    return refusal(game, npc) or "nothing they can cast would help you just now"


# ---------------------------------------------------------------------------- casting it
def cast(game, npc, arg: str | None) -> list[str]:
    """Pay for a spell and have it cast. Returns what to say."""
    from realmwalker.game import magic
    from realmwalker.game.services import charge, money

    why = refusal(game, npc)
    if why:
        return [f"{npc.first_name} shakes their head: {why}."]
    offer = next((o for o in offers(game, npc) if o[0] == arg), None)
    if offer is None:
        return ["They can't do that just now."]
    _, label, cost, sid, target = offer
    if money(game) < cost:
        return [f"You can't: you need {money_text(cost)}."]
    t = game.tables
    c = caster(game, npc)
    problem = magic.road_problem(game, c, sid, target, hired=True)
    if problem:
        return [f"{t.spells[sid]['name']}: {problem}."]
    charge(game, npc, cost)
    _OFFERS.clear()
    spell = t.spells[sid]
    how = "murmurs a prayer over" if tradition(npc) == "cleric" else "chalks a circle and speaks the words of"
    pre = [f"{escape_markup(npc.first_name)} takes your {money_text(cost)} and {how} "
           f"<magic>{spell['name']}</>" + (" behind a shuttered door" if secret(game, npc) else "") + "."]
    had = {it.uid for it in c.inventory}
    out = pre + magic.cast_on_road(game, c, sid, target, hired=True)
    made = [it for it in c.inventory if it.uid not in had]  # (what the spell makes is yours: Create Food and Water)
    if made:
        from realmwalker.rules.inventory import add_existing

        c.inventory = [it for it in c.inventory if it.uid in had]
        for it in made:
            add_existing(game.leader, t.items, it)
    npc.remember(f"cast {spell['name']} for the traveller on {game.moment.date_text()}")
    if tradition(npc) == "cleric" and game.party[1:]:
        from realmwalker.game.companions import react

        react(game, "prayer", quiet=True)
    game.cue("spell")
    game.dirty = True
    return out
