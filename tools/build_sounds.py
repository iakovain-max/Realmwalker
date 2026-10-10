"""Builds the game's sounds (assets/sounds) and its own music (assets/music) from free sound packs.

Every source is public domain (CC0): Kenney's RPG Audio, Interface Sounds and Impact Sounds; three packs from
OpenGameArt (artisticdude's RPG Sound Pack, rubberduck's 80 and 100 CC0 sound effects); and RandomMind's medieval
music. A few sounds are made here from nothing (plucked strings, chimes, a drum): the bow, the level-up, the journal.

What is done to every effect, so they sit together and never grate:
  * made mono, its silence trimmed (a click starts the instant you press), short fades so nothing clicks;
  * rumble below 60 Hz cut, and sharp highs softened where a sound is bright (coins, blades, paper);
  * brought to one loudness (the loudest tenth of a second of each is the same, BS.1770 weighting), with its peaks
    kept under -1 dB. How loud each kind of sound is then is set in data/sounds.json ("volume").
Music is brought to -18 LUFS (a quiet, even background level) and written as OGG Vorbis (~117 kbps).

Run:  .venv\\Scripts\\python.exe tools\\build_sounds.py   (downloads the packs into build/sound_packs the first time)
Then commit assets/sounds and assets/music. The game never builds them.
"""

from __future__ import annotations

import argparse
import io
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from realmwalker.audio import levels  # noqa: E402

SOUNDS = ROOT / "assets" / "sounds"
MUSIC = ROOT / "assets" / "music"
PACKS = ROOT / "build" / "sound_packs"

EFFECT_LUFS = -18.0  # the loudest 0.1 s of every effect (sharp ones may end a little lower, held by their peaks)
MUSIC_LUFS = -18.0
CEILING = 0.89  # -1 dBFS
RATE = 44100  # what the made sounds are written at

OGA = "https://opengameart.org/sites/default/files/"
SOURCES = {
    # name: (download, title, author, page)
    "kenney_rpg": ("https://kenney.nl/media/pages/assets/rpg-audio/8e99002d76-1677590336/kenney_rpg-audio.zip",
                   "RPG Audio", "Kenney (kenney.nl)", "https://kenney.nl/assets/rpg-audio"),
    "kenney_interface": ("https://kenney.nl/media/pages/assets/interface-sounds/fa43c1dd4d-1677589452/"
                         "kenney_interface-sounds.zip", "Interface Sounds", "Kenney (kenney.nl)",
                         "https://kenney.nl/assets/interface-sounds"),
    "kenney_impact": ("https://kenney.nl/media/pages/assets/impact-sounds/87b4ddecda-1677589768/kenney_impact-sounds.zip",
                      "Impact Sounds", "Kenney (kenney.nl)", "https://kenney.nl/assets/impact-sounds"),
    "oga_rpg": (OGA + "rpg_sound_pack.zip", "RPG Sound Pack", "artisticdude",
                "https://opengameart.org/content/rpg-sound-pack"),
    "oga_80": (OGA + "80-CC0-RPG-SFX_0.zip", "80 CC0 RPG SFX", "rubberduck",
               "https://opengameart.org/content/80-cc0-rpg-sfx"),
    "oga_100": (OGA + "100-CC0-SFX_0.zip", "100 CC0 SFX", "rubberduck", "https://opengameart.org/content/100-cc0-sfx"),
}
MUSIC_SOURCES = {
    # file: (download, title, page)
    "Exploration.wav": (OGA + "Exploration.wav", "Medieval: Exploration", "https://opengameart.org/content/medieval-exploration"),
    "harvestseason.wav": (OGA + "harvestseason.wav", "Medieval: Harvest Season",
                          "https://opengameart.org/content/medieval-harvest-season"),
    "Market_Day.wav": (OGA + "Market_Day.wav", "Medieval: Market Day", "https://opengameart.org/content/medieval-market-day"),
    "Rejoicing_0.mp3": (OGA + "Rejoicing_0.mp3", "Medieval: Rejoicing", "https://opengameart.org/content/medieval-rejoicing"),
    "Minstrel_Dance_0.mp3": (OGA + "Minstrel_Dance_0.mp3", "Medieval: Minstrel Dance",
                             "https://opengameart.org/content/medieval-minstrel-dance"),
    "battle_1.wav": (OGA + "battle_1.wav", "Medieval: Battle", "https://opengameart.org/content/medieval-battle"),
    "victory.wav": (OGA + "victory.wav", "Medieval: Victory Theme", "https://opengameart.org/content/medieval-victory-theme"),
    "defeat.wav": (OGA + "defeat.wav", "Medieval: Defeat Theme", "https://opengameart.org/content/medieval-defeat-theme"),
}
MUSIC_AUTHOR = "RandomMind (opengameart.org/users/randommind)"

