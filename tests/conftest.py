from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from realmwalker.data.registry import DataRegistry  # noqa: E402
from realmwalker.paths import Paths  # noqa: E402


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
