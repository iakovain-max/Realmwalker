"""Cards: what the player is told about anything that can be pointed at (docs/EXPANSIONS.md §4.15).

A card is logic's answer to "what is this?": a title, a subtitle, an icon (an atlas name), a few short lines with
markup and numbers, and a footer (who caused it, time left, how to end it). The interface draws it (`ui/tooltips.py`);
nothing here imports the interface. Cards are built only when they are shown, so they may look things up freely.

- `statuses(f, b)`: every state a fighter is in, worst first, each with its icon and card (conditions, Bloodied,
  dying, the marks and auras of spells, the body's own troubles);
- `creature(b, f, full=)`: a creature on the field, or a party member: health in words, states, a short stat block;
- `attack(b, f, opt, target)`, `spell(tables, sid, b=, f=, target=)`, `ability`, `choice`: the battle's options;
- `item(game, item)`: a thing's card lines beyond its description (bond, charges, a sentient thing's demand);
- `log_line(b, i)`: the roll behind a line of the battle log;
- `char_statuses(char, tables)`: the body's troubles outside a fight, as (icon, card).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from realmwalker.core.textgen import escape_markup as esc

MAX_LINES = 12  # a card keeps to about a dozen lines; the rest is "more on the sheet"


@dataclass
class Card:
    title: str
    subtitle: str = ""
    icon: str = ""  # an atlas name ("status/prone", "icon/cast"); "" for none
    lines: list[str] = field(default_factory=list)
    footer: str = ""
    more: bool = False  # there was more than fits

    def fit(self, most: int = MAX_LINES) -> "Card":
        if len(self.lines) > most:
            self.lines = self.lines[: most - 1]
            self.more = True
        return self

    def text(self) -> str:
        """The card as plain marked-up lines (for the side panel and tests)."""
        out = [self.title] + ([f"<dim>{self.subtitle}</>"] if self.subtitle else []) + self.lines
        if self.more:
            out.append("<dim>More on the sheet.</>")
        if self.footer:
            out.append(f"<dim>{self.footer}</>")
        return "\n".join(out)


@dataclass
class Status:
    id: str  # the icon's name under "status/" in the atlas
    card: Card

    @property
    def icon(self) -> str:
        return f"status/{self.id}"


# Every status the battle board can show (an icon each in the atlas, tools/status_art.py).
CONDITIONS = ("blinded", "charmed", "deafened", "frightened", "grappled", "incapacitated", "invisible", "paralyzed",
              "petrified", "poisoned", "prone", "restrained", "stunned", "unconscious")
STATES = CONDITIONS + ("exhaustion", "bloodied", "dying", "stable", "concentrating", "hidden", "flying", "dodging",
                       "readied", "marked", "temp_hp", "heroic", "slowed", "burning", "grappling", "blessed", "baned",
                       "shielded", "warded", "resisting", "guided", "no_heal", "no_opportunity", "surprised",
                       "attached", "bleeding", "festering", "pain", "drunk", "wounded", "spell", "sapped", "vexing",
                       "shaped")
ITEM_MARKS = ("bound", "demand")  # on an item's card and its row in the pack

# The worst first: what can kill or stop someone, then what hampers, then what helps.
_ORDER = {s: i for i, s in enumerate((
    "dying", "stable", "unconscious", "petrified", "paralyzed", "stunned", "incapacitated", "restrained", "grappled",
    "charmed", "frightened", "blinded", "poisoned", "burning", "bleeding", "prone", "attached", "deafened",
    "exhaustion", "slowed", "sapped", "baned", "no_heal", "no_opportunity", "marked", "surprised", "bloodied", "festering",
    "pain", "drunk", "wounded", "shaped", "grappling", "concentrating", "flying", "hidden", "invisible", "dodging", "readied",
    "shielded", "warded", "resisting", "blessed", "guided", "vexing", "temp_hp", "heroic", "spell"))}

# Words for the states that are not conditions (the conditions' own words are data/conditions.json).
_WORDS = {
    "bloodied": ("Bloodied", "Down to half their hit points or fewer."),
    "dying": ("Dying", "At 0 hit points: a death save each turn (10 or more succeeds). Three successes and they are "
                       "stable, three failures and they die; a 20 brings them back with 1 hit point, a 1 counts twice, "
                       "and a blow while down is a failure. Healing of any kind brings them back."),
    "stable": ("Stable", "Senseless but no longer dying. They wake with 1 hit point after a while, or at once if "
                         "healed."),
    "concentrating": ("Concentrating", "Holding a spell. Damage calls for a Constitution save (DC 10, or half the "
                                       "damage if more); failing it, being incapacitated, or casting another such "
                                       "spell ends it."),
    "hidden": ("Hidden", "Out of sight: their next attack has advantage, and a foe must find them first. Attacking, "
                         "or an enemy coming beside them, gives them away."),
    "flying": ("Flying", "Aloft: out of reach of blows from the ground unless the weapon reaches. Knocked prone or "
                         "slowed to nothing, they fall."),
    "dodging": ("Dodging", "Attacks against them have disadvantage and they have advantage on Dexterity saves, until "
                           "their next turn."),
    "readied": ("Ready", "Waiting with a blow: it strikes the first foe to come within reach (or into sight) before "
                         "their next turn, with their reaction."),
    "marked": ("Marked", "The next attack against them has advantage."),
    "temp_hp": ("Temporary hit points", "Lost first, before their own; they do not add up and fade after a rest."),
    "heroic": ("Heroic Inspiration", "Once, a failed saving throw or death save may be rolled again."),
    "slowed": ("Slowed", "Their speed is lowered."),
    "sapped": ("Sapped", "Reeling from a blow: their next attack roll has disadvantage (before the one who struck "
                         "them takes another turn)."),
    "shaped": ("In another shape", "Polymorph holds them in a borrowed body: its blows, armour and speed, its hit "
                                   "points as temporary ones on top of their own. No spells, no gear. It ends when "
                                   "those are gone or the caster's concentration does."),
    "vexing": ("Vexing", "Has seen the gap in a foe's guard: their next attack roll against that foe has advantage "
                         "(before the end of their next turn)."),
    "burning": ("Burning", "On fire: 1d4 fire damage at the start of each of their turns. An action puts it out."),
    "grappling": ("Grappling", "Holding someone: they move at half speed, and the one held cannot move away."),
    "blessed": ("Blessed", "Adds a die to attack rolls and saving throws."),
    "baned": ("Baned", "Takes a die off attack rolls and saving throws."),
    "shielded": ("Shielded", "Their Armour Class is raised."),
    "warded": ("Warded", "A ward of magic stands over them."),
    "resisting": ("Resisting", "Takes half damage of some kinds."),
    "guided": ("Guided", "Adds a die to an ability check."),
    "no_heal": ("Cannot heal", "No hit points can be regained until the curse lapses."),
    "no_opportunity": ("Cannot strike out", "Cannot make opportunity attacks."),
    "surprised": ("Surprised", "Caught unready: disadvantage on initiative."),
    "attached": ("Feeding", "Fastened onto someone, drinking their blood each turn until pulled off or killed."),
    "bleeding": ("Bleeding", "An open wound: blood is lost each round until it is bound (Medicine, or a bandage "
                             "after the fight)."),
    "festering": ("Festering", "A wound has gone bad. It needs cleaning and care, or fever follows."),
    "pain": ("In pain", "Pain clouds the mind and slows the hand."),
    "drunk": ("Drunk", "Bolder and clumsier."),
    "wounded": ("Wounded", "Hurt in body, not only in hit points: wounds heal with time and care, not with rest alone."),
    "spell": ("Under a spell", "Magic is working on them."),
    "exhaustion": ("Exhaustion", ""),
}


def _cond_data(tables) -> dict:
    return tables.conditions if hasattr(tables, "conditions") else {}


def _name_of(b, fid) -> str:
    if b is None or fid is None:
        return ""
    try:
        return b.fighter(fid).name
    except StopIteration:
        return ""


def _rounds(n: int) -> str:
    return "1 round left" if n == 1 else f"{n} rounds left"


def _ending(b, end: dict | None, rounds: int | None = None) -> str:
    """When a condition or buff ends, in words."""
    if end:
        if end.get("at") in ("turn_start", "turn_end"):
            whose = _name_of(b, end.get("of"))
            when = "start" if end["at"] == "turn_start" else "end"
            return f"Ends at the {when} of {esc(whose) + chr(39) + 's' if whose else 'a'} next turn."
        if end.get("conc") is not None:
            return f"Lasts while {esc(_name_of(b, end['conc']))} keeps concentrating."
        if end.get("on_damage"):
            return "Ends if they are hurt."
    if rounds is not None and rounds > 0:
        return _rounds(rounds) + "."
    return ""


def condition_card(tables, cid: str, f=None, b=None) -> Card:
    data = _cond_data(tables)
    c = (data.get("conditions") or {}).get(cid) or {}
    card = Card(c.get("name", cid.capitalize()), "condition", f"status/{cid}", [esc(c.get("text", ""))])
    if f is not None:
        src = f.sources.get(cid)
        if src is not None:
            who = _name_of(b, src)
            if who:
                card.lines.append(f"<dim>Caused by {esc(who)}.</>")
        save = next((se for se in getattr(f, "save_ends", ()) if se.get("cond") == cid), None)
        if save:
            card.lines.append(f"A {save['save'].upper()} save (DC {save['dc']}) at the end of each of their turns "
                              f"shakes it off.")
        n = f.conditions.get(cid, -1)
        card.footer = _ending(b, f.cond_ends.get(cid), n if n > 0 else None) or ("Until it is ended." if n < 0 else "")
    if cid == "prone":
        card.lines.append("<dim>Standing up costs half their movement.</>")
    elif cid == "grappled" and f is not None and f.grappled_by is not None:
        card.lines.append(f"<dim>An escape is an action: Athletics or Acrobatics against the hold.</>")
    return card


def shape_words(shape: dict, by: str) -> str:
    """What a shape's card says: Polymorph's (F.6), Animal Shapes' or Shapechange's (F.8), from what the shape keeps."""
    keeps = (shape.get("how") or {}).get("keeps") or ()
    if not shape.get("hours"):
        return f"{_WORDS['shaped'][1]} (Held by {by}.)"
    bits = ["A borrowed body: its blows, armour and speed, its hit points as temporary ones on top of their own."]
    bits.append("Their own mind, and their spells." if "spells" in keeps else
                "Their own mind; no spells, no gear." if "mind" in keeps else "No spells, no gear.")
    if shape.get("leave"):
        bits.append("A Bonus Action lets the shape go.")
    if shape.get("shift") == "self":
        bits.append("A Magic action shifts it into another shape, with fresh borrowed hit points.")
    elif shape.get("shift") == "caster":
        bits.append(f"{by} can give them a fresh shape with a Magic action.")
    bits.append(f"It ends when the borrowed hit points are gone{' or the concentration ends' if shape.get('conc') else ''},"
                f" and it outlasts the fight. (Cast by {by}.)")
    return " ".join(bits)


def _blade_card(b, f, bf: dict, tables) -> Card:
    """The poison smeared on a fighter's weapon: whose, and what it will do on the next fitting hit."""
    from realmwalker.rules import poisons

    pid = bf["poisoned_blade"]
    rec = dict(poisons.BLADES[pid]) if pid in poisons.BLADES else \
        (poisons.record(tables, pid) if isinstance(pid, str) and pid in tables.items else None) or \
        {"kind": "injury", "dc": 0, "damage": "1d4"}
    if bf.get("venom"):
        rec.update(poisons.venom_of(tables, bf["venom"]))
    if bf.get("poison_dc"):
        rec["dc"] = int(bf["poison_dc"])
    name = rec.get("name") or (tables.items.get(pid)["name"] if isinstance(pid, str) and pid in tables.items
                               else "basic poison")
    which = "any hit" if rec["kind"] == "contact" or pid == "poisoners_dose" else "the next hit that cuts or pierces"
    bits = []
    if rec.get("damage"):
        bits.append(f"{esc(rec['damage'])} poison damage" + (" (half on a save)" if rec.get("half") else ""))
    if rec.get("with"):
        bits.append(f"Poisoned and {esc(rec['with'])}")
    elif rec.get("hours") or rec.get("ends"):
        bits.append("Poisoned")
    what = " and ".join(bits) or "its venom"
    save = f", unless a Constitution save (DC {int(rec['dc'])}) is made" if rec.get("dc") else ""
    return Card(f"Poisoned blade ({esc(name)})", "", "status/poisoned",
                [f"On {which} within a minute: {what}{save}. Spent on that hit."], "")


