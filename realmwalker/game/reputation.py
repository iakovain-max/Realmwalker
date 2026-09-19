"""Your name in the world (M6): standing with each faction, fame and infamy, which factions you know of,
membership, bounties and crimes. Kept with the character (a new character in the same world starts unknown).

Standing runs from -100 to +100 per faction. What you do ripples through the web of relations: helping a
faction pleases its friends and annoys its enemies, in proportion to how strongly they feel about it, and
only once they hear of it (game.news carries deeds along the roads).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from realmwalker.world import factions as fx


@dataclass
class Renown:
    standing: dict[int, float] = field(default_factory=dict)  # faction id -> -100..100
    fame: int = 0
    infamy: int = 0
    known: set[int] = field(default_factory=set)  # factions the player knows of
    members: dict[int, int] = field(default_factory=dict)  # faction id -> rank (0 = sworn in)
    bounties: dict[int, int] = field(default_factory=dict)  # realm faction id -> copper on your head
    crimes: list[dict] = field(default_factory=list)
    heard: set[int] = field(default_factory=set)  # news ids already heard
    pending: list[dict] = field(default_factory=list)  # deeds still travelling to the factions who care
    marks: list[str] = field(default_factory=list)  # "branded", "flogged"
    flags: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "standing": {str(k): round(v, 2) for k, v in self.standing.items()},
            "fame": self.fame, "infamy": self.infamy, "known": sorted(self.known),
            "members": {str(k): v for k, v in self.members.items()},
            "bounties": {str(k): v for k, v in self.bounties.items()},
            "crimes": self.crimes, "heard": sorted(self.heard), "pending": self.pending, "marks": self.marks,
            "flags": self.flags,
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> Renown:
        d = d or {}
        return cls(
            standing={int(k): float(v) for k, v in d.get("standing", {}).items()},
            fame=int(d.get("fame", 0)), infamy=int(d.get("infamy", 0)), known=set(d.get("known", [])),
            members={int(k): int(v) for k, v in d.get("members", {}).items()},
            bounties={int(k): int(v) for k, v in d.get("bounties", {}).items()},
            crimes=list(d.get("crimes", [])), heard=set(d.get("heard", [])), pending=list(d.get("pending", [])),
            marks=list(d.get("marks", [])), flags=dict(d.get("flags", {})),
        )


# ---------------------------------------------------------------------------- standing
def standing(game, fid: int) -> int:
    return int(round(game.renown.standing.get(fid, 0.0)))


def standing_markup(game, fid: int) -> str:
    score = standing(game, fid)
    name, color = fx.standing_name(game.tables, score)
    return f"<{color}>{name}</> <dim>({score:+d})</>"


def set_standing(game, fid: int, value: float) -> None:
    game.renown.standing[fid] = max(-100.0, min(100.0, float(value)))


def change_standing(game, fid: int, amount: float) -> float:
    """Change standing with one faction only (no ripple). Returns the change actually made."""
    before = game.renown.standing.get(fid, 0.0)
    set_standing(game, fid, before + amount)
    return game.renown.standing[fid] - before


# ---------------------------------------------------------------------------- knowing about factions
def know(game, fid: int, *, quiet: bool = True) -> bool:
    """The player learns that a faction exists. True if it was news."""
    f = game.world.factions.get(fid)
    if f is None or fid in game.renown.known:
        return False
    game.renown.known.add(fid)
    if not quiet:
        game.say(f"<info>You learn of {f.name}</> <dim>({fx.kind_label(game.tables, f)}).</>", "info")
    return True


def public_factions_at(game, settlement) -> list:
    """Factions anyone in a settlement would know of: its lord and realm, its church, its public guilds."""
    w = game.world
    out = []
    owner = fx.owner_of(w, settlement)
    chain = owner
    seen = set()
    while chain is not None and chain.id not in seen:
        seen.add(chain.id)
        out.append(chain)
        chain = w.factions.get(chain.liege)
    for f in fx.active_factions(w):
        if f.secret or f in out:
            continue
        if f.seat == settlement.id or settlement.id in f.presence:
            out.append(f)
    return out


def learn_place(game, settlement, *, quiet: bool = True) -> list:
    """Arriving somewhere teaches you who rules it and who else is here."""
    return [f for f in public_factions_at(game, settlement) if know(game, f.id, quiet=quiet)]


def known_factions(game) -> list:
    return [f for f in fx.active_factions(game.world) if f.id in game.renown.known]


# ---------------------------------------------------------------------------- the start of a life
def starting_knowledge(game) -> None:
    """A new character knows the realms and churches of the places they have heard of, and their own people's."""
    w = game.world
    for sid in sorted(game.player.known_settlements | {game.player.home}):
        if 0 <= sid < len(w.settlements):
            learn_place(game, w.settlements[sid])
    church = fx.church_of(w, fx.faith_for_culture(game.tables, game.leader.culture))
    if church is not None:
        know(game, church.id)
    apply_ties(game)
    game.renown.flags["started"] = True


