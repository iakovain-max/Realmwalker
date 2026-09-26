"""Law and crime (M6): crimes, witnesses, the watch, bounties, sentences, jail, and escape.

A crime needs a witness to matter. A guard who sees it acts at once; anyone else reports it after an hour or
few, unless they are dead, bribed or frightened into silence. Reported crimes put a price on your head in that
realm (the top of the chain of lords), cost you standing, and become news. Where you are wanted, the watch
may recognise you (a disguise helps). When they take you, you may pay, go quietly and take the sentence the
local law demands, bribe the guard, run, or fight.

Everything here is logic; the arrest and sentence windows (ui/screens/law.py) only ask and show.
"""

from __future__ import annotations

from realmwalker.core import dice
from realmwalker.core.rng import RNG
from realmwalker.game import news, reputation
from realmwalker.rules.items import Item, money_text
from realmwalker.world import factions as fx

CONFINED_BUILDINGS = ("house", "keep", "hall", "store", "smithy", "healer", "stable")


# ---------------------------------------------------------------------------- where the law runs
def crime_def(game, cid: str) -> dict:
    return game.tables.law["crimes"][cid]


def settlement_here(game):
    return game.world.settlement_at(game.player.x, game.player.y)


def jurisdiction(game):
    """(realm, settlement or None): whose law runs where the player stands."""
    w = game.world
    p = game.player
    s = settlement_here(game)
    lord = fx.owner_of(w, s) if s is not None else fx.lord_at(w, p.x, p.y)
    if lord is None or lord.kind == "tribe":
        return None, s
    return fx.top_liege(w, lord), s


def laws_here(game) -> dict:
    realm, s = jurisdiction(game)
    return fx.laws_of(game.world, realm) if realm is not None else {}


def place_name(game, s=None) -> str:
    s = s if s is not None else settlement_here(game)
    if s is not None:
        return s.name
    area = game.world.area_at(game.player.x, game.player.y)
    return area.name if area is not None else "the wilds"


def rng_for(game, what: str) -> RNG:
    return game.world.rng.child(f"law/{what}/{game.world.time}")


def disguised(game) -> bool:
    return game.leader.effects.get("disguised", 0) > 0


# ---------------------------------------------------------------------------- witnesses
def witnesses_here(game, *, exclude=(), radius: int | None = None) -> list:
    """Townsfolk who can see the player right now (on a settlement's close-up map)."""
    from realmwalker.game.people import npcs_in
    from realmwalker.game.vision import can_see

    lm = game.local
    s = settlement_here(game)
    if lm is None or lm.kind != "settlement" or s is None:
        return []
    radius = radius or game.tables.law["guard_sight"] + 4
    p = game.player
    skip = {getattr(n, "id", n) for n in exclude}
    out = []
    for n in npcs_in(game.world, s.id):
        if not n.alive or not n.present or n.id in skip:
            continue
        if max(abs(n.x - p.lx), abs(n.y - p.ly)) > radius:
            continue
        if can_see(game, lm, (n.x, n.y), (p.lx, p.ly), radius):
            out.append(n)
    return out