def _plain(sid: str, title: str, text: str, footer: str = "") -> Status:
    return Status(sid, Card(title, "", f"status/{sid}", [text], footer))


def _buff_status(b, f, bf: dict, tables) -> Status | None:
    """A mark or aura from a spell or a power, by what it does."""
    src = str(bf.get("source") or "")
    sid = src.split(":", 1)[-1]
    spell = tables.spells[sid] if sid in tables.spells else {}
    name = spell.get("name") or sid.replace("_", " ").capitalize()
    if src == "dazed_still":
        return None  # (shown as the daze itself)
    marked = _catalogue_mark(b, bf, spell)
    if marked is not None:
        kind, title, lines = marked
        if bf.get("conc") is not None:
            lines.append(f"<dim>Held by {esc(_name_of(b, bf['conc']))}'s concentration.</>")
        footer = _ending(b, bf.get("ends"), int(bf["rounds"]) if bf.get("rounds") else None)
        return Status(kind, Card(title, "", f"status/{kind}", lines, footer))
    if bf.get("fumes"):  # (Burnt Othur Fumes in the lungs: rules/poisons.turn_start)
        left = int(bf.get("fumes_successes", 3)) - int(bf.get("fumes_saved", 0))
        return Status("poisoned", Card("Choking on fumes", "", "status/poisoned", [
            f"A Constitution save (DC {int(bf['fumes'])}) at the start of each of their turns: "
            f"{esc(str(bf.get('fumes_dice', '1d6')))} poison damage on a failure. {left} more "
            f"save{'s' if left != 1 else ''} and the smoke is out."], ""))
    if bf.get("poisoned_blade"):
        return Status("poisoned", _blade_card(b, f, bf, tables))
    if bf.get("until_act"):
        return None  # (Invisibility: the condition shows itself)
    if bf.get("marked"):
        kind = "marked"
    elif bf.get("burning"):
        kind = "burning"
    elif bf.get("slow") or bf.get("dazed"):
        kind = "slowed"
    elif bf.get("no_heal"):
        kind = "no_heal"
    elif bf.get("no_opportunity"):
        kind = "no_opportunity"
    elif bf.get("attack_die") or bf.get("save_die"):
        die = str(bf.get("attack_die") or bf.get("save_die"))
        kind = "baned" if die.startswith("-") else "blessed"
    elif bf.get("check_die") or bf.get("aimed"):
        kind = "guided"
    elif bf.get("ac") or bf.get("mage_armor"):
        kind = "shielded"
    elif bf.get("death_ward"):
        kind = "warded"
    elif bf.get("resist"):
        kind = "resisting"
    elif bf.get("fly"):
        kind = "flying"
    elif bf.get("sapped") or bf.get("unsteady"):
        kind = "sapped"
    elif bf.get("reeling"):
        kind = "marked"
    elif bf.get("protected") is not None or bf.get("parry_ac"):
        kind = "shielded"
    elif bf.get("vex") is not None:
        kind = "vexing"
    elif bf.get("distracted"):
        return None  # (shown as the mark it leaves, not as its own state)
    elif bf.get("goaded") is not None or bf.get("disarmed"):
        kind = "sapped"  # (a Battle Master's Goading and Disarming Attacks)
    elif bf.get("exposed") is not None:
        kind = "marked"  # (Distracting Strike)
    elif bf.get("maneuver_die"):
        kind = "guided"  # (a feint's, a lunge's or a commanded strike's die waiting for the hit)
    elif bf.get("eldritch_struck") is not None:
        kind = "baned"  # (an Eldritch Knight's Eldritch Strike: the next save against their spell is harder)
    else:
        kind = "spell"
    title, text = _WORDS[kind]
    lines = [text]
    if kind == "slowed" and bf.get("dazed"):
        title, lines = "Dazed (Cunning Strike)", ["On their next turn they may only act: no moving, no bonus action."]
    elif kind == "slowed":
        lines = [f"{int(bf['slow'])} feet off their speed."]
    elif kind == "guided" and bf.get("aimed"):
        title, lines = "Steady Aim", ["Their next attack roll this turn has advantage."]
    elif kind == "vexing":
        lines = [f"Their next attack roll against {esc(_name_of(b, bf['vex']))} has advantage."]
    elif kind == "sapped" and bf.get("goaded") is not None:
        title, lines = "Goaded (Battle Master)", ["Disadvantage on attack rolls against anyone but "
                                                 f"{esc(_name_of(b, bf['goaded']))}."]
    elif kind == "sapped" and bf.get("disarmed"):
        title, lines = "Disarmed", [f"Their {esc(str(bf['disarmed']).lower())} lies at their feet: it cannot be used "
                                    "until they take it up again on their turn."]
    elif kind == "marked" and bf.get("exposed") is not None:
        title, lines = "Distracted", ["The next attack against them by anyone but "
                                      f"{esc(_name_of(b, bf['exposed']))} has advantage."]
    elif kind == "baned" and bf.get("eldritch_struck") is not None:
        title, lines = "Eldritch Strike", ["Disadvantage on the next save against a spell of "
                                           f"{esc(_name_of(b, bf['eldritch_struck']))}'s, until the end of their next "
                                           "turn."]
    elif kind == "guided" and bf.get("maneuver_die"):
        title, lines = "A maneuver ready", [f"Their next hit{' in melee after moving' if bf.get('melee') else ''} adds "
                                            f"{int(bf['maneuver_die'])} to the damage (a superiority die)."]
    elif kind == "shielded" and str(bf.get("source", "")).startswith(("evasive_footwork", "bait:")):
        title, lines = "Light-footed (Battle Master)", [f"Armour Class +{int(bf['ac'])} until the Battle Master's "
                                                        "next turn."]
    elif kind == "sapped" and bf.get("unsteady"):
        title, lines = "Unsteady (Slasher)", ["Cut and off balance: their attack rolls have disadvantage until "
                                              f"{esc(_name_of(b, bf['unsteady']))}'s next turn."]
    elif kind == "sapped":
        lines = [_WORDS["sapped"][1]]
    elif kind == "marked" and bf.get("reeling"):
        title, lines = "Reeling (Crusher)", ["Every attack against them has advantage until "
                                             f"{esc(_name_of(b, bf['reeling']))}'s next turn."]
    elif kind == "shielded" and bf.get("protected") is not None:
        title, lines = "Shielded (Protection)", [f"{esc(_name_of(b, bf['protected']))}'s shield is in the way: "
                                                 "attacks against them have disadvantage."]
    elif kind == "shielded" and bf.get("parry_ac"):
        title, lines = "Parrying (Defensive Duelist)", [f"+{int(bf['parry_ac'])} AC against melee blows."]
    elif kind in ("blessed", "baned"):
        die = str(bf.get("attack_die") or bf.get("save_die")).lstrip("-")
        lines = [f"{'Adds' if kind == 'blessed' else 'Takes'} {die} {'to' if kind == 'blessed' else 'off'} attack "
                 f"rolls and saving throws."]
    elif kind == "shielded":
        lines = [f"Armour Class {'+' + str(bf['ac']) if bf.get('ac') else str(bf['mage_armor']) + ' + Dex'}."]
    elif kind == "resisting":
        lines = [f"Half damage from {', '.join(bf['resist'])}."]
    elif kind == "guided":
        lines = [f"Adds {bf['check_die']} to one ability check."]
    if spell and kind != "spell":
        title = f"{title} ({spell['name']})"
    elif kind == "spell" and spell:
        title = spell["name"]
        lines = [esc(spell.get("text", text))]
    if bf.get("conc") is not None:
        lines.append(f"<dim>Held by {esc(_name_of(b, bf['conc']))}'s concentration.</>")
    footer = _ending(b, bf.get("ends"), int(bf["rounds"]) if bf.get("rounds") else None)
    return Status(kind, Card(title, "", f"status/{kind}", lines, footer))


