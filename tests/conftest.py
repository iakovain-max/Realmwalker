from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from realmwalker.data.registry import DataRegistry  # noqa: E402
from realmwalker.paths import Paths  # noqa: E402
from tools.mock_player2 import MockPlayer2  # noqa: E402

UNREACHABLE = "http://127.0.0.1:9/v1"


@pytest.fixture
def home(tmp_path: Path) -> Path:
    return tmp_path / "home"


@pytest.fixture(scope="session")
def data() -> DataRegistry:
    registry, errors = DataRegistry.load(Paths().data)
    assert not errors, errors
    return registry


@pytest.fixture
def mock_p2():
    mock = MockPlayer2("ok").start()
    yield mock
    mock.stop()


@pytest.fixture
def make_app(home: Path):
    """Build headless apps; they are shut down automatically after the test."""
    from realmwalker.app import App

    apps = []

    def factory(*, base_url: str = UNREACHABLE, ai: bool = False, **kwargs):
        config = {"player2_base_url": base_url, **kwargs.pop("config", {})}
        settings = {"ai_enabled": ai, **kwargs.pop("settings", {})}
        app = App(home=home, headless=True, config_overrides=config, settings_overrides=settings, **kwargs)
        app.ai.retry_interval = 0.2
        apps.append(app)
        return app

    yield factory
    for app in apps:
        app.shutdown()
