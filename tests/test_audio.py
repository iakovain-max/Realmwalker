"""Sound and music, headless: the shipped files, loudness, choosing music by mood, crossfades, the interface sounds
the screens ask for, and the sounds of a fight. Nothing here opens a sound device."""

import re
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from realmwalker.audio import cues, levels
from realmwalker.audio.backend import SilentBackend
from realmwalker.audio.bank import SoundBank, read_wav
from realmwalker.audio.engine import Audio, level
from realmwalker.audio.music import LevelStore, MusicLibrary, MusicPlayer
from realmwalker.audio.watch import GameWatch
from realmwalker.config import Settings
from realmwalker.core.rng import RNG
from realmwalker.paths import Paths
from realmwalker.ui.input import KeyEvent, MouseEvent

ROOT = Path(__file__).resolve().parent.parent
SOUNDS = ROOT / "assets" / "sounds"
MUSIC = ROOT / "assets" / "music"


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def make_audio(data, tmp_path=None, clock=None, settings=None, user=None):
    clock = clock or Clock()
    bank = SoundBank(data["sounds.json"], SOUNDS)
    library = MusicLibrary(data["music.json"], MUSIC, user)
    return Audio(bank=bank, library=library, settings=settings or Settings(), clock=clock, rng=RNG(5, "test"),
                 backend=SilentBackend(clock))


# ---------------------------------------------------------------------------- the files
def test_every_effect_file_exists_reads_and_sits_at_one_loudness(data):
    """Every sound in data/sounds.json is there, short, never clipped, and built to the same loudness (so the volume
    numbers in the data are all that set how loud each kind is)."""
    for sid, d in data["sounds.json"]["sounds"].items():
        if sid.startswith("_"):
            continue
        for rel in d["files"]:
            path = SOUNDS / rel
            assert path.exists(), f"{sid}: {rel} is missing (run tools/build_sounds.py)"
            clip = read_wav(path)
            assert clip.samples.shape[1] == 1, rel
            assert 0.03 < clip.seconds < 2.5, (rel, clip.seconds)
            pk = float(np.abs(clip.samples).max())
            assert 0.05 < pk <= 0.9, (rel, pk)
            loud = levels.short_peak(clip.samples, clip.rate)
            assert -22.5 < loud < -17.5, (rel, loud)  # (a sharp sound held back by its peaks comes out a little quieter)


def test_no_unused_sound_files(data):
    used = {rel for d in data["sounds.json"]["sounds"].values() if isinstance(d, dict) for rel in d["files"]}
    on_disk = {p.name for p in SOUNDS.glob("*.wav")}
    assert not on_disk - used, sorted(on_disk - used)


def test_every_sound_the_code_asks_for_exists(data):
    """Any name in audio.play("..."), audio.ui("..."), game.cue("..."), sound_open/close = "...", or the fight's
    sound tables must be in data/sounds.json."""
    known = set(data["sounds.json"]["sounds"])
    pattern = re.compile(r"""(?:\.play|\.ui|\.cue|sound_open\s*=|sound_close\s*=)\(?\s*["']([a-z_]+)["']""")
    asked = set()
    for path in (ROOT / "realmwalker").rglob("*.py"):
        asked |= set(pattern.findall(path.read_text(encoding="utf-8")))
    asked |= set(cues.HIT_BY_TYPE.values()) | set(cues.ZONE_SOUNDS.values())
    asked |= {"swing", "bite", "bow", "throw", "spell_bolt", "spell", "deflect", "hit_crit", "fall", "heal", "buff",
              "moan", "growl", "coins", "equip", "levelup", "ui_move", "ui_click", "ui_toggle", "ui_error"}
    assert asked, "the pattern found nothing"
    assert not asked - known, sorted(asked - known)


def test_shipped_music_is_in_mood_folders_and_evened_out(data):
    moods = data["music.json"]["moods"]
    tunes = sorted(MUSIC.rglob("*.ogg"))
    assert tunes, "no music shipped (run tools/build_sounds.py)"
    for tune in tunes:
        mood = tune.parent.relative_to(MUSIC).as_posix()
        assert mood.split("/")[0] in moods, f"{tune.name} is in {mood}, which is not a mood in data/music.json"
        with sf.SoundFile(str(tune)) as f:
            assert f.channels == 2 and f.frames > f.samplerate * 20
            whole = f.read(dtype="float32", always_2d=True)
        assert -19.0 < levels.integrated(whole, f.samplerate) < -17.0, tune.name
    assert (MUSIC / "CREDITS.txt").exists() and (SOUNDS / "CREDITS.txt").exists()