def _catalogue_mark(b, bf: dict, spell: dict) -> tuple[str, str, list[str]] | None:
    """The marks of the spell catalogue (rules/engine/marks.py), as (status kind, title, lines); None for others."""
    name = spell.get("name", "")
    who = lambda key: esc(_name_of(b, bf.get(key))) or "the caster"  # noqa: E731
    if bf.get("outlined"):
        return "marked", "Outlined", ["Shining with a telltale light: every attack against them has advantage."]
    if bf.get("blurred"):
        return "shielded", "Blurred", ["Their shape swims and shifts: attacks against them have disadvantage."]
    if bf.get("images"):
        return "shielded", "Mirror images", [f"{int(bf['images'])} duplicates of them: a hit may land on one of "
                                             "them instead (a d6 each, 3 or more), and that image is gone."]
    if bf.get("sanctuary") is not None:
        return "warded", "Sanctuary", [f"A foe must make a Wisdom save (DC {int(bf['sanctuary'])}) to strike them or "
                                       "aim a spell at them; it ends if they attack or cast at a foe."]
    if bf.get("warded_kinds"):
        return "warded", f"Warded ({name or 'protection'})", [
            "Aberrations, celestials, elementals, fey, fiends and undead have disadvantage on attacks against them."
            if len(bf["warded_kinds"]) > 3 else
            f"{', '.join(k.capitalize() for k in bf['warded_kinds'])} have disadvantage on attacks against them."]
    if bf.get("ward_die"):
        return "shielded", f"Warded ({name or 'Blade Ward'})", [f"Every attack roll against them loses "
                                                                f"{esc(str(bf['ward_die']))}."]
    if bf.get("ac_floor"):
        return "shielded", f"Hard skin ({name or 'Barkskin'})", [f"Their Armour Class is at least "
                                                                 f"{int(bf['ac_floor'])}."]
    if bf.get("retaliate"):
        return "warded", f"Armour of frost ({name})" if name else "Armour of frost", [
            f"While their temporary hit points last, a melee blow on them costs the striker "
            f"{int(bf['retaliate'])} {esc(bf.get('retaliate_type', 'cold'))} damage."]
    if bf.get("bond") is not None:
        return "warded", "Warding Bond", [f"+{int(bf.get('ac', 1))} AC and saves, and half damage of every kind; "
                                          f"{who('bond')} takes the same harm they do."]
    if bf.get("quarry"):
        return "marked", f"{'Hexed' if bf.get('quarry_type') == 'necrotic' else 'Hunted'} ({name})" if name else             "Hunted", [f"{who('by')}'s hits on them deal {esc(str(bf['quarry']))} "
                       f"{esc(bf.get('quarry_type', 'force'))} more."]
    if bf.get("dot"):
        when = "start" if bf.get("dot_at", "start") == "start" else "end"
        line = f"{esc(str(bf['dot']))} {esc(bf.get('dot_type', 'fire'))} damage at the {when} of their " \
               f"{'next turn' if bf.get('dot_once') else 'turns'}"
        if bf.get("dot_save"):
            line += f", until a {bf['dot_save'].upper()} save (DC {int(bf.get('dc', 10))}) ends it"
        return ("burning" if bf.get("dot_type") == "fire" else "spell"), \
            (name or str(bf.get("dot_name", "Harm")).capitalize()), [line + "."]
    if bf.get("heroism"):
        return "blessed", f"Heroism ({name})" if name else "Heroism", [
            f"Fearless; {int(bf['heroism'])} temporary hit points at the start of each of their turns."]
    if bf.get("discord"):
        return "baned", "In discord (Symbol)", ["Quarrelling with their own: their attack rolls have disadvantage."]
    if bf.get("vulnerable"):
        return "marked", "Hallowed ground", [f"Vulnerable to {esc(', '.join(bf['vulnerable']))} damage here."]
    if bf.get("immune") and bf.get("source") == "hallow":
        return "blessed", "Hallowed ground", ["Courage: they cannot be frightened here."]
    if bf.get("weak") or bf.get("damage_die"):
        return "sapped", f"Enfeebled ({name})" if name else "Enfeebled", [
            "Disadvantage on Strength attacks and saves" + (f"; {esc(str(bf['damage_die']).lstrip('-'))} off the "
                                                            f"damage they deal." if bf.get("damage_die") else ".")]
    if bf.get("duel") is not None:
        return "sapped", "Compelled to duel", [f"Disadvantage on attacks against anyone but {who('duel')}."]
    if bf.get("maddened") is not None:
        return "spell", f"Crowned with madness ({name})" if name else "Maddened", [
            "Its action goes on a blow at one of its own friends within reach."]
    if bf.get("hit_extra"):
        return "blessed", name or "Favoured", [f"Their weapon hits deal {esc(str(bf['hit_extra']))} "
                                               f"{esc(bf.get('hit_type', 'radiant'))} more."]
    if bf.get("weapon_plus"):
        return "blessed", name or "Magic weapon", [f"+{int(bf['weapon_plus'])} to weapon attack and damage rolls."]
    if bf.get("smite"):
        how = {"melee": "melee weapon", "ranged": "ranged weapon"}.get(bf.get("smite_with", "melee"), "weapon")
        return "blessed", f"{name} readied" if name else "A smite readied", [
            f"Their next {how} hit carries the spell." + (f" {esc(spell['text'])}" if spell.get("text") else "")]
    if bf.get("shillelagh"):
        return "blessed", name or "Shillelagh", ["Their club or staff strikes with the spellcasting ability and a "
                                                 "bigger die."]
    if bf.get("soak"):
        return "resisting", name or "Resistance", [f"{esc(str(bf['soak']))} off {esc(str(bf.get('soak_type')))} "
                                                   "damage, once a turn."]
    if "expeditious_retreat" in (bf.get("traits") or ()):
        return "spell", name or "Expeditious Retreat", ["They may Dash as a bonus action."]
    # The second wave (D.2)
    if bf.get("confused"):
        return "spell", name or "Confused", ["At the start of each turn a d10 says what they do: wander off (1), "
                                             "nothing (2-6), strike at someone near (7-8), or act freely (9-10)."]
    if bf.get("sluggish"):
        return "sapped", name or "Slowed", ["Half speed, -2 AC and Dexterity saves, no bonus action, one attack "
                                            "an action."]
    if bf.get("haste"):
        return "blessed", name or "Hasted", ["Double speed, +2 AC, advantage on Dexterity saves and one more attack "
                                             "an action. When it ends, a turn of lethargy."]
    if bf.get("blink"):
        return "shielded", name or "Blinking", ["At the end of each of their turns, an even chance to vanish into "
                                                "the Ethereal Plane until their next turn."]
    if bf.get("thorns"):
        return "warded", name or "Fire Shield", [f"Whoever hits them in melee takes {esc(str(bf['thorns']))} "
                                                 f"{esc(bf.get('thorns_type', 'fire'))} damage."]
    # The third wave (D.3)
    if bf.get("dancing"):
        return "sapped", name or "Dancing", ["Dancing helplessly: they cannot move, their attacks and Dexterity saves "
                                             "have disadvantage, and attacks against them have advantage. Each turn "
                                             "they spend their action trying to stop (a Wisdom save)."]
    if bf.get("aloft"):
        return "spell", name or "Falling upward", ["Hanging high in the air where gravity runs backwards; they will "
                                                   "fall when the spell ends."]
    if bf.get("spell_ward") is not None:
        return "warded", name or "Globe of Invulnerability", [
            f"Spells below level {int(bf['spell_ward'])} cast from outside the barrier cannot touch them."]
    if bf.get("truesight"):
        return "blessed", name or "True Seeing", [f"They see the invisible, and through any darkness, "
                                                  f"{int(bf['truesight'])} feet."]
    # The fourth wave (D.4)
    if bf.get("time_stop") is not None:
        return "blessed", name or "Time stopped", [f"Time stands still for everyone else: {int(bf['time_stop'])} more "
                                                   "turns in a row, until anything they do touches another creature."]
    if bf.get("foresight"):
        return "blessed", name or "Foresight", ["They see what is coming: advantage on their attacks, saves and "
                                                "checks, and attacks against them have disadvantage."]
    if bf.get("holy") is not None:
        return "warded", name or "Holy Aura", ["Advantage on every save, and attacks against them have "
                                               "disadvantage; a fiend or undead that strikes them in melee may be "
                                               "blinded by the light."]
    if bf.get("befuddled"):
        return "sapped", name or "Befuddled", ["Their mind is in tatters: they cannot cast spells."]
    if bf.get("immune_damage"):
        what = ", ".join(esc(str(t)) for t in bf["immune_damage"])
        return "warded", name or "Mind Blank", [f"No {what} damage can touch them, and they cannot be charmed."]
    if bf.get("aura"):
        r = int(bf["aura"].get("radius", 30))
        return "blessed", name or "An aura", [f"Friends within {r} feet share its gift."]
    if bf.get("save_adv") or bf.get("heal_max"):
        lines = []
        if bf.get("save_adv"):
            what = ["death saves" if a == "death" else f"{a.upper()} saves" for a in bf["save_adv"]]
            lines.append(f"Advantage on {' and '.join(what)}.")
        if bf.get("heal_max"):
            lines.append("Healing they receive is the most the dice can give.")
        return "blessed", name or "Hope", lines
    if bf.get("save_adv_spells") or bf.get("save_adv_against") or bf.get("rise"):
        lines = []
        if bf.get("save_adv_spells"):
            lines.append("Advantage on saves against spells" + ("; a save takes no damage at all." if
                                                                  bf.get("evade_spells") else "."))
        if bf.get("save_adv_against"):
            lines.append("Advantage on saves against being " + ", ".join(esc(c) for c in bf["save_adv_against"]) + ".")
        if bf.get("rise"):
            lines.append("At the start of their turn at 0 hit points they regain 1.")
        return "warded", name or "Warded", lines
    return None


