"""Packages the game for friends (run by Build_For_Friends.bat).

1. Runs the tests (refuses to build a broken game).
2. Builds dist/Realmwalker/Realmwalker.exe with PyInstaller (no Python needed on their PC).
3. Adds README_FRIENDS.txt and a config.json with the debug console switched off.
4. Zips it all into Realmwalker.zip.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "Realmwalker"
ZIP = ROOT / "Realmwalker.zip"


def step(text: str) -> None:
    print(f"\n=== {text} ===", flush=True)


def make_icon() -> Path:
    """A simple icon: a gold '@' on a dark tile, drawn with the game's own font."""
    from PIL import Image, ImageDraw, ImageFont

    icon = ROOT / "assets" / "icon.ico"
    if icon.exists():
        return icon
    font = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "DejaVuSansMono.ttf"), 200)
    img = Image.new("RGBA", (256, 256), (16, 15, 20, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([8, 8, 247, 247], outline=(104, 88, 62, 255), width=10)
    draw.text((128, 128), "@", font=font, fill=(232, 196, 120, 255), anchor="mm")
    img.save(icon, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return icon


def main() -> int:
    python = sys.executable

    step("Running the tests")
    if subprocess.call([python, "-m", "pytest", "-q"], cwd=ROOT) != 0:
        print("Tests failed, so the game was not packaged.")
        return 1

    step("Building Realmwalker.exe (a few minutes)")
    make_icon()
    if subprocess.call([python, "-m", "PyInstaller", "realmwalker.spec", "--noconfirm", "--clean"], cwd=ROOT) != 0:
        return 1

    step("Adding the readme and settings")
    shutil.copy2(ROOT / "README_FRIENDS.txt", DIST / "README_FRIENDS.txt")
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    config["debug_console"] = False
    config["player2_base_url"] = ""
    (DIST / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    step("Checking that the packaged game starts")
    check_home = ROOT / "build" / "smoke_home"
    shutil.rmtree(check_home, ignore_errors=True)
    exe = DIST / "Realmwalker.exe"
    code = subprocess.call([str(exe), "--smoke-test", str(ROOT / "build" / "packaged_smoke.png"), "--home", str(check_home)])
    if code != 0:
        print("The packaged game did not start correctly; see build/smoke_home/logs.")
        return 1

    step("Zipping")
    if ZIP.exists():
        ZIP.unlink()
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in sorted(DIST.rglob("*")):
            if path.is_file():
                z.write(path, Path("Realmwalker") / path.relative_to(DIST))
    size_mb = ZIP.stat().st_size / 1_000_000
    print(f"\nDone! {ZIP.name} ({size_mb:.0f} MB) is ready to send to friends.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
