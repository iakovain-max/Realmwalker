"""How much the game can say before it starts repeating itself.

These are floors, not targets: a player reads the same fight text hundreds of times in an evening and the same
greetings in every town, so the lists that feed them must not quietly shrink. If a change here fails, either put
the lines back or raise the game's variety somewhere else first."""

import pytest

FLOORS = {
    # combat_text.json — read more often than anything else in the game
    "combat_text:miss": 8, "combat_text:armored_miss": 5,
    "combat_text:ranged_miss": 6, "combat_text:spell_miss": 5, "combat_text:crit": 6,
    "combat_text:down": 5, "combat_text:dead": 4, "combat_text:flee": 4,
    "combat_text:surrender": 4, "combat_text:beg": 6,
    # dialogue.json — every town, every person
    "dialogue:rumour_intro": 8, "dialogue:flavour_rumours": 12, "dialogue:goodbye": 8,
    "dialogue:person_lines": 10, "dialogue:no_rumours": 5, "dialogue:refuse_talk": 2,
    "dialogue:closed": 2, "dialogue:who_are_you": 8, "dialogue:who_are_you_ruler": 5, "dialogue:tell_about_self": 8,
    "dialogue:remember_threat": 5, "dialogue:remember_help": 5, "dialogue:about_place": 4, "dialogue:danger_rumour": 5,
    "dialogue:threaten_success": 5, "dialogue:threaten_failure": 5, "dialogue:bribe_accept": 5, "dialogue:bribe_refuse": 5,
    # people.json — the life of a street
    "people:text.moments": 12, "people:text.moments_day": 8, "people:text.moments_night": 8,
    "people:text.moments_market": 5, "people:text.moments_plague": 5, "people:text.moments_famine": 5,
    "people:text.moments_raided": 5, "people:text.moments_siege": 5,
    # people.json — what a stranger learns when they ask
    "people:text.backstory_common": 12, "people:text.secret": 20, "people:text.want": 20,
    # camping.json — every night on the road
    "camping:night.any": 8, "camping:night.fire": 5,
    # companions.json — weeks of walking beside the same people
    "companions:lines.road": 20, "companions:lines.camp": 12, "companions:lines.approve": 8,
    "companions:lines.disapprove": 8, "companions:lines.battle": 8, "companions:lines.road_tired": 6,
    "companions:lines.road_wet": 6, "companions:lines.road_night": 6, "companions:lines.road_cold": 5,
    "companions:lines.road_hot": 4, "companions:lines.hired": 6, "companions:lines.complain": 6,
}


def get(data, path):
    node = data
    for key in path.split("."):
        node = node[key]
    return node


@pytest.mark.parametrize("where,least", sorted(FLOORS.items()))
def test_the_game_has_enough_ways_to_say_it(data, where, least):
    name, path = where.split(":")
    lines = get(data[f"{name}.json"], path)
    assert len(lines) >= least, f"{where} is down to {len(lines)} lines; a player would hear them all in an hour"


def test_every_kind_of_blow_and_wound_has_more_than_one_line(data):
    text = data["combat_text.json"]
    for kind, lines in text["hit"].items():
        assert len(lines) >= 3, f"hits of kind {kind} have only {len(lines)} lines"
    for kind, by_severity in text["wound"].items():
        for severity, lines in by_severity.items():
            assert len(lines) >= 2, f"{kind} wounds at {severity} have only {len(lines)} lines"


def test_a_town_can_greet_you_in_many_ways(data):
    greeting = data["dialogue.json"]["greeting"]
    for mood, lines in greeting.items():
        assert len(lines) >= 5, f"{mood} people have only {len(lines)} ways to say hello"
    trades = data["dialogue.json"]["greeting_job"]
    jobs = set(data["people.json"]["occupations"])
    missing = jobs - set(trades)
    assert not missing, f"these trades say nothing of their own: {sorted(missing)}"
    for job, lines in trades.items():
        assert len(lines) >= 2, f"{job} has only {len(lines)} greeting"