def statuses(f, b=None) -> list[Status]:
    """Every state a fighter is in, worst first, each with its card. One icon per kind of state."""
    tables = f.t
    out: dict[str, Status] = {}

    def add(s: Status | None, key: str = "") -> None:
        key = key or (s.id if s is not None else "")
        if s is not None and key not in out:
            out[key] = s

    for cid in f.conditions:
        if cid in CONDITIONS:
            add(Status(cid, condition_card(tables, cid, f, b)))
    if f.state == "down":
        if f.stable:
            add(Status("stable", Card(*_WORDS["stable"][:1], "", "status/stable", [_WORDS["stable"][1]])))
        else:
            ok, bad = f.death_saves
            pips = "<good>" + "●" * ok + "</>" + "○" * (3 - ok) + "  <danger>" + "●" * bad + "</>" + "○" * (3 - bad)
            add(Status("dying", Card("Dying", "", "status/dying", [_WORDS["dying"][1], f"Saved {ok}, failed {bad}: {pips}"])))
    char = f.char
    level = int(getattr(char, "exhaustion", 0) or 0) if char is not None else 0
    if level:
        ex = _cond_data(tables).get("exhaustion") or {}
        add(Status("exhaustion", Card(f"Exhaustion {level}", "condition", "status/exhaustion",
                                      [esc(ex.get("text", "")),
                                       f"Every d20 roll {2 * level} lower, speed {5 * level} feet less."],
                                      "A long rest takes one level away.")))
    if f.state in ("fighting", "fleeing") and 0 < f.hp <= f.max_hp // 2:
        add(_plain("bloodied", *_WORDS["bloodied"], f"{f.hp} of {f.max_hp} hit points."))
    if "possessed" in f.conditions:  # (Magic Jar: a party soul in a foe's body)
        add(Status("charmed", Card("Possessed", "", "status/charmed", [
            "A soul from a Magic Jar has taken this body: it fights for the party, its own soul trapped in the gem."],
            "Ends when the soul leaves, or the body dies (a Charisma save sends the soul back to its gem).")))
    if getattr(f, "jar", None) is not None:
        add(_plain("spell", "Soul in the jar", "The body lies still; the soul is in a gem (Magic Jar). It may take a "
                   "humanoid foe within 100 feet (a Charisma save) or go home to the body."))
    if f.concentration is not None:
        sid = f.concentration.get("spell", "")
        sp = tables.spells[sid] if sid in tables.spells else {}
        rounds = f.concentration.get("rounds")
        add(Status("concentrating", Card(f"Concentrating on {sp.get('name', sid)}", "", "status/concentrating",
                                         [_WORDS["concentrating"][1]], _rounds(int(rounds)) + "." if rounds else "")))
    if f.z > 0:
        add(_plain("flying", "Flying", f"{int(f.z)} feet up. " + _WORDS["flying"][1]))
    if f.hidden:
        add(_plain("hidden", "Hidden", f"Stealth {f.hidden}: a foe must beat that with a Search. " + _WORDS["hidden"][1]))
    if f.dodging:
        add(_plain("dodging", *_WORDS["dodging"]))
    if f.readied:
        add(_plain("readied", "Ready", _WORDS["readied"][1].replace("(or into sight)", "" if f.readied == "reach"
                                                                     else "(or into sight)")))
    if getattr(f, "shape", None) is not None:  # (Polymorph: Expansion 3 F.6; Animal Shapes, Shapechange: F.8)
        by = esc(_name_of(b, f.shape["by"])) if b is not None else "a caster"
        add(_plain("shaped", _WORDS["shaped"][0], shape_words(f.shape, by)))
    if f.temp_hp > 0:
        add(_plain("temp_hp", f"{f.temp_hp} temporary hit points", _WORDS["temp_hp"][1]))
    if char is not None and char.uses.get("heroic_inspiration", 0) > 0:
        add(_plain("heroic", *_WORDS["heroic"]))
    if f.surprised:
        add(_plain("surprised", *_WORDS["surprised"]))
    if f.attached_to is not None:
        add(_plain("attached", "Feeding", f"Fastened onto {esc(_name_of(b, f.attached_to))}, drinking their blood."))
    if b is not None and f.active:
        held = [x for x in b.fighters if x.grappled_by == f.id and x.state != "dead"]
        if held:
            add(_plain("grappling", "Grappling", f"Holding {esc(held[0].name)}. " + _WORDS["grappling"][1].split(": ", 1)[1]))
    for bf in f.buffs:
        st = _buff_status(b, f, bf, tables)
        if st is not None:
            add(st, f"{st.id}:{bf.get('source', '')}")  # two spells of one kind show as two
    wounds = list(f.wounds or ())
    if any((getattr(w, "bleed", 0) and not getattr(w, "bandaged", False)) or getattr(w, "internal", False) for w in wounds):
        add(_plain("bleeding", *_WORDS["bleeding"]))
    if any(getattr(w, "infection", 0) > 0 for w in wounds):
        add(_plain("festering", *_WORDS["festering"]))
    if char is not None:
        from realmwalker.rules import health

        st = health.intox_stage(char)
        if st:
            add(_plain("drunk", st[0].capitalize(), _WORDS["drunk"][1]))
        st = health.pain_stage(char, tables)
        if st and st[0] != "hurting":
            add(_plain("pain", st[0].capitalize(), _WORDS["pain"][1]))
    if wounds and "bleeding" not in out:
        names = "; ".join(esc(w.label) for w in wounds[:3])
        add(_plain("wounded", f"{len(wounds)} wound{'s' if len(wounds) > 1 else ''}", names + "."))
    return sorted(out.values(), key=lambda s: _ORDER.get(s.id, 99))


