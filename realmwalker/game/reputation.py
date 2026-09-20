"""Your name in the world (M6): standing with each faction, fame and infamy, which factions you know of,
membership, bounties and crimes. Kept with the character (a new character in the same world starts unknown).

Standing runs from -100 to +100 per faction. What you do ripples through the web of relations: helping a
faction pleases its friends and annoys its enemies, in proportion to how strongly they feel about it, and
only once they hear of it (game.news carries deeds along the roads).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from realmwalker.world import factions as fx

RIPPLE = 0.5  # how much of a deed's weight reaches a faction's friends (and, reversed, its enemies)
RIPPLE_MIN_RELATION = 20  # factions that feel less strongly than this about each other don't care


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
    was = rank(game, fid)
    set_standing(game, fid, before + amount)
    now = rank(game, fid)
    if was is not None and now is not None and now != was:
        f = game.world.factions.get(fid)
        if f is not None:
            name = rank_name(game, fid)
            if now > was:
                game.say(f"<good>{f.name} calls you {name} now.</>", "good")
            else:
                game.say(f"<warn>{f.name} counts you no more than {name} now.</>", "warn")
    return game.renown.standing[fid] - before


# ---------------------------------------------------------------------------- deeds and their ripples
def ripple(world, amounts: dict[int, float]) -> dict[int, float]:
    """How a deed that changes standing with some factions changes it with everyone who cares about them."""
    out: dict[int, float] = {}
    for f in fx.active_factions(world):
        if f.id in amounts:
            continue
        total = 0.0
        for fid, amount in amounts.items():
            r = fx.relation(world, f.id, fid)
            if abs(r) >= RIPPLE_MIN_RELATION:
                total += amount * r / 100.0 * RIPPLE
        if abs(total) >= 0.5:
            out[f.id] = total
    return out


def deed(game, text: str, amounts: dict[int, float], *, x: int | None = None, y: int | None = None,
         witnessed: bool = True, immediate=(), importance: int = 2, fame: int = 0, infamy: int = 0,
         news_text: str | None = None) -> None:
    """Something the player did that people will talk about. amounts: standing change with each faction
    directly concerned; those in `immediate` know at once (they were there). Everyone else, including the
    friends and enemies of those concerned, learns of it when the news reaches them."""
    from realmwalker.game import news

    w = game.world
    x = game.player.x if x is None else x
    y = game.player.y if y is None else y
    game.leader.deeds.append(text)
    if not witnessed:
        return
    r = game.renown
    r.fame += int(fame)
    r.infamy += int(infamy)
    later: dict[int, float] = {}
    for fid, amount in amounts.items():
        if fid not in w.factions:
            continue
        if fid in immediate:
            change_standing(game, fid, amount)
            know(game, fid)
        else:
            later[fid] = amount
    for fid, amount in ripple(w, amounts).items():
        later.setdefault(fid, amount)
    if later:
        r.pending.append({"x": int(x), "y": int(y), "day": news.now_days(w),
                          "effects": {str(k): round(v, 2) for k, v in later.items()}})
    if news_text:
        news.add(w, news_text, x, y, kind="deed", importance=importance, factions=list(amounts), player=True)


def tick(game) -> None:
    """Deeds reach the factions who care, as the news travels."""
    from realmwalker.game import news

    w = game.world
    today = news.now_days(w)
    keep = []
    for entry in game.renown.pending:
        left = {}
        for key, amount in entry["effects"].items():
            f = w.factions.get(int(key))
            if f is None or not f.active:
                continue
            place = news.faction_place(w, f)
            if place is None or today >= entry["day"] + news.travel_days(entry["x"], entry["y"], *place):
                change_standing(game, int(key), amount)
            else:
                left[key] = amount
        if left:
            entry["effects"] = left
            keep.append(entry)
    game.renown.pending = keep
    # A faction cannot keep calling you an apprentice for ever: two ranks of goodwill promote you anyway.
    for fid in list(game.renown.members):
        if standing_rank(game, fid) >= confirmed_rank(game, fid) + 2:
            said = confirm_rank(game, fid)
            if said:
                game.say(f"<good>{said}</> <dim>(They could hardly go on calling you what they did.)</>", "good")


FOE_KINDS = {"bandit": "bandit_gang", "bandit_archer": "bandit_gang", "bandit_captain": "bandit_gang",
             "thug": "bandit_gang", "cultist": "cult", "cult_fanatic": "cult", "orc": "tribe", "goblin": "tribe",
             "ogre": "tribe"}


def foe_faction(game, def_id: str):
    """The faction a foe of this kind here most likely belongs to: the gang whose country this is, the nearest
    cult, the tribe of these lands."""
    kind = FOE_KINDS.get(def_id)
    w = game.world
    if kind is None or not w.factions:
        return None
    from realmwalker.game.news import faction_place

    p = game.player
    best, best_d = None, 10**9
    for f in fx.active_factions(w, kind):
        place = faction_place(w, f)
        if place is None:
            continue
        d = abs(place[0] - p.x) + abs(place[1] - p.y)
        limit = int(f.flags.get("range", 30 if kind == "tribe" else 40))
        if d <= limit and d < best_d:
            best, best_d = f, d
    return best


def battle_deeds(game, result) -> None:
    """Beating outlaws, cultists or raiders pleases the lords of the land and angers their fellows."""
    counts: dict[int, int] = {}
    for c in list(result.dead) + list(result.captives):
        f = foe_faction(game, c.def_id)
        if f is not None:
            counts[f.id] = counts.get(f.id, 0) + 1
    if not counts:
        return
    w = game.world
    realm = realm_here(game)
    for fid, n in counts.items():
        f = w.factions[fid]
        amounts = {fid: -min(25.0, 5.0 * n)}
        if realm is not None:
            amounts[realm.id] = min(10.0, 2.0 * n)
        survivors = bool(result.fled)
        place = w.area_at(game.player.x, game.player.y)
        where = place.name if place is not None else "the road"
        know(game, fid)
        if game.party[1:]:
            from realmwalker.game.companions import react

            react(game, "cult_hunted" if f.kind == "cult" else "outlaws_beaten" if f.kind == "bandit_gang" else
                  "victory", quiet=f.kind not in ("cult", "bandit_gang"))
        deed(game, f"fought {f.name}", amounts, immediate=(fid,) if survivors else (), fame=max(1, n // 2),
             importance=1 if n < 4 else 2, news_text=f"{game.leader.name} cut down {n} of {f.name} in {where}")


def realm_here(game):
    """The realm whose lands the player stands in (None in the wild)."""
    lord = fx.lord_at(game.world, game.player.x, game.player.y) if game.world.factions else None
    if lord is None or lord.kind == "tribe":
        return None
    return fx.top_liege(game.world, lord)


# ---------------------------------------------------------------------------- membership and titles
def standing_rank(game, fid: int) -> int:
    """The rank your standing with them would allow, if they were willing."""
    thresholds = game.tables.law["rank_standing"]
    score = standing(game, fid)
    return max(0, sum(1 for t in thresholds if score >= t) - 1)


def confirmed_rank(game, fid: int) -> int:
    """The rank they have actually given you. Old saves keep the rank they had."""
    ranks = game.renown.flags.setdefault("ranks", {})
    key = str(fid)
    if key not in ranks:
        ranks[key] = standing_rank(game, fid)
    return int(ranks[key])


def confirm_rank(game, fid: int) -> str:
    """They have seen what you can do: the next step is yours."""
    ranks = game.renown.flags.setdefault("ranks", {})
    key = str(fid)
    ranks[key] = min(standing_rank(game, fid), confirmed_rank(game, fid) + 1)
    game.dirty = True
    f = game.world.factions.get(fid)
    return f"{f.name} calls you {rank_name(game, fid)} now." if f is not None else ""


def needs_trial(game, fid: int) -> bool:
    """Your standing would carry you higher; they want a piece of work first."""
    return fid in game.renown.members and standing_rank(game, fid) > confirmed_rank(game, fid)


def rank(game, fid: int) -> int | None:
    if fid not in game.renown.members:
        return None
    return min(standing_rank(game, fid), confirmed_rank(game, fid))


def rank_name(game, fid: int) -> str:
    f = game.world.factions.get(fid)
    r = rank(game, fid)
    if f is None or r is None:
        return ""
    spec = game.tables.law["join"].get(f.kind)
    return spec["ranks"][min(r, len(spec["ranks"]) - 1)] if spec else "member"


def join_problem(game, f) -> str | None:
    """Why the player can't join a faction (None if they can)."""
    from realmwalker.rules.items import money_text

    spec = game.tables.law["join"].get(f.kind)
    if spec is None:
        return "they do not take members"
    if f.id in game.renown.members:
        return "you are already one of them"
    c = game.leader
    if standing(game, f.id) < spec["standing"]:
        return f"they need to think better of you first (at least {spec['standing']:+d})"
    if spec.get("skill") and spec["skill"] not in c.skills:
        return f"they want someone trained in {spec['skill'].replace('_', ' ')}"
    if spec.get("tool") and spec["tool"] not in c.tools:
        return f"they want someone who knows {game.tables.rules['tools'].get(spec['tool'], spec['tool'])}"
    if spec.get("classes") and c.cls not in spec["classes"]:
        return "they don't want your kind"
    if spec.get("faith") and fx.faith_for_culture(game.tables, c.culture) != f.faith:
        return "you are not of their faith"
    if sum(m.money for m in game.party) < spec["fee"]:
        return f"the fee is {money_text(spec['fee'])}"
    return None


