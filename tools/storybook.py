"""The storybook (docs/ADVENTURES.md §7, §9): what the game would tell, read without playing it.

Makes (or loads the cached) world, forges adventures on its threats and prints each as a synopsis: the premise, the
hook, the cast, the hidden truths, the threat's scheme, the chapters with their steps, the finale's keys, the endings
and the target. Each forging is undone before the next, so twenty synopses are twenty first forgings (the threats in
turn, each with its own adventure id and so its own seed).

`--check` fails (exit code 1) on: a role left unbound, a place that does not exist, a word left unfilled in any line
the tale can show (every variant of every beat, ending page, finale line, sign and lore it uses), a truth with fewer
than three routes, a chapter breaking the content rule (a step that is not a fight, a choice leaving a codeword), and
the six rules of a quest that matters (§5.15) as they apply to an adventure: (1) a person with a name and a stake
(the patron, bound); (2) a consequence to see later (every ending but the walking away changes the world); (3) a real
decision (a choice whose ways set different codewords); (4) a way through without a fight (every chapter); (5) a
thread outward (the villain is a figure of the history, the threat has its places at stake); (6) money only from
someone who would pay (no beat gives coin out of nothing).

    .venv/Scripts/python.exe tools/storybook.py --seed 77 --size medium --count 5
    .venv/Scripts/python.exe tools/storybook.py --seed 77 --check
"""

from __future__ import annotations

import argparse
import copy
import re
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from realmwalker.core import textgen  # noqa: E402
from realmwalker.game.state import new_game  # noqa: E402
from realmwalker.game.story import cast as castmod  # noqa: E402
from realmwalker.game.story import forge, places  # noqa: E402
from realmwalker.game.story import words as wordsmod  # noqa: E402
from realmwalker.game.story.steps import LEARN_ROUTES, STEPS  # noqa: E402
from realmwalker.world import threats  # noqa: E402
from realmwalker.world.generator import WorldOptions  # noqa: E402

SLOT = re.compile(r"\{[a-z_]+\}")
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]
WIDTH = 116


def load_tables():
    from tools.balance import load_tables as load

    return load()


def make_game(seed: int, size: str, tables, name: str | None = None):
    from tests.worlds import cached_world

    world = cached_world(WorldOptions(name or f"Storybook {seed}", seed, size), tables)
    game = new_game(world, tables)
    game.survival = False
    return game


def candidates(game, blueprint: str | None = None) -> list[dict]:
    out = []
    for t in sorted(threats.records(game.world).values(), key=lambda t: int(t["id"][1:])):
        if t["state"] == "ended" or t.get("adventure"):
            continue
        fits = forge.fitting(game, t)
        if fits and (blueprint is None or blueprint in fits):
            out.append(t)
    return out


def forge_once(game, t: dict, n: int) -> dict | None:
    """Forge adventure number n on a threat, then put the world back as it was (the record is returned)."""
    pol = game.world.politics
    keep = {k: copy.deepcopy(pol.get(k)) for k in ("story_sites", "story_people", "next_adventure", "adventures")}
    before = copy.deepcopy(t)
    pol["next_adventure"] = n
    try:
        adv = forge.make(game, t)
        return copy.deepcopy(adv) if adv else None
    finally:
        for k, v in keep.items():
            if v is None:
                pol.pop(k, None)
            else:
                pol[k] = v
        t.clear()
        t.update(before)


# ---------------------------------------------------------------------------- the synopsis
def _place(game, p: dict | None) -> str:
    if not p:
        return "?"
    w = game.world
    name = places.name(w, p) if places.exists(w, p) else f"(missing {p})"
    part = p.get("part")
    if part == "deepest":
        level = places.dungeon_level(w, p)
        return f"{name}, its deepest level ({level})"
    if part == "level":
        return f"{name}, level {p.get('level')}"
    if part:
        return f"{name} ({part})"
    return name