# The tunes the game ships with, by mood folder (see data/music.json).
TUNES = {
    "title/exploration.ogg": "Exploration.wav",
    "travel/harvest_season.ogg": "harvestseason.wav",
    "town/market_day.ogg": "Market_Day.wav",
    "town/rejoicing.ogg": "Rejoicing_0.mp3",
    "tavern/minstrel_dance.ogg": "Minstrel_Dance_0.mp3",
    "combat/battle.ogg": "battle_1.wav",
    "victory/victory.ogg": "victory.wav",
    "defeat/defeat.ogg": "defeat.wav",
}

KR, KI, KM = "kenney_rpg:Audio/", "kenney_interface:Audio/", "kenney_impact:Audio/"
AD, R80, R100 = "oga_rpg:RPG Sound Pack/", "oga_80:", "oga_100:"

# Effect name -> its sources (each becomes name_1.wav, name_2.wav...) and how to treat them:
# lp: soften above this many Hz; hp: cut below (default 60); most: the longest it may be, in seconds.
EFFECTS: dict[str, dict] = {
    # --- the interface
    "ui_move": {"src": [KM + "impactWood_light_000.ogg", KM + "impactWood_light_002.ogg", KM + "impactWood_light_003.ogg"],
                "lp": 4000, "most": 0.2},
    "ui_click": {"src": [AD + "interface/interface1.wav"], "lp": 9000, "most": 0.2},
    "ui_toggle": {"src": [R80 + "wood_02.ogg"], "lp": 8000, "most": 0.2},
    "ui_open": {"src": [KR + "bookOpen.ogg"], "lp": 9000, "most": 0.3},
    "ui_close": {"src": [KR + "bookClose.ogg"], "lp": 9000, "most": 0.3},
    "ui_page": {"src": [KR + "bookFlip2.ogg", KR + "bookFlip3.ogg"], "lp": 6500, "most": 0.45},
    "ui_pack": {"src": [KR + "handleSmallLeather.ogg", KR + "handleSmallLeather2.ogg"], "lp": 8000, "most": 0.4},
    "ui_map": {"src": [R100 + "paper_02.ogg", R100 + "paper_04.ogg"], "lp": 6500, "most": 0.5},
    "ui_error": {"src": [KM + "impactSoft_medium_000.ogg", KM + "impactSoft_medium_002.ogg"], "hp": 40, "most": 0.25},
    # --- things in the world
    "coins": {"src": [KR + "handleCoins2.ogg", R80 + "item_coins_01.ogg", R80 + "item_coins_03.ogg"], "lp": 7500,
              "most": 0.6},
    "equip": {"src": [AD + "inventory/cloth-heavy.wav", AD + "inventory/armor-light.wav"], "lp": 8000, "most": 0.5},
    "drink": {"src": [AD + "inventory/bottle.wav"], "lp": 8000, "most": 0.5},
    "drop": {"src": [KR + "dropLeather.ogg"], "most": 0.45},
    "pickup": {"src": [KR + "cloth2.ogg", KR + "cloth3.ogg"], "lp": 8000, "most": 0.45},
    "chest": {"src": [R100 + "wooded_box_open.ogg"], "lp": 8000, "most": 0.5},
    "unlock": {"src": [R80 + "lock_01.ogg", R80 + "lock_02.ogg", R80 + "lock_03.ogg"], "lp": 8000, "most": 0.45},
    "trap": {"src": [R100 + "metal_02.ogg"], "lp": 8000, "most": 0.4},
    "fire": {"src": [R80 + "spell_fire_07.ogg"], "lp": 9000, "most": 0.9},
    "door": {"src": [KR + "doorOpen_1.ogg"], "lp": 8000, "most": 1.0},
    "death": {"src": [R100 + "gong_02.ogg"], "lp": 6000, "most": 2.5},
    # --- fights
    "battle_start": {"src": [AD + "battle/sword-unsheathe2.wav", AD + "battle/sword-unsheathe4.wav",
                             AD + "battle/sword-unsheathe5.wav"], "lp": 7000, "most": 0.6},
    "growl": {"src": [AD + "NPC/ogre/ogre1.wav", AD + "NPC/ogre/ogre3.wav", AD + "NPC/gutteral beast/mnstr2.wav",
                      AD + "NPC/gutteral beast/mnstr5.wav"], "lp": 7000, "most": 1.0},
    "moan": {"src": [AD + "NPC/shade/shade1.wav", AD + "NPC/shade/shade4.wav"], "lp": 7000, "most": 1.0},
    "swing": {"src": [AD + "battle/swing.wav", AD + "battle/swing2.wav", AD + "battle/swing3.wav"], "lp": 9000,
              "most": 0.3},
    "bite": {"src": [AD + "NPC/beetle/bite-small.wav", AD + "NPC/beetle/bite-small2.wav"], "lp": 7500, "most": 0.4},
    "spell": {"src": [AD + "battle/magic1.wav", R80 + "spell_01.ogg"], "lp": 8000, "most": 0.9},
    "spell_bolt": {"src": [R80 + "spell_02.ogg"], "lp": 8000, "most": 0.6},
    "hit_slash": {"src": [R80 + "blade_01.ogg", R80 + "blade_02.ogg", R80 + "blade_03.ogg"], "lp": 7500, "most": 0.4},
    "hit_pierce": {"src": [KR + "chop.ogg", R100 + "hit_01.ogg", R100 + "hit_02.ogg"], "lp": 8000, "most": 0.35},
    "hit_blunt": {"src": [KM + f"impactPunch_medium_00{i}.ogg" for i in range(5)], "hp": 45, "most": 0.45},
    "hit_crit": {"src": [KM + f"impactPunch_heavy_00{i}.ogg" for i in range(3)], "hp": 40, "most": 0.55},
    "deflect": {"src": [KM + f"impactPlate_light_00{i}.ogg" for i in range(5)], "lp": 7000, "most": 0.5},
    "burn": {"src": [R80 + "spell_fire_06.ogg", R80 + "spell_fire_07.ogg"], "lp": 9000, "most": 0.8},
    "frost": {"src": [KM + f"impactGlass_light_00{i}.ogg" for i in range(3)], "lp": 7000, "most": 0.5},
    "thunder": {"src": [R100 + "explosion.ogg"], "hp": 40, "lp": 8000, "most": 0.8},
    "acid": {"src": [AD + "inventory/bubble.wav", AD + "inventory/bubble2.wav"], "lp": 8000, "most": 0.5},
    "web": {"src": [AD + "NPC/slime/slime2.wav", AD + "NPC/slime/slime5.wav"], "lp": 8000, "most": 0.45},
    "fall": {"src": [KM + f"impactSoft_heavy_00{i}.ogg" for i in range(3)], "hp": 40, "most": 0.6},
}