def health_words(f) -> str:
    """A fighter's health in a word, as anyone watching would judge it."""
    if f.state == "dead":
        return "<danger>dead</>"
    if f.state == "down":
        return "<good>stable</>" if f.stable else "<danger>dying</>"
    ratio = f.hp / max(1, f.max_hp)
    if ratio >= 1:
        return "<good>unhurt</>"
    if ratio > 0.5:
        return "<good>hurt</>"
    if ratio > 0.25:
        return "<warn>bloodied</>"
    return "<danger>near death</>"


def _cr(cr) -> str:
    cr = float(cr)
    return {0.125: "1/8", 0.25: "1/4", 0.5: "1/2"}.get(cr, str(int(cr)) if cr == int(cr) else str(cr))


def creature(b, f, *, full: bool = True) -> Card:
    """A fighter on the field: what it is, how it fares, its states, and (when known or `full`) a short stat block."""
    tables = f.t
    states = statuses(f, b)
    if f.char is not None:
        c = f.char
        cls = tables.classes.get(c.cls, {}).get("name", c.cls) if hasattr(tables, "classes") else c.cls
        card = Card(esc(c.name), f"level {c.level} {esc(cls)}", "icon/character")
        card.lines.append(f"Hit points {f.hp}/{f.max_hp}" + (f" (+{f.temp_hp})" if f.temp_hp else "")
                          + f" · AC {f.ac()} · speed {f.speed} ft")
        if c.wounds:
            card.lines.append("<danger>" + esc("; ".join(w.label for w in c.wounds[:3])) + "</>")
    else:
        d = f.cdef
        kind = f"{d.get('size', 'medium')} {d.get('kind', 'creature')}".strip()
        card = Card(esc(f.name), kind, "icon/danger")
        card.lines.append(f"Looks {health_words(f)}." if not full else f"Hit points {f.hp}/{f.max_hp} · {health_words(f)}")
        if d.get("descriptions"):
            card.lines.append(f"<dim>{esc(d['descriptions'][0])}</>")
    if states:
        card.lines.append("States: " + ", ".join(esc(s.card.title) for s in states[:6]))
    from realmwalker.rules import simulacrum

    if simulacrum.snow(f):
        card.lines.append("<magic>A Simulacrum: snow in a likeness.</> <dim>Nothing heals it; at 0 hit points it "
                          "melts. Its maker mends it at a long rest, 100 GP a hit point.</>")
    if f.char is None:
        if full:
            card.lines += _stat_lines(b, f)
            card.footer = f"Challenge {_cr(f.cdef.get('cr', 0))}"
        else:
            card.footer = "Study it (an action) to learn more."
    return card.fit()


