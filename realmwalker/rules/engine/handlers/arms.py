"""Arms of steel and shadow (Expansion 4 Part D): the fighter's and rogue's magic weapons and things of the DMG 2024.

Each is a book item made by `game/treasure.make_listed` (data/treasure.json "makers") with properties: `bonus`, kernel
traits (data/traits.json, the hooks and abilities below) and flags read elsewhere. A weapon's own power works only on
blows struck with it (`blade`); a power "while held" needs it in a hand (`held`). Powers that come back at dawn are
properties with `daily` (`ready`, `spend`; `rules/magic.dawn` clears `today`).

    vicious_weapon       2d6 more of the weapon's own damage on every hit
    executioners_axe     2d6 slashing more to a humanoid, and as many temporary hit points
    sword_of_wounding    2d6 necrotic more; a Constitution save (DC 15) or no healing (a save at the end of each turn)
    sword_of_sharpness   a 20 on the die: 14 slashing more and a level of exhaustion; things struck take the most
                         the dice can give (Battle.attack_object)
    vorpal_sword         slashing resistance cut through (Battle._ignores_resist); a 20 on the die takes the head off
                         a creature that has one and needs it (else 30 slashing more; Legendary Resistance saves it)
    sword_of_answering   the reaction: a blow back at whoever hurt the bearer within reach, with Advantage, through
                         any resistance or immunity (Battle._hit `raw`)
    sword_of_vengeance   cursed: Disadvantage with any other weapon (query.attack_roll), and a Wisdom save (DC 15) when
                         a foe hurts the bearer or the buff `vengeful` (that foe's id): blows only at it while it
                         stands (Battle.targets_for, attack_problem, tactics._targets)
    scimitar_of_speed    one blow with it as a bonus action each turn (ability speed_strike)
    dancing_sword        tossed with a bonus action: a Token "dancing_sword" that flies 30 feet and strikes with the
                         bearer's blow, again with each bonus action, back in the hand after the fourth
    defender             as the turn begins, some of its +3 is moved to Armor Class until the next (buff `defender`)
    luck_blade           a failed save or a missed blow rolled again once a day; Wish from its charges
    lordly_might         the Rod of Lordly Might: a flaming blade, an axe, a spear or the mace (`item.magic["form"]`),
                         Drain Life and Paralyze on a hit once a day each, Terrify from its charge
    veterans_cane        a walking cane (it strikes as a club) or a longsword, changed with a bonus action
"""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.rules import magic
from realmwalker.rules.engine import durations, query
from realmwalker.rules.engine.effects import special
from realmwalker.rules.engine.events import handler
from realmwalker.rules.engine.reactions import Decision, yes

HANDS = ("main_hand", "off_hand")
NO_HEAD_KINDS = ("ooze", "elemental", "plant", "construct")  # (the DM's call in the book: these have no head to lose)
TOO_BIG = ("gargantuan",)
FORMS = {"flame": "longsword", "axe": "battleaxe", "spear": "spear", "cane": "club", "sword": "longsword"}


# ---------------------------------------------------------------------------- which thing does what
def trait_prop(it, trait: str) -> dict | None:
    """The item's property that gives this kernel trait, if it has one."""
    return next((p for p in magic.props(it) if p.get("kind") == "trait" and p.get("trait") == trait), None)


def blade(f, opt, trait: str):
    """The magic weapon this blow is struck with, if it carries the trait and works for its bearer."""
    if f is None or f.char is None or opt is None or opt.item_uid is None or str(opt.kind).startswith("spell"):
        return None
    it = f.char.item(opt.item_uid)
    if it is None or trait_prop(it, trait) is None or not magic.working(f.char, it):
        return None
    return it


def held(f, trait: str):
    """The working item with this trait in one of the bearer's hands."""
    c = getattr(f, "char", None)
    if c is None:
        return None
    for slot in HANDS:
        it = c.equipped_item(slot)
        if it is not None and trait_prop(it, trait) is not None and magic.working(c, it):
            return it
    return None


def carried(char, trait: str):
    """A working item with this trait anywhere on the character (attuned if it must be)."""
    if char is None:
        return None
    for it in char.inventory:
        if it.magic and trait_prop(it, trait) is not None and magic.working(char, it):
            return it
    return None


def ready(it, trait: str) -> bool:
    """A once-a-day power not yet used since the last dawn."""
    p = trait_prop(it, trait) if it is not None else None
    return p is not None and not p.get("today")