# ---------------------------------------------------------------------------- getting the packs
def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Realmwalker sound builder"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def ensure_packs(folder: Path) -> None:
    for name, (url, *_rest) in SOURCES.items():
        dest = folder / name
        if dest.exists():
            continue
        print(f"Downloading {name} ...", flush=True)
        data = fetch(url)
        tmp = folder / f"{name}.partial"
        shutil.rmtree(tmp, ignore_errors=True)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for info in z.infolist():
                target = (tmp / info.filename).resolve()
                if tmp.resolve() not in target.parents or info.filename.startswith("__MACOSX"):
                    continue  # nothing outside the folder, and none of the Mac's shadow files
                if info.is_dir():
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(info))
        tmp.rename(dest)
    music = folder / "music"
    music.mkdir(parents=True, exist_ok=True)
    for name, (url, *_rest) in MUSIC_SOURCES.items():
        if not (music / name).exists():
            print(f"Downloading {name} ...", flush=True)
            data = fetch(url)
            (music / f"{name}.partial").write_bytes(data)
            (music / f"{name}.partial").rename(music / name)


def source_path(folder: Path, ref: str) -> Path:
    pack, rel = ref.split(":", 1)
    return folder / pack / rel


# ---------------------------------------------------------------------------- shaping a sound
def load_mono(path: Path) -> tuple[np.ndarray, int]:
    data, rate = sf.read(str(path), dtype="float64", always_2d=True)
    return data.mean(axis=1), int(rate)


