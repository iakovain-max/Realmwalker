"""The AI side of townsfolk: what we tell the AI about a settlement or a person, and how its reply is
applied. Nothing here talks to the AI service itself (the screens submit the requests); this is just
facts in, validated words out. Everything has a built-in fallback, so the AI is never required.
"""

from __future__ import annotations

from realmwalker.core import textgen
from realmwalker.core.rng import RNG
from realmwalker.game.dialogue import DIFFICULTY_DC, OUTCOMES
from realmwalker.game.people import NPC, Town, npcs_in, pronouns
from realmwalker.rules.character import Sheet

KIND_WORDS = {"hamlet": "hamlet", "village": "village", "town": "market town", "city": "walled city", "hold": "dwarven hold",
              "elfhall": "elven hall"}


# ---------------------------------------------------------------------------- settlements
def settlement_variables(game, settlement, town: Town) -> dict:
    t = game.tables
    culture = t.names["cultures"].get(settlement.culture, {}).get("label", settlement.culture)
    area = game.world.area_at(settlement.x, settlement.y)
    people = []
    for npc in npcs_in(game.world, settlement.id):
        if not npc.notable:
            continue
        words = " and ".join(t.people["personality"][tr]["words"] for tr in npc.traits)
        who = "woman" if npc.sex == "female" else "man"
        race = t.races.get(npc.race, {}).get("name", npc.race).lower()
        people.append(f"- id {npc.id}: {npc.name}, the {npc.title}, a {race} {who} aged {npc.age}, {words}")
    inns = sum(1 for b in (game.world.local_maps.get(f"{settlement.x},{settlement.y}").buildings
                           if f"{settlement.x},{settlement.y}" in game.world.local_maps else []) if b.kind == "inn")
    return {
        "name": settlement.name, "kind": KIND_WORDS.get(settlement.kind, settlement.kind), "culture": culture,
        "population": settlement.population, "land": game.biome_def(settlement.x, settlement.y)["name"],
        "region": area.name if area else "the wilds", "season": game.moment.season, "inn_count": max(0, inns),
        "people": "\n".join(people) or "- (none)",
    }


def apply_settlement(game, settlement, town: Town, data: dict) -> int:
    """Put AI text in place wherever the player has not seen the built-in text yet. Returns people updated."""
    if data.get("description") and not town.seen:
        town.description = data["description"]
        town.description_source = "ai"
    lm = game.world.local_maps.get(f"{settlement.x},{settlement.y}")
    if lm is not None and data.get("inn_names"):
        inns = [i for i, b in enumerate(lm.buildings) if b.kind == "inn"]
        for bi, name in zip(inns, data["inn_names"]):
            if bi not in town.names_seen:
                town.names[bi] = name
    updated = 0
    ids = set(town.npcs)
    for entry in data.get("people", []):
        npc = game.world.npcs.get(int(entry["id"]))
        if npc is None or npc.id not in ids or not npc.notable or npc.profile_seen:
            continue
        for key in ("appearance", "personality", "backstory", "secret", "want"):
            if entry.get(key):
                npc.profile[key] = entry[key]
        if entry.get("speech"):
            npc.speech = entry["speech"]
        npc.profile_source = "ai"
        updated += 1
    return updated


def fallback_description(game, settlement, rng: RNG) -> str:
    tables = game.tables.fallback["settlement"]
    values = {"name": settlement.name, "kind": KIND_WORDS.get(settlement.kind, settlement.kind),
              "land": game.biome_def(settlement.x, settlement.y)["name"], "season": game.moment.season}
    return textgen.tidy(textgen.fill(rng.choice(tables["passage"]), rng, tables, values))


def fallback_inn_name(game, rng: RNG) -> str:
    tavern = game.tables.fallback["tavern"]
    names = game.tables.names["cultures"]
    family = rng.choice(next(iter(names.values()))["family"])
    return textgen.fill(rng.choice(tavern["name_pattern"]), rng, tavern, {"family": family})


# ---------------------------------------------------------------------------- conversations
OUTCOME_HELP = {
    "reveal_info": "they share a rumour or piece of local knowledge",
    "reveal_hook": "they tell of a dangerous place worth looking into",
    "disposition_up": "they like the traveller more",
    "disposition_down": "they like the traveller less",
    "reputation_up": "they will speak well of the traveller to others",
    "reputation_down": "they will speak ill of the traveller to others",
    "price_down": "they lower their prices for the traveller",
    "price_up": "they raise their prices for the traveller",
    "give_item": "they give the traveller something small they own",
    "agree": "they agree (nothing else changes)",
    "refuse": "they refuse (nothing else changes)",
    "fight": "they attack the traveller",
    "call_guards": "they shout for the watch",
    "flee": "they run away",
    "unlock_topic": "they mention a subject the traveller can ask about later (name it in 'topic')",
    "none": "nothing else happens",
}