def _route(game, adv: dict, r: dict) -> str:
    how = r.get("how")
    if how == "talk":
        if r.get("role"):
            return f"ask the {r['role']} ({castmod.describe(game, {'cast': {'x': r.get('who')}}, 'x')})"
        return f"ask {castmod.describe(game, {'cast': {'x': r.get('who')}}, 'x')}"
    if how == "check":
        return f"{r.get('skill', 'a check')} at {_place(game, r.get('at'))}"
    if how == "divine":
        return "divination (Divination, Commune, Contact Other Plane)"
    return str(r)


def _step(game, adv: dict, st: dict) -> str:
    t, kind = st["target"], st["kind"]
    if kind == "go":
        text = f"go to {_place(game, t.get('place'))}"
    elif kind == "search":
        text = f"search {_place(game, t.get('place'))} ({t.get('skill')} {t.get('dc')})"
    elif kind == "witness":
        text = f"hear the {t.get('role')}"
    elif kind == "read":
        text = f"read {t.get('item')}"
    elif kind == "learn":
        text = f"learn the {t.get('truth')} (" + " | ".join(_route(game, adv, r) for r in t.get("routes", [])) + ")"
    elif kind == "prepare":
        names = [game.tables.items.get(i)["name"] if game.tables.items.get(i) else i for i in t.get("means", [])]
        text = "carry the means (" + " | ".join(names) + ")"
    elif kind == "choose":
        beat = game.tables.beats.get(st.get("beat", ""), {})
        flags = [op[1] for ch in beat.get("choices", []) for op in ch.get("ops", []) if op and op[0] == "flag"]
        text = "choose: " + " or ".join(flags) + " (codeword)"
    elif kind == "slay":
        text = f"defeat the {t.get('role')}" + (" (driving it off will do)" if t.get("fled_ok") else "")
    elif kind == "finale":
        fin = adv["finale"]
        text = f"FINALE {_place(game, t.get('place'))} ({fin['boss']}, template {fin['template']})"
    else:
        text = kind
    if st.get("optional"):
        text = f"[{text}]"
    if st.get("gives"):
        text += " -> " + ", ".join(st["gives"])
    return text