def test_the_world_reports_itself_in_more_than_one_way(data):
    """Two hundred and fifty years of history, and every siege told in the same two sentences, was too few."""
    for kind, lines in data["politics.json"]["text"].items():
        assert len(lines) >= 4, f"{kind} is written up only {len(lines)} ways"


def test_the_sky_turns_in_more_than_one_way(data):
    for kind, lines in data["fallback_text.json"]["weather_change"].items():
        assert len(lines) >= 4, f"{kind} weather is announced only {len(lines)} ways"


def test_every_land_sounds_like_itself_at_night(data):
    for land, lines in data["camping.json"]["night"].items():
        assert len(lines) >= 5, f"nights in {land} have only {len(lines)} sounds"


def test_every_band_can_find_you_three_ways(data):
    for group, spec in data["creatures.json"]["encounters"].items():
        assert len(spec["intro"]) >= 3, f"meeting {group} always reads the same"


def test_there_is_plenty_to_meet_on_the_road(data):
    assert len(data["travel_events.json"]["events"]) >= 20
    for name, event in data["travel_events.json"]["events"].items():
        assert len(event["intro"]) >= 3, f"{name} always begins the same way"
    assert len(data["quests.json"]["templates"]) >= 16
    assert len(data["quests.json"]["rewards_text"]) >= 4
    for template, words in data["quests.json"]["text"].items():
        assert len(words["pitch"]) >= 2, f"{template} is always asked for in the same words"


def test_every_kind_of_companion_has_a_voice_of_their_own(data):
    """What a companion cares about colours what they say on the road, at camp, and when they judge you."""
    comp = data["companions.json"]
    for value in comp["values"]:
        for kind in ("road", "camp", "approve", "disapprove"):
            assert len(comp["lines"].get(f"{kind}_{value}", [])) >= 2, f"a {value} companion has no {kind} lines"


def _pack(data, name):
    from realmwalker.world.tables import Tables

    return getattr(Tables(data), name)


def test_every_story_has_enough_ways_to_be_told(data):
    """docs/ADVENTURES.md §8.8: each beat >=3 intros; each blueprint >=3 titles and hooks, every chapter >=2 titles
    and >=3 reveals and openings; each villain temper >=6 first words and >=8 omens; each epilogue page kind >=4;
    epithets >=6 a tag; each weakness >=3 lore lines; each threat stage >=3 signs; a boss phase >=3 lines."""
    adventures, beats = _pack(data, "adventures"), _pack(data, "beats")
    villains, threats = _pack(data, "villains"), _pack(data, "threats")
    short = []
    for bid, beat in beats.items():
        if len(beat["text"][0]) < 3:
            short.append(f"beat {bid}: {len(beat['text'][0])} intros")
    for bid, bp in adventures.get("blueprints", {}).items():
        for k in ("title", "hook"):
            if len(bp[k]) < 3:
                short.append(f"blueprint {bid}: {len(bp[k])} {k}s")
        for ch in bp["chapters"]:
            if len(ch["title"]) < 2:
                short.append(f"{bid} chapter {ch['id']}: {len(ch['title'])} titles")
            for k in ("reveal", "opening"):
                if len(ch[k]) < 3:
                    short.append(f"{bid} chapter {ch['id']}: {len(ch[k])} {k}s")
        for e in bp.get("endings", []):
            for kind, lines in e.get("pages", {}).items():
                if len(lines) < 4:
                    short.append(f"{bid} ending {e['id']} page {kind}: {len(lines)} lines")
        for k, lines in bp["finale"].get("words", {}).items():
            if len(lines) < 3:
                short.append(f"{bid} finale {k}: {len(lines)} lines")
    for tag, lines in adventures.get("epithets", {}).items():
        if len(lines) < 6:
            short.append(f"epithets {tag}: {len(lines)}")
    for tid, temper in villains.get("tempers", {}).items():
        if len(temper.get("first_words", [])) < 6:
            short.append(f"temper {tid}: {len(temper.get('first_words', []))} first words")
        if len(temper.get("omens", [])) < 8:
            short.append(f"temper {tid}: {len(temper.get('omens', []))} omens")
    for kind, lst in villains.get("weaknesses", {}).items():
        for w in lst:
            if len(w.get("lore", [])) < 3:
                short.append(f"weakness {w['id']}: {len(w.get('lore', []))} lore lines")
    for bid, boss in villains.get("bosses", {}).items():
        phase = boss.get("phase")
        if phase and len(phase.get("lines", [])) < 3:
            short.append(f"boss {bid} phase: {len(phase['lines'])} lines")
    for kid, kind in threats.get("kinds", {}).items():
        for st in kind.get("stages", []):
            if len(st.get("signs", [])) < 3:
                short.append(f"threat {kid} stage {st['id']}: {len(st.get('signs', []))} signs")
    assert not short, "\n".join(short)