def fft_filter(x: np.ndarray, rate: int, hp: float | None = None, lp: float | None = None) -> np.ndarray:
    """Gentle (second-order) high- and low-pass filters, without phase shift."""
    n = len(x)
    size = 1 << int(np.ceil(np.log2(max(2, n * 2))))
    spec = np.fft.rfft(x, size)
    f = np.fft.rfftfreq(size, 1 / rate)
    h = np.ones_like(f)
    if hp:
        h *= 1 / np.sqrt(1 + (hp / np.maximum(f, 1e-3)) ** 4)
    if lp:
        h *= 1 / np.sqrt(1 + (f / lp) ** 4)
    return np.fft.irfft(spec * h, size)[:n]


def trim(x: np.ndarray, rate: int, most: float | None) -> np.ndarray:
    pk = np.abs(x).max()
    if pk <= 0:
        return x
    loud = np.nonzero(np.abs(x) > pk * 10 ** (-40 / 20))[0]
    start = max(0, loud[0] - int(0.003 * rate))
    tail = np.nonzero(np.abs(x) > pk * 10 ** (-55 / 20))[0]
    end = min(len(x), tail[-1] + int(0.01 * rate))
    x = x[start:end]
    if most and len(x) > most * rate:
        x = x[: int(most * rate)]
        fade = int(min(0.08, most * 0.25) * rate)
        x[-fade:] *= np.linspace(1, 0, fade) ** 2
    return x


def limit(x: np.ndarray, rate: int, ceiling: float) -> np.ndarray:
    """A look-ahead peak limiter: the gain dips just before a peak (1.5 ms) and comes back over 60 ms, so a brief
    spike (the first edge of a coin, a page) is held under the ceiling without being clipped."""
    look = max(1, int(0.0015 * rate))
    need = np.minimum(1.0, ceiling / np.maximum(np.abs(x), 1e-12))
    g = need.copy()
    for k in range(1, look + 1):
        g[:-k] = np.minimum(g[:-k], need[k:])
    rise = 1.0 / (0.06 * rate)
    out = np.empty_like(g)
    level = 1.0
    for i, v in enumerate(g):
        level = v if v < level else min(v, level + (1.0 - level) * rise * 8)
        out[i] = level
    smooth = np.convolve(out, np.ones(look) / look)[: len(out)]
    return np.clip(x * np.minimum(smooth, out), -ceiling, ceiling)