def _stat_lines(b, f) -> list[str]:
    d = f.cdef
    tables = f.t
    out = []
    speeds = dict(d.get("speeds") or d.get("speed") or {"walk": f.speed})
    sp = ", ".join(f"{k} {v} ft" if k != "walk" else f"{v} ft" for k, v in speeds.items() if v)
    out.append(f"AC {f.ac()} · speed {sp}")
    senses = ", ".join(f"{k} {v} ft" for k, v in (d.get("senses") or {}).items() if v)
    if senses:
        out.append(f"<dim>Senses: {senses}</>")
    for key, word in (("immune", "Immune"), ("resist", "Resists"), ("vulnerable", "Vulnerable")):
        if d.get(key):
            out.append(f"{word}: {', '.join(d[key])}")
    if d.get("condition_immune"):
        out.append(f"Never {', '.join(d['condition_immune'])}")
    traits = tables.traits.get("traits", {}) if hasattr(tables, "traits") else {}
    for tid in d.get("traits", []):
        t = traits.get(tid)
        if t and t.get("where") != "sheet":
            out.append(f"<title>{esc(t.get('name', tid))}.</> {esc(t.get('text', ''))}")
    if b is not None:
        for o in b.attack_options(f)[:4]:
            out.append(attack_line(o))
    for key in ("bonus_actions", "reactions"):
        for a in d.get(key) or ():
            out.append(f"<dim>{'Bonus' if key == 'bonus_actions' else 'Reaction'}:</> {esc(a.get('name', a.get('id', '')))}")
    for name, ready in sorted(f.recharge.items()):
        out.append(f"{esc(name.replace('_', ' ').capitalize())}: " + ("<good>ready</>" if ready else "<dim>recharging</>"))
    lr = d.get("legendary_resistance")
    if lr:
        left = f.creature.uses.get("legendary_resistance", int(lr.get("per_day", 3)))
        out.append(f"Legendary Resistance: {left} left today")
    if d.get("legendary"):
        left = f.creature.uses.get("legendary_actions", int(d["legendary"].get("uses", 3)))
        out.append(f"Legendary actions: {left} left this round")
    return out


