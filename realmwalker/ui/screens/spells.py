"""The Spells screen (S): what a caster knows, what they have prepared, what they can still cast today, and what each
one does. p prepares the chosen spell or puts it aside (2024: the list changes after a long rest or a new level, one
spell after a short rest for a wizard's Memorize Spell; an empty place may be filled at any time). A spell that works
outside a fight (one that lasts, like Mage Armour, or one that heals) can be cast from here: pick it, pick who it is
for, Enter. Spells a wand, a staff or a rod can cast outside a fight are listed last (Expansion 5 Part D): Enter
spends its charges, l pours more in for a higher level."""

from __future__ import annotations

from realmwalker.game import magic
from realmwalker.rules import spells as sp
from realmwalker.ui import colors, markup
from realmwalker.ui.input import KeyEvent
from realmwalker.ui.screens.base import Screen
from realmwalker.ui.widgets import Canvas

SCHOOLS = {"evocation": "Evocation", "abjuration": "Abjuration", "conjuration": "Conjuration",
           "divination": "Divination", "enchantment": "Enchantment", "illusion": "Illusion",
           "necromancy": "Necromancy", "transmutation": "Transmutation"}


def caster_summary(game, char) -> list[str]:
    t = game.tables
    sheet = game.sheet(char)
    total = sp.slots_total(char, t)
    left = sp.slots_left(char, t)
    lines = [f"<title>{markup.escape(char.name)}</>",
             f"<dim>{t.classes[char.cls]['name']} {char.level}</>", ""]
    if not sp.is_caster(char, t):
        lines.append("<dim>No magic. Some people are lucky like that.</>")
        return lines
    lines.append(f"<dim>Spell attack</> {sp.attack_bonus(sheet, t):+d}   <dim>Save DC</> {sp.save_dc(sheet, t)}")
    if total:
        slots = "  ".join(f"<info>L{i + 1}</> {left[i]}/{total[i]}" for i in range(len(total)) if total[i])
        lines.append(f"<dim>Slots left today:</> {slots}")
        lines.append("<dim>Slots come back with a long rest (camp, r).</>")
    else:
        lines.append("<dim>No spell slots yet: cantrips only.</>")
    if char.cls == "wizard":
        book = [s for s in char.spells.get("spellbook", []) if s in t.spells]
        lines.append(f"<dim>Spellbook:</> {len(book)} spells. Copy more from scrolls (Enter on a scroll in the pack).")
    count = sp.prepared_count(char, t)
    if count:
        mine, always = sp.prepared(char, t), sp.always_prepared(char, t)
        lines.append(f"<dim>Prepared:</> {len(mine)} of {count}" + (f" <dim>and {len(always)} always prepared</>"
                                                                   if always else ""))
        how = sp.preparing_open(char)
        lines.append("<dim>" + {"prepare": "Rested: change them freely (p) until the next fight.",
                                "memorize": "Memorize Spell: one may be swapped (p) until the next fight."}.get(
            how, "They change after a long rest" + (", one after a short rest" if "memorize_spell" in char.features
                                                     else "") + ".") + "</>")
    lines.append("")
    return lines


def prepared_words(game, char, sid: str) -> str:
    """Whether the chosen spell is prepared, and what p would do."""
    t = game.tables
    if t.spells[sid]["level"] == 0 or not sp.prepared_count(char, t):
        return ""
    if sid in sp.always_prepared(char, t):
        return "<good>Always prepared</> <dim>(beyond the count).</>"
    if sid in sp.prepared(char, t):
        why = sp.unprepare_problem(char, t, sid)
        return "<good>Prepared.</> <dim>" + (f"{why[:1].upper() + why[1:]}." if why else "p puts it aside.") + "</>"
    why = sp.prepare_problem(char, t, sid)
    adept = " A ritual: read from the book without preparing it." if sid in sp.ritual_spells(char, t) else ""
    if why and why != "not a spell you can prepare yet":
        return f"<warn>Not prepared:</> <dim>{why}.{adept}</>"
    return "<warn>Not prepared.</> <dim>" + ("p prepares it." if not why else why[:1].upper() + why[1:] + ".") \
        + adept + "</>"


