"""Lieutenants who remember (docs/ADVENTURES.md §5.5, the nemesis rule; Expansion 6 E.3).

A blueprint names the cast roles led by a lieutenant (`lieutenants`: [{as, creature, titles, turns}]); the role stays
a band (`band(cultists)`), and its head is a named person kept on the threat: `threat["lieutenants"]` [{as, name,
title, sex, culture, creature, trait, weakness, look, fate, grudge, scars, met, adv, turns}], the cast entry pointing
at it with "lt" (its index). A threat's lieutenants outlive a tale: when the villain comes back, they come back with it
as they were (`forge` reuses the living).

Fates: unmet, met, escaped (got away from a fight: a grudge, and a scar if it bled), spared (mercy refused: back to
the villain with a grudge), turned (came over to you: the blueprint's `turns` given at once), turncoat (seemed to
turn, and lied: it stands beside the villain at the end), slain (the villain grieves or rages, by its temper; its
wrath is villain.on_fight's), taken (given to the law, or questioned and kept), promoted (became a nemesis).

In a fight (`arm`, from finale.prepare): its trait's morale and, where the trait runs at all, a try at escape at
`flee_at` of its hit points (the kernel's boss phase "escape": gone at once with nobody beside it, else it must run
for it); each grudge more hit points, armour and a better blade (villains.json lieutenants.grudge). Every lieutenant
still free stands beside the villain at the finale, in the place of one of its men (`join_finale`, from
story.fight_finale): the lieutenant slain is not in the fight.

At the tale's end (`after_tale`, from endings.finish) each lieutenant gets a page in the epilogue, and the one with
the greatest grudge who is still free when its villain has fallen is promoted: a nemesis
(`world.politics["nemeses"]` [{lt, threat, life, band, next, state}]) who comes for that hero on the road
(`on_travel`) with the villain's old company, until slain or taken.
"""

from __future__ import annotations

from realmwalker.core import textgen
from realmwalker.core.textgen import escape_markup as esc

FREE = ("unmet", "met", "escaped", "spared", "turncoat")  # still the villain's: they stand with it at the end
AGAIN = ("unmet", "met", "escaped", "spared")  # who come back with a villain that returns


def spec(game) -> dict:
    return game.tables.villains.get("lieutenants") or {}


def _story():
    from realmwalker.game import story

    return story


def records(game, adv: dict) -> list:
    t = _story().threat_of(game, adv)
    return t.setdefault("lieutenants", []) if t is not None else []


def of(game, adv: dict, role: str) -> dict | None:
    """The lieutenant at the head of a role's band, or None."""
    entry = adv["cast"].get(role) or {}
    if "lt" not in entry:
        return None
    recs = records(game, adv)
    i = int(entry["lt"])
    return recs[i] if 0 <= i < len(recs) else None


def full(rec: dict) -> str:
    return f"{rec['name']} {rec['title']}".strip()


def _tale_lieutenants(game, adv: dict) -> list[tuple[str, dict]]:
    return [(role, rec) for role in adv["cast"] for rec in [of(game, adv, role)] if rec is not None]


def _words(game, adv: dict | None, rec: dict, villain: str | None = None) -> dict:
    from realmwalker.game.story import words as wordsmod

    w = {k: v for k, v in wordsmod.for_adventure(game, adv).items() if isinstance(v, str)} if adv else {}
    sp = spec(game)
    w.update(name=full(rec), short=rec["name"], scar=rec["scars"][-1] if rec.get("scars") else "the memory of you",
             trait=sp.get("traits", {}).get(rec["trait"], {}).get("words", rec["trait"]),
             weakness=rec.get("weakness", ""))
    w["villain"] = villain or w.get("villain_short") or w.get("villain") or "its master"
    return w


def _fill(game, text: str, words: dict, rng) -> str:
    return textgen.fill(text, rng, game.tables.adventures.get("words", {}), words)


def line(game, adv: dict | None, rec: dict, key: str, rng, *, villain: str | None = None, table: str = "lines") -> str:
    texts = spec(game).get(table, {}).get(key) or []
    return _fill(game, rng.choice(texts), _words(game, adv, rec, villain), rng) if texts else ""