def spend(it, trait: str) -> None:
    p = trait_prop(it, trait)
    if p is not None:
        p["today"] = 1


def form_def(it) -> str | None:
    """The weapon a shifting item is now (the Rod of Lordly Might's blades, the Veteran's Cane): its base item id."""
    form = (getattr(it, "magic", None) or {}).get("form")
    return FORMS.get(form) if form else None


def _roll(b, expr: str, crit: bool) -> int:
    return dice.roll(expr, b.rng, double_dice=crit).total


# ---------------------------------------------------------------------------- blows
@handler("vicious_weapon")
def vicious_weapon(b, f, ev, hook, buff) -> None:
    """2d6 more damage of the weapon's own kind on every hit."""
    if blade(f, ev.opt, "vicious_weapon") is not None:
        ev.extra += _roll(b, "2d6", ev.crit)


@handler("executioners_axe")
def executioners_axe(b, f, ev, hook, buff) -> None:
    """A humanoid struck takes 2d6 slashing more, and the wielder gains as many temporary hit points."""
    t = ev.target
    if t is None or t.kind != "humanoid" or blade(f, ev.opt, "executioners_axe") is None:
        return
    n = _roll(b, "2d6", ev.crit)
    ev.typed.append((n, "slashing"))
    if n > f.temp_hp:
        f.temp_hp = n
        b.say(f"The executioner's axe drinks deep: {f.the_name} has {n} hit points of grim strength.", "magic")


@handler("sword_of_wounding")
def sword_of_wounding(b, f, ev, hook, buff) -> None:
    """2d6 necrotic more; a Constitution save (DC 15) or the wound will not close (no hit points regained), with a save
    at the end of each of its turns."""
    t = ev.target
    if t is None or blade(f, ev.opt, "sword_of_wounding") is None:
        return
    ev.typed.append((_roll(b, "2d6", ev.crit), "necrotic"))
    if not t.active or any(bf.get("source") == "wounding" for bf in t.buffs):
        return
    if not b._save(t, "con", 15):
        durations.buff(t, {"no_heal": True, "repeat": "con", "dc": 15, "rounds": 600, "source": "wounding"})
        b.say(f"The wound on {t.the_name} gapes and will not close.", "good" if t.side != f.side else "danger")


def wounded(f) -> bool:
    return any(bf.get("source") == "wounding" for bf in f.buffs)


@handler("sword_of_sharpness")
def sword_of_sharpness(b, f, ev, hook, buff) -> None:
    """A 20 on the die: 14 slashing more, and the creature gains a level of exhaustion."""
    t = ev.target
    if ev.natural != 20 or t is None or blade(f, ev.opt, "sword_of_sharpness") is None:
        return
    ev.typed.append((14, "slashing"))
    tire(b, t)
    b.say(f"The blade bites to the bone: {t.the_name} reels, spent.", "good" if t.side != f.side else "danger")


def tire(b, t) -> None:
    """A level of exhaustion in a fight (a character's own; a creature's for the fight: Fighter `exhaustion`)."""
    if t.char is not None:
        t.char.exhaustion = min(6, int(t.char.exhaustion) + 1)
    else:
        t.__dict__["exhaustion"] = min(6, int(t.__dict__.get("exhaustion", 0)) + 1)
    b._event("condition", who=t.id, cond="exhaustion")


def sharp(f, opt) -> bool:
    """A blow of a Sword of Sharpness: things struck take the most its dice can give."""
    return blade(f, opt, "sword_of_sharpness") is not None


def has_head(t) -> bool:
    """Whether a creature has a head it cannot live without (the DM's judgement in the book)."""
    if t.kind in NO_HEAD_KINDS or t.size in TOO_BIG:
        return False
    if t.creature is not None:
        names = {str(x).lower() for x in (t.cdef.get("traits") or ())}
        if names & {"amorphous", "multiple_heads", "swarm", "headless"} or "swarm" in str(t.cdef.get("name", "")).lower():
            return False
    return True


@handler("vorpal_sword")
def vorpal_sword(b, f, ev, hook, buff) -> None:
    """A 20 on the die against a creature with a head: the head comes off, unless it cannot lose one (then 30 slashing
    more; Legendary Resistance may be spent to take that instead)."""
    t = ev.target
    if ev.natural != 20 or t is None or blade(f, ev.opt, "vorpal_sword") is None:
        return
    if not has_head(t) or query.defences(t, "slashing") == "immune" or b._legendary_resistance(t):
        ev.typed.append((30, "slashing"))
        return
    b.say(f"The vorpal blade sings: {t.the_name}'s head leaves {t.possessive} shoulders.",
          "good" if t.side != f.side else "danger")
    b._event("behead", who=t.id, by=f.id)
    ev.typed.append((t.hp + t.temp_hp + t.max_hp + 1, "slashing"))  # (no body lives through it)