def working_now(game) -> list[str]:
    """The lasting spells on anyone in the party, and how long each has left; the wards on the camp; the fallen the
    party carries."""
    from realmwalker.game import revival, spellwork

    out = []
    from realmwalker.game import shapeshift

    for c in game.party:
        for sid, hours in sp.lasting(c, game.tables).items():
            out.append(f"<magic>{markup.escape(game.tables.spells[sid]['name'])}</> on {markup.escape(c.name.split()[0])}"
                       f" <dim>({magic.lasting_text(hours)} left)</>")
        shaped = shapeshift.words(game, c)  # (Animal Shapes, Shapechange: Expansion 3 F.8)
        if shaped:
            out.append(f"{markup.escape(c.name.split()[0])} as {shaped}")
    for ward, rec in spellwork.wards_here(game).items():
        left = max(0.0, (float(rec["until"]) - game.world.time) / 60)
        when = "waiting" if ward in WAITING else f"{magic.lasting_text(left)} left"
        out.append(f"<magic>{WARD_NAMES.get(ward, ward)}</> over the camp <dim>({when})</>")
    from realmwalker.game import warding

    holy = warding.hallowed_at(game)
    if holy is not None:
        out.append(f"<magic>Hallowed ground</> here <dim>({markup.escape(warding.HALLOW_EXTRAS[holy['extra']])})</>")
    if game.renown.flags.get("glyph_room"):
        out.append("<magic>A glyph</> on the door of your room at the inn <dim>(waiting)</>")
    kept = warding.demiplane_things(game)
    coin = int((game.renown.flags.get("demiplane") or {}).get("money", 0))
    if kept or coin:
        out.append(f"<magic>Your demiplane</> holds {len(kept)} thing{'s' if len(kept) != 1 else ''}"
                   + (" and coin" if coin else ""))
    from realmwalker.game import waymagic

    for c in game.party:
        home = waymagic.sanctuary(game, c)
        if home is not None:
            out.append(f"<magic>Sanctuary</> of {markup.escape(c.name.split()[0])}: the temple of "
                       f"{markup.escape(home.name)} <dim>(Word of Recall)</>")
    from realmwalker.game import greatmagic

    for c in game.party:  # (Part E.7: a spell waiting on someone, a soul in its gem)
        words = greatmagic.contingency_words(game, c)
        if words:
            out.append(f"<magic>Contingency:</> {words}")
        if greatmagic.in_jar(c):
            out.append(f"<magic>{markup.escape(c.name.split()[0])}'s soul</> is in the gem of a Magic Jar "
                       "<dim>(Magic Jar again: go home)</>")
    for rec in greatmagic.clones(game):
        s = game.world.settlements[rec["settlement"]] if 0 <= int(rec.get("settlement", -1)) < len(
            game.world.settlements) else None
        days = (float(rec["ready"]) - game.world.time) / (24 * 60)
        out.append(f"<magic>A clone of {markup.escape(rec['who'].split()[0])}</> in the crypt of "
                   f"{markup.escape(s.name) if s else 'a temple'} "
                   + (f"<dim>(grown in {max(1, round(days))} days)</>" if days > 0 else "<good>(grown)</>"))
    for b in revival.bodies(game):
        out.append(f"<danger>{markup.escape(b['char'].name.split()[0])}</> lies dead "
                   f"<dim>({revival.when_text(revival.dead_for(game, b))}"
                   + ("; kept from decay" if float(b.get("repose", 0)) > game.world.time else "") + ")</>")
    return out