# ---------------------------------------------------------------------------- forging
def forge(game, adv: dict, t: dict, bp: dict, rng) -> None:
    """Named heads for the roles the blueprint gives a lieutenant; the threat's living ones come back as they were."""
    sp = spec(game)
    if not sp or not bp.get("lieutenants"):
        return
    recs = t.setdefault("lieutenants", [])
    for lspec in bp["lieutenants"]:
        role = lspec["as"]
        entry = adv["cast"].get(role)
        if not entry or "band" not in entry:
            continue
        i = next((k for k, r in enumerate(recs) if r["as"] == role and r["fate"] in AGAIN), None)
        if i is None:
            recs.append(_make(game, adv, t, lspec, rng.child(f"lt/{role}")))
            i = len(recs) - 1
        recs[i]["adv"] = adv["id"]
        recs[i]["turns"] = list(lspec.get("turns", []))
        entry["lt"] = i


def _make(game, adv: dict, t: dict, lspec: dict, rng) -> dict:
    from realmwalker.world import threats

    sp = spec(game)
    w = game.world
    names = game.tables.names["cultures"]
    fig = threats.villain_figure(w, t)
    culture = getattr(fig, "culture", "") if fig is not None and fig.kind == "person" else ""
    if culture not in names:
        town = (adv["places"].get("town") or {}).get("settlement")
        culture = w.settlements[int(town)].culture if town is not None else ""
    if culture not in names:
        culture = "heartland" if "heartland" in names else next(iter(names))
    sex = rng.choice(["male", "male", "female"])
    creature = [c for c in lspec.get("creature", []) if c in game.tables.creatures]
    return {"as": lspec["as"], "name": rng.choice(names[culture][sex]), "title": rng.choice(lspec["titles"]),
            "sex": sex, "culture": culture, "creature": rng.choice(creature) if creature else "",
            "trait": rng.choice(sorted(sp["traits"])), "weakness": _fill(game, rng.choice(sp["weaknesses"]),
                                                                          {"villain": threats.villain_name(w, t)}, rng),
            "look": rng.choice(sp["looks"]), "fate": "unmet", "grudge": 0, "scars": [], "met": 0,
            "adv": adv["id"], "turns": []}


# ---------------------------------------------------------------------------- met in a fight
def on_spawn(game, adv: dict, role: str, creatures: list, rng) -> str:
    """A role's band is spawned: its head becomes the lieutenant (their creature, name and tag). Returns what is said
    when one who got away meets you again."""
    rec = of(game, adv, role)
    if rec is None or not creatures or rec["fate"] not in FREE:
        return ""  # (one slain, taken or turned does not come back at the head of a band)
    head = creatures[0]
    if rec.get("creature") and rec["creature"] in game.tables.creatures and head.def_id != rec["creature"]:
        from realmwalker.rules.creatures import spawn

        new = spawn(game.tables, rec["creature"], rng.child("lt"), head.uid, now=game.world.time)
        new.story = head.story
        creatures[0] = head = new
    _dress(head, rec, adv["id"], role, int(adv["cast"][role]["lt"]))
    rec["met"] = int(rec.get("met", 0)) + 1
    again = rec["fate"] in ("escaped", "spared") and int(rec.get("grudge", 0)) > 0
    if rec["fate"] == "unmet":
        rec["fate"] = "met"
    return line(game, adv, rec, "returns", rng) if again else ""


def _dress(c, rec: dict, aid: str | None, role: str, i: int) -> None:
    c.name, c.named, c.sex = full(rec), True, rec.get("sex", c.sex)
    c.culture = c.culture or rec.get("culture", "")
    c.story = dict(c.story or {}, role=role, lt=i)
    if aid is not None:
        c.story["adv"] = aid


def _record_of(game, tag: dict) -> tuple[dict | None, dict | None]:
    """(the lieutenant's record, its adventure) from a creature's story tag; a nemesis has no adventure (its band's
    minions are not the lieutenant)."""
    if tag.get("role") == "minion":
        return None, None
    if "nemesis" in tag:
        nem = game.world.politics.get("nemeses", [])
        i = int(tag["nemesis"])
        return (nem[i]["lt"] if 0 <= i < len(nem) else None), None
    adv = _story().adventures(game.world).get(tag.get("adv"))
    if adv is None or "lt" not in tag:
        return None, None
    recs = records(game, adv)
    i = int(tag["lt"])
    return (recs[i] if 0 <= i < len(recs) else None), adv