def cuts_through(b, att, dtype: str) -> bool:
    """A Vorpal Sword's blow cuts through resistance to slashing (Battle._ignores_resist)."""
    if dtype != "slashing":
        return False
    w = b.__dict__.get("_wielded")
    return w is not None and w[0] is att and blade(att, w[1], "vorpal_sword") is not None


# ---------------------------------------------------------------------------- answering and vengeance
@handler("sword_of_answering")
def sword_of_answering(b, f, ev, hook, buff) -> None:
    """Hurt by a creature in reach: a blow back at it with the reaction, with Advantage, that nothing resists."""
    att = ev.actor
    if att is None or att is f or att.team == f.team or not att.active or not f.active or not f.reaction \
            or query.incapacitated(f) or b.__dict__.get("_answering") is not None:
        return
    it = held(f, "sword_of_answering")
    if it is None:
        return
    opt = next((o for o in b.attack_options(f) if o.item_uid == it.uid and o.is_melee and o.available), None)
    if opt is None or not b.in_reach(f, opt, att)[0]:
        return
    if not yes(b, Decision(f, "answering", f"{att.the_name} wounds {f.name}. The Sword of Answering stirs: strike back? "
                           f"(your reaction)", [("yes", "Answer"), ("no", "Hold")], default="yes")):
        return
    f.reaction = False
    b.say(f"The sword answers for {f.the_name}.", "magic")
    durations.buff(f, {"aimed": True, "source": "answering"})
    b.__dict__["_answering"] = f
    try:
        b._attack(f, opt, att)
    finally:
        b.__dict__.pop("_answering", None)
        f.buffs = [x for x in f.buffs if x.get("source") != "answering"]
    b._check_end()


def answering(b, att) -> bool:
    """The blow is the Sword of Answering's: no resistance or immunity stops it (Battle._hit)."""
    return att is not None and b.__dict__.get("_answering") is att


@handler("sword_of_vengeance")
def sword_of_vengeance(b, f, ev, hook, buff) -> None:
    """Hurt by a foe: a Wisdom save (DC 15) or the spirit in the sword turns every blow on that foe."""
    att = ev.actor
    if att is None or att is f or att.team == f.team or not att.active or not f.active or f.char is None:
        return
    if vengeful(b, f) is not None or not ev.amount:
        return
    if not b._save(f, "wis", 15):
        durations.buff(f, {"vengeful": att.id, "source": "vengeance"})
        b.say(f"The spirit in {f.the_name}'s sword howls for {att.the_name}'s blood.", "danger")


def vengeful(b, f):
    """The foe a Sword of Vengeance has fixed on, while it stands (the mark goes when it falls or the bearer does)."""
    vids = f.buff_value("vengeful") if f.buffs else []
    if not vids:
        return None
    vid = vids[0]
    foe = next((x for x in b.fighters if x.id == vid), None)
    if foe is None or not foe.active or not f.active:
        f.buffs = [x for x in f.buffs if not x.get("vengeful")]
        return None
    return foe


def only_at(b, f, targets: list) -> list:
    """The curse: while it holds, blows go only at the foe it named (if that foe can be reached at all)."""
    foe = vengeful(b, f)
    if foe is None:
        return targets
    return [foe] if foe in targets else targets


def other_weapon(att, opt) -> bool:
    """Attuned to a Sword of Vengeance, a blow with any other weapon (query.attack_roll: Disadvantage)."""
    c = getattr(att, "char", None)
    if c is None or opt is None or opt.kind not in ("melee", "ranged") or opt.item_uid is None or not c.attuned:
        return False
    sword = carried(c, "sword_of_vengeance")
    return sword is not None and sword.uid != opt.item_uid


# ---------------------------------------------------------------------------- the Scimitar of Speed
def speed_option(b, f):
    it = held(f, "scimitar_of_speed")
    if it is None:
        return None
    return next((o for o in b.attack_options(f) if o.item_uid == it.uid and o.available), None)


def speed_targets(b, f) -> list:
    opt = speed_option(b, f)
    return only_at(b, f, b.targets_for(f, opt)) if opt is not None else []