# ---------------------------------------------------------------------------- committing a crime
def commit(game, cid: str, *, victim=None, value: int = 0, witnesses=None, reported: bool = False,
           guard=None) -> dict | None:
    """The player breaks the law. Returns the crime record (None where no lord's law runs)."""
    from realmwalker.game.people import change_disposition

    realm, s = jurisdiction(game)
    if realm is None:
        return None
    spec = crime_def(game, cid)
    w = game.world
    fine = int(spec["fine"] + value * float(spec.get("value_mult", 0)))
    if witnesses is None:
        witnesses = witnesses_here(game)
    owner = fx.owner_of(w, s) if s is not None else fx.lord_at(w, game.player.x, game.player.y)
    rec = {
        "id": int(game.renown.flags.get("next_crime", 0)), "crime": cid, "realm": realm.id,
        "owner": owner.id if owner is not None else realm.id, "place": s.id if s is not None else -1,
        "x": game.player.x, "y": game.player.y, "time": w.time, "day": game.moment.total_days,
        "witnesses": [n.id for n in witnesses], "reported": False, "settled": False, "bounty": fine,
        "victim": victim.name if victim is not None else "", "disguised": disguised(game),
        "text": spec["news"].format(victim=victim.name if victim is not None else "a stranger",
                                    place=place_name(game, s)),
    }
    game.renown.flags["next_crime"] = rec["id"] + 1
    game.renown.crimes.append(rec)
    if game.party[1:]:
        from realmwalker.game.companions import react_to_crime

        react_to_crime(game, cid)
    if victim is not None:
        victim.remember(f"was wronged by the traveller ({spec['name']})")
    for n in witnesses:
        n.remember(f"saw the traveller commit {spec['name']}")
        change_disposition(n, -10 * int(spec["severity"]))
    guards = [n for n in witnesses if n.job == "guard"]
    if guard is not None and guard not in guards:
        guards.insert(0, guard)
    if reported or guards:
        report(game, rec)
        if guards or guard is not None:
            start_arrest(game, guards[0] if guards else None)
    elif witnesses:
        lo, hi = game.tables.law["report_minutes"]
        rec["report_at"] = w.time + rng_for(game, f"report{rec['id']}").randint(lo, hi)
        names = ", ".join(n.label() for n in witnesses[:2])
        game.say(f"<warn>You were seen</> <dim>({names}{' and others' if len(witnesses) > 2 else ''}).</> "
                 f"They will go to the watch unless something stops them.", "warn")
    else:
        rec["unseen"] = True
        game.say("<dim>No one saw.</>", "dim")
    game.dirty = True
    return rec


def report(game, rec: dict) -> None:
    """A crime reaches the watch: a price on your head, lost standing, and talk."""
    if rec.get("reported"):
        return
    rec["reported"] = True
    rec.pop("report_at", None)
    w = game.world
    spec = crime_def(game, rec["crime"])
    realm = w.factions.get(rec["realm"])
    if realm is None:
        return
    if rec.get("disguised"):
        game.say(f"<warn>The watch of {realm.name} is looking for a stranger in disguise, for {spec['name']}.</>", "warn")
        news.add(w, f"a stranger in disguise is wanted for {rec['text']}", rec["x"], rec["y"], kind="crime",
                 importance=max(1, int(spec["severity"]) - 1), factions=[realm.id], places=[rec["place"]])
        return
    game.renown.bounties[realm.id] = game.renown.bounties.get(realm.id, 0) + int(rec["bounty"])
    amounts = {realm.id: float(spec["standing"])}
    if rec["owner"] != realm.id:
        amounts[rec["owner"]] = float(spec["standing"]) * 0.6
    who = game.leader.name
    reputation.deed(game, f"was reported for {spec['name']} in {place_for(game, rec)}", amounts,
                    x=rec["x"], y=rec["y"], immediate=tuple(amounts), importance=int(spec["severity"]),
                    infamy=int(spec["infamy"]), news_text=f"{who} is wanted for {rec['text']}")
    game.say(f"<danger>You are wanted in {realm.name} for {spec['name']}.</> The price on your head there is "
             f"{money_text(game.renown.bounties[realm.id])}.", "danger")


def place_for(game, rec: dict) -> str:
    if rec.get("place", -1) >= 0:
        return game.world.settlements[rec["place"]].name
    return "the country"


def tick(game) -> None:
    """Witnesses go to the watch; prisoners you are leading try to slip away."""
    w = game.world
    for rec in game.renown.crimes:
        at = rec.get("report_at")
        if at is None or rec.get("reported") or w.time < at:
            continue
        rec.pop("report_at", None)
        tellers = [w.npcs.get(i) for i in rec["witnesses"]]
        tellers = [n for n in tellers if n is not None and n.alive and rec["id"] not in n.flags.get("silenced", [])]
        if tellers:
            game.say(f"<warn>{tellers[0].first_name} has gone to the watch.</>", "warn")
            report(game, rec)
        else:
            rec["unseen"] = True


def unreported_seen_by(game, npc) -> list[dict]:
    """Crimes this person saw that have not reached the watch yet."""
    return [r for r in game.renown.crimes if not r.get("reported") and npc.id in r.get("witnesses", [])
            and r["id"] not in npc.flags.get("silenced", []) and r.get("report_at") is not None]


def silence(npc, records: list[dict]) -> None:
    npc.flags.setdefault("silenced", []).extend(r["id"] for r in records)


# ---------------------------------------------------------------------------- the record in a realm
def open_crimes(game, realm_id: int) -> list[dict]:
    return [r for r in game.renown.crimes if r["realm"] == realm_id and r.get("reported") and not r.get("settled")
            and not r.get("disguised")]