def arm(battle, f, game) -> None:
    """A lieutenant in a fight: its trait's morale and its try at escape; each grudge, more of everything."""
    tag = (getattr(f.creature, "story", None) or {}) if f.creature is not None else {}
    if "lt" not in tag and "nemesis" not in tag:
        return
    rec, adv = _record_of(game, tag)
    if rec is None:
        return
    sp = spec(game)
    trait = sp["traits"].get(rec["trait"], {})
    d = dict(f.cdef)
    d["morale"] = trait.get("morale", d.get("morale", "warrior"))
    if float(trait.get("flee_at", 0)) > 0 and not d.get("boss_phase"):
        rng = battle.rng.child(f"lt-lines/{f.id}")
        d["boss_phase"] = {"at": float(trait["flee_at"]), "kind": "escape",
                           "lines": [_fill(game, x, _words(game, adv, rec), rng)
                                     for x in sp["lines"]["escape"]]}
    g = max(0, min(int(sp["grudge"]["max"]), int(rec.get("grudge", 0))))
    if g:
        d["ac"] = int(d["ac"]) + min(g * int(sp["grudge"]["ac"]), int(sp["grudge"]["ac_max"]))
        blades = sp["grudge"]["blade"]
        f.buffs.append({"id": "grudge", "name": "grudge", "damage_die": blades[min(g, len(blades)) - 1],
                        "rounds": -1})
        if not f.creature.uses.get("lt_armed"):
            f.creature.max_hp = int(round(f.creature.max_hp * (1.0 + float(sp["grudge"]["hp"]) * g)))
            f.creature.hp = f.creature.max_hp
            f.creature.uses["lt_armed"] = 1
    f.cdef = d


def on_battle(game, result) -> None:
    """After a fight: a lieutenant slain, taken or got away (by its story tag); a nemesis too."""
    rng = game.world.rng.child(f"lt-after/{game.world.time}")
    for c, how in [(c, "dead") for c in result.dead] + [(c, "taken") for c in getattr(result, "captives", [])] + \
            [(c, "fled") for c in getattr(result, "fled", [])]:
        tag = getattr(c, "story", None) or {}
        rec, adv = _record_of(game, tag)
        if rec is None:
            continue
        if "nemesis" in tag:
            _nemesis_after(game, int(tag["nemesis"]), how, c, rng)
            continue
        if adv is None or adv["state"] != "active" or rec["fate"] not in FREE:
            continue
        if how == "dead":
            _slain(game, adv, rec, rng)
        elif how == "taken":
            rec["fate"] = "taken"  # (the aftermath judges them next: on_fate)
        else:
            _escaped(game, adv, rec, c, rng)


def _say(game, adv: dict | None, text: str, colour: str) -> None:
    if not text:
        return
    if adv is not None:
        _story().journal(adv, text, int(game.moment.total_days))
    game.say(f"<{colour}>{esc(text)}</>", "story")


def _slain(game, adv: dict, rec: dict, rng) -> None:
    rec["fate"] = "slain"
    temper = ((_story().threat_of(game, adv) or {}).get("villain") or {}).get("temper") or ""
    _say(game, adv, line(game, adv, rec, "slain_grief" if temper in ("grieving", "proud") else "slain_rage", rng),
         "warn")


def _grudge(game, rec: dict) -> None:
    rec["grudge"] = min(int(spec(game)["grudge"]["max"]), int(rec.get("grudge", 0)) + 1)


def _escaped(game, adv: dict | None, rec: dict, c, rng) -> None:
    """Got away: a grudge, and a scar if you made them bleed."""
    if adv is not None:
        rec["fate"] = "escaped"
    _grudge(game, rec)
    if c.hp < c.max_hp:
        left = [s for s in spec(game)["scars"] if s not in rec["scars"]]
        if left:
            rec["scars"].append(rng.choice(left))
    if adv is not None:
        _say(game, adv, line(game, adv, rec, "escaped", rng), "warn")


def on_fate(game, creature, fate: str) -> str | None:
    """A lieutenant taken alive is judged: put to death (slain), spared or robbed and let go (they may turn - or go
    back to the villain with a grudge), bound for the law or questioned (taken). Returns what is said, or None."""
    tag = getattr(creature, "story", None) or {}
    rec, adv = _record_of(game, tag)
    if rec is None:
        return None
    rng = game.world.rng.child(f"lt-fate/{creature.uid}/{game.world.time}")
    if "nemesis" in tag:
        _nemesis_after(game, int(tag["nemesis"]), "dead" if fate == "execute" else "taken", creature, rng)
        return None
    if adv is None or adv["state"] != "active":
        return None
    if fate == "execute":
        _slain(game, adv, rec, rng)
        from realmwalker.game.story import villain

        villain.on_fight(game, adv, lieutenants=1)  # (as if they fell fighting: its notice, and its wrath)
        return None
    if fate not in ("spare", "rob"):
        rec["fate"] = "taken"
        return None
    trait = spec(game)["traits"].get(rec["trait"], {})
    chance = float(trait.get("turn", 0)) * (0.5 if fate == "rob" else 1.0)
    if rng.chance(chance):
        rec["fate"] = "turncoat" if rng.chance(float(trait.get("betray", 0))) else "turned"
        text = line(game, adv, rec, "turned", rng)
        _say(game, adv, text, "good")
        if rec["fate"] == "turned":  # (a turncoat's word is worthless: what it told you was a lie)
            from realmwalker.game.story import beats

            for g in rec.get("turns", []):
                kind, _, what = g.partition(":")
                if kind in ("clue", "key"):
                    for said in beats.OPS[kind](game, {"adv": adv["id"]}, what) or []:
                        game.say(said, "story")
        return text
    rec["fate"] = "spared"
    _grudge(game, rec)
    text = line(game, adv, rec, "spared_back", rng)
    _say(game, adv, text, "warn")
    return text