def start_at_the_bottom(game, fid: int) -> None:
    game.renown.flags.setdefault("ranks", {})[str(fid)] = 0


def join(game, f) -> str:
    from realmwalker.game.law import take_money
    from realmwalker.rules.items import money_text

    problem = join_problem(game, f)
    if problem:
        return f"You can't join: {problem}."
    spec = game.tables.law["join"][f.kind]
    take_money(game, spec["fee"])
    game.renown.members[f.id] = 0
    start_at_the_bottom(game, f.id)  # however well they think of you, you start where everyone starts
    change_standing(game, f.id, 10)
    know(game, f.id)
    fee = f" (the fee: {money_text(spec['fee'])})" if spec["fee"] else ""
    if game.party[1:]:
        from realmwalker.game.companions import react

        react(game, "cult" if f.kind == "cult" else "theft" if f.kind == "thieves_guild" else
              "prayer" if f.kind in ("temple", "knightly_order") else "joined")
    return f"<good>You are sworn into {f.name}</> as {rank_name(game, f.id)}{fee}."


def member_discount(game, factions) -> float:
    """Price cut for members of the seller's guild or church."""
    best = 0.0
    for f in factions:
        r = rank(game, f.id)
        spec = game.tables.law["join"].get(f.kind)
        if r is not None and spec:
            best = max(best, float(spec.get("discount", 0)) * (1 + r * 0.5))
    return min(0.3, best)