def worst_severity(game, realm_id: int) -> int:
    crimes = open_crimes(game, realm_id)
    if not crimes:
        return 1 if game.renown.bounties.get(realm_id, 0) > 0 else 0
    return max(int(crime_def(game, r["crime"])["severity"]) if r["crime"] in game.tables.law["crimes"] else 1
               for r in crimes)


def harshness(game, realm_id: int) -> str:
    realm = game.world.factions.get(realm_id)
    return fx.laws_of(game.world, realm).get("harshness", "stern") if realm is not None else "stern"


def sentence_for(game, realm_id: int) -> list[str]:
    sev = worst_severity(game, realm_id)
    if sev <= 0:
        return []
    return list(game.tables.law["punishments"][harshness(game, realm_id)][min(4, sev) - 1])


def sentence_text(steps: list[str]) -> str:
    words = []
    for step in steps:
        kind, _, n = step.partition(":")
        words.append({"fine": "a fine", "flogging": "a flogging", "branding": "branding", "death": "death by hanging",
                      "jail": f"{n} days in jail", "labour": f"{n} days of hard labour"}.get(kind, kind))
    if not words:
        return "nothing"
    return ", then ".join(words)


def can_buy_off(game, realm_id: int) -> bool:
    """Petty crimes can simply be paid for."""
    return worst_severity(game, realm_id) <= 2 and "death" not in sentence_for(game, realm_id)


def party_money(game) -> int:
    return sum(c.money for c in game.party)


def take_money(game, amount: int) -> int:
    """Take up to amount from the party; returns what was taken."""
    taken = 0
    for c in game.party:
        part = min(c.money, amount - taken)
        c.money -= part
        taken += part
        if taken >= amount:
            break
    return taken


def settle(game, realm_id: int) -> None:
    for r in open_crimes(game, realm_id):
        r["settled"] = True
    game.renown.bounties[realm_id] = 0


def pay_bounty(game, realm_id: int) -> str:
    bounty = game.renown.bounties.get(realm_id, 0)
    if not can_buy_off(game, realm_id):
        return "Your crimes here are too grave to buy off."
    if party_money(game) < bounty:
        return f"You don't have {money_text(bounty)}."
    take_money(game, bounty)
    settle(game, realm_id)
    reputation.change_standing(game, realm_id, 2)
    if game.party[1:]:
        from realmwalker.game.companions import react

        react(game, "paying_debts")
    back = return_confiscated(game, realm_id)
    realm = game.world.factions[realm_id]
    return f"You pay {money_text(bounty)}. Your record in {realm.name} is clean." + (f" {back}" if back else "")


# ---------------------------------------------------------------------------- the watch
def start_arrest(game, guard=None) -> None:
    realm, s = jurisdiction(game)
    if realm is None:
        return
    game.arrest = {"realm": realm.id, "settlement": s.id if s is not None else -1,
                   "guard": guard.id if guard is not None else -1, "time": game.world.time, "tried": []}
    game.travel = None
    game.dirty = True


def watch(game) -> None:
    """Guards on a settlement's close-up map may recognise a wanted face."""
    if game.arrest is not None or game.busy:
        return
    realm, s = jurisdiction(game)
    if realm is None or s is None or game.local is None or game.local.kind != "settlement":
        return
    wanted = game.renown.bounties.get(realm.id, 0) > 0
    hated = reputation.standing(game, realm.id) <= -60
    if not wanted and not hated:
        return
    from realmwalker.game.people import npcs_in
    from realmwalker.game.vision import can_see

    law = game.tables.law
    p = game.player
    w = game.world
    for n in npcs_in(w, s.id):
        if n.job != "guard" or not n.alive or not n.present:
            continue
        if n.flags.get("bribed_until", -1) > w.time or n.flags.get("looked_at", -10**9) > w.time - 60:
            continue
        if max(abs(n.x - p.lx), abs(n.y - p.ly)) > law["guard_sight"]:
            continue
        if not can_see(game, game.local, (n.x, n.y), (p.lx, p.ly), law["guard_sight"]):
            continue
        n.flags["looked_at"] = w.time
        rng = rng_for(game, f"recognise/{n.id}")
        if disguised(game):
            spotted = dice.d20(rng).natural + 2 >= int(game.renown.flags.get("disguise_dc", 10))
        else:
            spotted = rng.chance(law["recognise_chance"] + (0.25 if hated else 0.0))
        if spotted:
            game.say(f"<danger>{n.label().capitalize()} looks at you hard, and then again.</>", "danger")
            start_arrest(game, n)
            return