def finish(x: np.ndarray, rate: int, *, loudness: float = EFFECT_LUFS) -> np.ndarray:
    """Every effect to one loudness: if its sharpest peak would pass the ceiling, up to 4 dB of it is limited away,
    and only beyond that does the whole sound stay quieter."""
    x = x - x.mean()
    fin, fout = int(0.002 * rate), int(0.015 * rate)
    if len(x) > fin + fout:
        x[:fin] *= np.linspace(0, 1, fin)
        x[-fout:] *= np.linspace(1, 0, fout)
    y = x * levels.gain_to(levels.short_peak(x, rate), loudness, levels.peak(x), ceiling=1e9, most=30.0)
    over = levels.peak(y) / CEILING
    if over > 1.0:
        y /= max(1.0, over / 10 ** (4 / 20))  # no more than 4 dB for the limiter
        y = limit(y, rate, CEILING)
    return y


def write_wav(path: Path, x: np.ndarray, rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.clip(x, -1, 1).astype(np.float32), rate, subtype="PCM_16")


def shape(path: Path, spec: dict) -> tuple[np.ndarray, int]:
    x, rate = load_mono(path)
    x = fft_filter(x, rate, hp=spec.get("hp", 60), lp=spec.get("lp"))
    x = trim(x, rate, spec.get("most"))
    return finish(x, rate), rate


# ---------------------------------------------------------------------------- sounds made from nothing
def note(name: str) -> float:
    names = {"C": -9, "C#": -8, "D": -7, "D#": -6, "E": -5, "F": -4, "F#": -3, "G": -2, "G#": -1, "A": 0, "A#": 1, "B": 2}
    pitch, octave = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((names[pitch] + 12 * (octave - 4)) / 12)


def pluck(freq: float, seconds: float, rng: np.random.Generator, *, bright: float = 0.5, damp: float = 0.996) -> np.ndarray:
    """A plucked string (Karplus-Strong): a burst of noise going round a delay line, softened each time round."""
    n = max(2, int(round(RATE / freq - 0.5)))
    total = int(seconds * RATE)
    buf = rng.uniform(-1, 1, n)
    for _ in range(int(round((1 - bright) * 6))):
        buf = 0.5 * (buf + np.roll(buf, 1))
    out = np.zeros(total + n + 1)
    out[1:n + 1] = buf - buf.mean()
    i = n + 1
    while i < total:
        k = min(n, total - i)
        out[i:i + k] = damp * 0.5 * (out[i - n:i - n + k] + out[i - n - 1:i - n - 1 + k])
        i += k
    return out[1:total + 1]


def room(x: np.ndarray, rng: np.random.Generator, wet: float = 0.14, seconds: float = 0.7) -> np.ndarray:
    """A little air around a made sound: a short tail of decaying noise, mixed in quietly."""
    t = np.arange(int(seconds * RATE)) / RATE
    ir = rng.normal(0, 1, len(t)) * np.exp(-t / (seconds / 6.9))
    ir = fft_filter(ir, RATE, lp=5000)
    ir /= np.sqrt((ir ** 2).sum())
    size = 1 << int(np.ceil(np.log2(len(x) + len(ir))))
    tail = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[: len(x) + len(ir)]
    out = np.zeros(len(tail))
    out[: len(x)] += x
    return out + wet * tail / max(1e-9, np.abs(tail).max()) * np.abs(x).max()


def strum(notes: list[str], gap: float, ring: float, rng, *, bright: float = 0.45, last_ring: float | None = None) -> np.ndarray:
    total = int((gap * (len(notes) - 1) + (last_ring or ring) + 0.1) * RATE)
    out = np.zeros(total)
    for i, nm in enumerate(notes):
        dur = last_ring if (last_ring and i == len(notes) - 1) else ring
        s = pluck(note(nm), dur, rng, bright=bright, damp=0.997)
        s *= np.linspace(1, 0, len(s)) ** 0.6
        at = int(i * gap * RATE)
        out[at:at + len(s)] += s * (0.85 + 0.15 * i / max(1, len(notes) - 1))
    return out