def apply_ties(game) -> None:
    """Background ties become real standing: the lord you served, your temple, your family's house, a bounty."""
    w = game.world
    for tie in game.leader.ties:
        refs = tie.get("refs", {})
        fid = refs.get("faction")
        if tie.get("kind") == "noble_house" and fid is None:
            fid = make_family_house(game, tie)
            refs["faction"] = fid
        if fid is not None and fid in w.factions:
            know(game, fid)
            set_standing(game, fid, standing(game, fid) + int(refs.get("standing", 15)))
            if tie.get("kind") in ("guild", "temple", "noble_house", "scholar", "clan"):
                game.renown.members.setdefault(fid, 0)
        realm = refs.get("bounty_faction")
        if realm is not None and realm in w.factions and refs.get("bounty"):
            know(game, realm)
            game.renown.bounties[realm] = game.renown.bounties.get(realm, 0) + int(refs["bounty"])
            game.renown.crimes.append({"crime": "old", "text": refs.get("crime") or "an old charge",
                                       "realm": realm, "place": refs.get("bounty_place", -1), "day": -1,
                                       "reported": True, "bounty": int(refs["bounty"])})


def make_family_house(game, tie: dict) -> int | None:
    """A noble character's family: a minor house sworn to the lord of its seat, holding no land of its own."""
    w = game.world
    refs = tie.get("refs", {})
    place = refs.get("place")
    if place is None or not 0 <= place < len(w.settlements):
        return None
    seat = w.settlements[place]
    family = game.leader.name.split()[-1]
    lord = fx.owner_of(w, seat)
    fid = max(w.factions, default=-1) + 1
    f = fx.Faction(id=fid, name=tie.get("names", {}).get("house", f"House {family}"), kind="noble_house",
                   culture=game.leader.culture, seat=seat.id, liege=lord.id if lord else -1,
                   faith=fx.faith_for_culture(game.tables, game.leader.culture), values=["honor-bound"],
                   founded=game.moment.year - 90, wealth=150, military=10,
                   color=lord.color if lord else (120, 120, 120))
    f.flags.update(minor=True, family=family)
    head_name = tie.get("names", {}).get("head", f"{family}")
    head = fx.Figure(id=w.next_figure_id, name=head_name, sex="male", race=game.leader.race,
                     culture=game.leader.culture, born=game.moment.year - 55, faction=fid, title="Lord", role="ruler")
    w.next_figure_id += 1
    w.figures[head.id] = head
    f.leader = head.id
    f.rulers.append(head.id)
    f.members.append(head.id)
    w.factions[fid] = f
    if lord is not None:
        fx.set_relation(w, fid, lord.id, 45)
        top = fx.top_liege(w, lord)
        if top is not None and top is not lord:
            fx.set_relation(w, fid, top.id, 30)
    refs["standing"] = 50
    return fid


# ---------------------------------------------------------------------------- describing a faction
def wealth_word(wealth: int) -> str:
    for limit, word in ((150, "poor"), (800, "of modest means"), (3000, "comfortable"), (10000, "rich")):
        if wealth < limit:
            return word
    return "very rich"