def arrest_options(game) -> list[tuple[str, str, bool, str]]:
    """(id, label, enabled, why not) for the arrest window."""
    a = game.arrest
    realm_id = a["realm"]
    bounty = game.renown.bounties.get(realm_id, 0)
    steps = sentence_for(game, realm_id)
    out = []
    if bounty > 0 or steps:
        payable = can_buy_off(game, realm_id)
        out.append(("pay", f"Pay what you owe ({money_text(bounty)})", payable and party_money(game) >= bounty,
                    "your crimes are too grave to buy off" if not payable else "you don't have enough"))
        out.append(("quiet", f"Go quietly (the law here: {sentence_text(steps)})", True, ""))
    else:
        out.append(("quiet", "Go with them and explain yourself", True, ""))
    cost = bribe_cost(game)
    out.append(("bribe", f"[Persuasion] Offer the guard {money_text(cost)} to look the other way",
                "bribe" not in a["tried"] and party_money(game) >= cost and a.get("guard", -1) >= 0,
                "you have tried that" if "bribe" in a["tried"] else "no one to bribe" if a.get("guard", -1) < 0
                else "you don't have enough"))
    out.append(("run", "[Athletics] Run for it", "run" not in a["tried"], "they have hold of you now"))
    out.append(("fight", "Fight the watch", True, ""))
    return out


def bribe_cost(game) -> int:
    law = game.tables.law
    bounty = game.renown.bounties.get(game.arrest["realm"], 0) if game.arrest else 0
    return max(int(law["bribe"]["minimum"]), int(bounty * float(law["bribe"]["share"])))


def bribe_guard(game) -> tuple[bool, str]:
    a = game.arrest
    a["tried"].append("bribe")
    w = game.world
    guard = w.npcs.get(a.get("guard", -1))
    cost = bribe_cost(game)
    sheet = game.sheet()
    rng = rng_for(game, "bribe")
    dc = int(game.tables.law["bribe"]["dc"]) + worst_severity(game, a["realm"]) * 2
    if guard is not None:
        dc += -4 if "greedy" in guard.traits else 4 if "honest" in guard.traits else 0
    roll = dice.d20(rng).natural + sheet.skill_bonus("persuasion")
    if roll >= dc:
        take_money(game, cost)
        if guard is not None:
            guard.flags["bribed_until"] = w.time + 24 * 60
            guard.purse += cost
        game.arrest = None
        return True, (f"<good>The coin vanishes.</> The guard finds something interesting to look at on the far side "
                      f"of the street. <dim>(Persuasion {roll} vs {dc})</> You are still wanted; other guards may not "
                      f"be so blind.")
    return False, (f"<warn>The guard knocks your hand aside.</> \"Try that again and it'll be the worse for you.\" "
                   f"<dim>(Persuasion {roll} vs {dc})</>")


def run_for_it(game) -> tuple[bool, str]:
    a = game.arrest
    a["tried"].append("run")
    sheet = game.sheet()
    skill = "athletics" if sheet.skill_bonus("athletics") >= sheet.skill_bonus("acrobatics") else "acrobatics"
    rng = rng_for(game, "run")
    roll = dice.d20(rng).natural + sheet.skill_bonus(skill)
    dc = int(game.tables.law["run_dc"]) + (2 if game.leader.exhaustion else 0)
    realm_id = a["realm"]
    if roll >= dc:
        game.arrest = None
        rec = commit_direct(game, "fleeing_arrest", realm_id)
        if game.in_local:
            game.leave_local()
        return True, (f"<good>You break away</> and run, and keep running until the shouting is far behind. "
                      f"<dim>({skill.capitalize()} {roll} vs {dc})</> " +
                      (f"Running has added to your record in {game.world.factions[realm_id].name}." if rec else ""))
    return False, f"<warn>They drag you down in the street.</> <dim>({skill.capitalize()} {roll} vs {dc})</>"


def commit_direct(game, cid: str, realm_id: int) -> dict | None:
    """A crime the watch saw for themselves (running, fighting them): straight onto the record."""
    realm = game.world.factions.get(realm_id)
    if realm is None:
        return None
    return commit(game, cid, witnesses=[], reported=True)