WARD_NAMES = {"alarm": "Alarm", "hut": "Tiny Hut", "hound": "Faithful Hound", "rope": "Rope Trick",
              "mansion": "Magnificent Mansion", "meld": "Meld into Stone", "decoy": "Programmed Illusion",
              "mouth": "Magic Mouth", "veil": "An illusion of the land", "earthworks": "Move Earth's ditch and bank",
              "glyph": "Glyph of Warding", "symbol": "Symbol", "guards": "Guards and Wards", "forbiddance": "Forbiddance",
              "circle": "Magic Circle", "sanctum": "Private Sanctum", "demiplane": "The demiplane's door"}
WAITING = ("glyph", "symbol")  # (set off by what comes, not timed)


def spell_detail(game, char, sid: str, target, slot: int | None = None) -> list[str]:
    """What the chosen spell is, and whether it can be cast here and now (`slot`: a higher slot chosen with l)."""
    t = game.tables
    spell = t.spells[sid]
    school = SCHOOLS.get(spell.get("school", ""), "").lower()
    level = "Cantrip" if spell["level"] == 0 else f"Level {spell['level']}"
    bits = sp.summary(spell)
    lines = [f"<magic>{markup.escape(spell['name'])}</> <dim>{level}{', ' + school if school else ''}"
             + (f" · {', '.join(bits)}" if bits else "") + "</>",
             markup.escape(spell.get("text", ""))]
    prep = prepared_words(game, char, sid)
    if prep:
        lines.append(prep)
    levels = sp.slot_choices(char, t, sid)
    if sp.upcasts(spell) and len(levels) > 1 and not sp.free_cast(char, t, sid):
        level_now = slot if slot in levels else levels[0]
        gain = sp.up_gain(spell, level_now - spell["level"])
        lines.append(f"<magic>Slot:</> level {level_now}" + (f" <good>{', '.join(gain)}</>" if gain else "")
                     + " <dim>(l: another level)</>")
    if sid in (char.spells or {}).get("mastery", ()) and "spell_mastery" in char.features:
        lines.append("<good>Spell Mastery:</> <dim>cast at its own level without a slot, as often as you like.</>")
    elif sid in (char.spells or {}).get("signature", ()) and "signature_spells" in char.features:
        ready = sp.free_cast(char, t, sid)
        lines.append("<good>Signature spell:</> <dim>once without a slot, back with a short or long rest"
                     + (" (ready)." if ready else " (used).") + "</>")
    elif sid in sp.SPELL_BREAKER and "spell_breaker" in char.features:
        lines.append("<good>Spell Breaker:</> <dim>a reaction when a foe casts nearby.</>")
    ok, why = sp.can_cast(char, t, sid)
    if not ok and not (getattr(target, "data", None) or {}).get("free"):  # (a free choice is no casting: F.8)
        lines.append(f"<warn>{markup.escape(why[:1].upper() + why[1:])}.</>")
    problem = magic.road_problem(game, char, sid, target)
    if problem is None:
        whom = ""
        if t.spells[sid]["target"] == "place" and target is not char:
            from realmwalker.game import waymagic

            whom = f" to {markup.escape(target.name)}"
            if target.kind == "town" and sp.op(spell, "road").get("how") == "teleport":
                lines.append(f"<dim>{markup.escape(target.name)}: {waymagic.FAMILIARITY[target.known]} (←→ another place).</>")
        elif magic.road_targets(game, char, sid):
            from realmwalker.game.divining import Subject

            if isinstance(target, Subject):  # (Part E.3: what is sought, asked about or reached)
                whom = f" ({markup.escape(target.name)}; ←→ another)"
            else:
                whom = " on yourself" if target is char else f" on {markup.escape(target.name.split()[0])}"
        use = sp.road_use(t, sid)
        if use == "identify":
            thing = game.tables.items.name(magic.strange_things(game, char)[0], False)
            lines.append(f"<good>Enter casts it over the {markup.escape(thing)} now.</> <dim>It takes ten minutes.</>")
        elif use in ("heal", "cure"):
            lines.append(f"<good>Enter casts it{whom} now.</> <dim>It takes a minute.</>")
        elif use == "revive" or use in sp.ROAD_USES:
            from realmwalker.game import spellwork

            took = spellwork.minutes(spell)
            took_words = "an hour" if took == 60 else (f"{took // 60} hours" if took >= 120 and took % 60 == 0
                                                       else f"{took} minutes" if took > 1 else "a minute")
            lines.append(f"<good>Enter casts it{whom} now.</> <dim>It takes {took_words}"
                         + (" (ten more as a ritual, without a slot)." if spell.get("ritual") else ".") + "</>")
        else:
            hours = int(spell.get("rounds", 0)) / sp.ROUNDS_PER_HOUR
            lines.append(f"<good>Enter casts it{whom} now.</> <dim>It takes a minute and lasts "
                         f"{magic.lasting_text(hours)}, into any fight on the way.</>")
    elif problem != why:
        lines.append(f"<dim>{markup.escape(problem[:1].upper() + problem[1:])}.</>")
    return lines


