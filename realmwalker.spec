# PyInstaller build recipe for Realmwalker.exe. Used by tools/build_friends.py.
# -*- mode: python -*-

a = Analysis(
    ["main.py"],
    pathex=[],
    datas=[
        ("data", "data"),
        ("ai/prompts", "ai/prompts"),
        ("assets/fonts", "assets/fonts"),
    ],
    hiddenimports=[],
    excludes=["pytest", "tkinter", "matplotlib", "IPython", "PyInstaller"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Realmwalker",
    console=False,
    icon="assets/icon.ico",
)
coll = COLLECT(exe, a.binaries, a.datas, name="Realmwalker")