def attack_line(o) -> str:
    """One attack in a line: "Scimitar +4, 1d6+2 slashing, reach 5 ft"."""
    if o.extra.get("single_save") or o.extra.get("save"):
        a = o.extra
        return f"<title>{esc(o.name)}</>: {str(a.get('save', 'dex')).upper()} save DC {a.get('dc', '?')}, {o.damage} {o.damage_type}"
    where = f"range {o.range[0]}/{o.range[1]} ft" if o.range[0] else ("reach 10 ft" if o.reach else "reach 5 ft")
    sign = "+" if o.bonus >= 0 else ""
    return f"<title>{esc(o.name)}</> {sign}{o.bonus}, {o.damage} {o.damage_type}, {where}"


def attack(b, f, opt, target=None, *, known: bool = True) -> Card:
    """An attack on the action bar: to hit, damage, reach; and the chance against the one pointed at."""
    card = Card(esc(opt.name), opt.kind.replace("_", " "), "icon/attack", [attack_line(opt)])
    if opt.properties:
        card.lines.append(f"<dim>{', '.join(p.replace('_', '-') for p in opt.properties)}</>")
    from realmwalker.rules.engine.handlers import mastery

    trick = mastery.of(f, opt) if f is not None else None
    if trick:
        text = f.t.traits["traits"].get(f"mastery_{trick}", {}).get("text", "")
        card.lines.append(f"<good>Mastery: {trick.title()}</> <dim>{esc(text)}</>")
    if not opt.available and opt.reason:
        card.lines.append(f"<warn>{esc(opt.reason)}</>")
    if b is not None and target is not None and target.side != f.side and target.active:
        if known:
            card.lines += chance_lines(b, f, opt, target)
        else:
            card.lines.append(f"<dim>Against {esc(target.name)}: how hard it is to hit is not known yet (Study it).</>")
    return card.fit()


def chance_lines(b, f, opt, target) -> list[str]:
    from realmwalker.rules import grid

    chance = b.hit_chance(f, opt, target)
    adv, dis, why = b._adv_dis(f, target, opt)
    ac, cover = b.target_ac(f, target, opt)
    mode = " with advantage" if adv and not dis else (" with disadvantage" if dis and not adv else "")
    out = [f"Against {esc(target.name)}: <title>{int(round(chance * 100))}%</> to hit{mode} (AC {ac})"]
    notes = list(why) + ([grid.COVER_WORDS[cover]] if cover else [])
    if notes:
        out.append(f"<dim>{esc(', '.join(notes))}</>")
    from realmwalker.rules.engine import query

    kind = query.defences(target, opt.damage_type) if target.creature is not None and target.creature.def_id in b.known else ""
    if kind:
        out.append({"immune": "<danger>It is immune to that.</>", "resist": "<warn>It resists that: half damage.</>",
                    "vulnerable": "<good>It is hurt most by that: double damage.</>"}[kind])
    return out


def spell(tables, sid: str, *, b=None, f=None, target=None, level: int | None = None, scroll: bool = False) -> Card:
    """A spell: level, cost, range, area, concentration, what it does; the save DC or attack of the caster. `level`:
    the slot it would be cast with (what a higher slot adds); `scroll`: read from a scroll (its own numbers)."""
    from realmwalker.rules import spells as sprules

    sp = tables.spells[sid]
    lvl = int(sp.get("level", 0))
    sub = ("cantrip" if lvl == 0 else f"level {lvl}") + (f" {sp['school']}" if sp.get("school") else "")
    if level and lvl and level > lvl:
        sub += f", cast at level {level}"
    card = Card(esc(sp["name"]), sub, "icon/cast", [esc(sp.get("text", ""))])
    cast = {"action": "an action", "bonus": "a bonus action", "reaction": "a reaction"}.get(sp.get("cast", "action"),
                                                                                             "an action")
    rng = sp.get("range", 0)
    if isinstance(rng, str):
        where = rng  # "self" or "touch"
    else:
        where = "self" if sp.get("target") == "self" else ("touch" if rng in (0, 5) else f"{rng} ft")
    bits = [f"Costs {cast}", f"range {where}"]
    area = sp.get("area")
    if area:
        bits.append(f"{area['size']}-foot {area['shape']}")
    card.lines.append(", ".join(bits) + ".")
    what = sprules.summary(sp)
    if what:
        card.lines.append(", ".join(what))
    if level and lvl and level > lvl:
        gain = sprules.up_gain(sp, level - lvl)
        card.lines.append(f"<good>With a level {level} slot:</> {', '.join(gain) if gain else 'nothing more'}.")
    elif lvl and sprules.upcasts(sp) and level is None and not scroll:
        card.lines.append(f"<dim>A higher slot: {', '.join(sprules.up_gain(sp, 1))} a level.</>")
    if scroll:  # (DMG 2024: the scroll's numbers, no slot, no materials)
        dc, attack = sprules.scroll_numbers(tables, lvl)
        card.subtitle = f"{card.subtitle}, from a scroll"
        card.lines.append(f"<magic>From a scroll</>: save DC {dc}, attack +{attack}; no slot and no materials. It "
                          f"crumbles once the spell is cast.")
        how = sprules.scroll_reader(f.char, tables, sid) if f is not None and f.char is not None else None
        check = sprules.scroll_check(f.sheet, tables, sid, how) if how else None
        if check is not None:
            card.lines.append(f"<warn>Beyond you: an {check[2]} check first (DC {check[1]}, you have "
                              f"{check[0]:+d}); on a failure the scroll is lost and nothing happens.</>")
    elif f is not None and f.char is not None and not sp.get("thrown") \
            and any(o.get("op") == "save" for o in sp.get("effects", ())):
        card.lines.append(f"Save DC {sprules.save_dc(f.sheet, tables)}.")
    free = sprules.free_cast(f.char, tables, sid) if f is not None and f.char is not None and not scroll else None
    if free:  # (a wizard's Spell Mastery or Signature Spells)
        card.lines.append("<good>No slot: Spell Mastery.</>" if free == "mastery" else
                          "<good>No slot this time: a signature spell.</>")
    if b is not None and f is not None and target is not None and target.creature is not None \
            and target.creature.def_id in b.known:
        from realmwalker.rules.engine import query

        kind = query.defences(target, sprules.main_type(sp) or "")
        if kind:
            card.lines.append({"immune": "<danger>It is immune to that.</>", "resist": "<warn>It resists that.</>",
                               "vulnerable": "<good>It is hurt most by that.</>"}[kind])
    if sp.get("material") and not scroll:  # (a costly component: that very thing, not a focus)
        card.lines.append(f"<dim>Needs {esc(sp['material']['text'])}.</>")
        if f is not None and f.char is not None and sprules.component_problem(f.char, tables, sid):
            card.lines.append("<warn>None in the pack.</>")
    if sp.get("concentration"):
        card.lines.append("<magic>Concentration</>: one such spell at a time; damage may break it.")
    if sp.get("rounds"):
        r = int(sp["rounds"])
        card.footer = f"Lasts {r // 10} minute{'s' if r >= 20 else ''}." if r >= 10 else f"Lasts {_rounds(r).split(' left')[0]}."
    return card.fit()