def item_spell(game, char, value):
    """(item, property) of a spell listed from a wand, a staff or a rod ("charge:<uid>:<spell>"), or None."""
    if not str(value).startswith("charge:"):
        return None
    _, uid, sid = str(value).split(":", 2)
    return next(((it, pr) for it, pr in magic.item_spells(game, char) if it.uid == int(uid) and pr["spell"] == sid),
                None)


def spell_of(value) -> str:
    return str(value).split(":", 2)[2] if str(value).startswith(("charge:", "hat:")) else value


def hat_detail(game, char, value, target) -> list[str]:
    """A spell a wizard's hat could bring out: the check it asks, what a failure costs, and whether it can be tried."""
    from realmwalker.rules import hats

    t = game.tables
    _, uid, sid = str(value).split(":", 2)
    it = char.item(int(uid))
    if it is None:
        return []
    spell = t.spells[sid]
    title = markup.escape(it.magic.get("title") or "hat")
    lvl = "a cantrip" if spell["level"] == 0 else f"level {spell['level']}: a slot of that level"
    lines = [f"<magic>{markup.escape(spell['name'])}</> <dim>out of the {title}</>",
             markup.escape(spell.get("text", "")),
             f"<dim>A spell you do not know ({lvl}); Intelligence (Arcana) DC {hats.dc(t, sid, it)}. "
             + ("A failure spends the slot and brings something else out of the hat." if hats.many(it) else
                "Tried or not, the hat rests until a long rest.") + "</>"]
    problem = magic.hat_problem(game, char, value, target)
    lines.append("<good>Enter reaches into the hat.</>" if problem is None else
                 f"<dim>{markup.escape(problem[:1].upper() + problem[1:])}.</>")
    return lines


def item_detail(game, char, value, target, slot: int | None = None) -> list[str]:
    """What a spell drawn from a magic thing is, what it costs of the thing's charges, and whether it can be cast."""
    from realmwalker.rules import magic as magicrules

    t = game.tables
    held = item_spell(game, char, value)
    if held is None:
        return []
    it, prop = held
    sid = spell_of(value)
    spell = t.spells[sid]
    store = magicrules.pool(it) or {}
    title = markup.escape(it.magic.get("title") or t.items.name(it, False))
    levels = magicrules.charge_levels(it, prop, int(spell["level"]))
    level = slot if slot in levels else levels[0]
    cost = magicrules.charge_cost(prop, level)
    lines = [f"<magic>{markup.escape(spell['name'])}</> <dim>from the {title}</>", markup.escape(spell.get("text", "")),
             "<dim>" + ("At will." if magicrules.pooled(prop) and cost <= 0 else
                        f"{cost} charge{'s' if cost != 1 else ''} of {store.get('left', 0)} left" if store else
                        f"{magicrules.charges_left(prop, it)} left") + (f", at level {level}" if level > spell["level"]
                                                                        else "") + "</>"]
    if len(levels) > 1:
        gain = sp.up_gain(spell, level - spell["level"]) if level > spell["level"] else []
        lines.append("<magic>Charges:</> " + (f"<good>{', '.join(gain)}</>" if gain else "its own level")
                     + " <dim>(l: more or fewer)</>")
    problem = magic.road_problem(game, char, sid, target, charge=held)
    if problem is None:
        whom = ""
        if magic.road_targets(game, char, sid):
            whom = " on yourself" if target is char else f" on {markup.escape(getattr(target, 'name', '').split()[0])}" \
                if getattr(target, "name", "") else ""
        lines.append(f"<good>Enter casts it{whom} now.</>")
    else:
        lines.append(f"<dim>{markup.escape(problem[:1].upper() + problem[1:])}.</>")
    return lines