def chime(freqs: list[tuple[float, float]], seconds: float) -> np.ndarray:
    """A soft bell: a few sine partials (frequency, delay) with a gentle attack and a long fade."""
    t = np.arange(int(seconds * RATE)) / RATE
    out = np.zeros(len(t))
    for f, at in freqs:
        tt = np.clip(t - at, 0, None)
        env = (1 - np.exp(-tt / 0.008)) * np.exp(-tt / (seconds / 4)) * (t >= at)
        for ratio, amp in ((1.0, 1.0), (2.0, 0.35), (3.01, 0.12), (4.2, 0.05)):
            out += amp * env * np.sin(2 * np.pi * f * ratio * tt)
    return out


def drum(seconds: float = 0.7, low: float = 46, high: float = 120) -> np.ndarray:
    """A deep drum: a pitch that falls fast, and the slap of the skin."""
    t = np.arange(int(seconds * RATE)) / RATE
    f = low + (high - low) * np.exp(-t / 0.05)
    body = np.sin(2 * np.pi * np.cumsum(f) / RATE) * np.exp(-t / 0.2)
    rng = np.random.default_rng(7)
    slap = fft_filter(rng.normal(0, 1, len(t)), RATE, lp=1500, hp=200) * np.exp(-t / 0.012) * 0.25
    return body + slap


def made_sounds(folder: Path) -> dict[str, list[np.ndarray]]:
    rng = np.random.default_rng(1234)
    out: dict[str, list[np.ndarray]] = {}
    # The bow: a low string let go, and the whisper of the arrow leaving.
    bows = []
    for f0 in (98.0, 110.0):
        s = pluck(f0, 0.45, rng, bright=0.8, damp=0.985)
        s *= np.exp(-np.arange(len(s)) / RATE / 0.12)
        hiss = fft_filter(rng.normal(0, 1, len(s)), RATE, hp=1500, lp=5000) * \
            np.exp(-np.abs(np.arange(len(s)) / RATE - 0.05) / 0.03) * 0.12
        bows.append(fft_filter(s + hiss, RATE, hp=70, lp=6000))
    out["bow"] = bows
    out["levelup"] = [room(strum(["A3", "C#4", "E4", "A4", "C#5"], 0.075, 1.4, rng, last_ring=1.9), rng)]
    out["quest"] = [room(strum(["E4", "A4"], 0.11, 1.0, rng), rng)]
    out["quest_done"] = [room(strum(["D4", "F#4", "A4", "D5"], 0.08, 1.2, rng, last_ring=1.6), rng)]
    out["heal"] = [room(chime([(note("E5"), 0.0), (note("B5"), 0.09)], 1.1), rng, wet=0.2)]
    out["buff"] = [room(chime([(note("G5"), 0.0)], 0.9), rng, wet=0.2)]
    rumble = drum()
    gap = int(0.17 * RATE)
    two = np.zeros(len(rumble) + gap)
    two[: len(rumble)] += rumble * 0.6
    two[gap:] += rumble
    out["danger"] = [two]
    # A hit of magic that is neither fire nor ice: a dull thud with a ringing edge.
    thud = drum(0.35, 70, 220) * 0.8
    ring = chime([(note("D#5"), 0.0)], 0.35) * 0.35
    out["magic_hit"] = [thud + ring[: len(thud)]]
    # Going down (or up) a stair: four footsteps, fading.
    steps = []
    for i in range(4):
        s, r = load_mono(folder / "kenney_rpg" / "Audio" / f"footstep0{i}.ogg")
        if r != RATE:
            s = np.interp(np.arange(int(len(s) * RATE / r)) * r / RATE, np.arange(len(s)), s)
        steps.append(s)
    walk = np.zeros(int(0.3 * RATE * 3) + max(len(s) for s in steps))
    for i, s in enumerate(steps):
        at = int(0.3 * RATE * i)
        walk[at:at + len(s)] += s * (1.0 - 0.18 * i)
    out["stairs"] = [fft_filter(walk, RATE, hp=60, lp=7000)]
    return out