def title_problem(game, realm) -> str | None:
    spec = game.tables.law["titles"]
    if realm.kind not in spec["names"]:
        return "they grant no titles"
    if any(t.get("realm") == realm.id for t in game.renown.flags.get("titles", [])):
        return "they have already honoured you"
    if standing(game, realm.id) < spec["standing"]:
        return "you are not honoured enough here"
    if game.renown.fame < spec["fame"]:
        return "you are not famous enough"
    return None


def grant_title(game, realm) -> str:
    problem = title_problem(game, realm)
    if problem:
        return f"No title for you: {problem}."
    names = game.tables.law["titles"]["names"][realm.kind]
    title = names[0] if game.leader.sex == "male" else names[1]
    game.renown.flags.setdefault("titles", []).append({"realm": realm.id, "title": title})
    game.renown.fame += 5
    if game.party[1:]:
        from realmwalker.game.companions import react

        react(game, "title")
    return f"<good>You kneel, and rise as {title} {game.leader.name}</>, honoured by {realm.name}."


def titles(game) -> list[str]:
    return [t["title"] for t in game.renown.flags.get("titles", [])]


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
    game.renown.flags["start_day"] = game.moment.total_days


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
    wars = [x for x in w.wars if x.get("active") and f.id in (x["attacker"], x["defender"])]
    for war in wars:
        other = w.factions.get(war["defender"] if war["attacker"] == f.id else war["attacker"])
        if other is not None:
            since = t.calendar.at(int(war["started"] * 1440)).year if war["started"] > -10**6 else "?"
            lines.append(f"<danger>At war with {esc(other.name)}</> <dim>(since {since}).</>")
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