@special("speed_strike")
def speed_strike(c, o, victim) -> None:
    """One blow of the scimitar, with the bonus action."""
    b, f = c.b, c.caster
    opt = speed_option(b, f)
    targets = speed_targets(b, f)
    if opt is None or not targets:
        return
    t = c.target if c.target in targets else min(targets, key=lambda t: (t.hp, t.id))
    b._attack(f, opt, t)
    b._check_end()


# ---------------------------------------------------------------------------- the Dancing Sword
def dancer(b, f):
    """The Dancing Sword's token in the air, if it is dancing."""
    return next((t for t in b.tokens if t.owner == f.id and t.kind == "dancing_sword"), None)


def dancing(b, f, it) -> bool:
    """The sword is in the air (its blows are the token's, not the hand's)."""
    tok = dancer(b, f)
    return tok is not None and tok.item_uid == it.uid


def _dance_option(b, f, it):
    from dataclasses import replace

    opt = b._weapon_option(f, f.sheet, it, "main")
    return replace(opt, available=True, reason="")


def toss_targets(b, f) -> list:
    """Whom the sword can reach as it is tossed: it flies 30 feet and strikes someone beside it."""
    if held(f, "dancing_sword") is None or dancer(b, f) is not None:
        return []
    return only_at(b, f, [e for e in b.enemies_of(f) if e.active and b.feet(f, e) <= 35 and b.can_see(f, e)])


def dance_targets(b, f) -> list:
    """Whom the dancing sword can reach: 30 feet from where it hangs, and within 30 feet of its bearer."""
    tok = dancer(b, f)
    if tok is None:
        return []
    from realmwalker.rules import grid

    out = []
    for e in b.enemies_of(f):
        if not e.active:
            continue
        from_tok = grid.gap((tok.x, tok.y, 1), e.space) * grid.SQUARE_FT
        if from_tok <= 35 and b.feet(f, e) <= 35:
            out.append(e)
    return only_at(b, f, out)


def _fly_to(b, tok, target) -> None:
    from realmwalker.rules import grid

    occ = {cell for x in b.on_field() for cell in x.cells}
    best = None
    for c in target.cells:
        for dx, dy in grid.DIRS8:
            sq = (c[0] + dx, c[1] + dy)
            if sq in occ or not b.field.passable(*sq):
                continue
            d = grid.gap((tok.x, tok.y, 1), (sq[0], sq[1], 1))
            if d <= 6 and (best is None or d < best[0]):
                best = (d, sq)
    if best is not None:
        start = (tok.x, tok.y)
        tok.x, tok.y = best[1]
        b._event("token_move", id=tok.id, path=[start, best[1]])


def _dance_blow(b, f, tok, target) -> None:
    it = f.char.item(tok.item_uid) if f.char is not None else None
    if it is None:
        return
    _fly_to(b, tok, target)
    b._event("token_strike", id=tok.id, to=target.id)
    tok.blows += 1
    b._attack(f, _dance_option(b, f, it), target)
    if tok.blows >= 4 and tok in b.tokens:
        home(b, f, tok, "Its fourth blow struck, the sword flies back to")
    b._check_end()


def home(b, f, tok, words: str = "The sword flies back to") -> None:
    if tok in b.tokens:
        b.tokens.remove(tok)
        b._event("token_end", id=tok.id)
        b.say(f"{words} {f.the_name}'s hand.", "magic")


@special("dance_toss")
def dance_toss(c, o, victim) -> None:
    """The sword thrown into the air: it flies at a foe and strikes."""
    b, f = c.b, c.caster
    it = held(f, "dancing_sword")
    targets = toss_targets(b, f)
    if it is None or not targets:
        return
    t = c.target if c.target in targets else min(targets, key=lambda t: (t.hp, t.id))
    from realmwalker.rules.combat import Token

    tok = Token(b._zone_id(), "dancing_sword", f.x, f.y, f.id, rounds=100, spell="dancing_sword", item_uid=it.uid)
    b.tokens.append(tok)
    b._event("token", id=tok.id, what=tok.kind, x=tok.x, y=tok.y, owner=f.id)
    b.say(f"{f.the_name} tosses the sword into the air, and it dances.", "magic")
    _dance_blow(b, f, tok, t)


@special("dance_strike")
def dance_strike(c, o, victim) -> None:
    b, f = c.b, c.caster
    tok = dancer(b, f)
    targets = dance_targets(b, f)
    if tok is None or not targets:
        return
    t = c.target if c.target in targets else min(targets, key=lambda t: (t.hp, t.id))
    _dance_blow(b, f, tok, t)