def allowed_outcomes(game, npc: NPC) -> list[str]:
    occ = game.tables.people["occupations"].get(npc.job, {})
    out = list(OUTCOMES)
    if not occ.get("trade"):
        out = [o for o in out if o not in ("price_down", "price_up")]
    if not npc.inventory and npc.purse < 20:
        out.remove("give_item")
    if not any(n.job == "guard" and n.alive for n in npcs_in(game.world, npc.settlement)):
        out.remove("call_guards")
    return out


def dialogue_variables(game, npc: NPC) -> dict:
    t = game.tables
    s = game.world.settlements[npc.settlement]
    pron = pronouns(npc)
    race = t.races.get(npc.race, {}).get("name", npc.race).lower()
    words = " and ".join(t.people["personality"][tr]["words"] for tr in npc.traits)
    prof = npc.profile
    npc_text = (f"{npc.name}, the {npc.title} of {s.name}; a {race} {'woman' if npc.sex == 'female' else 'man'} of "
                f"{npc.age}; {words}; speaks in a {npc.speech} way. Looks: {prof.get('appearance', '')} "
                f"Background: {prof.get('backstory', '')} {pron['They']} secretly {prof.get('secret', 'has nothing to hide')}. "
                f"{pron['They']} want{'s'}: {prof.get('want', 'a quiet life')}.")
    w = game.weather
    from realmwalker.world.weather import KIND_WORDS as WEATHER

    situation = (f"{game.moment.part_of_day(game.latitude)} in {game.moment.season}, "
                 f"{WEATHER.get(w.kind, w.kind)}, {round(w.temp)}°C")
    c = game.leader
    sheet = Sheet(c, t)
    look = {-3: "in rags", -2: "in rags", -1: "shabbily dressed", 0: "plainly dressed", 1: "well dressed",
            2: "finely dressed", 3: "dressed like a lord"}[max(-3, min(3, sheet.social()))]
    state = []
    if any(w_.bleed and not w_.bandaged for w_ in c.wounds):
        state.append("bleeding")
    elif c.wounds:
        state.append("wounded")
    if c.dirt >= 60:
        state.append("filthy")
    weapon = c.equipped_item("main_hand")
    armed = f"carrying a {t.items.name(weapon, with_qty=False)}" if weapon else "unarmed"
    deeds = "; ".join(c.deeds[-3:]) or "nothing known"
    player = (f"{c.name.split()[0]}, a {t.races[c.race]['name'].lower()} {t.classes[c.cls]['name'].lower()}, {look}, "
              f"{armed}{', ' + ', '.join(state) if state else ''}. Known deeds: {deeds}.")
    offers = []
    occ = t.people["occupations"].get(npc.job, {})
    if occ.get("trade"):
        offers.append(f"goods to sell ({occ['trade']})")
    if npc.inventory:
        offers.append("these items: " + ", ".join(t.items.name(i) for i in npc.inventory[:4]))
    elif npc.purse >= 20:
        offers.append("a few coins")
    for svc in occ.get("services", []):
        offers.append(svc.replace("_", " "))
    allowed = allowed_outcomes(game, npc)
    from realmwalker.game.dialogue import SKILLS_ALLOWED

    return {
        "npc": npc_text, "place": f"{s.name}, a {KIND_WORDS.get(s.kind, s.kind)}", "situation": situation,
        "player": player, "memory": "; ".join(npc.memory[-5:]) or "nothing; they have not met",
        "mood": npc.mood(), "offers": ", ".join(offers) or "nothing but words",
        "skills": ", ".join(sorted(SKILLS_ALLOWED)),
        "outcomes": "\n".join(f"- {o}: {OUTCOME_HELP[o]}" for o in allowed),
    }


def apply_dialogue(conv, data: dict) -> int:
    """The AI's opening line and special options for a conversation. Returns how many options were kept."""
    game = conv.game
    npc = conv.npc
    allowed = set(allowed_outcomes(game, npc))
    if data.get("line") and not conv.greeted:
        conv.greeted = True
        conv.npc_says(f"<ai>{data['line'].replace('<', '(').replace('>', ')')}</>")
    options = []
    for opt in data.get("options", []) or []:
        if opt["difficulty"] not in DIFFICULTY_DC:
            continue
        text = opt["text"].strip()
        if text.startswith("["):
            text = text.split("]", 1)[-1].strip()
        skill_name = game.tables.rules["skills"][opt["skill"]]["name"]
        for part in ("success", "failure"):
            if opt[part]["outcome"] not in allowed:
                opt[part]["outcome"] = "none" if part == "success" else "refuse"
        options.append({"text": f"[{skill_name}] {text}", "skill": opt["skill"], "difficulty": opt["difficulty"],
                        "success": opt["success"], "failure": opt["failure"], "used": False, "source": "ai"})
    if options:
        conv.special = options
    npc.flags["ai_day"] = game.moment.total_days
    return len(options)
