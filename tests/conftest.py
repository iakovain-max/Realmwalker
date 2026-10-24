from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from realmwalker.data.registry import DataRegistry  # noqa: E402
from realmwalker.paths import Paths  # noqa: E402


@pytest.fixture(autouse=True)
def _quiet_tales(request, monkeypatch):
    """Expansion 6: a new life is offered a tale at once, and entering a town near a threat may offer one: a hook
    beat that waits for the player, as it should in play. The tests written before the story engine walk and talk
    through towns, so outside tests marked `story` no hook is offered (everything else of the story runs)."""
    if request.node.get_closest_marker("story") is None:
        from realmwalker.game import story

        monkeypatch.setattr(story, "offer_hook", lambda game, t, town=None: None)


@pytest.fixture
def home(tmp_path: Path) -> Path:
    return tmp_path / "home"


@pytest.fixture(scope="session")
def data() -> DataRegistry:
    registry, errors = DataRegistry.load(Paths().data)
    assert not errors, errors
    return registry


@pytest.fixture
def make_app(home: Path):
    """Build headless apps; they are shut down automatically after the test."""
    from realmwalker.app import App

    apps = []

    def factory(**kwargs):
        config = kwargs.pop("config", {})
        settings = kwargs.pop("settings", {})
        app = App(home=home, headless=True, config_overrides=config, settings_overrides=settings, **kwargs)
        apps.append(app)
        return app

    yield factory
    for app in apps:
        app.shutdown()