def ability(b, f, aid: str, name: str, ok: bool, why: str) -> Card:
    card = Card(esc(name), "ability", "icon/ability")
    traits = f.t.traits.get("traits", {})
    act, owner = None, None
    for tid, t in traits.items():
        acts = t.get("activate") or []
        for a in acts if isinstance(acts, list) else [acts]:
            if a.get("id") == aid:
                act, owner = a, t
                break
        if act is not None:
            break
    text = (owner or traits.get(aid) or {}).get("text") or _ABILITY_WORDS.get(aid, "")
    if text:
        card.lines.append(esc(text))
    cost = (act or {}).get("cost")
    if cost:
        card.lines.append(f"<dim>Costs {'a bonus action' if cost == 'bonus' else 'an ' + cost}.</>")
    uses = (act or {}).get("uses") or (aid if f.char is not None and aid in f.char.uses else None)
    if f.char is not None and uses:
        card.lines.append(f"<dim>Uses left: {int(f.char.uses.get(uses, 0))}</>")
    if not ok and why:
        card.lines.append(f"<warn>{esc(why)}</>")
    return card.fit()


_ABILITY_WORDS = {
    "offhand": "A blow with the light weapon in the other hand, as a bonus action, after attacking with the first. "
               "Its damage does not add the ability modifier unless it is negative.",
    "spirit_strike": "The spiritual weapon strikes a foe beside it (a melee spell attack), and may first move 20 feet.",
    "put_out": "Drop and roll: the flames go out (an action).",
}


def choice(b, f, kind: str, value, label: str, ok: bool, why: str, target=None, *, known: bool = True) -> Card:
    """The card for a row of the battle's choice list."""
    if kind == "attack" and value is not None and hasattr(value, "damage"):
        return attack(b, f, value, target, known=known)
    if kind in ("cast", "wish") and isinstance(value, str) and value.split(":")[-1] in f.t.spells:
        card = spell(f.t, value.split(":")[-1], b=b, f=f, target=target, scroll=value.startswith("scroll:"))
        if not ok and why:
            card.lines.append(f"<warn>{esc(why)}</>")
        return card
    if kind == "ability":
        return ability(b, f, str(value), label, ok, why)
    card = Card(label, kind, "icon/item" if kind == "item" else "icon/more")
    if not ok and why:
        card.lines.append(f"<warn>{esc(why)}</>")
    return card


def item_marks(game, item) -> list[str]:
    """The small marks an item carries in the pack: bound to someone, or a sentient thing wanting something."""
    m = item.magic or {}
    out = []
    if m.get("attune") and any(item.uid in getattr(c, "attuned", ()) for c in getattr(game, "party", ())):
        out.append("bound")
    if (m.get("sentient") or {}).get("demand"):
        out.append("demand")
    return out


def item_mark_card(game, item, mark: str) -> Card:
    from realmwalker.game import magic_items

    if mark == "bound":
        who = magic_items.bearer(game, item)
        first = (who.name.split() or ["its bearer"])[0] if who is not None else "its bearer"
        return Card("Bound", "attuned", "status/bound",
                    [f"Bound to {esc(first)}: its powers answer them alone.",
                     "<dim>Three such bonds at most. Ending one takes a short rest (a).</>"])
    mind = item.magic["sentient"]
    demand = mind["demand"]
    want = magic_items.data(game)["sentient"]["demands"].get(demand.get("kind"), "something of you") \
        .replace("{thing}", demand.get("thing_name", "thing"))
    return Card("It wants something", "a sentient thing's demand", "status/demand",
                [esc(want), "<dim>Until it is met, it may withhold its power or turn on its bearer.</>"])


def log_line(b, index: int) -> Card | None:
    """The rolls behind a line of the battle log ("d20 15 + 5 = 20 vs AC 16 — hit [flanking]"), if any."""
    rolls = getattr(b, "rolls", {}).get(index)
    if not rolls:
        return None
    return Card("The dice", "", "icon/more", [esc(r) for r in rolls]).fit()


def char_statuses(char, tables=None) -> list[tuple[str, Card]]:
    """The body's troubles outside a fight (hunger, cold, wounds...), each with the existing panel icon and a card."""
    from realmwalker.rules import body, health

    out: list[tuple[str, Card]] = []
    if char.exhaustion:
        out.append(("icon/tired", Card(f"Exhaustion {char.exhaustion}", "condition", "status/exhaustion",
                                       [f"Every d20 roll {2 * char.exhaustion} lower, speed {5 * char.exhaustion} feet "
                                        f"less. Six levels kill."], "A long rest takes one level away.")))
    if any((w.bleed and not w.bandaged) or w.internal for w in char.wounds):
        out.append(("icon/bleed", Card(*_WORDS["bleeding"][:1], "", "status/bleeding", [_WORDS["bleeding"][1]])))
    if any(w.infection > 0 for w in char.wounds):
        out.append(("icon/festering", Card(*_WORDS["festering"][:1], "", "status/festering", [_WORDS["festering"][1]])))
    if any(d.get("phase") == "sick" for d in char.diseases):
        out.append(("icon/sick", Card("Sick", "", "icon/sick", ["A sickness has hold: rest, warmth and a healer's "
                                                                "care help it pass."])))
    st = body.heat_stage(char.body_heat)
    if st:
        cold = char.body_heat < 50
        out.append(("icon/cold" if cold else "icon/hot",
                    Card(st[0].capitalize(), "", "icon/cold" if cold else "icon/hot",
                         ["Get to a fire, shelter, dry clothes." if cold else "Shade, water and rest."])))
    for key, icon, help_ in (("thirst", "thirst", "Drink: a waterskin (e), a stream, a well."),
                             ("hunger", "hunger", "Eat something (e), or cook at camp."),
                             ("fatigue", "tired", "Rest or sleep (r).")):
        st = body.stage(key, getattr(char, key))
        if st:
            out.append((f"icon/{icon}", Card(st[0].capitalize(), "", f"icon/{icon}", [help_])))
    st = health.pain_stage(char, tables)
    if st and st[0] != "hurting":
        out.append(("icon/pain", Card(st[0].capitalize(), "", "status/pain", [_WORDS["pain"][1]])))
    st = health.intox_stage(char)
    if st:
        out.append(("icon/drunk", Card(st[0].capitalize(), "", "status/drunk", [_WORDS["drunk"][1]])))
    st = body.stage("wet", char.wet)
    if st and char.wet >= 35:
        out.append(("icon/wet", Card(st[0].capitalize(), "", "icon/wet", ["Wet clothes chill fast: dry them by a fire."])))
    return out