def test_every_situation_has_enough_ways_to_be_told(data):
    """docs/ADVENTURES.md §8.8 (C.10): every predicament (vignettes and an adventure's own too) has >=3 titles,
    stakes, pleas and first notes where it has them, >=3 lines for each ending and for its lapse, and >=3 ways of
    describing each obstacle; each scene's lines >=3 variants."""
    sits, scenes = _pack(data, "situations"), _pack(data, "scenes")
    short = []
    for pid, p in sits.get("predicaments", {}).items():
        if pid.startswith("_"):
            continue
        for k in ("title", "stakes", "plea", "first"):
            if k in p.get("words", {}) and len(p["words"][k]) < 3:
                short.append(f"{pid}: {len(p['words'][k])} {k}")
        for e in p.get("endings", []) + [dict(p.get("lapse") or {}, id="lapse")]:
            if len(e.get("line", [])) < 3:
                short.append(f"{pid} ending {e['id']}: {len(e.get('line', []))} lines")
        for ob in p.get("obstacles", []):
            if len(ob.get("note", [])) < 3:
                short.append(f"{pid} obstacle {ob['id']}: {len(ob.get('note', []))} notes")
    for sid, sc in scenes.items():
        if sid.startswith("_") or not isinstance(sc, dict):
            continue
        for k, lines in (sc.get("words") or {}).items():
            if isinstance(lines, list) and len(lines) < 3:
                short.append(f"scene {sid} {k}: {len(lines)} lines")
    assert not short, "\n".join(short)


def test_part_d_has_enough_ways_to_be_told(data):
    """Expansion 6 D.5: every line a Part D step says (recruit, rally, confront, escort, hold, rite, a captive's talk,
    an ambush, a band waiting) has >=3 ways in adventures.json "words", every letter a beat hands you >=3 hands of it,
    and each opening's beat >=3 intros (the first hour is read once a life, and many lives are lived)."""
    from realmwalker.game.story import deeds, opening

    adventures, beats = _pack(data, "adventures"), _pack(data, "beats")
    words = adventures.get("words", {})
    short = [f"words {k}: {len(words.get(k, []))}" for k in deeds.DEFAULT_WORDS if len(words.get(k, [])) < 3]

    def letters(node):
        if isinstance(node, list):
            if len(node) > 1 and node[0] == "letter":
                yield node[1]
            for x in node:
                yield from letters(x)
        elif isinstance(node, dict):
            for x in node.values():
                yield from letters(x)

    short += [f"letter {k}: {len(words.get(k, []))}" for k in set(letters(beats)) if len(words.get(k, [])) < 3]
    for kind in opening.KINDS:
        for bid in (opening.BEATS[kind], opening.TOLD.get(kind)):
            if bid is not None and len(beats[bid]["text"][0]) < 3:
                short.append(f"opening beat {bid}: {len(beats[bid]['text'][0])} intros")
    assert set(letters(beats)), "the Risen's letter and the outlaws' warning are beats' letters"
    assert not short, "\n".join(short)