def fight_the_watch(game) -> str:
    """Resist: the guards nearby fight you (and killing them is murder)."""
    from realmwalker.game.fight import start_battle
    from realmwalker.game.people import npcs_in
    from realmwalker.rules.creatures import spawn

    a = game.arrest
    game.arrest = None
    w = game.world
    commit(game, "resisting_arrest", witnesses=[], reported=True)
    game.arrest = None
    s = w.settlements[a["settlement"]] if a.get("settlement", -1) >= 0 else None
    guards = []
    if s is not None:
        p = game.player
        guards = [n for n in npcs_in(w, s.id) if n.job == "guard" and n.alive and n.present]
        guards.sort(key=lambda n: max(abs(n.x - p.lx), abs(n.y - p.ly)))
        guards = guards[:3]
    rng = rng_for(game, "resist")
    creatures = []
    for n in guards:
        c = spawn(game.tables, n.stats, rng, 9000 + n.id)
        c.name = n.first_name
        c.named = True
        game.battle_npcs[c.uid] = n.id
        creatures.append(c)
    if not creatures:
        from realmwalker.game.encounters import make_encounter

        game.encounter = make_encounter(game, "town_watch", rng)
        return "The watch comes for you."
    start_battle(game, creatures, "Steel comes out. The watch means to take you, one way or another.", title="The watch")
    return "You fight."


# ---------------------------------------------------------------------------- sentences
def go_quietly(game) -> None:
    """Give yourself up: the sentence becomes a pending state the sentence window walks through."""
    a = game.arrest
    game.arrest = None
    realm_id = a["realm"]
    steps = sentence_for(game, realm_id)
    game.sentence = {"realm": realm_id, "settlement": a.get("settlement", -1), "steps": steps, "done": [],
                     "notes": [], "escaped": False}
    if not steps:
        game.sentence["notes"].append("The sergeant hears you out, shrugs, and lets you go. There is nothing "
                                      "against your name here.")
    game.dirty = True


def next_step(game) -> str | None:
    s = game.sentence
    if s is None:
        return None
    left = [st for st in s["steps"] if st not in s["done"]]
    return left[0] if left else None