def synopsis(game, adv: dict) -> str:
    w = game.world
    t = threats.records(w)[adv["threat"]]
    words = wordsmod.for_adventure(game, adv)
    fig = threats.villain_figure(w, t)
    lines = []
    head = adv["title"].upper()
    tail = f"({adv['blueprint']}, tier {adv['tier']}, threat {t['id']}, adventure {adv['id']}, world seed " \
           f"{w.meta.seed})"
    lines.append(f"{head:<{max(len(head) + 2, WIDTH - len(tail))}}{tail}")

    def field(label: str, text: str) -> None:
        wrapped = textwrap.wrap(text, WIDTH - 10) or [""]
        lines.append(f"{label:<10}{wrapped[0]}")
        lines.extend(" " * 10 + more for more in wrapped[1:])

    who = words.get("villain", "?")
    if fig is not None:
        born = getattr(fig, "born", None)
        kills = len(getattr(fig, "kills", []) or [])
        who += f" (the {words.get('beast', 'beast')} of the history, born {born}, {kills} killed; figure {fig.id})"
    field("Premise", f"{adv['words']['premise']} Villain: {who}. Den: {_place(game, adv['places'].get('home'))}.")
    field("Hook", adv["words"]["hook"])
    for role in adv["cast"]:
        entry = adv["cast"][role]
        state = "to be chosen when the town fills" if castmod.pending(entry) else "bound"
        field(role.capitalize(), f"{castmod.describe(game, adv, role)} ({state})")
    hidden = []
    for name, h in adv.get("hidden", {}).items():
        wk = wordsmod.weakness(game, adv) if name == "weakness" else None
        if wk is not None:
            hidden.append(f"{name} = {wk['name']} (keys {', '.join(wk.get('keys', []))}; means "
                          f"{', '.join(wk.get('means', []))}; {len(adv.get('candidates', {}).get(name, []))} "
                          f"candidate(s))")
        else:
            hidden.append(f"{name} = {h}")
    field("Hidden", "; ".join(hidden) or "none")
    st_ids = t["scheme"]["stages"]
    now = int(t["scheme"].get("stage", -1))
    scheme = []
    for i, sid in enumerate(st_ids):
        mark = " (now)" if i == now else ""
        scheme.append(("DOOM " if i == len(st_ids) - 1 else "") + sid + mark)
    field("Scheme", " -> ".join(scheme) + f"   (state {t['state']})")
    places_line = "; ".join(f"{k} = {_place(game, p)}" for k, p in adv["places"].items())
    field("Places", places_line)
    for i, ch in enumerate(adv["chapters"]):
        label = f"{ROMAN[i] if i < len(ROMAN) else i + 1:<4}{ch['title']}"
        steps = "; ".join(_step(game, adv, st) for st in ch["steps"])
        wrapped = textwrap.wrap(steps, WIDTH - 22) or [""]
        if len(label) >= 22:
            lines.append(label)
            lines.extend(" " * 22 + more for more in wrapped)
        else:
            lines.append(f"{label:<22}{wrapped[0]}")
            lines.extend(" " * 22 + more for more in wrapped[1:])
        for more in textwrap.wrap(f"-> reveal: {ch['reveal']}", WIDTH - 22):
            lines.append(" " * 22 + more)
    keys = adv["finale"].get("keys", {})
    field("Keys", " | ".join(f"{k} -> {', '.join(v)}" for k, v in keys.items()) or "none")
    bp = game.tables.adventures["blueprints"][adv["blueprint"]]
    ends = []
    for e in bp.get("endings", []):
        cond = " and ".join(e.get("if", [])) or "otherwise"
        ends.append(f"{e['id']} ({cond})")
    field("Endings", " | ".join(ends))
    field("Target", f"tier {adv['tier']} = level {adv['target_level']}; epithets "
                    f"{', '.join(bp.get('epithets', []))}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------- the check
def _templates(game, adv: dict) -> list[tuple[str, str]]:
    """Every line the tale can show, as (where, template)."""
    tb = game.tables
    bp = tb.adventures["blueprints"][adv["blueprint"]]
    t = threats.records(game.world)[adv["threat"]]
    out: list[tuple[str, str]] = []
    beat_ids = {"story_hook"}
    for ch in bp["chapters"]:
        for st in ch["steps"]:
            if st.get("beat"):
                beat_ids.add(st["beat"])
    temper = tb.villains.get("tempers", {}).get(t["villain"].get("temper") or "", {})
    for move in temper.get("moves", {}):
        m = tb.villains.get("moves", {}).get(move, {})
        if m.get("beat"):
            beat_ids.add(m["beat"])
    for bid in sorted(beat_ids):
        beat = tb.beats.get(bid)
        if beat is None:
            out.append((f"beat {bid}", "{missing_beat}"))
            continue
        for line in beat.get("title", []):
            out.append((f"beat {bid} title", line))
        for pi, page in enumerate(beat["text"]):
            for line in page:
                out.append((f"beat {bid} page {pi + 1}", line))
        for ci, ch in enumerate(beat.get("choices", [])):
            for k in ("label", "result", "fail_result"):
                for line in ch.get(k, []):
                    out.append((f"beat {bid} choice {ci + 1} {k}", line))
    for e in bp.get("endings", []):
        for kind, lines in e.get("pages", {}).items():
            for line in lines:
                out.append((f"ending {e['id']} {kind}", line))
    for k, lines in bp["finale"].get("words", {}).items():
        for line in lines:
            out.append((f"finale {k}", line))
    for line in temper.get("first_words", []) + temper.get("omens", []):
        out.append(("temper", line))
    wk = wordsmod.weakness(game, adv)
    for line in (wk or {}).get("lore", []):
        out.append(("weakness lore", line))
    for family, lines in tb.adventures.get("words", {}).items():  # (witnesses' tales, the patron, nested tables)
        for line in lines:
            out.append((f"words {family}", line))
    for tag in bp.get("epithets", []):
        for line in tb.adventures.get("epithets", {}).get(tag, []):
            out.append((f"epithet {tag}", line))
    return out


def problems(game, adv: dict) -> list[str]:
    w, tb = game.world, game.tables
    bp = tb.adventures["blueprints"][adv["blueprint"]]
    t = threats.records(w)[adv["threat"]]
    out = []
    aid = f"{adv['id']} ({adv['title']})"
    for role in bp["cast"]:
        entry = adv["cast"].get(role)
        if not entry and ("chance" not in bp["cast"][role]):
            out.append(f"{aid}: the {role} is not bound")
        elif entry and not castmod.pending(entry) and castmod.person(w, entry) is None and "settlement" not in entry:
            out.append(f"{aid}: the {role} is bound to nobody who exists")
    for name, p in adv["places"].items():
        if not places.exists(w, p):
            out.append(f"{aid}: the place {name} does not exist")
    for ch in adv["chapters"]:
        for st in ch["steps"]:
            for k in ("place", "at"):
                p = st["target"].get(k)
                if isinstance(p, dict) and not places.exists(w, p):
                    out.append(f"{aid}: step {st['id']}'s {k} does not exist")
            if st["kind"] == "learn" and len(st["target"].get("routes", [])) < LEARN_ROUTES:
                out.append(f"{aid}: the truth of step {st['id']} has fewer than {LEARN_ROUTES} routes")
            if st["kind"] == "finale" and st["target"].get("level") not in w.politics.get("story_sites", {}) and \
                    st["target"].get("level"):
                pass  # (story_sites are undone with the forging; the forge test checks they are written)
        if all(STEPS[s["kind"]].fight for s in ch["steps"]):
            out.append(f"{aid}: chapter {ch['id']} is nothing but fights (the content rule)")
    words = wordsmod.for_adventure(game, adv)
    words.setdefault("hook", adv["words"]["hook"])
    words.setdefault("goal", adv["chapters"][0]["goal"])
    tables = tb.adventures.get("words", {})
    rng = w.rng.child("storybook")
    for field in ("title",):
        if SLOT.search(adv[field]):
            out.append(f"{aid}: an unfilled word in the {field}: {adv[field]}")
    for k, v in adv["words"].items():
        if SLOT.search(v):
            out.append(f"{aid}: an unfilled word in the {k}: {v}")
    for ch in adv["chapters"]:
        for k in ("title", "goal", "opening", "reveal"):
            if SLOT.search(ch[k]):
                out.append(f"{aid}: an unfilled word in chapter {ch['id']}'s {k}: {ch[k]}")
    for where, line in _templates(game, adv):
        text = textgen.fill(line, rng, tables, words)
        left = SLOT.findall(text)
        if left:
            out.append(f"{aid}: {where}: {', '.join(left)} left unfilled in \"{line[:60]}...\"")
    for i, sid in enumerate(t["scheme"]["stages"]):
        stage = threats.stages(tb, t)[i]
        tw = threats._words(w, t, rng)
        for line in stage.get("signs", []) + stage.get("flavour", []):
            left = SLOT.findall(textgen.fill(line, rng, {}, tw))
            if left:
                out.append(f"{aid}: sign of {sid}: {', '.join(left)} left unfilled")
    out += six_rules(game, adv, bp, t)
    return out


def _choice_flags(beat: dict) -> list[set]:
    flags = []
    for ch in beat.get("choices", []):
        got = set()
        for part in ("ops", "success", "failure"):
            got |= {op[1] for op in ch.get(part, []) if op and op[0] == "flag"}
        flags.append(got)
    return flags


def six_rules(game, adv: dict, bp: dict, t: dict) -> list[str]:
    """§5.15's six rules, as they apply to an adventure (situations meet them in full from Part C)."""
    w, tb = game.world, game.tables
    aid = f"{adv['id']} ({adv['title']})"
    out = []
    # 1. a person with a name and a stake: the one who asks (the patron) is bound
    patron = adv["cast"].get("patron")
    if not patron:
        out.append(f"{aid}: rule 1: nobody asks (no patron)")
    # 2. a consequence to see later: every ending but walking away changes the world
    for e in bp.get("endings", []):
        if e.get("if") and not e.get("ops"):
            out.append(f"{aid}: rule 2: the ending {e['id']} leaves nothing behind")
    # 3. a real decision: a choose step whose ways set different codewords
    decided = False
    for ch in adv["chapters"]:
        for st in ch["steps"]:
            if st["kind"] == "choose":
                fl = [f for f in _choice_flags(tb.beats.get(st.get("beat", ""), {})) if f]
                if len(fl) >= 2 and len({frozenset(f) for f in fl}) >= 2:
                    decided = True
    if not decided:
        out.append(f"{aid}: rule 3: no decision with two ways that end differently")
    # 4. a way through without a fight, in every chapter
    for ch in adv["chapters"]:
        if not any(not STEPS[s["kind"]].fight for s in ch["steps"]):
            out.append(f"{aid}: rule 4: chapter {ch['id']} has no way without a fight")
    # 5. a thread outward: the villain is of the history, and places are at stake
    if threats.villain_figure(w, t) is None and t["villain"].get("figure") is not None:
        out.append(f"{aid}: rule 5: the villain's figure is not in the history")
    if not t.get("stakes"):
        out.append(f"{aid}: rule 5: the threat has no settlement at stake")
    # 6. money only from someone who would pay: no beat hands out coin
    for ch in adv["chapters"]:
        for st in ch["steps"]:
            beat = tb.beats.get(st.get("beat", ""), {})
            for c in beat.get("choices", []):
                for part in ("ops", "success", "failure"):
                    for op in c.get(part, []):
                        if op and op[0] in ("money", "gold", "coin") and (len(op) < 2 or int(op[1]) > 0):
                            out.append(f"{aid}: rule 6: beat {st['beat']} gives coin out of nothing")
    return out


# ---------------------------------------------------------------------------- situations (Part C, §5.15-5.16, §7)
VISIBLE = {"npc_fate", "dead_kin", "away", "tie", "grave", "mark", "favour", "contact", "shop", "move", "law",
           "disposition", "standing", "item", "plant", "hand", "give_back", "lay_scar", "news", "step", "key", "tell"}
OUTWARD = {"favour", "contact", "tie", "thread", "step", "key", "standing", "law"}
OUTWARD_ROOTS = {"threat", "politics", "faction", "history", "adventure", "companion", "vignette", "land"}
OUTWARD_ROLES = {"band", "faction", "threat", "figure", "site"}
FIGHT_ONLY = {"assassinate", "clear_lair", "bounty"}  # (work done only by blood: a rescue or a retrieval may be crept)


def forge_situations(game, count: int) -> list[dict]:
    """Up to `count` situations forged from the towns' own roots, nearest towns first, round after round (each town
    peopled as the hero would find it; the rarity rules are the rarity measure's, not the storybook's)."""
    from realmwalker.game.people import prepare_town
    from realmwalker.game.story import situations

    w = game.world
    towns = sorted((s for s in w.settlements if s.population > 0 and s.kind in ("village", "town", "city")),
                   key=lambda s: (abs(s.x - game.player.x) + abs(s.y - game.player.y), s.id))[:24]
    out = []
    for _ in range(4):
        for s in towns:
            if len(out) >= count:
                return out
            prepare_town(game, s)
            sit = situations.make(game, s.id)
            if sit is not None:
                out.append(sit)
    return out


def _role_line(game, sit: dict, role: str) -> str:
    from realmwalker.game.story import situations

    rec = sit["roles"][role]
    full, _, title = situations._name(game, rec)
    w = game.world
    if rec.get("npc") is not None:
        n = w.npcs.get(rec["npc"])
        bits = [title] + ([rec["kin"]] if rec.get("kin") else []) + ([rec["tie"]] if rec.get("tie") else [])
        if n is not None:
            bits.append(f"{n.age}")
        return f"{full} ({', '.join(b for b in bits if b)})"
    if rec.get("band") is not None or rec.get("faction") is not None:
        return f"{rec.get('name', full)} ({rec.get('kind', 'band')}, faction {rec.get('faction')}, site {rec.get('site')})"
    return full


def _act_text(game, sit: dict, a: dict) -> str:
    from realmwalker.game.story import situations
    from realmwalker.rules.items import money_text

    label = situations._fill(game, sit, a.get("label") or a["id"], f"act/{a['id']}")
    extra = []
    if a.get("check"):
        extra.append(f"{a['check'][0].replace('_', ' ').title()} {a['check'][1]}")
    if a.get("price"):
        extra.append(money_text(situations._price(sit, a)))
    if a.get("needs"):
        extra.append("after " + ", ".join(a["needs"]))
    return f"{a['id']}: {label}" + (f" ({'; '.join(extra)})" if extra else "")


def situation_synopsis(game, sit: dict) -> str:
    """A situation as §7 prints it: predicament, turn, roles, stakes, meeting, obstacles and their ways, goals,
    endings, the lapse and the thread outward."""
    from realmwalker.game.story import situations

    w = game.world
    spec = situations.spec_of(game, sit)
    situations._write_words(game, sit)
    town = w.settlements[sit["town"]]
    root = sit["root"]
    where = f"root: {root.get('kind')} {root.get('key', '')}".strip()
    if sit.get("adventure"):
        where += f"; inside adventure {sit['adventure']}, step {sit.get('step')}"
    head = situations.title(game, sit).upper()
    tail = f"(situation {sit['id']}, {town.name}; {where})"
    lines = [f"{head:<{max(len(head) + 2, WIDTH - len(tail))}}{tail}"]

    def field(label: str, text: str) -> None:
        wrapped = textwrap.wrap(text, WIDTH - 13) or [""]
        lines.append(f"{label:<13}{wrapped[0]}")
        lines.extend(" " * 13 + more for more in wrapped[1:])

    turn = (sit.get("turn") or {}).get("id") or "none"
    field("Predicament", f"{spec.get('name', sit['predicament'])} ({sit['predicament']})      Turn  {turn}")
    for role in sit["roles"]:
        field("Roles" if role == next(iter(sit["roles"])) else "", f"{role:<11}{_role_line(game, sit, role)}")
    field("Stakes", f"{sit['words'].get('stakes', '')} (due day {sit['clock']['due']}, made day {sit['made']})")
    m = sit.get("meeting") or {}
    scene = ((situations.data(game).get("meetings") or {}).get(m.get("kind")) or {}).get("scene")
    field("Meeting", f"{m.get('kind')} (scene {scene})")
    field("Plea", sit["words"].get("plea", ""))
    for ob in sit["obstacles"]:
        note = situations._fill(game, sit, ob.get("note"), f"note/{ob['id']}")
        ways = [_act_text(game, sit, a) for a in ob.get("acts", [])]
        if ob.get("favour"):
            ways.append("a favour called in")
        if ob.get("spells"):
            ways.append("magic: " + ", ".join(ob["spells"]))
        field("Obstacle", f"{ob['kind']} ({ob.get('who', '-')}): {note} Ways: " + " | ".join(ways))
    acts = [_act_text(game, sit, a) + f" [with {a.get('who')}]" for a in spec.get("acts", [])]
    if acts:
        field("Acts", " | ".join(acts))
    if sit.get("quest") or spec.get("work"):
        field("Work", (spec.get("work") or {}).get("kind", "?"))
    field("Goals", "; ".join(f"{g['id']} = {g['test']}" for g in sit["goals"]))
    for e in spec.get("endings", []):
        ops = ", ".join(o[0] if len(o) < 2 else f"{o[0]} {o[1]}" for o in e.get("ops", []))
        line = situations._fill(game, sit, e.get("line"), f"end/{e['id']}")
        cond = f" if {' and '.join(e['if'])}" if e.get("if") else ""
        field("Endings" if e is spec["endings"][0] else "", f"{e['id']} ({e['tone']}{cond}): {line} [{ops}]")
    lapse = spec.get("lapse") or {}
    field("Lapse", f"{situations._fill(game, sit, lapse.get('line'), 'end/lapsed')} "
                   f"[{', '.join(o[0] for o in lapse.get('ops', []))}]")
    field("Connects", "; ".join(_threads(game, sit)) or "nothing outward")
    return "\n".join(lines)


def _all_ops(spec: dict) -> list[list]:
    acts = [a for ob in spec.get("obstacles", []) for a in ob.get("acts", [])] + spec.get("acts", [])
    out = [o for e in spec.get("endings", []) for o in e.get("ops", [])]
    out += [o for a in acts for o in a.get("then", [])] + [o for g in spec.get("goals", []) for o in g.get("then", [])]
    return out


def _leading_ops(spec: dict, e: dict) -> list[list]:
    """The ops of the acts that make an ending's goal true (the hermit thrown from the bridge is dead by the act)."""
    goal = next((g for g in spec.get("goals", []) if g["id"] == e.get("when")), None)
    flags = {goal["test"][1]} if goal and goal["test"][0] == "flag" else set()
    acts = [a for ob in spec.get("obstacles", []) for a in ob.get("acts", [])] + spec.get("acts", [])
    return [o for a in acts if any(x[:2] == ["flag", f] for x in a.get("then", []) for f in flags)
            for o in a.get("then", [])]


def _threads(game, sit: dict) -> list[str]:
    from realmwalker.game.story import situations

    spec = situations.spec_of(game, sit)
    out = []
    if sit.get("adventure"):
        out.append(f"adventure {sit['adventure']}")
    if sit.get("threat"):
        out.append(f"threat {sit['threat']}")
    if sit["root"].get("kind") in OUTWARD_ROOTS:
        out.append(f"root {sit['root']['kind']}")
    out += [f"{r} ({k})" for r, rec in sit["roles"].items() for k in OUTWARD_ROLES if rec.get(k) is not None][:3]
    ties = sorted({o[0] for o in _all_ops(spec) if o and o[0] in OUTWARD})
    if ties:
        out.append("a lasting tie: " + ", ".join(ties))
    if any(o and o[0] == "disposition" and int(o[2]) <= -20 for o in _all_ops(spec)):
        out.append("an enemy made")
    if spec.get("work"):
        out.append(f"work: {spec['work'].get('kind')}")
    return out


def situation_rules(game, sit: dict) -> list[str]:
    """§5.15's six rules for one situation: (1) a person with a name and a stake; (2) every ending leaves something
    to see later; (3) a real decision (two endings that end differently); (4) a way through without a fight; (5) a
    thread outward; (6) money only from someone who would pay, and never the whole of a reward."""
    from realmwalker.game.story import situations

    spec = situations.spec_of(game, sit)
    sid = f"{sit['id']} ({sit['predicament']}, {game.world.settlements[sit['town']].name})"
    out = []
    asker = situations.asker(game, sit)
    if asker is None or not asker.name or not sit["words"].get("stakes"):
        out.append(f"{sid}: rule 1: nobody with a name asks, or nothing is at stake")
    for e in spec.get("endings", []) + [dict(spec.get("lapse") or {}, id="lapse")]:
        if not any(o and o[0] in VISIBLE for o in e.get("ops", []) + _leading_ops(spec, e)):
            out.append(f"{sid}: rule 2: the ending {e.get('id')} leaves nothing to see later")
    ends = {(e.get("tone"), tuple(sorted(o[0] for o in e.get("ops", [])))) for e in spec.get("endings", [])}
    ends.add(((spec.get("lapse") or {}).get("tone"), tuple(sorted(o[0] for o in (spec.get("lapse") or {}).get("ops", [])))))
    if len(ends) < 2:
        out.append(f"{sid}: rule 3: no two endings end differently")
    acts = [a for ob in sit["obstacles"] for a in ob.get("acts", [])] + spec.get("acts", [])
    peaceful = [a for a in acts if a.get("way", "talk") != "fight"] + \
        [ob for ob in sit["obstacles"] if ob.get("favour") or ob.get("spells")]
    work = (spec.get("work") or {}).get("kind")
    if not peaceful and work in FIGHT_ONLY:
        out.append(f"{sid}: rule 4: no way through without a fight")
    if not _threads(game, sit):
        out.append(f"{sid}: rule 5: nothing connects it outward")
    for e in spec.get("endings", []):
        money = [o for o in e.get("ops", []) if o and o[0] == "money" and int(o[1]) > 0]
        if not money:
            continue
        if asker is None:
            out.append(f"{sid}: rule 6: the ending {e['id']} pays, and nobody of the town would pay it")
        if not any(o[0] in VISIBLE and o[0] not in ("money",) for o in e.get("ops", [])):
            out.append(f"{sid}: rule 6: the ending {e['id']} rewards with money alone")
    return out


def situation_words(game, sit: dict) -> list[str]:
    """Every line the situation can show, each variant filled: a slot left unfilled is a problem."""
    from realmwalker.game.story import situations

    spec = situations.spec_of(game, sit)
    values = situations._values(game, sit)
    tables = game.tables.adventures.get("words", {})
    rng = game.world.rng.child(f"storybook/{sit['id']}")
    lines = []
    for k, v in spec.get("words", {}).items():
        if k != "keep" and isinstance(v, list):
            lines += [(f"words.{k}", x) for x in v if isinstance(x, str)]
    for e in spec.get("endings", []) + [dict(spec.get("lapse") or {}, id="lapse")]:
        lines += [(f"ending {e.get('id')}", x) for x in e.get("line", [])]
    acts = [a for ob in sit["obstacles"] for a in ob.get("acts", [])] + spec.get("acts", [])
    for ob in sit["obstacles"]:
        lines += [(f"obstacle {ob['id']}", x) for x in ob.get("note", []) + ob.get("magic_note", [])]
    for a in acts:
        for k in ("label", "say", "fail_say", "note"):
            lines += [(f"act {a['id']} {k}", x) for x in a.get(k) or []]
    out = []
    for where, line in lines:
        left = SLOT.findall(textgen.fill(line, rng, tables, values))
        if left:
            out.append(f"{sit['id']} ({sit['predicament']}): {where}: {', '.join(left)} left unfilled in "
                       f"\"{line[:60]}...\"")
    return out


def run_situations(seed: int, size: str, count: int, check: bool, quiet: bool = False, tables=None,
                   name: str | None = None) -> tuple[list[dict], list[str]]:
    tables = tables or load_tables()
    game = make_game(seed, size, tables, name)
    sits = forge_situations(game, count)
    trouble = [] if sits else [f"seed {seed}: no situation could be forged"]
    for sit in sits:
        if not quiet:
            print(situation_synopsis(game, sit))
            print()
        if check:
            trouble += situation_rules(game, sit) + situation_words(game, sit)
    return sits, trouble


# ---------------------------------------------------------------------------- the command
def run(seed: int, size: str, count: int, blueprint: str | None, check: bool, quiet: bool = False,
        tables=None, name: str | None = None) -> tuple[list[dict], list[str]]:
    tables = tables or load_tables()
    game = make_game(seed, size, tables, name)
    found = candidates(game, blueprint)
    made, trouble = [], []
    if not found:
        trouble.append(f"seed {seed}: no threat here has a tale to forge")
        return made, trouble
    for i in range(count):
        t = found[i % len(found)]
        adv = forge_once(game, t, i)
        if adv is None:
            trouble.append(f"seed {seed}: no tale could be forged on {t['id']}")
            continue
        made.append(adv)
        if not quiet:
            print(synopsis(game, adv))
            print()
        if check:
            trouble += problems(game, adv)
    return made, trouble


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seed", type=int, default=77)
    ap.add_argument("--size", default="medium")
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--blueprint", default=None)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--name", default=None, help="the world's name (a test world's, to use its cache)")
    ap.add_argument("--situations", type=int, default=0, help="print (and --check) this many situations instead")
    a = ap.parse_args()
    if a.situations:
        _, trouble = run_situations(a.seed, a.size, a.situations, a.check, name=a.name)
    else:
        _, trouble = run(a.seed, a.size, a.count, a.blueprint, a.check, name=a.name)
    if a.check:
        for p in trouble:
            print("PROBLEM:", p)
        print(f"storybook --check: {len(trouble)} problem(s)")
        return 1 if trouble else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