class SpellsScreen(Screen):
    title = "Spells"
    sound_open = "ui_page"

    def __init__(self, app, game, index: int = 0) -> None:
        super().__init__(app)
        self.game = game
        self.index = index
        self.sel = 0
        self.offset = 0
        self.target = 0
        self.slot: int | None = None  # a higher slot chosen with l (None: the lowest)
        self.message = ""

    @property
    def char(self):
        self.index = max(0, min(self.index, len(self.game.party) - 1))
        return self.game.party[self.index]

    def spells(self) -> list[str]:
        t = self.game.tables
        from realmwalker.rules import feats

        c = self.char
        known = list(dict.fromkeys(sp.known_spells(c, t) + sp.preparable(c, t) + sp.ritual_spells(c, t)
                                   + feats.ritual_spells(c, t)))
        things = [f"charge:{it.uid}:{pr['spell']}" for it, pr in magic.item_spells(self.game, c)]
        from realmwalker.rules import hats

        hat = [f"hat:{it.uid}:{s}" for it, _p in hats.worn(c) for s in hats.spells(c, t, it, battle=False)]
        return sorted(known, key=lambda s: (t.spells[s]["level"], t.spells[s]["name"])) + \
            sorted(dict.fromkeys(things), key=lambda v: t.spells[spell_of(v)]["name"]) + hat

    def current(self) -> str | None:
        spells = self.spells()
        if not spells:
            return None
        self.sel = max(0, min(self.sel, len(spells) - 1))
        return spells[self.sel]

    def targets(self) -> list:
        sid = self.current()
        return magic.road_targets(self.game, self.char, spell_of(sid)) if sid else []

    def chosen_target(self):
        targets = self.targets()
        if not targets:
            return self.char
        if self.char in targets and self.target == 0:
            self.target = targets.index(self.char)  # yourself first
        self.target %= len(targets)
        return targets[self.target]

    # ------------------------------------------------------------------ actions
    def cast(self) -> None:
        sid = self.current()
        if sid is None:
            return
        if sid.startswith("hat:"):  # (a wizard's hat: a spell not known, on a check)
            lines = magic.cast_from_hat(self.game, self.char, sid, self.chosen_target())
            for text in lines:
                self.game.say(text, "magic")
            self.message = " ".join(lines)
            return
        held = item_spell(self.game, self.char, sid)
        if held is not None:  # (a wand's, a staff's or a rod's spell: its charges)
            lines = magic.cast_on_road(self.game, self.char, spell_of(sid), self.chosen_target(), self.slot,
                                       charge=held)
            for text in lines:
                self.game.say(text, "magic")
            self.message = " ".join(lines)
            return
        lines = magic.cast_on_road(self.game, self.char, sid, self.chosen_target(), self.slot)
        for text in lines:
            self.game.say(text, "magic")
        self.message = " ".join(lines)

    def next_slot(self) -> None:
        """l: the next slot level the chosen spell could be cast with (a higher one does more)."""
        sid = self.current()
        t = self.game.tables
        if sid is None or sid.startswith("hat:"):
            return
        held = item_spell(self.game, self.char, sid)
        if held is not None:  # (more charges, a higher level)
            from realmwalker.rules import magic as magicrules

            levels = magicrules.charge_levels(held[0], held[1], int(t.spells[spell_of(sid)]["level"]))
            now = self.slot if self.slot in levels else levels[0]
            self.slot = levels[(levels.index(now) + 1) % len(levels)] if len(levels) > 1 else None
            if len(levels) < 2:
                self.message = "It takes no more charges than that."
            return
        levels = sp.slot_choices(self.char, t, sid)
        if not sp.upcasts(t.spells[sid]) or len(levels) < 2:
            self.message = f"{t.spells[sid]['name']} gains nothing from a higher slot." if levels else ""
            self.slot = None
            return
        now = self.slot if self.slot in levels else levels[0]
        self.slot = levels[(levels.index(now) + 1) % len(levels)]

    def prepare(self) -> None:
        """Prepare the chosen spell, or put it aside."""
        sid = self.current()
        t = self.game.tables
        if sid is None or sid.startswith(("charge:", "hat:")) or t.spells[sid]["level"] == 0 \
                or not sp.prepared_count(self.char, t):
            return
        if self.game.battle is not None:
            self.message = "Not in the middle of a fight."
            return
        self.message = sp.toggle_prepared(self.char, t, sid)
        self.game.dirty = True

    def scribe(self) -> None:
        """Write the chosen spell out as a scroll (ink and quill, parchment, inks and a slot)."""
        sid = self.current()
        if sid is None or sid.startswith(("charge:", "hat:")):
            return
        lines = magic.scribe(self.game, self.char, sid)
        for text in lines:
            self.game.say(text, "magic")
        self.message = " ".join(lines)

    def store(self) -> None:
        """r: cast the chosen spell into a Ring of Spell Storing someone in the party wears (game/wonders.py)."""
        sid = self.current()
        if sid is None or sid.startswith(("charge:", "hat:")):
            return
        from realmwalker.game import wonders

        lines = wonders.store(self.game, self.char, sid, self.slot)
        for text in lines:
            self.game.say(text, "magic")
        self.message = " ".join(lines)

    def next_member(self) -> None:
        self.index = (self.index + 1) % max(1, len(self.game.party))
        self.sel = self.offset = self.target = 0
        self.message = ""

    def handle_key(self, ev: KeyEvent) -> bool:
        n = len(self.spells())
        if ev.key in ("escape", "S"):
            self.close()
        elif ev.key == "tab":
            self.next_member()
        elif ev.key == "up":
            self.sel = max(0, self.sel - 1)
            self.slot = None
        elif ev.key == "down":
            self.sel = min(max(0, n - 1), self.sel + 1)
            self.slot = None
        elif ev.key == "pageup":
            self.sel = max(0, self.sel - 10)
        elif ev.key == "pagedown":
            self.sel = min(max(0, n - 1), self.sel + 10)
        elif ev.key == "home":
            self.sel = 0
        elif ev.key == "end":
            self.sel = max(0, n - 1)
        elif ev.key in ("left", "right"):
            targets = self.targets()
            if targets:
                self.chosen_target()
                step = 1 if ev.key == "right" else -1
                group = lambda i: getattr(targets[i % len(targets)], "data", {}).get("group")  # noqa: E731
                if ev.shift and group(self.target) is not None:  # (Shift: the first of the next kind: Wish's uses)
                    i, here = self.target, group(self.target)
                    for _ in range(len(targets)):
                        i += step
                        if group(i) != here:
                            break
                    if step < 0:  # (back to the first of that kind)
                        there = group(i)
                        while group(i - 1) == there and (i - 1) % len(targets) != self.target % len(targets):
                            i -= 1
                    self.target = i % len(targets)
                else:
                    self.target = (self.target + step) % len(targets)
        elif ev.key in ("enter", "kpenter"):
            self.cast()
        elif ev.key == "w":
            self.scribe()
        elif ev.key == "p":
            self.prepare()
        elif ev.key == "l":
            self.next_slot()
        elif ev.key == "r":
            self.store()
        return True

    # ------------------------------------------------------------------ drawing
    def render(self, canvas: Canvas) -> None:
        game = self.game
        t = game.tables
        c = self.char
        w, h = canvas.width, canvas.height
        canvas.frame(0, 0, w, h - 1, f"Spells: {markup.escape(c.name)}", double=True)
        spells = self.spells()
        sid = self.current()
        lw = min(30, max(22, w // 4))
        rx, rw = lw + 5, w - lw - 7
        bottom = h - 4
        # The list, with a heading for each level.
        rows: list[tuple[str, str | None]] = []
        last = None
        for i, s in enumerate(spells):
            level = "items" if s.startswith("charge:") else "hat" if s.startswith("hat:") else t.spells[s]["level"]
            if level != last:
                rows.append(("Wands, staffs, rods" if level == "items" else "Out of the hat" if level == "hat"
                             else "Cantrips" if level == 0 else f"Level {level}", None))
                last = level
            rows.append((s, str(i)))
        visible = max(1, bottom - 2)
        at = next((r for r, (_, i) in enumerate(rows) if i == str(self.sel)), 0)
        if at < self.offset:
            self.offset = max(0, at - 1)
        elif at >= self.offset + visible:
            self.offset = at - visible + 1
        target = self.chosen_target() if sid else c
        known = set(sp.known_spells(c, t))
        mine, always = set(sp.prepared(c, t)), set(sp.always_prepared(c, t))
        y = 2
        for label, i in rows[self.offset:self.offset + visible]:
            if i is None:
                canvas.text(2, y, label, colors.TITLE, max_width=lw)
            else:
                idx = int(i)
                chosen = idx == self.sel
                if chosen:
                    canvas.fill(2, y, lw, 1, colors.HILITE_BG)
                canvas.hit(2, y, lw, 1, lambda idx=idx: setattr(self, "sel", idx))
                held = item_spell(game, c, label)
                if label.startswith("hat:"):  # (a wizard's hat's Unknown Spell)
                    ok = road = magic.hat_problem(game, c, label, target if chosen else None, listed=True) is None
                elif held is not None:  # (a wand's, a staff's or a rod's spell)
                    from realmwalker.rules import magic as magicrules

                    ok = magicrules.charges_left(held[1], held[0]) > 0
                    road = magic.road_problem(game, c, spell_of(label), target if chosen else None,
                                              charge=held) is None
                else:
                    ready = label in known
                    ok = ready and sp.can_cast(c, t, label)[0]
                    road = magic.road_problem(game, c, label, target if chosen else None) is None
                bg = colors.HILITE_BG if chosen else None
                canvas.text(2, y, "►" if chosen else " ", colors.TITLE, bg)
                canvas.text(3, y, "●" if road else " ", colors.named("good"), bg)
                mark = "◆" if label in always else ("√" if label in mine else " ")
                canvas.text(4, y, mark, colors.named("magic"), bg)
                canvas.text(6, y, t.spells[spell_of(label)]["name"], colors.SELECT_FG if chosen else
                            (colors.named("magic") if ok else colors.DIM), bg, max_width=lw - 4)
            y += 1
        if len(rows) > visible:
            canvas.text(2, bottom, f"{self.offset + 1}-{min(len(rows), self.offset + visible)} of {len(rows)}",
                        colors.FAINT, max_width=lw)
        if spells:
            canvas.markup(2, bottom - 1 if len(rows) > visible else min(bottom, y + 1),
                          "<good>●</> <dim>castable here</>" + ("  <magic>√</> <dim>prepared</>" if mine or always
                                                                else ""), max_width=lw)
        # The caster, what is working now, and the chosen spell.
        lines = caster_summary(game, c)
        now = working_now(game)
        if now:
            lines += ["<title>Working now</>"] + now + [""]
        if sid and sid.startswith("charge:"):
            lines += item_detail(game, c, sid, target, self.slot)
        elif sid and sid.startswith("hat:"):
            lines += hat_detail(game, c, sid, target)
        elif sid:
            lines += spell_detail(game, c, sid, target, self.slot)
        y = 2
        for line in lines:
            if y >= bottom - 2:
                break
            y += canvas.wrapped(rx, y, line, rw, max_lines=max(1, bottom - 2 - y)) if line else 1
        if self.message:
            canvas.wrapped(rx, bottom - 1, self.message, rw, max_lines=2)
        # Buttons along the bottom.
        bx = canvas.button(2, h - 2, "Close", self.close, hotkey="Esc")
        held = item_spell(game, c, sid) if sid else None
        if sid and sid.startswith("hat:"):
            bx = canvas.button(bx + 2, h - 2, "Reach into the hat", self.cast, hotkey="Enter",
                               enabled=magic.hat_problem(game, c, sid, target) is None)
        elif held is not None:
            bx = canvas.button(bx + 2, h - 2, "Cast", self.cast, hotkey="Enter",
                               enabled=magic.road_problem(game, c, spell_of(sid), target, charge=held) is None)
        elif sid:
            bx = canvas.button(bx + 2, h - 2, "Cast", self.cast, hotkey="Enter",
                               enabled=magic.road_problem(game, c, sid, target) is None)
            level = game.tables.spells[sid]["level"]
            if level > 0 and sp.prepared_count(c, t):
                if sid in mine or sid in always:
                    why = sp.unprepare_problem(c, t, sid)
                    bx = canvas.button(bx + 2, h - 2, "Put aside", self.prepare, hotkey="p", enabled=why is None,
                                       tooltip=f"Take it off the prepared list: {why}." if why else
                                       "Take it off the prepared list, to prepare another in its place.")
                else:
                    why = sp.prepare_problem(c, t, sid)
                    bx = canvas.button(bx + 2, h - 2, "Prepare", self.prepare, hotkey="p", enabled=why is None,
                                       tooltip=f"Prepare it: {why}." if why else "Add it to the prepared list.")
            if level > 0:
                problem = magic.scribe_problem(game, c, sid)
                bx = canvas.button(bx + 2, h - 2, "Write a scroll", self.scribe, hotkey="w", enabled=problem is None,
                                   tooltip=f"Write it out as a scroll: {problem}." if problem else
                                   f"Write it out as a scroll ({magic.SCRIBE_HOURS_PER_LEVEL * level} hours, a sheet of "
                                   f"parchment, {magic.money_text(magic.scribe_cost(level))} of inks and a spell slot).")
            from realmwalker.game import wonders

            if 1 <= level <= 5 and wonders.rings(game):
                why = wonders.store_problem(game, c, sid, self.slot)
                bx = canvas.button(bx + 2, h - 2, "Into the ring", self.store, hotkey="r", enabled=why is None,
                                   tooltip=f"Cast it into the Ring of Spell Storing: {why}." if why else
                                   "Cast it into the Ring of Spell Storing (the slot spent): whoever wears the ring "
                                   "can cast it later, once, with your numbers.")
        if len(game.party) > 1:
            bx = canvas.button(bx + 2, h - 2, "Next member", self.next_member, hotkey="Tab")
        place = sid is not None and t.spells[spell_of(sid)]["target"] == "place"
        hint = "↑↓ choose" + ((" · ←→ where" if place else " · ←→ on whom") if self.targets() else "")
        canvas.text(bx + 2, h - 2, hint, colors.FAINT, max_width=max(0, w - bx - 4))

    def autoplay_keys(self) -> list[KeyEvent]:
        return [KeyEvent(k) for k in ("down", "enter", "right", "down", "p", "tab", "pagedown", "escape")]