@handler("dancing_sword_return")
def dancing_sword_return(b, f, ev, hook, buff) -> None:
    """Thirty feet or more from its bearer as their turn begins, the sword stops dancing and comes back."""
    tok = dancer(b, f)
    if tok is None:
        return
    from realmwalker.rules import grid

    if grid.gap((tok.x, tok.y, 1), f.space) * grid.SQUARE_FT > 30 or not f.active:
        home(b, f, tok, "Too far from its bearer, the sword falls out of the air and is caught up again by")


# ---------------------------------------------------------------------------- the Defender
def defence(b, f) -> int:
    """How much of the Defender's +3 goes to Armor Class this turn (the battle's judgement): all of it when hurt and
    pressed, two against two foes or more, one against one; nothing with nobody near."""
    near = sum(1 for e in b.enemies_of(f) if e.standing and b.gap(f, e) <= max(1, b.reach_of(e)))
    if not near:
        return 0
    if f.hp < f.max_hp // 2:
        return 3
    return 2 if near >= 2 else 1


@handler("defender")
def defender(b, f, ev, hook, buff) -> None:
    it = held(f, "defender")
    if it is None:
        return
    n = defence(b, f)
    f.buffs = [x for x in f.buffs if x.get("source") != "defender"]
    if n:
        durations.buff(f, {"ac": n, "defender": n, "source": "defender"}, durations.until(b, f, "turn_start"))
        b.say(f"{f.the_name} turns the Defender to guard: +{n} to Armor Class, +{3 - n} to the blade.", "magic")


def defender_shift(f, it) -> int:
    """What the Defender gave to the guard this turn (taken off its attack and damage: Battle._weapon_option)."""
    if it is None or trait_prop(it, "defender") is None or not f.buffs:
        return 0
    return sum(int(v) for v in f.buff_value("defender"))


# ---------------------------------------------------------------------------- the Luck Blade
@handler("luck_blade_save")
def luck_blade_save(b, f, ev, hook, buff) -> None:
    """A failed save rolled again (the second roll stands), once a day."""
    it = carried(f.char, "luck_blade")
    if ev.roll != "save" or ev.ok or it is None or not ready(it, "luck_blade") or query.incapacitated(f):
        return
    if ev.bonus + 20 < ev.dc:
        return
    if not yes(b, Decision(f, "luck_blade", f"{f.the_name} fails a {ev.ability.upper()} save. Call on the Luck Blade "
                           f"to roll again? (once a day)", [("yes", "Roll again"), ("no", "Accept it")], default="yes")):
        return
    spend(it, "luck_blade")
    again = dice.d20(b.rng).natural
    ev.ok = again + ev.bonus >= ev.dc
    b.dice_say(f"{f.name} calls on the Luck Blade: {again} + {ev.bonus} = {again + ev.bonus} vs DC {ev.dc} — "
               f"{'saved' if ev.ok else 'failed'}")


@handler("luck_blade_attack")
def luck_blade_attack(b, f, ev, hook, buff) -> None:
    """A missed blow rolled again (the second roll stands), once a day."""
    it = carried(f.char, "luck_blade")
    if it is None or not ready(it, "luck_blade") or query.incapacitated(f):
        return
    if ev.total + 20 - ev.natural < ev.ac:
        return
    if not yes(b, Decision(f, "luck_blade", f"{f.the_name}'s blow misses ({ev.total} against AC {ev.ac}). Call on the "
                           f"Luck Blade to roll again? (once a day)", [("yes", "Roll again"), ("no", "Keep it")],
                           default="yes")):
        return
    spend(it, "luck_blade")
    again = dice.d20(b.rng).natural
    total = ev.total - ev.natural + again
    b.dice_say(f"{f.name} calls on the Luck Blade: {again} → {total} vs AC {ev.ac}")
    if again == 20 or again != 1 and total >= ev.ac:
        ev.hit, ev.total = True, total
        if again == 20:
            ev.crit = True  # (a 20 rolled again is a critical hit)


# ---------------------------------------------------------------------------- the Rod of Lordly Might
ROD_FORMS = {"rod_flame": "flame", "rod_axe": "axe", "rod_spear": "spear", "rod_mace": None}
ROD_WORDS = {"flame": "A blade of fire leaps from the rod's head.", "axe": "Two crescent blades spring from the rod.",
             "spear": "A spear point springs from the rod and its haft lengthens.",
             None: "The rod folds back into a flanged mace."}