def carry_out(game) -> list[str]:
    """Carry out the next step of the sentence. Returns what happened."""
    s = game.sentence
    step = next_step(game)
    if step is None:
        finish_sentence(game)
        return []
    s["done"].append(step)
    kind, _, n = step.partition(":")
    realm_id = s["realm"]
    notes: list[str] = []
    if kind == "fine":
        bounty = game.renown.bounties.get(realm_id, 0)
        paid = take_money(game, bounty)
        notes.append(f"They take {money_text(paid)} from you." if paid else "You have nothing for them to take.")
        owed = bounty - paid
        if owed > 0:
            days = max(1, owed // int(game.tables.law["fine_per_jail_day"]))
            notes.append(f"You still owe {money_text(owed)}: {days} days in jail instead.")
            s["steps"].insert(s["steps"].index(step) + 1, f"jail:{days}")
    elif kind == "flogging":
        notes += flog(game)
    elif kind == "branding":
        notes += brand(game, realm_id)
    elif kind in ("jail", "labour"):
        notes += serve(game, kind, int(n or 1), realm_id)
    elif kind == "death":
        notes += hang(game, realm_id)
    s["notes"] += notes
    if next_step(game) is None and game.over is None:
        finish_sentence(game)
    return notes


def finish_sentence(game) -> None:
    s = game.sentence
    if s is None:
        return
    if not s.get("escaped"):
        settle(game, s["realm"])
        back = return_confiscated(game, s["realm"])
        if back:
            s["notes"].append(back)
        realm = game.world.factions.get(s["realm"])
        if realm is not None and s["steps"]:
            s["notes"].append(f"Your debt to {realm.name} is paid.")
    s["finished"] = True


def flog(game) -> list[str]:
    from realmwalker.rules.wounds import Wound

    c = game.leader
    rng = rng_for(game, "flog")
    lashes = rng.randint(10, 30)
    for _ in range(2 if lashes < 20 else 3):
        c.wounds.append(Wound("torso", "cut", 1, bleed=1, created=game.world.time, note="the lash"))
    c.hp = max(1, c.hp - rng.randint(2, 6))
    game.renown.marks.append("flogged")
    return [f"They tie you to the post in the square and give you {lashes} lashes. People watch. Some of them laugh."]


def brand(game, realm_id: int) -> list[str]:
    from realmwalker.rules.wounds import Wound

    c = game.leader
    arm = "left_arm" if "lost_right_arm" in c.injuries else "right_arm"
    c.wounds.append(Wound(arm, "burn", 1, created=game.world.time, note="the brand"))
    realm = game.world.factions[realm_id]
    if "branded" not in game.renown.marks:
        game.renown.marks.append("branded")
        c.appearance = (c.appearance + " " if c.appearance else "") + f"A thief's brand scars the back of one hand."
    return [f"The iron hisses. {realm.name} has marked you for a criminal, and everyone who sees your hand will know it."]


def hang(game, realm_id: int) -> list[str]:
    game.sentence["gallows"] = True
    return ["The sentence is death. They take you to the cells to wait for the morning."]


def gallows_choice(game, escape: bool) -> list[str]:
    """The last night: try to get out, or face the rope."""
    s = game.sentence
    realm = game.world.factions[s["realm"]]
    if escape:
        ok, text = attempt_escape(game, int(game.tables.law["gallows_escape_dc"]))
        if ok:
            return [text]
        s["notes"].append(text)
    from realmwalker.game import survival

    c = game.leader
    c.death_cause = f"hanged by {realm.name}"
    c.hp = 0
    survival.check_death(game, c)
    s["finished"] = True
    return [f"In the grey morning they hang you in front of a crowd. {realm.name[:1].upper() + realm.name[1:]} "
            "has had its justice."]


def attempt_escape(game, dc: int) -> tuple[bool, str]:
    s = game.sentence
    sheet = game.sheet()
    skill = "sleight_of_hand" if sheet.skill_bonus("sleight_of_hand") >= sheet.skill_bonus("athletics") else "athletics"
    roll = dice.d20(rng_for(game, "escape")).natural + sheet.skill_bonus(skill)
    how = "work the lock with a bent nail" if skill == "sleight_of_hand" else "wrench a bar loose"
    realm_id = s["realm"]
    if roll >= dc:
        s["escaped"] = True
        s["finished"] = True
        commit(game, "jailbreak", witnesses=[], reported=True)
        game.arrest = None
        if game.in_local:
            game.leave_local()
        if game.renown.flags.get("confiscated") and s.get("settlement", -1) >= 0:
            game.say(f"Your belongings are still with the watch in {game.world.settlements[s['settlement']].name}; "
                     f"settle what you owe there to get them back.", "warn")
        return True, (f"<good>You {how} and slip out into the dark.</> <dim>({skill.replace('_', ' ')} {roll} vs {dc})"
                      f"</> By morning you are miles away, and wanted more than ever in "
                      f"{game.world.factions[realm_id].name}.")
    return False, f"<warn>You {how}, but the jailer hears.</> <dim>({skill.replace('_', ' ')} {roll} vs {dc})</>"


def serve(game, kind: str, days: int, realm_id: int) -> list[str]:
    """Days in the cells or at hard labour. Your gear is held until you are released."""
    confiscate(game, realm_id)
    game.confined = {"kind": kind}
    try:
        for _ in range(days):
            if kind == "labour":
                game.pass_time(10 * 60, "walk")
                game.pass_time(14 * 60, "sleep")
            else:
                game.pass_time(24 * 60, "rest")
            if game.over is not None:
                break
    finally:
        game.confined = None
    for c in game.party:
        c.dirt = min(100.0, c.dirt + 40)
    if game.over is not None:
        return [f"You do not live to see the end of your sentence."]
    what = "in a cell that stinks of the last man who had it" if kind == "jail" else "breaking stones on the lord's road"
    return [f"{days} days {what}. Bread and water, and time to think."]


def prison_rations(char) -> None:
    """The jailer's bread and water: enough to live on."""
    if char.hunger >= 45:
        char.hunger = max(20.0, char.hunger - 35)
    if char.thirst >= 35:
        char.thirst = max(10.0, char.thirst - 45)


# ---------------------------------------------------------------------------- confiscated gear
def confiscate(game, realm_id: int) -> None:
    held = game.renown.flags.get("confiscated")
    if held:
        return
    items = []
    money = 0
    for c in game.party:
        keep = {uid for slot, uid in c.equipped.items()
                if game.tables.items.get(c.item(uid).def_id).get("category") == "clothing"} if c.equipped else set()
        taken = [it for it in c.inventory if it.uid not in keep]
        c.inventory = [it for it in c.inventory if it.uid in keep]
        c.equipped = {slot: uid for slot, uid in c.equipped.items() if uid in keep}
        items += [it.to_dict() for it in taken]
        money += c.money
        c.money = 0
    s = game.sentence or {}
    game.renown.flags["confiscated"] = {"realm": realm_id, "settlement": s.get("settlement", -1), "items": items,
                                        "money": money}


def return_confiscated(game, realm_id: int) -> str:
    from realmwalker.rules.inventory import add_existing

    held = game.renown.flags.get("confiscated")
    if not held or held.get("realm") != realm_id:
        return ""
    banned = set(contraband_for(game, realm_id))
    c = game.leader
    lost = 0
    for d in held["items"]:
        it = Item.from_dict(d)
        if it.def_id in banned:
            lost += 1
            continue
        add_existing(c, game.tables.items, it)
    c.money += int(held.get("money", 0))
    del game.renown.flags["confiscated"]
    return "Your belongings are handed back" + (", less what the law forbids." if lost else ".")


def contraband_for(game, realm_id: int) -> list[str]:
    realm = game.world.factions.get(realm_id)
    if realm is None:
        return []
    return list(game.tables.law["contraband"].get(realm.culture, []))


# ---------------------------------------------------------------------------- other ways to break the law
def gate_search(game, settlement) -> list[str]:
    """Walled towns sometimes search travellers at the gate."""
    realm = fx.realm_of_settlement(game.world, settlement)
    if realm is None or not settlement.walled:
        return []
    rng = rng_for(game, f"gate/{settlement.id}")
    if not rng.chance(game.tables.law["gate_search_chance"]):
        return []
    banned = set(contraband_for(game, realm.id))

    def forbidden(it) -> bool:
        return it.def_id in banned or "contraband" in it.tags

    found = [it for c in game.party for it in list(c.inventory) if forbidden(it)]
    if not found:
        return ["The gate wardens go through your packs, find nothing they care about, and wave you in."]
    from realmwalker.rules.inventory import remove_item

    value = 0
    for c in game.party:
        for it in list(c.inventory):
            if forbidden(it):
                value += game.tables.items.get(it.def_id)["value"] * it.qty
                remove_item(c, it.uid, it.qty)
    names = ", ".join(sorted({game.tables.items.name(it) for it in found}))
    commit(game, "smuggling", value=value, witnesses=[], reported=True)
    if game.quests:
        from realmwalker.game import quests

        quests.on_goods_seized(game)
    return [f"<warn>The gate wardens search your packs and find {names}.</> That is forbidden here. They take it."]


def trespass_check(game, building_index: int) -> None:
    """Walking into someone's house or shop at night, while they are home."""
    from realmwalker.game.people import is_day, npcs_in

    lm = game.local
    s = settlement_here(game)
    if lm is None or s is None or is_day(game):
        return
    b = lm.buildings[building_index]
    if b.kind not in CONFINED_BUILDINGS:
        return
    key = f"{s.id}/{building_index}/{game.moment.total_days}"
    done = game.renown.flags.setdefault("trespass_seen", [])
    if key in done:
        return
    inside = [n for n in npcs_in(game.world, s.id) if n.alive and n.present and b.x <= n.x < b.x + b.w
              and b.y <= n.y < b.y + b.h]
    if not inside:
        return
    done.append(key)
    game.renown.flags["trespass_seen"] = done[-20:]
    game.say(f"<warn>{inside[0].label().capitalize()} wakes and sees you in their home.</>", "warn")
    commit(game, "trespass", victim=inside[0], witnesses=inside)


def poaching_check(game) -> None:
    """Hunting where the game belongs to the lord."""
    realm, s = jurisdiction(game)
    if realm is None:
        return
    rule = game.tables.law["hunting"].get(realm.culture, "free")
    if rule != "lords_only":
        return
    near = any(abs(t.x - game.player.x) + abs(t.y - game.player.y) <= 8 for t in game.world.settlements)
    if near and rng_for(game, "gamekeeper").chance(0.3):
        game.say("<warn>A gamekeeper's horn sounds somewhere behind you. You have been seen.</>", "warn")
        commit(game, "poaching", witnesses=[], reported=True)


def magic_check(game, caster) -> None:
    """Working magic where the law forbids it or wants a licence (and heresy, for priests of other gods)."""
    realm, s = jurisdiction(game)
    if realm is None or s is None or game.local is None:
        return
    laws = fx.laws_of(game.world, realm)
    witnesses = witnesses_here(game)
    if not witnesses:
        return
    divine = caster.cls == "cleric"
    faith = fx.faith_for_culture(game.tables, caster.culture)
    if divine and laws.get("religion") == "state_only" and faith != laws.get("faith"):
        commit(game, "heresy", witnesses=witnesses)
    elif not divine and laws.get("magic") == "forbidden":
        commit(game, "forbidden_magic", witnesses=witnesses)
    elif not divine and laws.get("magic") == "licensed" and realm.id not in game.renown.flags.get("licences", []):
        commit(game, "unlicensed_magic", witnesses=witnesses)


def buy_licence(game, realm_id: int) -> str:
    fee = int(game.tables.law["licence_fee"])
    if party_money(game) < fee:
        return f"A licence costs {money_text(fee)}, and you don't have it."
    take_money(game, fee)
    game.renown.flags.setdefault("licences", []).append(realm_id)
    return f"You pay {money_text(fee)} and get a sealed paper: you may work magic in {game.world.factions[realm_id].name}."


# ---------------------------------------------------------------------------- theft from a shop
def steal_from_shop(game, npc, item_id: str) -> tuple[bool, str]:
    """Palm something from a merchant's stock. Returns (got away with it, what happened)."""
    from realmwalker.game import economy
    from realmwalker.game.people import change_disposition
    from realmwalker.rules.inventory import add_item

    shop = economy.shop_state(game, npc)
    if shop["stock"].get(item_id, 0) <= 0:
        return False, "There are none left."
    sheet = game.sheet()
    rng = rng_for(game, f"steal/{npc.id}/{item_id}")
    roll = dice.d20(rng).natural + sheet.skill_bonus("sleight_of_hand")
    watch_dc = 11 + (3 if "suspicious" in npc.traits else 0) - (2 if "weary" in npc.traits else 0)
    value = int(game.tables.items.get(item_id)["value"])
    name = game.tables.items.get(item_id)["name"]
    if roll >= watch_dc:
        shop["stock"][item_id] -= 1
        if shop["stock"][item_id] <= 0:
            del shop["stock"][item_id]
        add_item(game.leader, game.tables.items, item_id, 1, made_at=game.world.time, tags=["stolen"])
        seen_by = [n for n in witnesses_here(game, exclude=[npc]) if dice.d20(rng).natural + 1 >= roll]
        text = f"<loot>The {name} goes into your sleeve.</> <dim>(Sleight of Hand {roll} vs {watch_dc})</>"
        if seen_by:
            text += f" <warn>But {seen_by[0].label()} saw.</>"
            commit(game, "theft", victim=npc, value=value, witnesses=seen_by)
        return True, text
    change_disposition(npc, -40)
    npc.remember("caught the traveller stealing")
    commit(game, "theft", victim=npc, value=value, witnesses=[npc] + witnesses_here(game, exclude=[npc]))
    return False, (f"<danger>\"Thief!\"</> {npc.first_name} grabs your wrist. <dim>(Sleight of Hand {roll} vs "
                   f"{watch_dc})</>")


def is_fence(game, npc) -> bool:
    """Members of the thieves' guild will buy stolen goods, from their own."""
    secret = npc.flags.get("secret")
    f = game.world.factions.get(secret) if secret is not None else None
    return f is not None and f.kind == "thieves_guild" and f.id in game.renown.members


# ---------------------------------------------------------------------------- disguise
def put_on_disguise(game, char) -> str:
    sheet = game.sheet(char)
    rng = rng_for(game, "disguise")
    bonus = sheet.skill_bonus("deception")
    if "disguise_kit" in char.tools:
        bonus += sheet.proficiency
    quality = dice.d20(rng).natural + bonus
    game.renown.flags["disguise_dc"] = quality
    char.effects["disguised"] = 12.0
    game.pass_time(20)
    word = "a stranger even to yourself" if quality >= 18 else "passable" if quality >= 12 else "not very convincing"
    return f"You paint, powder and pad yourself into someone else: {word}. <dim>(Disguise {quality}; it lasts half a day.)</>"