def names_list(names: list[str], limit: int = 5) -> str:
    if len(names) > limit:
        names = names[:limit] + [f"{len(names) - limit} more"]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def faction_details(game, f) -> str:
    """Everything the player knows about a faction, as marked-up text."""
    from realmwalker.core.textgen import escape_markup as esc

    w = game.world
    t = game.tables
    data = t.factions
    year = game.moment.year
    lines = [f"<title>{esc(f.name[:1].upper() + f.name[1:])}</>"]
    sub = fx.kind_label(t, f)
    liege = w.factions.get(f.liege)
    if liege is not None and liege.active:
        sub += f" · sworn to {esc(liege.name)}"
    lines.append(f"<dim>{sub}</>")
    lines.append("")
    if f.seat >= 0:
        seat = w.settlements[f.seat]
        kind = t.sites["settlement_types"][seat.kind]["name"]
        lines.append(f"Seat: <place>{esc(seat.name)}</> <dim>({kind})</>.")
    held = fx.holdings(w, f, deep=f.kind in ("kingdom", "elven_realm"))
    if held:
        known = [s.name for s in held if s.id in game.player.known_settlements]
        more = len(held) - len(known)
        text = f"Holds {len(held)} settlement{'s' if len(held) != 1 else ''}"
        if known:
            text += ": " + esc(names_list(known)) + (f", and {more} you do not know" if more else "")
        lines.append(text + ".")
    if f.kind == "tribe" and f.area >= 0:
        area = w.areas[f.area]
        people = f.flags.get("people", "raiders")
        lines.append(f"{people.capitalize()} of <place>{esc(area.name)}</>.")
    if f.presence and f.kind not in fx.REALM_KINDS:
        where = [w.settlements[i].name for i in f.presence if i in game.player.known_settlements]
        if where:
            label = "Temples" if f.kind == "temple" else "Found"
            lines.append(f"{label} in {esc(names_list(where, 6))}.")
    leader = fx.leader_of(w, f)
    if leader is not None and leader.alive:
        lines.append(f"Led by <name>{esc(leader.full_name())}</>, {leader.age(year)} years old.")
        heirs = [fig for fig in (w.figures.get(i) for i in f.members) if fig and fig.alive and fig.role == "heir"]
        if heirs:
            lines.append(f"<dim>Heir: {esc(heirs[0].name)}, {heirs[0].age(year)}.</>")
    if f.values:
        vals = [f"<info>{data['values'][v]['label']}</> <dim>({data['values'][v]['text']})</>" for v in f.values]
        lines.append("They are " + " and ".join(vals) + ".")
    faith = data["faiths"].get(f.faith)
    if faith and f.kind != "temple":
        lines.append(f"<dim>They follow {faith['name']}.</>" if not faith.get("cult") else
                     f"<magic>They serve {faith['god']}, god of {faith['about']}.</>")
    elif faith:
        lines.append(f"<dim>{faith['god']}: {faith['about']}.</>")
    lines.append(f"<dim>About {max(0, round(f.military, -1 if f.military > 30 else 0)):,} fighting folk; "
                 f"{wealth_word(f.wealth)}.</>")
    if f.laws:
        lines.append("")
        lines.append("<title>Their laws</>")
        laws = data["laws"]
        for key in ("magic", "weapons", "religion", "serfdom", "slavery", "harshness"):
            value = f.laws.get(key)
            if value is None:
                continue
            text = laws[key].get(str(value).lower(), "")
            if text:
                lines.append(f"· {text}")
    friends, enemies = [], []
    for other in known_factions(game):
        if other.id == f.id:
            continue
        state, color = fx.relation_state(w, t, f.id, other.id)
        entry = (fx.relation(w, f.id, other.id), f"<{color}>{esc(other.name)}</> <dim>({state})</>")
        if state in ("allied", "friendly", "liege of", "vassal of"):
            friends.append(entry)
        elif state in ("hostile", "rival", "at war"):
            enemies.append(entry)
    if friends or enemies:
        lines.append("")
    if friends:
        lines.append("Friends: " + ", ".join(text for _, text in sorted(friends, key=lambda p: -p[0])[:5]) + ".")
    if enemies:
        lines.append("Enemies: " + ", ".join(text for _, text in sorted(enemies, key=lambda p: p[0])[:5]) + ".")
    lines.append("")
    lines.append(f"Your standing: {standing_markup(game, f.id)}")
    if f.id in game.renown.members:
        lines.append("<good>You are one of them.</>")
    bounty = game.renown.bounties.get(f.id, 0)
    if bounty:
        from realmwalker.rules.items import money_text

        lines.append(f"<danger>There is a price on your head here: {money_text(bounty)}.</>")
    return "\n".join(lines)