def test_title_music_ships():
    assert list((MUSIC / "title").glob("*.ogg"))


# ---------------------------------------------------------------------------- loudness
def test_loudness_matches_the_standard():
    rate = 48000
    t = np.arange(rate * 3) / rate
    sine = np.sin(2 * np.pi * 997 * t)
    assert abs(levels.integrated(sine, rate) - -3.01) < 0.05  # BS.1770's own calibration tone
    assert abs(levels.integrated(np.stack([sine, sine], 1) * 0.1, rate) - -20.0) < 0.05
    assert levels.integrated(np.zeros(rate), rate) < levels.SILENT
    g = levels.gain_to(-30.0, -18.0, 0.5, ceiling=0.95)
    assert abs(g - 0.95 / 0.5) < 1e-9  # louder by 12 dB would clip: the peak holds it back


def test_volume_curve():
    assert level(0) == 0 and level(10) == 1.0
    assert 0.3 < level(5) < 0.4  # half way sounds about half as loud
    assert level(99) == 1.0 and level(-3) == 0


# ---------------------------------------------------------------------------- choosing music
def write_tune(path: Path, seconds: float = 2.0, rate: int = 8000, amp: float = 0.2) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    t = np.arange(int(seconds * rate)) / rate
    tone = (amp * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    sf.write(str(path), np.stack([tone, tone], 1), rate)
    return path


def test_moods_fall_back_from_kind_to_mood_to_fallback(data, tmp_path):
    user = tmp_path / "music"
    lib = MusicLibrary(data["music.json"], MUSIC, user)
    assert lib.resolve("travel/desert")[0] == "travel"  # no desert tunes: the travel ones
    assert lib.resolve("tavern")[0] == "tavern"
    assert lib.resolve("dungeon/crypt") == ("", [])  # nothing shipped for under the ground: quiet
    assert lib.resolve("boss/dragon")[0] == "combat"  # a dragon with no music of its own: the fight's
    assert lib.resolve("death")[0] == "defeat"
    assert lib.resolve(None) == ("", [])
    mine = write_tune(user / "travel" / "desert" / "dunes.wav")
    lib.scan()
    assert lib.resolve("travel/desert") == ("travel/desert", [mine])
    assert lib.resolve("travel/forest")[0] == "travel"
    # The player's tunes for a mood replace the game's.
    mine2 = write_tune(user / "title" / "my_title.wav")
    lib.scan()
    assert lib.resolve("title") == ("title", [mine2])
    assert lib.count("title") == (1, 1)


def test_music_folders_are_made_with_a_readme(data, tmp_path):
    user = tmp_path / "music"
    lib = MusicLibrary(data["music.json"], MUSIC, user)
    lib.make_folders()
    assert (user / "combat" / "undead").is_dir() and (user / "travel" / "forest").is_dir()
    text = (user / "README.txt").read_text(encoding="utf-8")
    assert "combat" in text and "travel" in text and ".mp3" in text


def player_for(data, tmp_path, clock):
    user = tmp_path / "music"
    lib = MusicLibrary(data["music.json"], None, user)
    backend = SilentBackend(clock)
    player = MusicPlayer(lib, backend, clock, RNG(3, "music"), LevelStore(tmp_path / "levels.json", None))
    return player, lib, user


def run(player, clock, seconds: float, step: float = 0.05) -> None:
    for _ in range(int(seconds / step)):
        clock.t += step
        player.tick()


def test_music_crossfades_between_moods_and_resumes(data, tmp_path):
    clock = Clock()
    player, lib, user = player_for(data, tmp_path, clock)
    write_tune(user / "travel" / "road.wav", seconds=30)
    write_tune(user / "combat" / "fight.wav", seconds=30)
    lib.scan()
    player.want("travel/forest")
    run(player, clock, 10.0)  # the first tune comes after a few quiet seconds, then fades in
    assert player.current is not None and player.current.path.name == "road.wav"
    assert player.current.fade == 1.0
    played = player.current.read
    player.want("combat/people")
    run(player, clock, 0.1)
    assert player.current.path.name == "fight.wav"
    assert player.fading and player.fading[0].path.name == "road.wav" and player.fading[0].target == 0
    run(player, clock, 5.0)
    assert not player.fading  # faded out and closed
    player.want("travel/hills")  # back within four minutes: the road tune carries on where it was
    run(player, clock, 0.1)
    assert player.current.path.name == "road.wav" and player.current.read >= played * 0.5
    # Measured once and remembered.
    assert (tmp_path / "levels.json").exists()


def test_music_carries_on_across_moods_that_share_tunes(data, tmp_path):
    clock = Clock()
    player, lib, user = player_for(data, tmp_path, clock)
    write_tune(user / "travel" / "road.wav", seconds=30)
    lib.scan()
    player.want("travel/forest")
    run(player, clock, 10.0)
    deck = player.current
    player.want("travel/desert")
    run(player, clock, 1.0)
    assert player.current is deck and not player.fading


def test_once_moods_play_once_and_gaps_wait(data, tmp_path):
    clock = Clock()
    player, lib, user = player_for(data, tmp_path, clock)
    write_tune(user / "victory" / "win.wav", seconds=2)
    write_tune(user / "travel" / "road.wav", seconds=2)
    lib.scan()
    player.want("victory")
    run(player, clock, 5.0)
    assert player.current is None and player.once_done
    assert player.started.count("win.wav") == 1
    player.want("travel")
    run(player, clock, 12.0)  # the first quiet, then the tune, then the gap between tunes (40 s or more)
    assert player.started.count("road.wav") == 1 and player.current is None and player.wait_until is not None


def test_a_single_tune_without_gaps_goes_round(data, tmp_path):
    clock = Clock()
    player, lib, user = player_for(data, tmp_path, clock)
    write_tune(user / "title" / "theme.wav", seconds=1.5)
    lib.scan()
    player.want("title")
    run(player, clock, 6.0)
    assert player.current is not None and player.current.loop and player.started == ["theme.wav"]


def test_a_broken_tune_is_skipped(data, tmp_path):
    clock = Clock()
    player, lib, user = player_for(data, tmp_path, clock)
    bad = user / "combat" / "broken.ogg"
    bad.parent.mkdir(parents=True)
    bad.write_bytes(b"not music at all")
    good = write_tune(user / "combat" / "good.wav")
    lib.scan()
    player.want("combat")
    run(player, clock, 1.0)
    assert bad in player.bad or player.current.path == good
    run(player, clock, 5.0)
    assert not player.broken


def test_preview_overrides_the_mood(data, tmp_path):
    clock = Clock()
    player, lib, user = player_for(data, tmp_path, clock)
    write_tune(user / "combat" / "fight.wav", seconds=30)
    lib.scan()
    player.want("title")
    player.preview = "combat"
    run(player, clock, 1.0)
    assert player.current.path.name == "fight.wav"
    player.preview = None
    run(player, clock, 4.0)
    assert player.current is None  # no title tunes in this folder: quiet again


def test_shipped_tunes_play_headless(data, tmp_path):
    clock = Clock()
    audio = make_audio(data, clock=clock)
    audio.want_music("title")
    for _ in range(10):
        clock.t += 0.1
        audio.update()
    assert audio.music.started == ["exploration.ogg"]
    assert audio.music.now_playing() == "exploration"


# ---------------------------------------------------------------------------- effects
def test_effects_respect_volume_cooldown_and_priority(data):
    clock = Clock()
    settings = Settings()
    audio = make_audio(data, clock=clock, settings=settings)
    assert audio.play("swing")
    assert not audio.play("swing")  # a moment later: too soon
    clock.t += 0.1
    assert audio.play("swing")
    assert not audio.play("no_such_sound") and "no_such_sound" in audio.unknown
    settings.effects_volume = 0
    clock.t += 1
    assert not audio.play("swing")
    # One interface sound per frame: the most important.
    audio.ui("ui_click")
    audio.ui("ui_open")
    audio.ui("ui_move")
    assert audio.pending == "ui_open"
    audio.update()
    assert audio.history[-1] == "ui_open" and audio.pending is None
    # Delayed sounds wait as silence in front of the sound itself.
    settings.effects_volume = 8
    assert audio.play("hit_blunt", delay=0.5)
    voice = audio.voices[-1][1]
    assert voice.queued_seconds() > 0.5


def test_mute_and_background(data):
    settings = Settings()
    audio = make_audio(data, settings=settings)
    assert audio.backend.master == level(settings.volume)
    settings.muted = True
    audio.apply_settings()
    assert audio.backend.master == 0
    settings.muted = False
    settings.sound_in_background = False
    audio.set_focus(False)
    assert audio.backend.master == 0
    audio.set_focus(True)
    assert audio.backend.master > 0


def test_settings_volumes_are_kept_in_range(home):
    home.mkdir(parents=True, exist_ok=True)
    path = home / "settings.json"
    path.write_text('{"volume": 40, "music_volume": -2, "effects_volume": 5, "muted": true}', encoding="utf-8")
    s = Settings.load(path)
    assert (s.volume, s.music_volume, s.effects_volume, s.muted) == (10, 0, 5, True)


def test_player_music_folder_is_in_the_home_folder_for_tests(home):
    assert Paths(home).music == Path(home) / "music"


# ---------------------------------------------------------------------------- the app and its screens
def test_screens_ask_for_sounds_and_music(make_app):
    from realmwalker.ui.screens.settings_screen import SettingsScreen

    app = make_app()
    assert app.music_mood() == "title"
    app.handle_event(KeyEvent("s"))
    assert isinstance(app.top, SettingsScreen) and app.audio.pending == "ui_open"
    app.update()
    app.handle_event(KeyEvent("down"))
    assert app.audio.pending == "ui_move"
    app.update()
    app.handle_event(KeyEvent("escape"))
    assert app.audio.pending == "ui_close"
    app.update()
    assert app.music_mood() == "title"


def test_settings_change_volumes_and_mute(make_app):
    from realmwalker.ui.screens.settings_screen import SettingsScreen

    app = make_app()
    screen = SettingsScreen(app)
    app.push(screen)
    screen.selected = next(i for i, o in enumerate(screen.options) if o.label == "Music")
    before = app.settings.music_volume
    app.handle_event(KeyEvent("left"))
    assert app.settings.music_volume == before - 1
    assert app.audio.music.volume == level(before - 1)
    app.handle_event(KeyEvent("m", ctrl=True))
    assert app.settings.muted and app.audio.backend.master == 0
    app.handle_event(KeyEvent("m", ctrl=True))
    assert not app.settings.muted


def test_clicking_a_button_clicks(make_app):
    import tcod.console

    app = make_app()
    con = tcod.console.Console(120, 45, order="F")
    app.render(con)
    region = next(r for r in app.regions if r.action is not None)
    app.handle_event(MouseEvent("click", region.x, region.y))
    assert app.audio.pending is not None


def test_music_page_lists_moods_and_listens(make_app):
    import tcod.console

    from realmwalker.ui.screens.music import MusicScreen

    app = make_app()
    screen = MusicScreen(app)
    app.push(screen)
    for size in ((80, 30), (160, 50)):
        app.render(tcod.console.Console(*size, order="F"))
    assert app.error_count == 0
    app.handle_event(KeyEvent("enter"))
    assert app.audio.music.preview == "title"
    app.handle_event(KeyEvent("o"))  # headless: never opens a folder window, just says where it is
    assert not app.open_folder(app.paths.music)
    app.handle_event(KeyEvent("escape"))
    assert app.audio.music.preview is None


def test_game_music_follows_the_place(make_app, data):
    app = make_app()
    game = _small_game(app)
    from realmwalker.ui.screens.game_screen import GameScreen

    screen = GameScreen(app, game)
    mood = screen.music()
    assert mood.startswith("travel/")
    assert mood.split("/")[1] in data["music.json"]["moods"]["travel"]["kinds"]


def _small_game(app):
    from realmwalker.game.state import new_game
    from realmwalker.world.generator import WorldGenerator, WorldOptions

    world = WorldGenerator(WorldOptions("Soundland", 7, "small"), app.tables).generate()
    return new_game(world, app.tables)


# ---------------------------------------------------------------------------- what the game says
class Member:
    def __init__(self) -> None:
        self.level = 1
        self.money = 100
        self.equipped = {"main_hand": 3}


class FakeGame:
    def __init__(self) -> None:
        self.party = [Member()]
        self.cues: list[str] = []


def test_the_game_is_listened_to(data):
    clock = Clock()
    audio = make_audio(data, clock=clock)
    ears = GameWatch()
    g = FakeGame()
    g.cues.append("chest")
    ears.hear(g, audio)  # a game just loaded: nothing from before plays
    assert not audio.history and not g.cues
    g.cues.append("chest")
    g.party[0].money -= 10
    ears.hear(g, audio)
    audio.update()
    assert "chest" in audio.history and "coins" in audio.history
    clock.t += 2
    g.party[0].level = 2
    g.party[0].equipped = {"main_hand": 4}
    ears.hear(g, audio)
    audio.update()
    assert "levelup" in audio.history and "equip" in audio.history


# ---------------------------------------------------------------------------- the sounds of a fight
def test_fight_events_have_sounds():
    melee = {"kind": "attack", "hit": True, "melee": True, "how": "melee", "weapon": "longsword"}
    assert cues.battle_sounds(melee) == [("start", "swing")]
    assert cues.battle_sounds({**melee, "weapon": "bite"}) == [("start", "bite")]
    bow = {"kind": "attack", "hit": False, "melee": False, "how": "ranged", "weapon": "shortbow", "armoured": True}
    assert cues.battle_sounds(bow) == [("start", "bow"), ("impact", "deflect")]
    assert cues.battle_sounds({"kind": "damage", "dtype": "fire", "crit": True}) == [("impact", "burn"), ("impact", "hit_crit")]
    assert cues.battle_sounds({"kind": "cast", "area": [(1, 1)], "effect": "save", "dtype": "thunder"}) == \
        [("start", "spell"), ("impact", "thunder")]
    assert cues.battle_sounds({"kind": "dead", "who": 3}) == [("impact", "fall")]
    assert cues.battle_sounds({"kind": "move", "path": []}) == []
    times = cues.timeline([melee, {"kind": "damage", "dtype": "slashing"}, melee], 10.0)
    assert times[0] == (10.0, "swing") and times[1] == (10.3 + 0.14, "hit_slash") and times[2][0] > times[0][0]


def test_fight_music_by_foe():
    class F:
        def __init__(self, kind):
            self.kind = kind

    assert cues.combat_mood([F("beast"), F("beast"), F("humanoid")], False) == "combat/beasts"
    assert cues.combat_mood([F("humanoid")], True) == "boss"
    assert cues.combat_mood([F("dragon")], False) == "boss/dragon"
    assert cues.foes_cry(["undead"]) == "moan" and cues.foes_cry(["humanoid"]) is None


def test_a_fight_makes_its_sounds(make_app):
    """A whole fight, headless: blades drawn as it opens, blows as they land, and the fight's music."""
    from realmwalker.game.encounters import make_encounter
    from realmwalker.game.fight import start_battle
    from realmwalker.ui.screens.battle import BattleScreen

    app = make_app()
    game = _small_game(app)
    app.start_game(game)
    app.update()
    enc = make_encounter(game, "bandits", game.world.rng.child("sound-test"))
    start_battle(game, enc.creatures, "Bandits!", title="Bandits")
    screen = BattleScreen(app, game)
    app.push(screen)
    assert "battle_start" in app.audio.history
    assert app.music_mood().startswith("combat/")
    for f in game.battle.side("party"):
        f.auto = True
    for _ in range(400):
        if game.battle.outcome is not None:
            break
        app.update()
    heard = set(app.audio.history)
    assert heard & {"swing", "bow", "throw", "spell", "spell_bolt"}, heard
    assert app.error_count == 0


def test_added_tunes_take_over_from_a_looping_one(data, tmp_path):
    """The game's one title tune goes round and round; the player adds their own and looks for new music: theirs
    takes over."""
    clock = Clock()
    shipped, user = tmp_path / "shipped", tmp_path / "music"
    write_tune(shipped / "title" / "old.wav", seconds=1.5)
    lib = MusicLibrary(data["music.json"], shipped, user)
    player = MusicPlayer(lib, SilentBackend(clock), clock, RNG(3, "music"), LevelStore(None, shipped))
    player.want("title")
    run(player, clock, 3.0)
    assert player.current.loop and player.current.path.name == "old.wav"
    write_tune(user / "title" / "new.wav", seconds=30)
    lib.scan()
    player.recheck = True
    run(player, clock, 3.0)
    assert player.current.path.name == "new.wav"
    player.stop()