# ---------------------------------------------------------------------------- the finale
def join_finale(game, adv: dict, actor) -> list[str]:
    """Every lieutenant still the villain's stands beside it at the end, each in the place of one of its men (the
    band is led, not swollen: law 5's numbers stay the finale's); once, and they stay in its band."""
    if actor is None or not actor.creatures or adv.get("lt_joined"):
        return []
    from realmwalker.rules.creatures import spawn

    adv["lt_joined"] = True
    rng = game.world.rng.child(f"lt-finale/{adv['id']}")
    uid = max(c.uid for c in actor.creatures) + 1
    out = []
    for role, rec in _tale_lieutenants(game, adv):
        if rec["fate"] not in FREE:
            continue
        cid = rec.get("creature") or ""
        if cid not in game.tables.creatures:
            group = (adv["cast"].get(role) or {}).get("band")
            enc = game.tables.creatures.encounters.get(group or "")
            cid = enc["members"][0][0] if enc else ""
        if cid not in game.tables.creatures:
            continue
        c = spawn(game.tables, cid, rng.child(role), uid, now=game.world.time)
        uid += 1
        _dress(c, rec, adv["id"], role, int(adv["cast"][role]["lt"]))
        men = [m for m in actor.creatures if (getattr(m, "story", None) or {}).get("role") == "minion"]
        if men:
            actor.creatures.remove(men[-1])
        actor.creatures.append(c)
        key = "turncoat" if rec["fate"] == "turncoat" else "joins_grudge" if int(rec.get("grudge", 0)) else "joins"
        out.append(line(game, adv, rec, key, rng))
    return [x for x in out if x]


# ---------------------------------------------------------------------------- the end of the tale
def after_tale(game, adv: dict) -> None:
    """Each lieutenant's page in the epilogue; the one with the greatest grudge still free when its villain has
    fallen is promoted: a nemesis who will come for you."""
    sp = spec(game)
    pairs = _tale_lieutenants(game, adv)
    if not sp or not pairs:
        return
    rng = game.world.rng.child(f"lt-epilogue/{adv['id']}")
    fallen = bool(adv.get("boss_dead") or adv.get("boss_taken")) and adv.get("ending") != "bargained" and         adv.get("villain_fate") not in ("spare", "rob")  # (a villain let go keeps its own)
    free = [rec for _, rec in pairs if rec["fate"] in ("met", "unmet", "escaped", "spared")]
    nem = sp["nemesis"]
    best = max(free, key=lambda r: (int(r.get("grudge", 0)), r["name"]), default=None)
    if fallen and best is not None and int(best.get("grudge", 0)) >= int(nem["grudge"]):
        _promote(game, adv, best, rng)
    villain = _words(game, adv, pairs[0][1]).get("villain")
    for role, rec in pairs:
        page = {"slain": "slain", "taken": "taken", "turned": "turned", "turncoat": "turncoat",
                "promoted": "promoted"}.get(rec["fate"], "free")
        text = line(game, adv, rec, page, rng, villain=villain, table="epilogue")
        if text:
            adv.setdefault("epilogue", []).insert(max(0, len(adv.get("epilogue", [])) - 1),
                                                  {"about": f"lieutenant:{role}", "text": text})


def _promote(game, adv: dict, rec: dict, rng) -> None:
    from realmwalker.game.story import forge as forgemod

    t = _story().threat_of(game, adv) or {}
    sp = spec(game)["nemesis"]
    band = sp["band"].get(t.get("kind", ""), "") or (adv["cast"].get(rec["as"]) or {}).get("band", "")
    if band not in game.tables.creatures.encounters:
        return
    rec["fate"] = "promoted"
    lo, hi = sp["first"]
    nem = game.world.politics.setdefault("nemeses", [])
    nem.append({"lt": dict(rec, scars=list(rec.get("scars", []))), "threat": t.get("id"),
                "villain": _words(game, adv, rec).get("villain"), "life": forgemod.life_of(game), "band": band,
                "next": int(game.moment.total_days) + rng.randint(int(lo), int(hi)), "state": "hunting"})