# ---------------------------------------------------------------------------- music
def build_music(folder: Path) -> None:
    for rel, name in TUNES.items():
        data, rate = sf.read(str(folder / "music" / name), dtype="float32", always_2d=True)
        if data.shape[1] == 1:
            data = np.repeat(data, 2, axis=1)
        data = data[:, :2]
        lufs = levels.integrated(data, rate)
        g = levels.gain_to(lufs, MUSIC_LUFS, levels.peak(data), ceiling=0.95, most=4.0)
        data = np.ascontiguousarray(data * g, dtype=np.float32)
        out = MUSIC / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        # Vorbis is written a little at a time: one huge write overflows the encoder's stack on Windows.
        with sf.SoundFile(str(out), "w", rate, 2, format="OGG", subtype="VORBIS", compression_level=0.6) as f:
            for i in range(0, len(data), 8192):
                f.write(data[i:i + 8192])
        print(f"  {rel:32s} {len(data) / rate:6.1f} s   {lufs:6.1f} -> {levels.integrated(data, rate):6.1f} LUFS  "
              f"{out.stat().st_size // 1024} KB")


# ---------------------------------------------------------------------------- credits
def write_credits() -> None:
    lines = ["Sounds in Realmwalker", "=====================", "",
             "Every sound here is in the public domain (Creative Commons CC0 1.0,",
             "https://creativecommons.org/publicdomain/zero/1.0/). Thank you to their makers:", ""]
    for _name, (_url, title, author, page) in SOURCES.items():
        lines.append(f"  {title} by {author}  -  {page}")
    lines += ["", "The bow, the level-up harp, the journal's notes, the chimes, the drum and the magic thud were made",
              "for Realmwalker by tools/build_sounds.py (also CC0).", "",
              "Each sound was trimmed, softened and brought to the same loudness by tools/build_sounds.py.", ""]
    (SOUNDS / "CREDITS.txt").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    lines = ["Music in Realmwalker", "====================", "",
             f"The tunes that come with the game are by {MUSIC_AUTHOR},",
             "in the public domain (Creative Commons CC0 1.0). Thank you!", ""]
    for rel, name in TUNES.items():
        _url, title, page = MUSIC_SOURCES[name]
        lines.append(f"  {rel:30s} {title}  -  {page}")
    lines += ["", "Each was brought to the same loudness (-18 LUFS) by tools/build_sounds.py.",
              "Your own music goes in the 'music' folder next to the game, not here (see the README there).", ""]
    (MUSIC / "CREDITS.txt").write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--packs", default=str(PACKS), help="folder for the downloaded packs")
    parser.add_argument("--no-music", action="store_true", help="only the effects")
    args = parser.parse_args(argv)
    folder = Path(args.packs)
    folder.mkdir(parents=True, exist_ok=True)
    ensure_packs(folder)

    for old in SOUNDS.glob("*.wav"):
        old.unlink()
    print("Effects:")
    for name, spec in EFFECTS.items():
        for i, ref in enumerate(spec["src"], 1):
            x, rate = shape(source_path(folder, ref), spec)
            write_wav(SOUNDS / f"{name}_{i}.wav", x, rate)
        print(f"  {name:14s} {len(spec['src'])} file(s)")
    for name, clips in made_sounds(folder).items():
        for i, x in enumerate(clips, 1):
            x = fft_filter(x, RATE, hp=50)
            write_wav(SOUNDS / f"{name}_{i}.wav", finish(trim(x, RATE, None), RATE), RATE)
        print(f"  {name:14s} {len(clips)} made")
    if not args.no_music:
        print("Music:")
        build_music(folder)
    write_credits()
    print("\nDone. Commit assets/sounds and assets/music.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