def rod_form(b, f, aid: str) -> str | None:
    """Why this form of the rod cannot be taken now (None: it can)."""
    it = held(f, "lordly_might")
    if it is None:
        return "the rod is not in hand"
    if (it.magic.get("form") or None) == ROD_FORMS[aid]:
        return "it is that already"
    return None


@special("rod_button")
def rod_button(c, o, victim) -> None:
    b, f = c.b, c.caster
    it = held(f, "lordly_might")
    if it is None:
        return
    form = o.get("form") or None
    if form:
        it.magic["form"] = form
    else:
        it.magic.pop("form", None)
    b._event("arms_form", who=f.id, what={"flame": "flaming blade", "axe": "axe", "spear": "spear"}.get(form, "mace"))
    b.say(f"{ROD_WORDS[form]} <dim>({f.name})</>", "magic")


@handler("lordly_might")
def lordly_might(b, f, ev, hook, buff) -> None:
    """On a hit with the rod: the flaming blade's fire; Drain Life and Paralyze, each once a day (the battle's
    judgement: on a foe still strong enough to be worth it)."""
    it = blade(f, ev.opt, "lordly_might")
    t = ev.target
    if it is None or t is None:
        return
    if it.magic.get("form") == "flame":
        ev.typed.append((_roll(b, "2d6", ev.crit), "fire"))
    worth = t.active and t.hp > max(12, f.max_hp // 3)
    if worth and ready(it, "rod_paralyze") and not query.condition_immune(t, "paralyzed") \
            and "paralyzed" not in t.conditions and _press(b, f, "rod_paralyze", t, "Paralyze"):
        spend(it, "rod_paralyze")
        if not b._save(t, "con", 17):
            if durations.give(b, t, "paralyzed", rounds=10, source=f):
                t.save_ends.append({"cond": "paralyzed", "save": "con", "dc": 17})
                b._event("condition", who=t.id, cond="paralyzed")
                b.say(f"The rod's power locks {t.the_name} rigid.", "good" if t.side != f.side else "danger")
        return
    if worth and ready(it, "rod_drain") and t.kind not in ("construct", "undead") \
            and _press(b, f, "rod_drain", t, "Drain Life"):
        spend(it, "rod_drain")
        if not b._save(t, "con", 17):
            n = _roll(b, "4d6", ev.crit)
            ev.typed.append((n, "necrotic"))
            b._heal(f, max(1, n // 2))
            b.say(f"The rod drinks the life out of {t.the_name}.", "magic")


def _press(b, f, key: str, t, name: str) -> bool:
    return yes(b, Decision(f, key, f"{f.name} hits {t.the_name} with the rod. Press its {name} button? (once a day)",
                           [("yes", name), ("no", "Not now")], default="yes", free=True))


# ---------------------------------------------------------------------------- the Veteran's Cane
def cane_form(b, f, want: str) -> str | None:
    it = held(f, "veterans_cane")
    if it is None:
        return "the cane is not in hand"
    if (it.magic.get("form") or "sword") == want:
        return "it is that already"
    return None


@special("cane_turn")
def cane_turn(c, o, victim) -> None:
    b, f = c.b, c.caster
    it = held(f, "veterans_cane")
    if it is None:
        return
    it.magic["form"] = o.get("form", "sword")
    b._event("arms_form", who=f.id, what="sword" if it.magic["form"] == "sword" else "cane")
    b.say(f"{f.the_name} gives the cane a twist: it is a longsword." if it.magic["form"] == "sword" else
          f"{f.the_name} gives the sword a twist: it is a walking cane again.", "magic")


# ---------------------------------------------------------------------------- warning, proof against detection
def warned(b) -> set:
    """Ids of those who roll Initiative with Advantage: the bearer of a Weapon of Warning (attuned, on their person)
    and their friends within 30 feet."""
    out = set()
    for f in b.fighters:
        if f.char is None or carried(f.char, "weapon_of_warning") is None:
            continue
        for x in b.team(f.team):
            if x is f or b.feet(f, x) <= 30:
                out.add(x.id)
    return out


def hidden_from_divination(f) -> bool:
    """Nobody's divination finds or aims at this one (Nondetection; an Amulet of Proof against Detection)."""
    if f.buffs and any(f.buff_value("nondetection")):
        return True
    return f.char is not None and magic.flag(f.char, "nondetection")
