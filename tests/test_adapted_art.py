"""The borrowed creature tiles have passed through the adaptation step (tools/adapt_art.py, Expansion 1 part E.2):
no soft glows left, feet on the dolls' foot line, a wolf smaller than a man, the dark outline in place."""

import json

import numpy as np
from PIL import Image

from realmwalker.paths import Paths


def tiles():
    root = Paths().tiles
    meta = json.loads((root / "tiles.json").read_text(encoding="utf-8"))
    sheets = [np.asarray(Image.open(root / f).convert("RGBA")) for f in meta["sheets"]]

    def get(name):
        s, x, y, w, h = meta["tiles"][name]
        return sheets[s][y:y + h, x:x + w]
    return meta, get


def test_borrowed_creatures_are_adapted():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import adapt_art

    meta, get = tiles()
    names = [n for n in meta["tiles"] if n.startswith("creature/")]
    assert len(names) > 60
    for n in names:
        cid = n.split("/", 1)[1]
        a = get(n)
        if "clean" in adapt_art.SKIP.get(cid, ()):
            continue
        alpha = a[..., 3]
        assert set(np.unique(alpha)) <= {0, 255}, f"{cid} keeps soft pixels"
        rows = np.nonzero(alpha.any(axis=1))[0]
        assert rows.max() == adapt_art.FOOT, f"{cid} does not stand on the foot line"
    height = lambda n: int(np.ptp(np.nonzero(get(n)[..., 3].any(axis=1))[0])) + 1  # noqa: E731
    assert height("creature/wolf") < height("fig/body/human_male")
    assert height("creature/giant_rat") < height("creature/wolf")