# ---------------------------------------------------------------------------- the nemesis
def due(game) -> int | None:
    """The nemesis who comes for this hero now (on the road, out of towns), or None."""
    from realmwalker.game.story import forge as forgemod

    today = int(game.moment.total_days)
    life = forgemod.life_of(game)
    for i, n in enumerate(game.world.politics.get("nemeses", [])):
        if n["state"] == "hunting" and n["life"] == life and int(n["next"]) <= today:
            return i
    return None


def on_travel(game) -> bool:
    """A nemesis due steps into the road with the villain's old company."""
    if game.encounter is not None or game.battle is not None or \
            game.world.settlement_at(game.player.x, game.player.y) is not None:
        return False
    i = due(game)
    if i is None:
        return False
    from realmwalker.game.encounters import land_budget, make_encounter
    from realmwalker.rules.creatures import spawn, spawn_group

    n = game.world.politics["nemeses"][i]
    rec = n["lt"]
    rng = game.world.rng.child(f"nemesis/{i}/{game.world.time}")
    lo, hi = spec(game)["nemesis"]["again"]
    n["next"] = int(game.moment.total_days) + rng.randint(int(lo), int(hi))  # (beaten off, they come again)
    enc = make_encounter(game, n["band"], rng)
    creatures = spawn_group(game.tables, n["band"], rng.child("band"), now=game.world.time,
                            party_size=len(game.party), budget=land_budget(game, rng.child("budget"),
                                                                           difficulty="high"))
    if not creatures:
        return False
    if rec.get("creature") in game.tables.creatures:
        creatures[0] = spawn(game.tables, rec["creature"], rng.child("lt"), creatures[0].uid, now=game.world.time)
    for c in creatures[1:]:
        c.story = {"nemesis": i, "role": "minion"}
    _dress(creatures[0], rec, None, rec["as"], -1)
    creatures[0].story = {"nemesis": i, "role": rec["as"]}
    enc.creatures = creatures
    enc.intro = line(game, None, rec, "nemesis", rng, villain=n.get("villain"))
    enc.attitude = "hostile"
    game.encounter = enc
    game.travel = None
    return True


def _nemesis_after(game, i: int, how: str, c, rng) -> None:
    nem = game.world.politics.get("nemeses", [])
    if not 0 <= i < len(nem) or nem[i]["state"] != "hunting":
        return
    n = nem[i]
    rec = n["lt"]
    if how == "fled":
        _escaped(game, None, rec, c, rng)
        game.say(f"<warn>{esc(line(game, None, rec, 'nemesis_fled', rng, villain=n.get('villain')))}</>", "story")
        return
    n["state"] = "slain" if how == "dead" else "taken"
    text = line(game, None, rec, "nemesis_slain", rng, villain=n.get("villain"))
    game.say(f"<good>{esc(text)}</>", "story")
    from realmwalker.world import news

    news.add(game.world, text, game.player.x, game.player.y, importance=2, player=True)
    game.leader.deeds.append(f"ended the grudge of {full(rec)}")


# ---------------------------------------------------------------------------- the journal
def journal_lines(game, adv: dict) -> list[str]:
    """Its hands, as far as you know them: met ones by name, trait and scars; their fates."""
    out = []
    sp = spec(game)
    for _, rec in _tale_lieutenants(game, adv):
        if rec["fate"] == "unmet":
            continue
        trait = sp.get("traits", {}).get(rec["trait"], {}).get("words", rec["trait"])
        bits = [f"{esc(full(rec))}, {esc(rec['look'])}; {esc(trait)}"]
        if int(rec.get("met", 0)) >= 2 or rec["fate"] in ("taken", "turned", "turncoat", "spared"):
            bits.append(f"they {esc(rec['weakness'])}")
        if rec.get("scars"):
            bits.append("marked by " + esc(", ".join(rec["scars"])))
        fate = {"met": "", "escaped": "<warn>got away</>", "spared": "<warn>spared, and went back</>",
                "turned": "<good>came over to you</>", "turncoat": "<good>came over to you</>",
                "slain": "<danger>dead</>", "taken": "<dim>taken</>", "promoted": "<danger>sworn against you</>"}
        mark = fate.get(rec["fate"], "")
        grudge = "!" * int(rec.get("grudge", 0))
        out.append("  " + "; ".join(bits) + (f" {mark}" if mark else "") + (f" <danger>{grudge}</>" if grudge else ""))
    return out
